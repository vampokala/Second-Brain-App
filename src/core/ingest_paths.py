"""Path filters shared by vault scan and filesystem watcher."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.supported_formats import is_supported

_SKIP_NAME_RE = re.compile(
    r"^(\.DS_Store|~\$.*|.*\.tmp$|.*\.swp)$",
    re.IGNORECASE,
)


class IngestPathError(ValueError):
    """Raised when a requested vault-relative path is invalid for ingest."""


def should_skip_path(path: Path, vault: Path) -> bool:
    """Return True for junk paths that must not be ingested."""
    name = path.name
    if _SKIP_NAME_RE.match(name):
        return True
    try:
        rel = path.relative_to(vault)
    except ValueError:
        return True
    parts = rel.parts
    if ".git" in parts or ".obsidian" in parts or "node_modules" in parts:
        return True
    return False


def resolve_vault_ingest_path(
    vault: Path,
    relpath: str,
    *,
    vision_enabled: bool,
) -> Path:
    """Resolve and validate a vault-relative path for selective ingest.

    Raises:
        IngestPathError: path traversal, missing file, unsupported, or junk path.
    """
    if not isinstance(relpath, str) or not relpath.strip():
        raise IngestPathError("path is empty")
    norm = relpath.replace("\\", "/").strip().lstrip("/")
    if not norm or ".." in Path(norm).parts:
        raise IngestPathError(f"invalid path: {relpath}")
    vault_root = vault.resolve()
    candidate = (vault_root / norm).resolve()
    try:
        candidate.relative_to(vault_root)
    except ValueError as exc:
        raise IngestPathError(f"path escapes vault: {relpath}") from exc
    if not candidate.is_file():
        raise IngestPathError(f"not a file: {norm}")
    if should_skip_path(candidate, vault_root):
        raise IngestPathError(f"path not eligible for ingest: {norm}")
    if not is_supported(candidate.suffix, vision_enabled=vision_enabled):
        raise IngestPathError(f"unsupported file type: {norm}")
    return candidate
