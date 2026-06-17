"""Tests for native systemd service setup rendering."""

from pathlib import Path

import yaml

from opensuse_ai.service_setup import (
    NativeServiceOptions,
    build_native_service_files,
    write_native_service_files,
)


def _options(tmp_path: Path, *, demo: bool = False) -> NativeServiceOptions:
    app_dir = tmp_path / "opt" / "suse-assist"
    return NativeServiceOptions(
        app_dir=app_dir,
        data_dir=tmp_path / "var" / "lib" / "suse-assist",
        venv_dir=app_dir / ".venv",
        unit_dir=tmp_path / "systemd",
        config_path=app_dir / "config-systemd.yaml",
        service_user="suseai",
        model_tier="test",
        port=19000,
        demo=demo,
        n_threads=4,
    )


def test_native_service_rendering_uses_real_system_context_by_default(tmp_path: Path):
    files = build_native_service_files(_options(tmp_path))

    assert files.service_path == tmp_path / "systemd" / "suse-assist.service"
    assert "--demo" not in files.service_text
    assert "--port 19000" in files.service_text
    assert f"ReadWritePaths={tmp_path}/var/lib/suse-assist" in files.service_text
    assert "HF_HUB_OFFLINE=1" in files.service_text

    config = yaml.safe_load(files.config_text)
    assert config["model"]["tier"] == "test"
    assert config["model"]["n_gpu_layers"] == 0
    assert config["model"]["n_threads"] == 4
    assert config["rag"]["persist_directory"] == f"{tmp_path}/var/lib/suse-assist/vectorstore"


def test_native_service_rendering_can_enable_demo_mode(tmp_path: Path):
    files = build_native_service_files(_options(tmp_path, demo=True))

    assert " web --demo --port 19000" in files.service_text


def test_write_native_service_files(tmp_path: Path):
    options = _options(tmp_path)

    files = write_native_service_files(options)

    assert files.config_path.read_text() == files.config_text
    assert files.service_path.read_text() == files.service_text
    assert options.data_dir.is_dir()
