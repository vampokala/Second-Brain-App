"""Content-hash manifest for skipping unchanged vault files during ingest."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = ".ingest-manifest.json"
_MANIFEST_LOCK = threading.Lock()


def file_sha256(path: Path, *, retries: int = 3) -> str:
    """Return hex SHA-256 digest of file contents."""
    from src.core.fs_retry import retry_os

    def _hash() -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    return retry_os(_hash, retries=retries, label=f"sha256:{path.name}")


def manifest_path(vault: Path) -> Path:
    return vault / MANIFEST_FILENAME


def load_manifest(path: Path) -> dict[str, Any]:
    """Load manifest JSON; return empty dict when missing or invalid."""
    from src.core.fs_retry import retry_os

    if not path.is_file():
        return {"version": 1, "files": {}}
    try:
        raw = retry_os(
            lambda: path.read_text(encoding="utf-8"),
            label="manifest_read",
        )
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("manifest_load_failed path=%s error=%s", path, exc)
        return {"version": 1, "files": {}}
    if not isinstance(data, dict):
        return {"version": 1, "files": {}}
    files = data.get("files")
    if not isinstance(files, dict):
        data["files"] = {}
    data.setdefault("version", 1)
    return data


def save_manifest(path: Path, data: dict[str, Any]) -> None:
    """Persist manifest atomically."""
    from src.core.fs_retry import retry_os

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload = json.dumps(data, indent=2, sort_keys=True)

    def _write() -> None:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)

    retry_os(_write, label="manifest_save")


def update_manifest_entry(
    path: Path,
    relpath: str,
    digest: str,
    *,
    size: int,
    mtime_ms: int,
) -> None:
    """Load-upsert-save under a process-wide lock to avoid lost updates."""
    with _MANIFEST_LOCK:
        data = load_manifest(path)
        upsert_entry(data, relpath, digest, size=size, mtime_ms=mtime_ms)
        save_manifest(path, data)


def remove_manifest_entry(path: Path, relpath: str) -> None:
    """Drop one path from the manifest under lock."""
    with _MANIFEST_LOCK:
        data = load_manifest(path)
        files = data.get("files")
        if isinstance(files, dict) and relpath in files:
            del files[relpath]
            save_manifest(path, data)


def clear_manifest(path: Path) -> None:
    """Reset manifest to empty under lock."""
    with _MANIFEST_LOCK:
        if path.is_file():
            path.unlink()
        save_manifest(path, {"version": 1, "files": {}})


def should_skip(relpath: str, digest: str, manifest: dict[str, Any]) -> bool:
    """Return True when *relpath* digest matches the stored manifest entry."""
    files = manifest.get("files")
    if not isinstance(files, dict):
        return False
    entry = files.get(relpath)
    if not isinstance(entry, dict):
        return False
    stored = entry.get("digest")
    return isinstance(stored, str) and stored == digest


def upsert_entry(
    manifest: dict[str, Any],
    relpath: str,
    digest: str,
    *,
    size: int,
    mtime_ms: int,
) -> None:
    """Record or update one file entry in the manifest."""
    files = manifest.setdefault("files", {})
    if not isinstance(files, dict):
        manifest["files"] = {}
        files = manifest["files"]
    files[relpath] = {
        "digest": digest,
        "size": size,
        "mtime_ms": mtime_ms,
    }
