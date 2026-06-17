"""Deployment health checks for suse-assist."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from opensuse_ai.config import Config


@dataclass(frozen=True)
class DoctorCheck:
    """One health-check result."""

    name: str
    status: str
    detail: str
    hint: str = ""


@dataclass(frozen=True)
class DoctorReport:
    """Full health-check report."""

    checks: list[DoctorCheck]

    @property
    def ok(self) -> bool:
        return not any(c.status == "fail" for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == "warn" for c in self.checks)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "has_warnings": self.has_warnings,
            "checks": [asdict(c) for c in self.checks],
        }


def run_doctor(config: Config, *, web_port: int = 7860) -> DoctorReport:
    """Run cheap deployment checks without loading the LLM."""
    checks = [
        _check_data_dir(config),
        _check_model(config),
        _check_vectorstore(config),
        _check_embeddings(config),
        _check_host_context_mount(),
        _check_web_port(web_port),
        _check_podman(),
    ]
    return DoctorReport(checks)


def _check_data_dir(config: Config) -> DoctorCheck:
    data_dir = Path(config.data_dir)
    target = data_dir if data_dir.exists() else data_dir.parent

    if not target.exists():
        return DoctorCheck(
            "data directory",
            "fail",
            f"{data_dir} does not exist and parent {target} is missing",
            "Create the data directory or fix data_dir in config.yaml.",
        )

    if not os.access(target, os.W_OK):
        return DoctorCheck(
            "data directory",
            "fail",
            f"{target} is not writable",
            "Fix ownership/permissions for the assistant data directory.",
        )

    disk = shutil.disk_usage(target)
    free_gb = disk.free / (1024**3)
    status = "ok" if free_gb >= 2 else "warn"
    hint = "" if status == "ok" else "Keep several GiB free for GGUF models and indexes."
    return DoctorCheck(
        "data directory",
        status,
        f"{data_dir} usable; {free_gb:.1f} GiB free",
        hint,
    )


def _check_model(config: Config) -> DoctorCheck:
    if config.model.inference_mode == "api":
        return DoctorCheck(
            "local model",
            "ok",
            f"API mode configured ({config.model.api_model_id}); no local GGUF required",
        )

    model_path = Path(config.data_dir) / "models" / config.model.filename
    if model_path.exists():
        size_gb = model_path.stat().st_size / (1024**3)
        return DoctorCheck(
            "local model",
            "ok",
            f"{model_path} present ({size_gb:.2f} GiB)",
        )

    return DoctorCheck(
        "local model",
        "fail",
        f"{model_path} missing",
        "Run a networked setup/download step, or import an offline bundle containing this GGUF.",
    )


def _check_vectorstore(config: Config) -> DoctorCheck:
    persist_dir = Path(config.rag.persist_directory)
    if not persist_dir.exists():
        return DoctorCheck(
            "vector store",
            "fail",
            f"{persist_dir} missing",
            "Run suse-assist ingest or import an offline bundle with the LanceDB index.",
        )

    try:
        count = _vectorstore_count(config)
    except Exception as exc:
        return DoctorCheck(
            "vector store",
            "fail",
            f"could not open {persist_dir}: {exc}",
            "Rebuild the index with suse-assist ingest.",
        )

    if count <= 0:
        return DoctorCheck(
            "vector store",
            "fail",
            f"{persist_dir} opened but has no chunks",
            "Run suse-assist ingest.",
        )

    return DoctorCheck("vector store", "ok", f"{count} indexed chunks")


def _vectorstore_count(config: Config) -> int:
    """Open the configured vector store and return its row count."""
    from opensuse_ai.rag import create_backend

    backend = create_backend(config.rag)
    return backend.count


def _check_embeddings(config: Config) -> DoctorCheck:
    cache_dir = Path(config.embedding.cache_dir)
    if _has_sentence_transformer_snapshot(cache_dir):
        return DoctorCheck("embedding cache", "ok", f"cached model found under {cache_dir}")

    return DoctorCheck(
        "embedding cache",
        "warn",
        f"no cached sentence-transformers snapshot found under {cache_dir}",
        "Offline retrieval may fail until the embedding model is cached or bundled.",
    )


def _has_sentence_transformer_snapshot(cache_dir: Path) -> bool:
    candidates = [cache_dir, cache_dir / "hub"]
    for base in candidates:
        if not base.exists():
            continue
        for modules_file in base.glob("models--*/snapshots/*/modules.json"):
            if modules_file.is_file():
                return True
    return False


def _check_host_context_mount() -> DoctorCheck:
    host_root = os.environ.get("SUSE_AI_HOST_ROOT", "")
    if not host_root:
        return DoctorCheck(
            "host context",
            "warn",
            "SUSE_AI_HOST_ROOT is not set",
            "Container deployments should mount /:/host:ro and set SUSE_AI_HOST_ROOT=/host.",
        )

    os_release = Path(host_root) / "etc" / "os-release"
    if os_release.exists():
        return DoctorCheck("host context", "ok", f"{host_root} exposes /etc/os-release")

    return DoctorCheck(
        "host context",
        "fail",
        f"{host_root}/etc/os-release not found",
        "Fix the host root bind mount or unset SUSE_AI_HOST_ROOT for native runs.",
    )


def _check_web_port(port: int) -> DoctorCheck:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", port))

    if result == 0:
        return DoctorCheck("web port", "ok", f"127.0.0.1:{port} is accepting TCP connections")

    return DoctorCheck(
        "web port",
        "warn",
        f"127.0.0.1:{port} is not listening",
        "Start the web UI if you expect a browser-accessible assistant.",
    )


def _check_podman() -> DoctorCheck:
    podman = shutil.which("podman")
    if podman is None:
        return DoctorCheck(
            "podman",
            "warn",
            "podman not found on PATH",
            "Container/OEM deployments need Podman; native source runs do not.",
        )

    try:
        proc = subprocess.run(
            [podman, "ps", "--format", "{{.Names}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception as exc:
        return DoctorCheck(
            "podman",
            "warn",
            f"podman exists but could not be queried: {exc}",
            "Check Podman service/user permissions.",
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip() or "podman ps failed"
        return DoctorCheck("podman", "warn", detail, "Check Podman service/user permissions.")

    containers = [line for line in proc.stdout.splitlines() if line.strip()]
    if containers:
        return DoctorCheck("podman", "ok", f"running containers: {', '.join(containers)}")
    return DoctorCheck("podman", "ok", "podman available; no running containers")
