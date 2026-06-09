"""
Answer-quality + latency evaluation framework.

Benchmarks one or more models on the same question set and scores them on
*both* response time and answer quality, fully offline:

  Phase 1 (generate): for each model, load it, answer every eval question
  through the real RAG + system-context pipeline, record latency/tokens and
  the answer text, then unload to free memory before the next model.

  Phase 2 (judge): load the judge model once and score every recorded answer
  with the LLM judge, plus embedding similarity against the gold reference.

Running generation and judging in separate phases means at most one large
model is resident at a time — important on the memory-constrained VM.
"""

import copy
import gc
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from opensuse_ai.config import Config
from opensuse_ai.eval_dataset import EVAL_ITEMS, EvalItem
from opensuse_ai.quality import QualityScorer

logger = logging.getLogger(__name__)


@dataclass
class AnswerRecord:
    """A model's answer to one eval question, with timing."""

    query_id: str
    query: str
    reference: str
    expected_facts: list[str]
    answer: str
    latency_ms: float
    tokens_used: int
    tokens_per_second: float
    similarity: float = 0.0
    judge_score: int = 0
    judge_reason: str = ""


@dataclass
class ModelEvalResult:
    """Aggregated quality + latency result for one model."""

    model_name: str
    repo_id: str
    avg_judge_score: float = 0.0  # 1-5
    avg_similarity: float = 0.0  # 0-1
    avg_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    records: list[AnswerRecord] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.model_name}: quality {self.avg_judge_score:.2f}/5, "
            f"similarity {self.avg_similarity:.3f}, "
            f"latency {self.avg_latency_ms / 1000:.1f}s, "
            f"{self.avg_tokens_per_second:.1f} tok/s"
        )


