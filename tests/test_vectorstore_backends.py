"""Tests for the vector store backend (LanceDB)."""

import tempfile

import pytest

from opensuse_ai.config import RAGConfig
from opensuse_ai.vectorstore.base import VectorStoreBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunks(n: int = 5) -> list[dict]:
    """Create *n* dummy document chunks."""
    return [
        {
            "id": f"doc_{i}",
            "text": f"This is test document number {i}.",
            "metadata": {
                "source_url": f"https://example.com/page{i}",
                "title": f"Page {i}",
                "section": "Testing",
                "chunk_index": i,
            },
        }
        for i in range(n)
    ]


def _make_embeddings(n: int = 5, dim: int = 8) -> list[list[float]]:
    """Create *n* dummy embedding vectors of dimension *dim*."""
    return [[float(j + i * 0.1) for j in range(dim)] for i in range(n)]


# ---------------------------------------------------------------------------
# LanceBackend tests
# ---------------------------------------------------------------------------

class TestLanceBackend:
    """Integration tests for the LanceDB backend."""

    def test_is_vector_store_backend(self):
        """LanceBackend should implement VectorStoreBackend."""
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, collection_name="test_col")
            backend = LanceBackend(cfg)
            assert isinstance(backend, VectorStoreBackend)

    def test_count_empty(self):
        """Empty store should have count == 0."""
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, collection_name="test_empty")
            backend = LanceBackend(cfg)
            assert backend.count == 0

    def test_add_and_count(self):
        """Adding documents should increase the count."""
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, collection_name="test_add")
            backend = LanceBackend(cfg)

            chunks = _make_chunks(3)
            embeddings = _make_embeddings(3)
            backend.add_documents(chunks, embeddings)

            assert backend.count == 3

    def test_add_empty(self):
        """Adding an empty list should be a no-op."""
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, collection_name="test_noop")
            backend = LanceBackend(cfg)
            backend.add_documents([], [])
            assert backend.count == 0

    def test_query_empty_store(self):
        """Querying an empty store should return an empty list."""
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, collection_name="test_qempty")
            backend = LanceBackend(cfg)
            results = backend.query([0.0] * 8, top_k=2)
            assert results == []

    def test_query(self):
        """Querying should return results with expected keys."""
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, collection_name="test_query")
            backend = LanceBackend(cfg)

            chunks = _make_chunks(5)
            embeddings = _make_embeddings(5)
            backend.add_documents(chunks, embeddings)

            results = backend.query(embeddings[0], top_k=2)
            assert len(results) == 2
            for r in results:
                assert "text" in r
                assert "metadata" in r
                assert "distance" in r
                # Metadata should contain the expected fields
                assert "source_url" in r["metadata"]
                assert "title" in r["metadata"]
                assert "section" in r["metadata"]
                assert "chunk_index" in r["metadata"]


# ---------------------------------------------------------------------------
# Backend factory tests
# ---------------------------------------------------------------------------

class TestCreateBackend:
    """Tests for the create_backend factory function."""

    def test_create_lance_backend(self):
        """Factory should create a LanceBackend when backend='lancedb'."""
        from opensuse_ai.rag import create_backend
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, backend="lancedb")
            backend = create_backend(cfg)
            assert isinstance(backend, LanceBackend)

    def test_invalid_backend_raises(self):
        """Factory should raise ValueError for an unknown backend."""
        from opensuse_ai.rag import create_backend

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig(persist_directory=tmpdir, backend="invalid")
            with pytest.raises(ValueError, match="Unknown vector store backend"):
                create_backend(cfg)
