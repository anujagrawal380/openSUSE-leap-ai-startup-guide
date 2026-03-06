"""
RAG (Retrieval-Augmented Generation) pipeline for the openSUSE AI assistant.

Handles document chunking, embedding, vector storage (ChromaDB),
and context retrieval for grounding LLM responses in official documentation.
"""

import logging
from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from opensuse_ai.config import Config, EmbeddingConfig, RAGConfig
from opensuse_ai.scraper import ScrapedPage

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Wraps sentence-transformers for generating embeddings."""

    def __init__(self, config: EmbeddingConfig):
        logger.info("Loading embedding model: %s", config.model_name)
        self.model = SentenceTransformer(config.model_name, device=config.device)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        return self.model.encode(query, normalize_embeddings=True).tolist()


class VectorStore:
    """ChromaDB-backed vector store for document chunks."""

    def __init__(self, rag_config: RAGConfig, embedding_engine: EmbeddingEngine):
        self.config = rag_config
        self.embedding_engine = embedding_engine

        persist_dir = Path(rag_config.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
        )

        self.collection = self.client.get_or_create_collection(
            name=rag_config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return self.collection.count()

    def add_documents(self, chunks: list[dict]) -> None:
        """
        Add document chunks to the vector store.

        Each chunk is a dict with keys: id, text, metadata.
        """
        if not chunks:
            return

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            ids = [c["id"] for c in batch]
            texts = [c["text"] for c in batch]
            metadatas = [c["metadata"] for c in batch]
            embeddings = self.embedding_engine.embed(texts)

            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            logger.info("Indexed batch %d-%d (%d chunks)", i, i + len(batch), len(batch))

    def query(self, query_text: str, top_k: int | None = None) -> list[dict]:
        """
        Retrieve the most relevant chunks for a query.

        Returns list of dicts with keys: text, metadata, distance.
        """
        k = top_k or self.config.top_k
        query_embedding = self.embedding_engine.embed_query(query_text)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
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


class RAGPipeline:
    """
    End-to-end RAG pipeline: ingest docs -> chunk -> embed -> store -> retrieve.
    """

    def __init__(self, config: Config):
        self.config = config
        self.embedding_engine = EmbeddingEngine(config.embedding)
        self.vector_store = VectorStore(config.rag, self.embedding_engine)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.rag.chunk_size,
            chunk_overlap=config.rag.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def ingest(self, pages: list[ScrapedPage]) -> int:
        """
        Ingest scraped documentation pages into the vector store.

        Returns the total number of chunks indexed.
        """
        all_chunks = []
        chunk_id = 0

        for page in pages:
            texts = self.splitter.split_text(page.content)
            for i, text in enumerate(texts):
                all_chunks.append({
                    "id": f"doc_{chunk_id}",
                    "text": text,
                    "metadata": {
                        "source_url": page.url,
                        "title": page.title,
                        "section": page.section,
                        "chunk_index": i,
                    },
                })
                chunk_id += 1

        logger.info("Created %d chunks from %d pages", len(all_chunks), len(pages))
        self.vector_store.add_documents(all_chunks)
        return len(all_chunks)

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        """Retrieve relevant context chunks for a user query."""
        return self.vector_store.query(query, top_k=top_k)

    def format_context(self, results: list[dict]) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        if not results:
            return "No relevant documentation found."

        parts = []
        for i, r in enumerate(results, 1):
            source = r["metadata"].get("source_url", "unknown")
            title = r["metadata"].get("title", "")
            parts.append(
                f"[Source {i}: {title}]\n{r['text']}\n(Reference: {source})"
            )

        return "\n\n---\n\n".join(parts)

    @property
    def is_populated(self) -> bool:
        """Check if the vector store has any documents."""
        return self.vector_store.count > 0
