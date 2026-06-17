"""Tests for deployment health checks."""

from pathlib import Path
from unittest.mock import patch

from opensuse_ai.config import Config
from opensuse_ai.doctor import run_doctor


def _cfg(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.data_dir = str(tmp_path / "data")
    cfg.rag.persist_directory = str(tmp_path / "data" / "vectorstore")
    cfg.embedding.cache_dir = str(tmp_path / "data" / "models" / "embeddings")
    cfg.model.filename = "test.gguf"
    return cfg


def test_doctor_reports_missing_required_runtime_files(tmp_path):
    cfg = _cfg(tmp_path)

    with patch("opensuse_ai.doctor.shutil.which", return_value=None):
        report = run_doctor(cfg)

    checks = {c.name: c for c in report.checks}
    assert report.ok is False
    assert checks["local model"].status == "fail"
    assert checks["vector store"].status == "fail"
    assert checks["embedding cache"].status == "warn"


def test_doctor_accepts_api_mode_without_local_model(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.model.inference_mode = "api"

    with patch("opensuse_ai.doctor._vectorstore_count", return_value=12), \
         patch("opensuse_ai.doctor.shutil.which", return_value=None):
        Path(cfg.rag.persist_directory).mkdir(parents=True)

        report = run_doctor(cfg)

    checks = {c.name: c for c in report.checks}
    assert checks["local model"].status == "ok"
    assert checks["vector store"].status == "ok"


def test_doctor_finds_model_and_embedding_cache(tmp_path):
    cfg = _cfg(tmp_path)
    model_path = Path(cfg.data_dir) / "models" / cfg.model.filename
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"fake model")

    modules = (
        Path(cfg.embedding.cache_dir)
        / "models--sentence-transformers--all-MiniLM-L6-v2"
        / "snapshots"
        / "abc"
        / "modules.json"
    )
    modules.parent.mkdir(parents=True)
    modules.write_text("{}")

    with patch("opensuse_ai.doctor._vectorstore_count", return_value=1), \
         patch("opensuse_ai.doctor.shutil.which", return_value=None):
        Path(cfg.rag.persist_directory).mkdir(parents=True)

        report = run_doctor(cfg)

    checks = {c.name: c for c in report.checks}
    assert checks["local model"].status == "ok"
    assert checks["embedding cache"].status == "ok"
    assert checks["vector store"].status == "ok"
