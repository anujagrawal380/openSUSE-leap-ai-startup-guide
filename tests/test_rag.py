"""Tests for the RAG pipeline (unit-level, no model downloads)."""

from unittest.mock import MagicMock, patch

from opensuse_ai.config import Config
from opensuse_ai.rag import RAGPipeline
from opensuse_ai.scraper import ScrapedPage


def test_format_context_empty():
    """format_context with no results should return a fallback message."""
    cfg = Config()
    # Mock the heavy components
    with patch("opensuse_ai.rag.EmbeddingEngine"), \
         patch("opensuse_ai.rag.VectorStore"):
        pipeline = RAGPipeline(cfg)
        result = pipeline.format_context([])
        assert "No relevant documentation" in result


def test_format_context_with_results():
    """format_context should format results with source info."""
    cfg = Config()
    with patch("opensuse_ai.rag.EmbeddingEngine"), \
         patch("opensuse_ai.rag.VectorStore"):
        pipeline = RAGPipeline(cfg)
        results = [
            {
                "text": "Use zypper install to install packages.",
                "metadata": {
                    "source_url": "https://doc.opensuse.org/page1",
                    "title": "Package Management",
                },
                "distance": 0.15,
            },
        ]
        formatted = pipeline.format_context(results)
        assert "zypper install" in formatted
        assert "Package Management" in formatted
        assert "doc.opensuse.org" in formatted


def test_wiki_source_configured():
    """The default config should include the MediaWiki SDB source."""
    from opensuse_ai.config import Config

    wiki = [s for s in Config().doc_sources if s.kind == "mediawiki"]
    assert len(wiki) == 1
    assert wiki[0].pages
    assert "api.php" in wiki[0].base_url


def test_rerank_falls_back_to_vector_order(tmp_path):
    """With rerank on but the model unavailable, vector order is kept."""
    from opensuse_ai.config import Config
    from opensuse_ai.rag import RAGPipeline

    cfg = Config()
    cfg.rag.persist_directory = str(tmp_path / "store")
    cfg.rag.rerank = True
    cfg.rag.top_k = 2
    pipeline = RAGPipeline(cfg)

    fake = [{"text": f"t{i}", "metadata": {}, "distance": i / 10} for i in range(6)]
    pipeline.vector_store.query = lambda q, top_k=None: fake[:top_k]
    pipeline._get_reranker = lambda: None

    results = pipeline.retrieve("query")
    assert results == fake[:2]


def test_rerank_reorders_with_scores(tmp_path):
    """Cross-encoder scores should reorder candidates."""
    from opensuse_ai.config import Config
    from opensuse_ai.rag import RAGPipeline

    cfg = Config()
    cfg.rag.persist_directory = str(tmp_path / "store")
    cfg.rag.rerank = True
    cfg.rag.top_k = 2
    pipeline = RAGPipeline(cfg)

    fake = [{"text": f"t{i}", "metadata": {}, "distance": i / 10} for i in range(4)]
    pipeline.vector_store.query = lambda q, top_k=None: fake[:top_k]

    class FakeReranker:
        def predict(self, pairs):
            return [0.1, 0.9, 0.5, 0.2]  # candidate 1 best, then 2

    pipeline._get_reranker = lambda: FakeReranker()
    results = pipeline.retrieve("query")
    assert [r["text"] for r in results] == ["t1", "t2"]
