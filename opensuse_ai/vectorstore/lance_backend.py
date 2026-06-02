"""
LanceDB vector store backend.

Uses the LanceDB columnar format for vector storage and retrieval.
Provides a lightweight, embedded alternative to ChromaDB with efficient
disk-based vector search.
"""

import logging
from pathlib import Path

import lancedb
import pyarrow as pa

from opensuse_ai.config import RAGConfig
from opensuse_ai.vectorstore.base import VectorStoreBackend

logger = logging.getLogger(__name__)


class LanceBackend(VectorStoreBackend):
    """LanceDB-backed vector store for document chunks."""

    def __init__(self, rag_config: RAGConfig):
        self.config = rag_config
        self._table_name = rag_config.collection_name

        persist_dir = Path(rag_config.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.db = lancedb.connect(str(persist_dir))
        self._table = None

        # Try to open an existing table
        if self._table_name in self.db.list_tables():
            self._table = self.db.open_table(self._table_name)
            logger.info(
                "Opened existing LanceDB table '%s' (%d rows)",
                self._table_name,
                self._table.count_rows(),
            )

    def _create_table(self, vector_dim: int) -> None:
        """Create the LanceDB table with the correct schema."""
        schema = pa.schema([
            pa.field("id", pa.utf8()),
            pa.field("text", pa.utf8()),
            pa.field("vector", pa.list_(pa.float32(), vector_dim)),
            pa.field("source_url", pa.utf8()),
            pa.field("title", pa.utf8()),
            pa.field("section", pa.utf8()),
            pa.field("chunk_index", pa.int32()),
        ])
        self._table = self.db.create_table(self._table_name, schema=schema)
        logger.info("Created LanceDB table '%s'", self._table_name)

    def add_documents(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """
        Add document chunks with pre-computed embeddings.

        Batches inserts in groups of 100 for consistency with the ChromaDB backend.
        """
        if not chunks:
            return

        # Create the table on first insert using the embedding dimensionality
        if self._table is None:
            vector_dim = len(embeddings[0])
            self._create_table(vector_dim)

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]

            rows = []
            for chunk, embedding in zip(batch_chunks, batch_embeddings):
                metadata = chunk.get("metadata", {})
                rows.append({
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "vector": embedding,
                    "source_url": metadata.get("source_url", ""),
                    "title": metadata.get("title", ""),
                    "section": metadata.get("section", ""),
                    "chunk_index": metadata.get("chunk_index", 0),
                })

            self._table.add(rows)
            logger.info(
                "Indexed batch %d-%d (%d chunks)", i, i + len(batch_chunks), len(batch_chunks)
            )

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """
        Retrieve the most relevant chunks for a query embedding.

        Uses cosine distance for vector search.
        Returns list of dicts with keys: text, metadata, distance.
        """
        if self._table is None:
            return []

        results = (
            self._table.search(query_embedding)
            .metric("cosine")
            .limit(top_k)
            .to_list()
        )

        retrieved = []
        for row in results:
            retrieved.append({
                "text": row["text"],
                "metadata": {
                    "source_url": row.get("source_url", ""),
                    "title": row.get("title", ""),
                    "section": row.get("section", ""),
                    "chunk_index": row.get("chunk_index", 0),
                },
                "distance": row.get("_distance", 0.0),
            })

        return retrieved

    @property
    def count(self) -> int:
        """Return number of documents in the table."""
        if self._table is None:
            return 0
        return self._table.count_rows()
