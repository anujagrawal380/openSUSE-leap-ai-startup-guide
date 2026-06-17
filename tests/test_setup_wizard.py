"""Tests for first-run setup workflow."""

from pathlib import Path

from opensuse_ai.bundle import export_bundle
from opensuse_ai.config import Config
from opensuse_ai.setup_wizard import SetupOptions, run_setup


def _cfg(data_dir: Path) -> Config:
    cfg = Config()
    cfg.data_dir = str(data_dir)
    cfg.model.tier = "test"
    cfg.model.filename = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
    cfg.rag.persist_directory = str(data_dir / "vectorstore")
    cfg.embedding.cache_dir = str(data_dir / "models" / "embeddings")
    return cfg


def test_setup_offline_skips_network_work(tmp_path: Path):
    cfg = _cfg(tmp_path / "data")

    result = run_setup(
        cfg,
        SetupOptions(
            model_tier="test",
            offline=True,
            skip_model=False,
            skip_ingest=False,
        ),
    )

    assert result.model_tier == "test"
    assert "model download skipped offline" in result.actions
    assert "ingest skipped offline" in result.actions
    assert result.doctor is not None
    assert not result.doctor.ok


def test_setup_imports_offline_bundle(tmp_path: Path):
    source_cfg = _cfg(tmp_path / "source")
    model = Path(source_cfg.data_dir) / "models" / source_cfg.model.filename
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")
    emb = Path(source_cfg.embedding.cache_dir) / "models--x" / "snapshots" / "abc" / "modules.json"
    emb.parent.mkdir(parents=True)
    emb.write_text("{}")
    vector = Path(source_cfg.rag.persist_directory) / "opensuse_docs.lance" / "data.bin"
    vector.parent.mkdir(parents=True)
    vector.write_bytes(b"vectors")

    bundle = tmp_path / "bundle.tar.gz"
    export_bundle(source_cfg, bundle)

    target_cfg = _cfg(tmp_path / "target")
    result = run_setup(
        target_cfg,
        SetupOptions(
            model_tier="test",
            bundle_path=bundle,
            offline=True,
            skip_ingest=True,
        ),
    )

    assert "imported bundle (3 files)" in result.actions
    assert (Path(target_cfg.data_dir) / "models" / target_cfg.model.filename).is_file()
