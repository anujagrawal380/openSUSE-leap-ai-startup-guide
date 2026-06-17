"""First-run setup workflow for suse-assist."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from opensuse_ai.config import Config
from opensuse_ai.doctor import DoctorReport, run_doctor


Progress = Callable[[str], None]


@dataclass(frozen=True)
class SetupOptions:
    """Inputs for the first-run setup workflow."""

    model_tier: str = "auto"
    max_pages: int | None = None
    bundle_path: Path | None = None
    offline: bool = False
    skip_model: bool = False
    skip_ingest: bool = False
    overwrite_bundle: bool = False
    web_port: int = 7860


@dataclass(frozen=True)
class SetupResult:
    """Summary of setup actions and final health."""

    model_tier: str
    actions: list[str] = field(default_factory=list)
    doctor: DoctorReport | None = None


def run_setup(
    config: Config,
    options: SetupOptions,
    *,
    progress: Progress | None = None,
) -> SetupResult:
    """Run first-time setup tasks in a deterministic order."""
    log = progress or (lambda message: None)
    actions: list[str] = []

    resolved_tier = config.apply_model_tier(options.model_tier)
    Path(config.data_dir).mkdir(parents=True, exist_ok=True)
    log(f"Selected model tier: {resolved_tier}")

    if options.bundle_path is not None:
        from opensuse_ai.bundle import import_bundle

        result = import_bundle(
            config,
            options.bundle_path,
            overwrite=options.overwrite_bundle,
        )
        actions.append(f"imported bundle ({result.files} files)")
        log(f"Imported offline bundle: {options.bundle_path}")

    if not options.skip_model and config.model.inference_mode == "local":
        if _model_present(config):
            actions.append("model already present")
            log("Model already present")
        elif options.offline:
            actions.append("model download skipped offline")
            log("Offline mode: skipped model download")
        else:
            _download_model(config)
            actions.append("downloaded model")
            log("Downloaded model")

    if not options.skip_ingest:
        if _vectorstore_present(config):
            actions.append("vector store already present")
            log("Vector store already present")
        elif options.offline:
            actions.append("ingest skipped offline")
            log("Offline mode: skipped documentation ingest")
        else:
            _ingest_docs(config, options.max_pages)
            actions.append("ingested documentation")
            log("Ingested documentation")

    doctor = run_doctor(config, web_port=options.web_port)
    actions.append("ran doctor")
    return SetupResult(model_tier=resolved_tier, actions=actions, doctor=doctor)


def _model_present(config: Config) -> bool:
    return (Path(config.data_dir) / "models" / config.model.filename).is_file()


def _vectorstore_present(config: Config) -> bool:
    path = Path(config.rag.persist_directory)
    return path.exists() and any(path.rglob("*"))


def _download_model(config: Config) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("huggingface-hub is required to download model files") from exc

    model_dir = Path(config.data_dir) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id=config.model.repo_id,
        filename=config.model.filename,
        local_dir=str(model_dir),
    )


def _ingest_docs(config: Config, max_pages: int | None) -> None:
    from opensuse_ai.rag import RAGPipeline
    from opensuse_ai.scraper import scrape_all_sources

    if max_pages is not None:
        for source in config.doc_sources:
            source.max_pages = max_pages

    pages = scrape_all_sources(config.doc_sources, Path(config.data_dir))
    if not pages:
        raise RuntimeError("No documentation pages were scraped")

    RAGPipeline(config).ingest(pages)
