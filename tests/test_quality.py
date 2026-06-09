"""Tests for answer-quality scoring (parsing + similarity), no model needed."""

from opensuse_ai.quality import QualityScorer, cosine_similarity


def test_cosine_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_orthogonal():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_parse_clean_json():
    score, reason = QualityScorer._parse_judge('{"score": 4, "reason": "good"}')
    assert score == 4
    assert reason == "good"


def test_parse_json_with_surrounding_noise():
    text = 'Here is my verdict:\n{"score": 5, "reason": "accurate"}\nThanks.'
    score, reason = QualityScorer._parse_judge(text)
    assert score == 5
    assert reason == "accurate"


def test_parse_strips_think_block():
    text = '<think>let me reason 2 or 3...</think>{"score": 2, "reason": "wrong"}'
    score, _ = QualityScorer._parse_judge(text)
    assert score == 2


def test_parse_bare_digit_fallback():
    score, _ = QualityScorer._parse_judge("I would rate this a 3 out of 5.")
    assert score == 3


def test_parse_out_of_range_falls_back():
    # score 9 is invalid; fallback finds first 1-5 digit, else 1
    score, _ = QualityScorer._parse_judge('{"score": 9}')
    assert score == 1


def test_parse_unparseable():
    score, reason = QualityScorer._parse_judge("no number here at all")
    assert score == 1
    assert "unparseable" in reason


class _FakeEmbed:
    """Returns a fixed vector for known text, orthogonal otherwise."""

    def embed_query(self, text: str):
        return [1.0, 0.0] if "zypper" in text else [0.0, 1.0]


def test_similarity_uses_embeddings():
    scorer = QualityScorer(_FakeEmbed())
    assert scorer.similarity("use zypper install", "run zypper in") == 1.0
    assert scorer.similarity("use apt", "run zypper in") == 0.0


def test_similarity_empty_answer():
    scorer = QualityScorer(_FakeEmbed())
    assert scorer.similarity("", "anything") == 0.0


def test_gemini_judge_requires_key(monkeypatch):
    from opensuse_ai.quality import GeminiJudge

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        GeminiJudge()
        assert False, "expected ValueError without key"
    except ValueError as e:
        assert "GEMINI_API_KEY" in str(e)


def test_gemini_judge_parses_response(monkeypatch):
    import opensuse_ai.quality as q
    from opensuse_ai.quality import GeminiJudge

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": '{"score": 4, "reason": "ok"}'}]}}
                ]
            }

    monkeypatch.setattr(q, "requests", type("R", (), {"post": staticmethod(lambda *a, **k: _Resp()), "RequestException": Exception}), raising=False)
    judge = GeminiJudge(api_key="dummy")
    score, reason = judge.score("q", "a zypper answer", "ref", ["zypper"])
    assert score == 4
    assert reason == "ok"


def test_gemini_judge_empty_answer_short_circuits(monkeypatch):
    from opensuse_ai.quality import GeminiJudge

    judge = GeminiJudge(api_key="dummy")
    assert judge.score("q", "   ", "ref", []) == (1, "empty answer")


def test_parse_judge_batch_maps_by_id():
    from opensuse_ai.quality import parse_judge_batch

    text = 'noise [{"id":"a","score":5,"reason":"good"},{"id":"b","score":2,"reason":"bad"}] end'
    out = parse_judge_batch(text, ["a", "b"])
    assert out["a"] == (5, "good")
    assert out["b"] == (2, "bad")


def test_parse_judge_batch_fills_missing():
    from opensuse_ai.quality import parse_judge_batch

    out = parse_judge_batch('[{"id":"a","score":4,"reason":"ok"}]', ["a", "b"])
    assert out["a"] == (4, "ok")
    assert out["b"][0] == 1  # missing -> default 1


def test_score_batch_single_call(monkeypatch):
    """score_batch must hit the API exactly once for many items."""
    from opensuse_ai.quality import GeminiJudge

    calls = {"n": 0}

    def fake_generate(self, sys_p, user_p, max_tokens):
        calls["n"] += 1
        return '[{"id":"x","score":5,"reason":"a"},{"id":"y","score":3,"reason":"b"}]', None

    monkeypatch.setattr(GeminiJudge, "_generate", fake_generate)
    judge = GeminiJudge(api_key="dummy")
    items = [
        {"id": "x", "query": "q", "reference": "r", "expected_facts": [], "answer": "a"},
        {"id": "y", "query": "q", "reference": "r", "expected_facts": [], "answer": "a"},
    ]
    out = judge.score_batch(items)
    assert calls["n"] == 1
    assert out["x"] == (5, "a")
    assert out["y"] == (3, "b")
