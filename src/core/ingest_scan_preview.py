"""Dry-run vault scan: classify new/changed files without ingesting."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from src.api.models_ingest import IngestScanFile, IngestScanPreviewResponse, IngestScanPreviewSummary
from src.core.ingest_manifest import file_sha256, load_manifest, manifest_path, should_skip
from src.core.ingest_paths import should_skip_path
from src.core.supported_formats import is_supported

logger = logging.getLogger(__name__)


def collect_vault_files(
    vault: Path,
    vault_subdirs: list[str],
    *,
    vision_enabled: bool,
) -> list[Path]:
    """Walk vault subdirs and return supported, non-junk files."""
    vault_root = vault.resolve()
    out: list[Path] = []
    for sub in vault_subdirs:
        root = vault_root / sub
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if not is_supported(path.suffix, vision_enabled=vision_enabled):
                continue
            if should_skip_path(path, vault_root):
                continue
            out.append(path.resolve())
    return sorted(out)


def classify_vault_file(
    vault: Path,
    abs_path: Path,
    manifest: dict[str, Any],
) -> tuple[Literal["new", "changed", "unchanged", "error"], IngestScanFile | None]:
    """Classify one vault file against the ingest manifest."""
    vault_root = vault.resolve()
    rel = str(abs_path.relative_to(vault_root)).replace("\\", "/")
    try:
        stat = abs_path.stat()
        digest = file_sha256(abs_path)
    except OSError as exc:
        logger.warning("scan_preview_hash_failed path=%s error=%s", abs_path, exc)
        return "error", None
    if should_skip(rel, digest, manifest):
        return "unchanged", None
    files = manifest.get("files")
    has_entry = isinstance(files, dict) and isinstance(files.get(rel), dict)
    change: Literal["new", "changed"] = "changed" if has_entry else "new"
    return change, IngestScanFile(
        path=rel,
        change=change,
        size=int(stat.st_size),
        mtime_ms=int(stat.st_mtime * 1000),
    )


def scan_vault_preview(
    vault: Path,
    vault_subdirs: list[str],
    *,
    vision_enabled: bool,
) -> IngestScanPreviewResponse:
    """Walk vault and return new/changed files without ingesting."""
    vault_root = vault.resolve()
    collected = collect_vault_files(vault_root, vault_subdirs, vision_enabled=vision_enabled)
    manifest = load_manifest(manifest_path(vault_root))
    candidates: list[IngestScanFile] = []
    unchanged = 0
    for abs_path in collected:
        kind, entry = classify_vault_file(vault_root, abs_path, manifest)
        if kind == "unchanged":
            unchanged += 1
            continue
        if entry is None:
            continue
        candidates.append(entry)
    new_count = sum(1 for f in candidates if f.change == "new")
    changed_count = sum(1 for f in candidates if f.change == "changed")
    logger.info(
        "vault_scan_preview total_scanned=%s new=%s changed=%s unchanged=%s",
        len(collected),
        new_count,
        changed_count,
        unchanged,
    )
    return IngestScanPreviewResponse(
        files=candidates,
        summary=IngestScanPreviewSummary(
            total_scanned=len(collected),
            new=new_count,
            changed=changed_count,
            unchanged=unchanged,
        ),
    )
