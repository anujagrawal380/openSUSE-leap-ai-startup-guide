"""Tests for configuration loading."""

from pathlib import Path

from opensuse_ai.config import Config, ModelConfig, RAGConfig


def test_default_config():
    """Default config should have sensible values."""
    cfg = Config()
    assert cfg.model.repo_id == "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
    assert cfg.rag.chunk_size == 800
    assert cfg.rag.top_k == 4
    assert len(cfg.doc_sources) > 0


def test_config_from_missing_yaml(tmp_path: Path):
    """Loading a non-existent YAML should return defaults."""
    cfg = Config.from_yaml(tmp_path / "nonexistent.yaml")
    assert cfg.model.n_ctx == 2048


def test_config_from_yaml(tmp_path: Path):
    """Loading a YAML should override defaults."""
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text(
        "model:\n"
        "  n_ctx: 4096\n"
        "  temperature: 0.7\n"
        "rag:\n"
        "  chunk_size: 1000\n"
        "  top_k: 6\n"
        "log_level: DEBUG\n"
    )
    cfg = Config.from_yaml(yaml_file)
    assert cfg.model.n_ctx == 4096
    assert cfg.model.temperature == 0.7
    assert cfg.rag.chunk_size == 1000
    assert cfg.rag.top_k == 6
    assert cfg.log_level == "DEBUG"
    # Unchanged defaults should persist
    assert cfg.model.repo_id == "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
