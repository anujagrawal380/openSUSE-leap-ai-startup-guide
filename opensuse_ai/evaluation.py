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
import logging
from dataclasses import dataclass, field

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
) -> None:
    """Score every recorded answer in place with similarity + LLM judge."""
    from opensuse_ai.assistant import Assistant
    from opensuse_ai.rag import EmbeddingEngine

    embedding_engine = EmbeddingEngine(config.embedding)
    scorer = QualityScorer(embedding_engine)

    # Load the judge model once (its own bare llama-cpp instance).
    judge_cfg = copy.deepcopy(config)
    judge_cfg.apply_model_tier(judge_tier)
    judge_assistant = Assistant(judge_cfg, rag_pipeline=None)
    judge_assistant.load_model()
    judge_model = judge_assistant._local_model

    for result in results:
        for rec in result.records:
            rec.similarity = scorer.similarity(rec.answer, rec.reference)
            rec.judge_score, rec.judge_reason = scorer.judge(
                judge_model,
                rec.query,
                rec.answer,
                rec.reference,
                rec.expected_facts,
            )
            if progress:
                progress(result.model_name, rec.query_id, rec.judge_score)

    _free_model(judge_assistant)

    # Aggregate
    for result in results:
        recs = result.records
        n = len(recs) or 1
        result.avg_judge_score = sum(r.judge_score for r in recs) / n
        result.avg_similarity = sum(r.similarity for r in recs) / n
        result.avg_latency_ms = sum(r.latency_ms for r in recs) / n
        result.avg_tokens_per_second = sum(r.tokens_per_second for r in recs) / n


def evaluate(
    config: Config,
    model_tiers: list[str],
    judge_tier: str,
    system_context=None,
    items: list[EvalItem] | None = None,
    gen_progress=None,
    judge_progress=None,
) -> list[ModelEvalResult]:
    """Run the full two-phase evaluation and return per-model results."""
    items = items or EVAL_ITEMS
    results = [
        generate_answers(config, tier, items, system_context, gen_progress)
        for tier in model_tiers
    ]
    score_results(config, results, judge_tier, judge_progress)
    return results


def render_markdown(results: list[ModelEvalResult], judge_tier: str) -> str:
    """Render a comparison report as Markdown."""
    lines = [
        "# Model Quality & Latency Evaluation",
        "",
        f"Judge model tier: `{judge_tier}`. "
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
    return "\n".join(lines)
