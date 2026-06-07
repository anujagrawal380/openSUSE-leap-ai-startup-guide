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
import re
from dataclasses import dataclass

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


@dataclass
class QueryScore:
    """Quality scores for one answered query."""

    query_id: str
    similarity: float  # 0-1 cosine
    judge_score: int  # 1-5
    judge_reason: str = ""


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
    ) -> tuple[int, str]:
        """
        Score an answer 1-5 with a local LLM judge.

        ``judge_model`` is a loaded llama_cpp.Llama instance. Returns
        (score, reason); falls back to a parsed integer or 1 on bad output.
        """
        if not answer.strip():
            return 1, "empty answer"

        user_prompt = (
            f"QUESTION:\n{query}\n\n"
            f"REFERENCE ANSWER:\n{reference}\n\n"
            f"EXPECTED FACTS: {', '.join(expected_facts) or 'n/a'}\n\n"
            f"ASSISTANT ANSWER:\n{answer}\n\n"
            "Return only the JSON object."
        )
        try:
            resp = judge_model.create_chat_completion(
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=120,
                temperature=0.0,
            )
            text = resp["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - judge must never abort a run
            logger.warning("Judge call failed: %s", e)
            return 1, f"judge error: {e}"

        return self._parse_judge(text)

    @staticmethod
    def _parse_judge(text: str) -> tuple[int, str]:
        """Extract (score, reason) from the judge's reply, robust to noise."""
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
        # Fallback: first standalone 1-5 digit in the text.
        digit = re.search(r"\b([1-5])\b", text)
        if digit:
            return int(digit.group(1)), text[:120]
        return 1, "unparseable judge output"
