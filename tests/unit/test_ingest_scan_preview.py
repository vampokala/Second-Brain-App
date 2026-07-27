"""Unit tests for scan preview classification and path validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.core.ingest_manifest import file_sha256, save_manifest, upsert_entry
from src.core.ingest_paths import IngestPathError, resolve_vault_ingest_path
from src.core.ingest_scan_preview import scan_vault_preview


def test_resolve_vault_ingest_path_accepts_valid_file(tmp_path: Path) -> None:
    vault = tmp_path
    target = vault / "raw" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_text("hello", encoding="utf-8")

    resolved = resolve_vault_ingest_path(vault, "raw/note.md", vision_enabled=False)
    assert resolved == target.resolve()


def test_resolve_vault_ingest_path_rejects_traversal(tmp_path: Path) -> None:
    vault = tmp_path
    (vault / "raw").mkdir()
    with pytest.raises(IngestPathError, match="invalid path"):
        resolve_vault_ingest_path(vault, "../etc/passwd", vision_enabled=False)


def test_resolve_vault_ingest_path_rejects_missing(tmp_path: Path) -> None:
    vault = tmp_path
    (vault / "raw").mkdir()
    with pytest.raises(IngestPathError, match="not a file"):
        resolve_vault_ingest_path(vault, "raw/missing.md", vision_enabled=False)


def test_resolve_vault_ingest_path_rejects_unsupported(tmp_path: Path) -> None:
    vault = tmp_path
    target = vault / "raw" / "bin.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x00\x01")
    with pytest.raises(IngestPathError, match="unsupported"):
        resolve_vault_ingest_path(vault, "raw/bin.exe", vision_enabled=False)


def test_resolve_vault_ingest_path_rejects_junk(tmp_path: Path) -> None:
    vault = tmp_path
    target = vault / "raw" / ".DS_Store"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    with pytest.raises(IngestPathError, match="not eligible"):
        resolve_vault_ingest_path(vault, "raw/.DS_Store", vision_enabled=False)


def test_resolve_vault_ingest_path_rejects_empty() -> None:
    with pytest.raises(IngestPathError, match="empty"):
        resolve_vault_ingest_path(Path("/tmp"), "  ", vision_enabled=False)


def test_scan_preview_classifies_new_changed_unchanged(tmp_path: Path) -> None:
    vault = tmp_path
    raw = vault / "raw"
    raw.mkdir()
    (raw / "new.md").write_text("brand new", encoding="utf-8")
    changed = raw / "changed.md"
    changed.write_text("v1", encoding="utf-8")
    same = raw / "same.md"
    same.write_text("stable", encoding="utf-8")

    digest_same = file_sha256(same)
    digest_old = file_sha256(changed)
    changed.write_text("v2", encoding="utf-8")

    manifest = {"version": 1, "files": {}}
    upsert_entry(manifest, "raw/changed.md", digest_old, size=2, mtime_ms=1)
    upsert_entry(manifest, "raw/same.md", digest_same, size=6, mtime_ms=1)
    save_manifest(vault / ".ingest-manifest.json", manifest)

    preview = scan_vault_preview(vault, ["raw", "wiki"], vision_enabled=False)

    paths = {f.path: f.change for f in preview.files}
    assert paths["raw/new.md"] == "new"
    assert paths["raw/changed.md"] == "changed"
    assert "raw/same.md" not in paths
    assert preview.summary.new == 1
    assert preview.summary.changed == 1
    assert preview.summary.unchanged == 1
    assert preview.summary.total_scanned == 3


def test_scan_preview_empty_vault(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    preview = scan_vault_preview(tmp_path, ["raw"], vision_enabled=False)
    assert preview.files == []
    assert preview.summary.total_scanned == 0