def _free_model(assistant) -> None:
    """Release a loaded llama-cpp model and reclaim its memory."""
    model = getattr(assistant, "_local_model", None)
    if model is not None:
        close = getattr(model, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001
                pass
    assistant._local_model = None
    gc.collect()


def generate_answers(
    config: Config,
    tier_name: str,
    items: list[EvalItem],
    system_context=None,
    progress=None,
) -> ModelEvalResult:
    """Load one model and answer every eval item through the full pipeline."""
    from opensuse_ai.assistant import Assistant
    from opensuse_ai.rag import RAGPipeline

    cfg = copy.deepcopy(config)
    resolved = cfg.apply_model_tier(tier_name)

    rag = RAGPipeline(cfg)
    assistant = Assistant(cfg, rag)
    assistant.load_model()

    result = ModelEvalResult(model_name=resolved, repo_id=cfg.model.repo_id)

    for item in items:
        assistant.reset_conversation()
        resp = assistant.ask(item.query, system_context=system_context)
        tps = (
            resp.tokens_used / (resp.generation_time_ms / 1000)
            if resp.generation_time_ms > 0
            else 0.0
        )
        result.records.append(
            AnswerRecord(
                query_id=item.id,
                query=item.query,
                reference=item.reference,
                expected_facts=item.expected_facts,
                answer=resp.text,
                latency_ms=resp.generation_time_ms,
                tokens_used=resp.tokens_used,
                tokens_per_second=tps,
            )
        )
        if progress:
            progress(resolved, item.id, resp.generation_time_ms)

    _free_model(assistant)
    return result


def score_results(
    config: Config,
    results: list[ModelEvalResult],
    judge_tier: str,
    progress=None,
    judge_backend: str = "local",
    judge_model_name: str = "gemini-2.5-flash",
) -> None:
    """
    Score every recorded answer in place with similarity + an LLM judge.

    judge_backend:
      "local"  — a local llama-cpp model of tier ``judge_tier`` (offline, but
                 same-family bias when judging Qwen with Qwen).
      "gemini" — the external Google Gemini API (neutral frontier judge; needs
                 GEMINI_API_KEY and internet, so it runs off the VM).
    """
    from opensuse_ai.rag import EmbeddingEngine

    embedding_engine = EmbeddingEngine(config.embedding)
    scorer = QualityScorer(embedding_engine)

    if judge_backend == "gemini":
        from opensuse_ai.quality import GeminiJudge

        # One batched call per model keeps total API calls low (5 instead of
        # 40) — essential under the free-tier rate limit.
        gemini = GeminiJudge(model=judge_model_name)
        for result in results:
            for rec in result.records:
                rec.similarity = scorer.similarity(rec.answer, rec.reference)
            items = [
                {
                    "id": rec.query_id,
                    "query": rec.query,
                    "reference": rec.reference,
                    "expected_facts": rec.expected_facts,
                    "answer": rec.answer,
                }
                for rec in result.records
            ]
            verdicts = gemini.score_batch(items)
            for rec in result.records:
                rec.judge_score, rec.judge_reason = verdicts.get(
                    rec.query_id, (1, "no verdict")
                )
                if progress:
                    progress(result.model_name, rec.query_id, rec.judge_score)
        _aggregate(results)
        return

    # Local llama-cpp judge (per-answer; the model is already on the machine).
    from opensuse_ai.assistant import Assistant

    judge_cfg = copy.deepcopy(config)
    judge_cfg.apply_model_tier(judge_tier)
    judge_assistant = Assistant(judge_cfg, rag_pipeline=None)
    judge_assistant.load_model()
    judge_model = judge_assistant._local_model
    # Qwen3 hybrid-thinking judges (not the 2507 instruct builds) must be told
    # /no_think or they spend the token budget inside <think>.
    no_think = (
        "qwen3" in judge_cfg.model.repo_id.lower()
        and "2507" not in judge_cfg.model.filename.lower()
    )

    for result in results:
        for rec in result.records:
            rec.similarity = scorer.similarity(rec.answer, rec.reference)
            rec.judge_score, rec.judge_reason = scorer.judge(
                judge_model, rec.query, rec.answer, rec.reference,
                rec.expected_facts, no_think=no_think,
            )
            if progress:
                progress(result.model_name, rec.query_id, rec.judge_score)

    _free_model(judge_assistant)
    _aggregate(results)


def _aggregate(results: list[ModelEvalResult]) -> None:
    """Compute per-model averages from scored records."""
    for result in results:
        recs = result.records
        n = len(recs) or 1
        result.avg_judge_score = sum(r.judge_score for r in recs) / n
        result.avg_similarity = sum(r.similarity for r in recs) / n
        result.avg_latency_ms = sum(r.latency_ms for r in recs) / n
        result.avg_tokens_per_second = sum(r.tokens_per_second for r in recs) / n


def save_answers(results: list[ModelEvalResult], path: Path) -> None:
    """Persist generated answers (pre-scoring) so judging can be re-run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"model_name": r.model_name, "repo_id": r.repo_id,
         "records": [asdict(rec) for rec in r.records]}
        for r in results
    ]
    path.write_text(json.dumps(payload, indent=2))


def load_answers(path: Path) -> list[ModelEvalResult]:
    """Load previously generated answers for a judge-only re-run."""
    payload = json.loads(path.read_text())
    results = []
    for entry in payload:
        result = ModelEvalResult(
            model_name=entry["model_name"], repo_id=entry.get("repo_id", "")
        )
        result.records = [AnswerRecord(**rec) for rec in entry["records"]]
        results.append(result)
    return results


def evaluate(
    config: Config,
    model_tiers: list[str],
    judge_tier: str,
    system_context=None,
    items: list[EvalItem] | None = None,
    gen_progress=None,
    judge_progress=None,
    answers_cache: Path | None = None,
    reuse_answers: bool = False,
    judge_backend: str = "local",
    judge_model_name: str = "gemini-2.5-flash",
) -> list[ModelEvalResult]:
    """
    Run the two-phase evaluation and return per-model results.

    If ``reuse_answers`` is set and ``answers_cache`` exists, the generation
    phase is skipped and answers are loaded from disk — useful for iterating
    on the judge without paying the (slow) generation cost again.
    """
    items = items or EVAL_ITEMS
    if reuse_answers and answers_cache and answers_cache.exists():
        results = load_answers(answers_cache)
    else:
        results = [
            generate_answers(config, tier, items, system_context, gen_progress)
            for tier in model_tiers
        ]
        if answers_cache:
            save_answers(results, answers_cache)
    score_results(
        config, results, judge_tier, judge_progress,
        judge_backend=judge_backend, judge_model_name=judge_model_name,
    )
    return results


def render_markdown(results: list[ModelEvalResult], judge_label: str) -> str:
    """Render a comparison report as Markdown."""
    lines = [
        "# Model Quality & Latency Evaluation",
        "",
        f"Judge: `{judge_label}`. "
        f"Questions: {len(results[0].records) if results else 0}. "
        "Quality 1-5 (LLM judge), similarity 0-1 (embedding cosine vs gold answer).",
        "",
        "| Model | Quality (1-5) | Similarity | Avg latency | tok/s |",
        "|-------|---------------|------------|-------------|-------|",
    ]
    for r in sorted(results, key=lambda x: x.avg_judge_score, reverse=True):
        lines.append(
            f"| {r.model_name} | {r.avg_judge_score:.2f} | "
            f"{r.avg_similarity:.3f} | {r.avg_latency_ms / 1000:.1f} s | "
            f"{r.avg_tokens_per_second:.1f} |"
        )
    lines.append("")
    lines.append(
        "tok/s counts prompt + completion tokens (comparable across models, "
        "overstates pure generation speed)."
    )

    # Per-query detail per model (judge score + one-line reason).
    for r in sorted(results, key=lambda x: x.avg_judge_score, reverse=True):
        lines.append("")
        lines.append(f"## {r.model_name} — per-question detail")
        lines.append("")
        lines.append("| Question | Quality | Similarity | Judge reason |")
        lines.append("|----------|---------|------------|--------------|")
        for rec in r.records:
            reason = rec.judge_reason.replace("|", "/").replace("\n", " ")[:100]
            lines.append(
                f"| {rec.query_id} | {rec.judge_score}/5 | "
                f"{rec.similarity:.3f} | {reason} |"
            )
    return "\n".join(lines)
