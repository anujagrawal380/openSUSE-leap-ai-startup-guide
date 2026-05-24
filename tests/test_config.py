"""Tests for configuration loading."""

from pathlib import Path

from opensuse_ai.config import MODEL_TIERS, Config, recommend_model_tier


def test_default_config():
    """Default config should have sensible values."""
    cfg = Config()
    assert cfg.model.tier == "test"
    assert cfg.model.repo_id == "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
    assert cfg.rag.chunk_size == 500
    assert cfg.rag.top_k == 2
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
        "  tier: standard\n"
        "  n_ctx: 4096\n"
        "  temperature: 0.7\n"
        "rag:\n"
        "  chunk_size: 1000\n"
        "  top_k: 6\n"
        "log_level: DEBUG\n"
    )
    cfg = Config.from_yaml(yaml_file)
    assert cfg.model.tier == "standard"
    assert cfg.model.n_ctx == 4096
    assert cfg.model.temperature == 0.7
    assert cfg.rag.chunk_size == 1000
    assert cfg.rag.top_k == 6
    assert cfg.log_level == "DEBUG"
    # Unchanged defaults should persist
    assert cfg.model.repo_id == "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"


def test_recommend_model_tier_by_ram():
    """Auto tier selection should choose the highest tier that fits RAM."""
    assert recommend_model_tier(2.0) == "test"
    assert recommend_model_tier(4.0) == "lite"
    assert recommend_model_tier(8.0) == "standard"
    assert recommend_model_tier(16.0) == "full"


def test_apply_model_tier_standard():
    """Applying a tier should update local model settings."""
    cfg = Config()
    resolved = cfg.apply_model_tier("standard")
    standard = MODEL_TIERS["standard"]
    assert resolved == "standard"
    assert cfg.model.tier == "standard"
    assert cfg.model.repo_id == standard.repo_id
    assert cfg.model.filename == standard.filename
    assert cfg.model.n_ctx == standard.n_ctx


def test_apply_model_tier_custom_preserves_model_fields():
    """Custom tier should leave explicit model settings untouched."""
    cfg = Config()
    cfg.model.repo_id = "example/custom"
    cfg.model.filename = "custom.gguf"
    resolved = cfg.apply_model_tier("custom")
    assert resolved == "custom"
    assert cfg.model.repo_id == "example/custom"
    assert cfg.model.filename == "custom.gguf"
