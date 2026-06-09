"""
Answer-quality scoring for the evaluation framework.

Two complementary, fully offline signals:

- Embedding similarity: cosine similarity between the model's answer and the
  gold reference answer, using the already-cached MiniLM embedding model.
  Cheap and deterministic; rewards semantic closeness.

- LLM-as-judge: a strong local model scores the answer 1-5 on accuracy,
  grounding and helpfulness, given the question, the answer and the reference.
  Slower but catches correctness the embedding score misses.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


JUDGE_SYSTEM_PROMPT = """\
You are a strict evaluator of answers from an openSUSE Linux onboarding \
assistant. Score the ASSISTANT ANSWER against the REFERENCE ANSWER and the \
EXPECTED FACTS on a 1-5 integer scale:

5 = fully correct, grounded, covers the expected facts, no errors
4 = correct and helpful with minor omissions
3 = partially correct or missing important facts
2 = mostly wrong, misleading, or off-topic
1 = incorrect, harmful, or empty

Judge technical correctness for openSUSE specifically (zypper, YaST, firewalld, \
Btrfs/Snapper). Penalise commands that do not exist or belong to other distros. \
Reply with ONLY a JSON object: {"score": <int 1-5>, "reason": "<one sentence>"}."""


JUDGE_BATCH_SYSTEM_PROMPT = """\
You are a strict evaluator of answers from an openSUSE Linux onboarding \
assistant. You will be given several numbered items, each with a QUESTION, a \
REFERENCE ANSWER, the EXPECTED FACTS, and the ASSISTANT ANSWER to score.

Score each ASSISTANT ANSWER against its REFERENCE and EXPECTED FACTS on a 1-5 \
integer scale:

5 = fully correct, grounded, covers the expected facts, no errors
4 = correct and helpful with minor omissions
3 = partially correct or missing important facts
2 = mostly wrong, misleading, or off-topic
1 = incorrect, harmful, or empty

Judge technical correctness for openSUSE specifically (zypper, YaST, firewalld, \
Btrfs/Snapper). Penalise commands that do not exist or belong to other distros.

Reply with ONLY a JSON array, one object per item, in the same order:
[{"id": "<id>", "score": <int 1-5>, "reason": "<one sentence>"}]"""


@dataclass
class QueryScore:
    """Quality scores for one answered query."""

    query_id: str
    similarity: float  # 0-1 cosine
    judge_score: int  # 1-5
    judge_reason: str = ""


def build_judge_prompt(
    query: str, answer: str, reference: str, expected_facts: list[str]
) -> str:
    """User-turn prompt shared by every judge backend."""
    return (
        f"QUESTION:\n{query}\n\n"
        f"REFERENCE ANSWER:\n{reference}\n\n"
        f"EXPECTED FACTS: {', '.join(expected_facts) or 'n/a'}\n\n"
        f"ASSISTANT ANSWER:\n{answer}\n\n"
        "Return only the JSON object."
    )


def parse_judge(text: str) -> tuple[int, str]:
    """Extract (score, reason) from a judge reply, robust to noise."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            score = int(data.get("score", 0))
            if 1 <= score <= 5:
                return score, str(data.get("reason", "")).strip()
        except (ValueError, TypeError):
            pass
    digit = re.search(r"\b([1-5])\b", text)
    if digit:
        return int(digit.group(1)), text[:120]
    return 1, "unparseable judge output"


def build_batch_prompt(items: list[dict]) -> str:
    """
    Build a single prompt scoring many answers at once.

    Each item dict needs: id, query, reference, expected_facts, answer.
    """
    blocks = []
    for i, it in enumerate(items, 1):
        facts = ", ".join(it.get("expected_facts") or []) or "n/a"
        blocks.append(
            f"### ITEM {i} (id: {it['id']})\n"
            f"QUESTION: {it['query']}\n"
            f"REFERENCE ANSWER: {it['reference']}\n"
            f"EXPECTED FACTS: {facts}\n"
            f"ASSISTANT ANSWER: {it['answer']}\n"
        )
    return (
        "Score every item below. Return ONLY the JSON array described, one "
        "object per item, using each item's id.\n\n" + "\n".join(blocks)
    )


def parse_judge_batch(text: str, ids: list[str]) -> dict[str, tuple[int, str]]:
    """
    Parse a JSON array of verdicts into {id: (score, reason)}.

    Missing or malformed entries default to (1, "..."). Robust to surrounding
    prose and <think> blocks.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    out: dict[str, tuple[int, str]] = {}
    match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if match:
        try:
            for entry in json.loads(match.group(0)):
                eid = str(entry.get("id", ""))
                score = int(entry.get("score", 0))
                if eid and 1 <= score <= 5:
                    out[eid] = (score, str(entry.get("reason", "")).strip())
        except (ValueError, TypeError):
            pass
    for eid in ids:
        out.setdefault(eid, (1, "missing from batch verdict"))
    return out


def _retry_delay_seconds(resp) -> float | None:
    """Extract Google's suggested RetryInfo delay (seconds) from an error body."""
    try:
        for detail in resp.json().get("error", {}).get("details", []):
            if detail.get("@type", "").endswith("RetryInfo"):
                d = detail.get("retryDelay", "")  # e.g. "9s"
                return float(d.rstrip("s")) if d.endswith("s") else None
    except (ValueError, AttributeError):
        pass
    return None


