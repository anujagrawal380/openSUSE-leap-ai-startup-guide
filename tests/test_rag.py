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
