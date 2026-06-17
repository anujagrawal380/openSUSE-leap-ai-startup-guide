"""Helpers for native systemd deployment."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class NativeServiceOptions:
    """Inputs used to render a native suse-assist systemd deployment."""

    app_dir: Path = Path("/opt/suse-assist")
    data_dir: Path = Path("/var/lib/suse-assist")
    venv_dir: Path = Path("/opt/suse-assist/.venv")
    unit_dir: Path = Path("/etc/systemd/system")
    config_path: Path = Path("/opt/suse-assist/config-systemd.yaml")
    service_user: str = "suseai"
    model_tier: str = "auto"
    port: int = 7860
    demo: bool = False
    n_threads: int = os.cpu_count() or 1


@dataclass(frozen=True)
class NativeServiceFiles:
    """Paths and rendered content for a native service deployment."""

    service_path: Path
    config_path: Path
    service_text: str
    config_text: str


def build_native_service_files(options: NativeServiceOptions) -> NativeServiceFiles:
    """Render the systemd unit and config file without writing them."""
    service_path = options.unit_dir / "suse-assist.service"
    return NativeServiceFiles(
        service_path=service_path,
        config_path=options.config_path,
        service_text=render_native_service(options),
        config_text=render_native_config(options),
    )


def render_native_config(options: NativeServiceOptions) -> str:
    """Render the config used by the native systemd service."""
    config = {
        "model": {
            "inference_mode": "local",
            "tier": options.model_tier,
            "n_gpu_layers": 0,
            "n_threads": options.n_threads,
        },
        "embedding": {
            "cache_dir": str(options.data_dir / "models" / "embeddings"),
        },
        "rag": {
            "persist_directory": str(options.data_dir / "vectorstore"),
            "backend": "lancedb",
        },
        "prompt_cache": {
            "enabled": True,
            "path": str(options.data_dir / "prompt_cache.json"),
        },
        "data_dir": str(options.data_dir),
        "log_level": "INFO",
    }
    return yaml.safe_dump(config, sort_keys=False)


def render_native_service(options: NativeServiceOptions) -> str:
    """Render a hardened systemd unit for the web UI."""
    demo_arg = " --demo" if options.demo else ""
    return f"""[Unit]
Description=openSUSE AI Onboarding Assistant
Documentation=https://github.com/anujagrawal380/openSUSE-leap-ai-startup-guide
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={options.service_user}
Group={options.service_user}
WorkingDirectory={options.app_dir}
Environment=PATH={options.venv_dir}/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1
Environment=HF_HUB_OFFLINE=1
Environment=TRANSFORMERS_OFFLINE=1
ExecStart={options.venv_dir}/bin/suse-assist --config {options.config_path} web{demo_arg} --port {options.port}
Restart=on-failure
RestartSec=10
TimeoutStartSec=900
StartLimitIntervalSec=300
StartLimitBurst=5

NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths={options.data_dir}
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes

[Install]
WantedBy=multi-user.target
"""


def write_native_service_files(options: NativeServiceOptions) -> NativeServiceFiles:
    """Write rendered native service files to disk."""
    files = build_native_service_files(options)
    files.config_path.parent.mkdir(parents=True, exist_ok=True)
    files.service_path.parent.mkdir(parents=True, exist_ok=True)
    options.data_dir.mkdir(parents=True, exist_ok=True)

    files.config_path.write_text(files.config_text)
    files.service_path.write_text(files.service_text)
    return files


def create_service_user(user: str) -> None:
    """Create the system service user when it does not already exist."""
    if subprocess.run(["id", user], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return
    subprocess.run(
        ["useradd", "--system", "--create-home", "--shell", "/sbin/nologin", user],
        check=True,
    )


def enable_native_service() -> None:
    """Reload systemd and enable/start suse-assist.service."""
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "suse-assist.service"], check=True)