class GeminiJudge:
    """
    External LLM judge using the Google Gemini API.

    A frontier model from a different family than the judged models removes
    the self-evaluation bias of judging Qwen with Qwen. Runs off the VM (the
    VM has no outbound internet); the API key is read from the environment,
    never stored in the repo.
    """

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        min_interval_s: float = 4.0,
        max_attempts: int = 8,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Export it before running the "
                "external judge; it is never read from a file in the repo."
            )
        # Free-tier endpoints rate-limit bursts (RPM), returning 429/503. Pace
        # calls to stay under the limit instead of hammering and falling back.
        self.min_interval_s = min_interval_s
        self.max_attempts = max_attempts
        self._last_call = 0.0

    def _generate(self, system_prompt: str, user_prompt: str, max_tokens: int):
        """
        POST one request to Gemini and return (text, error).

        On success: (text, None). On failure: (None, "reason"). Paces to the
        configured RPM and retries 429/503 honouring Google's retryDelay.
        """
        url = f"{self.BASE}/{self.model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": max_tokens,
                # Disable Gemini 2.5 "thinking" — the judge only needs the JSON
                # verdict, and hidden reasoning tokens make each call far slower.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        headers = {"Content-Type": "application/json", "X-goog-api-key": self.api_key}

        # Proactively pace to stay under the free-tier RPM limit.
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)

        for attempt in range(self.max_attempts):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=90)
            except requests.RequestException as e:
                logger.warning("Gemini request error: %s", e)
                time.sleep(3 * (attempt + 1))
                continue
            finally:
                self._last_call = time.monotonic()

            if resp.status_code in (429, 503):
                delay = _retry_delay_seconds(resp) or (3 * (attempt + 1))
                logger.info("Gemini %s; retrying in %.0fs", resp.status_code, delay)
                time.sleep(min(delay, 45))
                continue
            if resp.status_code != 200:
                return None, f"gemini http {resp.status_code}: {resp.text[:120]}"
            try:
                cand = resp.json()["candidates"][0]
                text = "".join(p.get("text", "") for p in cand["content"]["parts"])
            except (KeyError, IndexError, ValueError):
                return None, "gemini: no candidate text"
            return text, None
        return None, "gemini: exhausted retries (overloaded)"

    def score(
        self, query: str, answer: str, reference: str, expected_facts: list[str]
    ) -> tuple[int, str]:
        if not answer.strip():
            return 1, "empty answer"
        text, err = self._generate(
            JUDGE_SYSTEM_PROMPT,
            build_judge_prompt(query, answer, reference, expected_facts),
            max_tokens=512,
        )
        if err:
            return 1, err
        return parse_judge(text)

    def score_batch(self, items: list[dict]) -> dict[str, tuple[int, str]]:
        """
        Score many answers in a single API call.

        ``items`` is a list of dicts with id/query/reference/expected_facts/
        answer. Returns {id: (score, reason)}. One call per batch — the way to
        keep total API calls low (e.g. one batch per model = 5 calls, not 40).
        """
        ids = [str(it["id"]) for it in items]
        if not items:
            return {}
        # ~80 tokens of verdict per item, plus slack.
        max_tokens = 200 + 80 * len(items)
        text, err = self._generate(
            JUDGE_BATCH_SYSTEM_PROMPT, build_batch_prompt(items), max_tokens
        )
        if err:
            return {eid: (1, err) for eid in ids}
        return parse_judge_batch(text, ids)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors (handles non-normalised inputs)."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class QualityScorer:
    """Scores answers via embedding similarity and an LLM judge."""

    def __init__(self, embedding_engine):
        self.embed = embedding_engine

    def similarity(self, answer: str, reference: str) -> float:
        """Cosine similarity between answer and reference embeddings."""
        if not answer.strip():
            return 0.0
        a = self.embed.embed_query(answer)
        b = self.embed.embed_query(reference)
        return round(cosine_similarity(a, b), 4)

    def judge(
        self,
        judge_model,
        query: str,
        answer: str,
        reference: str,
        expected_facts: list[str],
        no_think: bool = False,
    ) -> tuple[int, str]:
        """
        Score an answer 1-5 with a local LLM judge.

        ``judge_model`` is a loaded llama_cpp.Llama instance. ``no_think``
        appends the Qwen3 "/no_think" soft switch so a hybrid-thinking judge
        emits the verdict directly instead of spending the token budget inside
        a <think> block (which would truncate before the JSON and score 1).
        Returns (score, reason); falls back to a parsed integer or 1.
        """
        if not answer.strip():
            return 1, "empty answer"

        user_prompt = build_judge_prompt(query, answer, reference, expected_facts)
        if no_think:
            user_prompt += " /no_think"
        try:
            resp = judge_model.create_chat_completion(
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=256,
                temperature=0.0,
            )
            text = resp["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - judge must never abort a run
            logger.warning("Judge call failed: %s", e)
            return 1, f"judge error: {e}"

        return parse_judge(text)

    # Backwards-compatible alias (tests call QualityScorer._parse_judge).
    _parse_judge = staticmethod(parse_judge)
