"""
Abstract base class for vector store backends.

All backends (ChromaDB, LanceDB, etc.) implement this interface so
the RAG pipeline can swap storage engines without changing its own logic.
"""

from abc import ABC, abstractmethod


class VectorStoreBackend(ABC):
    """Abstract interface for a vector store backend."""

    @abstractmethod
    def add_documents(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """
        Add document chunks with pre-computed embeddings.

        Args:
            chunks: List of dicts with keys ``id``, ``text``, ``metadata``.
            embeddings: Parallel list of embedding vectors, one per chunk.
        """
        ...

    @abstractmethod
    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """
        Retrieve the *top_k* most relevant results for a query embedding.

        Returns:
            List of dicts with keys ``text``, ``metadata``, ``distance``.
        """
        ...

    @property
    @abstractmethod
    def count(self) -> int:
        """Return the number of documents currently in the store."""
        ...
