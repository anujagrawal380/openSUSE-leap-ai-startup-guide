"""
Configuration for the openSUSE AI Onboarding Assistant.

Centralizes all knobs: model selection, RAG parameters, resource limits,
and documentation sources.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModelTier:
    """Hardware-oriented model tier."""

    name: str
    label: str
    min_available_ram_gb: float
    repo_id: str
    filename: str
    n_ctx: int
    max_tokens: int
    description: str


MODEL_TIERS: dict[str, ModelTier] = {
    "test": ModelTier(
        name="test",
        label="Test",
        min_available_ram_gb=0.0,
        repo_id="TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        filename="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        n_ctx=2048,
        max_tokens=350,
        description="Tiny CI/demo fallback; not recommended for end users.",
    ),
    "lite": ModelTier(
        name="lite",
        label="Lite",
        min_available_ram_gb=3.0,
        repo_id="Qwen/Qwen3-1.7B-GGUF",
        filename="Qwen3-1.7B-Q8_0.gguf",
        n_ctx=32768,
        max_tokens=500,
        description="Recommended low-resource tier for 4 GB systems.",
    ),
    "standard": ModelTier(
        name="standard",
        label="Standard",
        min_available_ram_gb=6.0,
        repo_id="lmstudio-community/Qwen3-4B-Instruct-2507-GGUF",
        filename="Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        n_ctx=32768,
        max_tokens=700,
        description="Recommended default candidate for 8 GB systems.",
    ),
    "full": ModelTier(
        name="full",
        label="Full",
        min_available_ram_gb=14.0,
        repo_id="Qwen/Qwen3-8B-GGUF",
        filename="Qwen3-8B-Q4_K_M.gguf",
        n_ctx=32768,
        max_tokens=900,
        description="Higher-quality tier for systems with workstation-class memory.",
    ),
}


def available_ram_gb() -> float:
    """Return currently available RAM in GiB, or 0 when it cannot be detected."""
    try:
        import psutil

        return psutil.virtual_memory().available / (1024**3)
    except ImportError:
        return 0.0


def recommend_model_tier(ram_gb: float | None = None) -> str:
    """Choose the highest tier that fits the detected available RAM."""
    ram_gb = available_ram_gb() if ram_gb is None else ram_gb
    selected = "lite"
    for name, tier in MODEL_TIERS.items():
        if ram_gb >= tier.min_available_ram_gb:
            selected = name
    return selected


@dataclass
class ModelConfig:
    """SLM model configuration."""

    # Inference mode: "local" = llama-cpp-python, "api" = HF Inference API
    inference_mode: str = "local"
    # Hardware tier: "test", "lite", "standard", "full", "auto", or "custom"
    tier: str = "test"
    # HuggingFace model repo for the GGUF quantized model (local mode)
    repo_id: str = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
    filename: str = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
    # HF Inference API model (api mode) — used when inference_mode="api"
    api_model_id: str = "Qwen/Qwen3-235B-A22B"
    # Inference parameters — tuned for Qwen3 family.
    # TinyLlama (test tier) overrides n_ctx/max_tokens via apply_model_tier().
    n_ctx: int = 32768
    n_threads: int = 4
    n_gpu_layers: int = -1  # -1 = offload all layers to GPU (Metal on macOS, CUDA on Linux)
    temperature: float = 0.4
    max_tokens: int = 700
    top_p: float = 0.9
    repeat_penalty: float = 1.1


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
    top_k: int = 4  # number of retrieved chunks per query
    collection_name: str = "opensuse_docs"
    persist_directory: str = "./data/vectorstore"
    backend: str = "chroma"  # "chroma" or "lancedb"


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

    def apply_model_tier(
        self,
        requested_tier: str | None = None,
        ram_gb: float | None = None,
    ) -> str:
        """
        Apply a model tier to the local model settings.

        Returns the resolved tier name. The "custom" tier leaves repo/filename/context
        fields untouched so advanced users can provide their own model in config.yaml.
        """
        tier_name = requested_tier or self.model.tier
        if tier_name == "auto":
            tier_name = recommend_model_tier(ram_gb)

        if tier_name == "custom":
            self.model.tier = "custom"
            return "custom"

        if tier_name not in MODEL_TIERS:
            valid = ", ".join(["auto", "custom", *MODEL_TIERS])
            raise ValueError(f"Unknown model tier '{tier_name}'. Expected one of: {valid}")

        tier = MODEL_TIERS[tier_name]
        self.model.tier = tier_name
        self.model.repo_id = tier.repo_id
        self.model.filename = tier.filename
        self.model.n_ctx = tier.n_ctx
        self.model.max_tokens = tier.max_tokens
        return tier_name

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
