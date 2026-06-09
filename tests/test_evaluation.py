"""Tests for the evaluation framework aggregation + reporting (no models)."""

from opensuse_ai.evaluation import AnswerRecord, ModelEvalResult, render_markdown


def _rec(judge: int, sim: float, latency: float, tps: float) -> AnswerRecord:
    return AnswerRecord(
        query_id="q",
        query="q?",
        reference="ref",
        expected_facts=[],
        answer="ans",
        latency_ms=latency,
        tokens_used=100,
        tokens_per_second=tps,
        similarity=sim,
        judge_score=judge,
    )


def test_summary_format():
    r = ModelEvalResult(model_name="standard", repo_id="x")
    r.avg_judge_score = 4.5
    r.avg_similarity = 0.812
    r.avg_latency_ms = 90000
    r.avg_tokens_per_second = 30.6
    s = r.summary()
    assert "4.50/5" in s
    assert "0.812" in s
    assert "90.0s" in s


def test_render_markdown_sorts_by_quality():
    a = ModelEvalResult(model_name="gemma3-4b", repo_id="g")
    a.avg_judge_score, a.avg_similarity, a.avg_latency_ms, a.avg_tokens_per_second = (
        3.0, 0.6, 80000, 35.0,
    )
    a.records = [_rec(3, 0.6, 80000, 35.0)]
    b = ModelEvalResult(model_name="standard", repo_id="q")
    b.avg_judge_score, b.avg_similarity, b.avg_latency_ms, b.avg_tokens_per_second = (
        4.5, 0.8, 94000, 30.6,
    )
    b.records = [_rec(5, 0.8, 94000, 30.6)]

    md = render_markdown([a, b], judge_label="gemini-2.5-flash")
    assert "| standard |" in md
    assert "| gemma3-4b |" in md
    # higher-quality 'standard' row must appear before 'gemma3-4b'
    assert md.index("| standard |") < md.index("| gemma3-4b |")
    assert "Judge: `gemini-2.5-flash`" in md


def test_gemma_model_registered():
    from opensuse_ai.config import EXTRA_MODELS, Config

    assert "gemma3-4b" in EXTRA_MODELS
    cfg = Config()
    resolved = cfg.apply_model_tier("gemma3-4b")
    assert resolved == "gemma3-4b"
    assert "gemma-3-4b" in cfg.model.filename


def test_recommend_ladder_excludes_extra_models():
    """Auto tier recommendation must never pick an EXTRA_MODELS entry."""
    from opensuse_ai.config import MODEL_TIERS, recommend_model_tier

    assert recommend_model_tier(64.0) in MODEL_TIERS
