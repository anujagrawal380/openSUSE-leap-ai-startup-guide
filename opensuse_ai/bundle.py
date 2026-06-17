"""Offline bundle export/import for suse-assist runtime data."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from opensuse_ai.config import Config

BUNDLE_ROOT = "suse-assist-bundle"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class BundleResult:
    """Summary of a bundle operation."""

    path: Path
    files: int
    bytes: int


def export_bundle(config: Config, output_path: str | Path) -> BundleResult:
    """Create an offline bundle with model, vector store, and embedding cache."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    files = _collect_runtime_files(config)
    if not files:
        raise FileNotFoundError("No runtime data found to bundle.")

    manifest = _build_manifest(config, files)

    with tempfile.TemporaryDirectory(prefix="suse-assist-bundle-") as tmp:
        manifest_path = Path(tmp) / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

        mode = "w:gz" if str(output).endswith((".gz", ".tgz")) else "w"
        with tarfile.open(output, mode) as tar:
            tar.add(manifest_path, arcname=f"{BUNDLE_ROOT}/{MANIFEST_NAME}")
            for src, arcname in files:
                tar.add(src, arcname=f"{BUNDLE_ROOT}/{arcname}")

    total_bytes = sum(src.stat().st_size for src, _ in files if src.is_file())
    return BundleResult(path=output, files=len(files), bytes=total_bytes)


def import_bundle(
    config: Config,
    bundle_path: str | Path,
    *,
    overwrite: bool = False,
) -> BundleResult:
    """Import an offline bundle into ``config.data_dir`` after checksum verification."""
    bundle = Path(bundle_path)
    if not bundle.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle}")

    with tempfile.TemporaryDirectory(prefix="suse-assist-import-") as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(bundle, "r:*") as tar:
            _safe_extract(tar, tmp_path)

        root = tmp_path / BUNDLE_ROOT
        manifest_path = root / MANIFEST_NAME
        if not manifest_path.exists():
            raise ValueError(f"Bundle is missing {BUNDLE_ROOT}/{MANIFEST_NAME}")

        manifest = json.loads(manifest_path.read_text())
        _verify_manifest(root, manifest)

        imported_files = 0
        imported_bytes = 0
        data_root = Path(config.data_dir)
        for entry in manifest.get("files", []):
            rel = Path(entry["path"])
            if not rel.parts or rel.parts[0] != "data":
                raise ValueError(f"Invalid bundle path outside data/: {rel}")

            src = root / rel
            dest = data_root / Path(*rel.parts[1:])
            if dest.exists() and not overwrite:
                raise FileExistsError(
                    f"Target already exists: {dest}. Re-run with overwrite enabled."
                )

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            imported_files += 1
            imported_bytes += dest.stat().st_size

    return BundleResult(path=bundle, files=imported_files, bytes=imported_bytes)


def _collect_runtime_files(config: Config) -> list[tuple[Path, str]]:
    data_dir = Path(config.data_dir)
    paths = [
        data_dir / "models" / config.model.filename,
        Path(config.rag.persist_directory),
        Path(config.embedding.cache_dir),
    ]

    files: list[tuple[Path, str]] = []
    for path in paths:
        if path.is_file():
            files.append((path, _arcname_for_data_path(config, path)))
        elif path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                files.append((child, _arcname_for_data_path(config, child)))
    return files


def _arcname_for_data_path(config: Config, path: Path) -> str:
    data_dir = Path(config.data_dir).resolve()
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(data_dir)
    except ValueError as exc:
        raise ValueError(f"Runtime path is outside data_dir: {path}") from exc
    return str(Path("data") / rel)


def _build_manifest(config: Config, files: list[tuple[Path, str]]) -> dict:
    return {
        "schema": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "model": {
            "tier": config.model.tier,
            "repo_id": config.model.repo_id,
            "filename": config.model.filename,
            "inference_mode": config.model.inference_mode,
        },
        "rag": {
            "backend": config.rag.backend,
            "collection_name": config.rag.collection_name,
        },
        "embedding": {
            "model_name": config.embedding.model_name,
        },
        "files": [
            {
                "path": arcname,
                "size": src.stat().st_size,
                "sha256": _sha256(src),
            }
            for src, arcname in files
        ],
    }


def _verify_manifest(root: Path, manifest: dict) -> None:
    if manifest.get("schema") != 1:
        raise ValueError(f"Unsupported bundle schema: {manifest.get('schema')}")

    for entry in manifest.get("files", []):
        rel = Path(entry["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe bundle path: {rel}")
        src = root / rel
        if not src.is_file():
            raise ValueError(f"Manifest file missing from bundle: {rel}")
        expected_size = entry["size"]
        if src.stat().st_size != expected_size:
            raise ValueError(f"Size mismatch for {rel}")
        expected_sha = entry["sha256"]
        actual_sha = _sha256(src)
        if actual_sha != expected_sha:
            raise ValueError(f"Checksum mismatch for {rel}")


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in tar.getmembers():
        target = (dest / member.name).resolve()
        if dest != target and dest not in target.parents:
            raise ValueError(f"Unsafe path in bundle: {member.name}")
        if member.islnk() or member.issym():
            raise ValueError(f"Links are not allowed in bundles: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"Unsupported tar member in bundle: {member.name}")
    tar.extractall(dest)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
