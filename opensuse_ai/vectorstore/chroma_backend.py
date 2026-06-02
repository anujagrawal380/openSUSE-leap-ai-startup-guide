"""
ChromaDB vector store backend.

Wraps chromadb.PersistentClient to provide the VectorStoreBackend interface.
This is the original storage engine used by the project.
"""

import logging
from pathlib import Path

import chromadb

from opensuse_ai.config import RAGConfig
from opensuse_ai.vectorstore.base import VectorStoreBackend

logger = logging.getLogger(__name__)


class ChromaBackend(VectorStoreBackend):
    """ChromaDB-backed vector store for document chunks."""

    def __init__(self, rag_config: RAGConfig):
        self.config = rag_config

        persist_dir = Path(rag_config.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
        )

        self.collection = self.client.get_or_create_collection(
            name=rag_config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """
        Add document chunks with pre-computed embeddings.

        Batches inserts in groups of 100 to avoid memory spikes.
        """
        if not chunks:
            return

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]

            ids = [c["id"] for c in batch_chunks]
            texts = [c["text"] for c in batch_chunks]
            metadatas = [c["metadata"] for c in batch_chunks]

            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=batch_embeddings,
            )
            logger.info(
                "Indexed batch %d-%d (%d chunks)", i, i + len(batch_chunks), len(batch_chunks)
            )

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """
        Retrieve the most relevant chunks for a query embedding.

        Returns list of dicts with keys: text, metadata, distance.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            retrieved.append({
                "text": doc,
                "metadata": meta,
                "distance": dist,
            })

        return retrieved

    @property
    def count(self) -> int:
        """Return number of documents in the collection."""
        return self.collection.count()
