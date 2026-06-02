"""
RAG (Retrieval-Augmented Generation) pipeline for the openSUSE AI assistant.

Handles document chunking, embedding, vector storage,
and context retrieval for grounding LLM responses in official documentation.

Supports pluggable vector store backends (ChromaDB, LanceDB) via the
``opensuse_ai.vectorstore`` package.
"""

import logging
import os
import socket
from inspect import signature
from pathlib import Path
from urllib.parse import urlparse

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from opensuse_ai.config import Config, EmbeddingConfig, RAGConfig
from opensuse_ai.scraper import ScrapedPage
from opensuse_ai.vectorstore.base import VectorStoreBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def create_backend(rag_config: RAGConfig) -> VectorStoreBackend:
    """
    Instantiate the correct vector store backend based on ``rag_config.backend``.

    Supported values: ``"chroma"``, ``"lancedb"``.
    """
    backend = rag_config.backend.lower()

    if backend == "chroma":
        from opensuse_ai.vectorstore.chroma_backend import ChromaBackend

        return ChromaBackend(rag_config)

    if backend == "lancedb":
        from opensuse_ai.vectorstore.lance_backend import LanceBackend

        return LanceBackend(rag_config)

    raise ValueError(
        f"Unknown vector store backend '{rag_config.backend}'. "
        f"Expected one of: chroma, lancedb"
    )


# ---------------------------------------------------------------------------
# Embedding engine (unchanged — stays in rag.py)
# ---------------------------------------------------------------------------

class EmbeddingEngine:
    """Wraps sentence-transformers for generating embeddings."""

    def __init__(self, config: EmbeddingConfig):
        logger.info("Loading embedding model: %s", config.model_name)
        cache_dir = Path(config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_files_only = _offline_requested() or _disable_dead_local_proxy()
        model_name = config.model_name
        if local_files_only:
            model_name = _find_cached_sentence_transformer(config.model_name, cache_dir)

        kwargs = {
            "device": config.device,
            "cache_folder": str(cache_dir),
        }
        if "local_files_only" in signature(SentenceTransformer.__init__).parameters:
            kwargs["local_files_only"] = local_files_only
        elif local_files_only:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        self.model = SentenceTransformer(model_name, **kwargs)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        return self.model.encode(query, normalize_embeddings=True).tolist()


# ---------------------------------------------------------------------------
# VectorStore — thin adapter that owns an EmbeddingEngine + a backend
# ---------------------------------------------------------------------------

class VectorStore:
    """
    High-level vector store that pairs an embedding engine with a
    pluggable storage backend.

    Kept for backward compatibility with existing call-sites; new code
    should prefer ``create_backend`` + ``EmbeddingEngine`` directly.
    """

    def __init__(
        self,
        rag_config: RAGConfig,
        embedding_engine: EmbeddingEngine | None = None,
        embedding_config: EmbeddingConfig | None = None,
    ):
        self.config = rag_config
        self._embedding_engine = embedding_engine
        self._embedding_config = embedding_config
        self.backend: VectorStoreBackend = create_backend(rag_config)

    @property
    def embedding_engine(self) -> EmbeddingEngine:
        if self._embedding_engine is None:
            if self._embedding_config is None:
                raise RuntimeError("Embedding configuration is required to load embeddings.")
            self._embedding_engine = EmbeddingEngine(self._embedding_config)
        return self._embedding_engine

    @property
    def count(self) -> int:
        return self.backend.count

    def add_documents(self, chunks: list[dict]) -> None:
        """
        Add document chunks to the vector store.

        Each chunk is a dict with keys: id, text, metadata.
        Embeddings are computed internally and forwarded to the backend.
        """
        if not chunks:
            return

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = self.embedding_engine.embed(texts)
            self.backend.add_documents(batch, embeddings)

    def query(self, query_text: str, top_k: int | None = None) -> list[dict]:
        """
        Retrieve the most relevant chunks for a query.

        Returns list of dicts with keys: text, metadata, distance.
        """
        k = top_k or self.config.top_k
        query_embedding = self.embedding_engine.embed_query(query_text)
        return self.backend.query(query_embedding, k)


# ---------------------------------------------------------------------------
# RAG pipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    End-to-end RAG pipeline: ingest docs -> chunk -> embed -> store -> retrieve.
    """

    def __init__(self, config: Config):
        self.config = config
        self.vector_store = VectorStore(config.rag, embedding_config=config.embedding)
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
        seen_texts: set[str] = set()
        duplicates = 0

        for page in pages:
            texts = self.splitter.split_text(page.content)
            for i, text in enumerate(texts):
                # openSUSE book index/part/chapter pages nest the same content,
                # so the crawler yields many identical chunks. Drop exact dupes
                # to keep the store lean and avoid repeated retrieval citations.
                key = text.strip()
                if key in seen_texts:
                    duplicates += 1
                    continue
                seen_texts.add(key)
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

        if duplicates:
            logger.info("Skipped %d duplicate chunks", duplicates)

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


def _offline_requested() -> bool:
    """Return True when HuggingFace/transformers offline mode is requested."""
    return any(
        os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
    )


def _disable_dead_local_proxy() -> bool:
    """
    Clear stale localhost proxy env vars and prefer local cached model files.

    This prevents old container proxy settings such as http://127.0.0.1:13128
    from breaking an otherwise cached/offline VM run.
    """
    proxy_vars = ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY")
    for name in proxy_vars:
        proxy_url = os.environ.get(name)
        if not proxy_url:
            continue

        parsed = urlparse(proxy_url)
        if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port is None:
            continue

        try:
            with socket.create_connection((parsed.hostname, parsed.port), timeout=0.25):
                return False
        except OSError:
            for proxy_name in proxy_vars:
                os.environ.pop(proxy_name, None)
            logger.warning(
                "Disabled stale localhost proxy %s; using cached HuggingFace files only.",
                proxy_url,
            )
            return True

    return False


def _find_cached_sentence_transformer(model_name: str, cache_dir: Path) -> str:
    """
    Return a local sentence-transformers snapshot path when available.

    Passing the snapshot path directly avoids HuggingFace metadata requests in
    offline/proxy-constrained VM sessions.
    """
    model_names = [model_name]
    if "/" not in model_name:
        model_names.append(f"sentence-transformers/{model_name}")

    cache_slugs = [f"models--{name.replace('/', '--')}" for name in model_names]
    candidates = [
        parent / cache_slug
        for cache_slug in cache_slugs
        for parent in (
            cache_dir,
            cache_dir / "hub",
            Path.home() / ".cache" / "huggingface" / "hub",
        )
    ]

    for base in candidates:
        snapshots = base / "snapshots"
        if not snapshots.exists():
            continue
        for snapshot in sorted(snapshots.iterdir(), reverse=True):
            if (snapshot / "modules.json").exists():
                logger.info("Using cached embedding snapshot at %s", snapshot)
                return str(snapshot)

    return model_name
