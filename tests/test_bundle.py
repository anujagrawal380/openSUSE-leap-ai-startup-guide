"""Tests for offline bundle export/import."""

import json
import tarfile
from pathlib import Path

from opensuse_ai.bundle import BUNDLE_ROOT, export_bundle, import_bundle
from opensuse_ai.config import Config


def _cfg(data_dir: Path) -> Config:
    cfg = Config()
    cfg.data_dir = str(data_dir)
    cfg.model.filename = "test.gguf"
    cfg.rag.persist_directory = str(data_dir / "vectorstore")
    cfg.embedding.cache_dir = str(data_dir / "models" / "embeddings")
    return cfg


def _seed_runtime_data(data_dir: Path) -> Config:
    cfg = _cfg(data_dir)
    model = data_dir / "models" / "test.gguf"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")

    vector = data_dir / "vectorstore" / "opensuse_docs.lance" / "data.bin"
    vector.parent.mkdir(parents=True)
    vector.write_bytes(b"vectors")

    emb = data_dir / "models" / "embeddings" / "models--x" / "snapshots" / "abc" / "modules.json"
    emb.parent.mkdir(parents=True)
    emb.write_text("{}")
    return cfg


def test_export_bundle_writes_manifest_and_runtime_files(tmp_path: Path):
    cfg = _seed_runtime_data(tmp_path / "data")
    output = tmp_path / "bundle.tar.gz"

    result = export_bundle(cfg, output)

    assert result.files == 3
    with tarfile.open(output, "r:gz") as tar:
        names = tar.getnames()
        assert f"{BUNDLE_ROOT}/manifest.json" in names
        manifest = json.load(tar.extractfile(f"{BUNDLE_ROOT}/manifest.json"))

    paths = {entry["path"] for entry in manifest["files"]}
    assert "data/models/test.gguf" in paths
    assert "data/vectorstore/opensuse_docs.lance/data.bin" in paths
    assert "data/models/embeddings/models--x/snapshots/abc/modules.json" in paths


def test_import_bundle_restores_runtime_files(tmp_path: Path):
    source_cfg = _seed_runtime_data(tmp_path / "source")
    output = tmp_path / "bundle.tar.gz"
    export_bundle(source_cfg, output)

    target_cfg = _cfg(tmp_path / "target")
    result = import_bundle(target_cfg, output)

    assert result.files == 3
    assert (Path(target_cfg.data_dir) / "models" / "test.gguf").read_bytes() == b"model"
    assert (
        Path(target_cfg.rag.persist_directory)
        / "opensuse_docs.lance"
        / "data.bin"
    ).read_bytes() == b"vectors"
