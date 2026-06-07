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
