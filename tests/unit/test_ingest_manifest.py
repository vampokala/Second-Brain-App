from __future__ import annotations

from pathlib import Path

from src.core.ingest_manifest import (
    file_sha256,
    load_manifest,
    save_manifest,
    should_skip,
    upsert_entry,
)


def test_file_sha256_retries_transient_deadlock(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")
    calls = {"n": 0}
    real_open = Path.open

    def flaky_open(self, *args, **kwargs):  # noqa: ANN001
        if self == path and calls["n"] == 0:
            calls["n"] += 1
            raise OSError(35, "Resource deadlock avoided")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky_open)
    digest = file_sha256(path, retries=3)
    assert len(digest) == 64
    assert calls["n"] == 1


def test_file_sha256_stable_digest(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")

    first = file_sha256(path)
    second = file_sha256(path)

    assert first == second
    assert len(first) == 64


def test_should_skip_when_digest_matches() -> None:
    manifest = {"version": 1, "files": {"raw/a.txt": {"digest": "abc123"}}}

    assert should_skip("raw/a.txt", "abc123", manifest) is True
    assert should_skip("raw/a.txt", "changed", manifest) is False
    assert should_skip("raw/other.txt", "abc123", manifest) is False


def test_save_and_load_manifest_roundtrip(tmp_path: Path) -> None:
    manifest_file = tmp_path / ".ingest-manifest.json"
    data = {"version": 1, "files": {}}
    upsert_entry(data, "raw/x.txt", "digest1", size=10, mtime_ms=1000)

    save_manifest(manifest_file, data)
    loaded = load_manifest(manifest_file)

    assert loaded["files"]["raw/x.txt"]["digest"] == "digest1"
    assert loaded["files"]["raw/x.txt"]["size"] == 10


def test_remove_manifest_entry_drops_path(tmp_path: Path) -> None:
    from src.core.ingest_manifest import load_manifest, remove_manifest_entry, save_manifest, upsert_entry

    manifest_file = tmp_path / ".ingest-manifest.json"
    data = {"version": 1, "files": {}}
    upsert_entry(data, "raw/x.txt", "digest1", size=10, mtime_ms=1000)
    save_manifest(manifest_file, data)

    remove_manifest_entry(manifest_file, "raw/x.txt")
    loaded = load_manifest(manifest_file)
    assert "raw/x.txt" not in loaded["files"]


def test_update_manifest_entry_persists(tmp_path: Path) -> None:
    from src.core.ingest_manifest import load_manifest, update_manifest_entry

    manifest_file = tmp_path / ".ingest-manifest.json"
    update_manifest_entry(manifest_file, "raw/y.txt", "abc", size=3, mtime_ms=1)
    loaded = load_manifest(manifest_file)
    assert loaded["files"]["raw/y.txt"]["digest"] == "abc"

