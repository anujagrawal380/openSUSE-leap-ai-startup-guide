"""
Configuration for the openSUSE AI Onboarding Assistant.

Centralizes all knobs: model selection, RAG parameters, resource limits,
and documentation sources.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelConfig:
    """SLM model configuration."""

    # Inference mode: "local" = llama-cpp-python, "api" = HF Inference API
    inference_mode: str = "local"
    # HuggingFace model repo for the GGUF quantized model (local mode)
    repo_id: str = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
    filename: str = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
    # HF Inference API model (api mode) — used when inference_mode="api"
    api_model_id: str = "HuggingFaceH4/zephyr-7b-beta"
    # Inference parameters
    n_ctx: int = 2048  # context window (matches TinyLlama training window)
    n_threads: int = 4
    n_gpu_layers: int = -1  # -1 = offload all layers to GPU (Metal on macOS, CUDA on Linux)
    temperature: float = 0.4
    max_tokens: int = 350
    top_p: float = 0.9
    repeat_penalty: float = 1.3


@dataclass
class EmbeddingConfig:
    """Embedding model for the retrieval pipeline."""

    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"


@dataclass
class RAGConfig:
    """Retrieval-Augmented Generation pipeline settings."""

    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k: int = 2  # number of retrieved chunks per query (keep small for 1.1B model)
    collection_name: str = "opensuse_docs"
    persist_directory: str = "./data/vectorstore"


@dataclass
class DocumentationSource:
    """A documentation source to ingest."""

    name: str = ""
    base_url: str = ""
    start_urls: list[str] = field(default_factory=list)
    max_pages: int = 200


@dataclass
class Config:
    """Top-level configuration."""

    model: ModelConfig = field(default_factory=ModelConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    data_dir: str = "./data"
    log_level: str = "INFO"
    doc_sources: list[DocumentationSource] = field(default_factory=lambda: [
        DocumentationSource(
            name="openSUSE Leap Startup Guide",
            base_url="https://doc.opensuse.org",
            start_urls=[
                "https://doc.opensuse.org/documentation/leap/startup/html/book-startup/index.html",
            ],
            max_pages=100,
        ),
        DocumentationSource(
            name="openSUSE Leap Reference",
            base_url="https://doc.opensuse.org",
            start_urls=[
                "https://doc.opensuse.org/documentation/leap/reference/html/book-reference/index.html",
            ],
            max_pages=150,
        ),
    ])

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load configuration from a YAML file, falling back to defaults."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        cfg = cls()
        if "model" in raw:
            for k, v in raw["model"].items():
                if hasattr(cfg.model, k):
                    setattr(cfg.model, k, v)
        if "embedding" in raw:
            for k, v in raw["embedding"].items():
                if hasattr(cfg.embedding, k):
                    setattr(cfg.embedding, k, v)
        if "rag" in raw:
            for k, v in raw["rag"].items():
                if hasattr(cfg.rag, k):
                    setattr(cfg.rag, k, v)
        for simple in ("data_dir", "log_level"):
            if simple in raw:
                setattr(cfg, simple, raw[simple])

        return cfg
