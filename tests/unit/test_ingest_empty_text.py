"""Empty extractable text must fail ingest and must not update the manifest."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.core.ingest_manifest import load_manifest
from src.core.ingest_pipeline import IngestPipeline


def test_ingest_file_sync_fails_when_no_chunks(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path
    raw = vault / "raw" / "uploads" / "scanned.pdf"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"%PDF-1.4 empty")

    settings = MagicMock()
    settings.vault_path = vault
    settings.database_url_sync = "postgresql://unused"
    settings.embed_model = "nomic-embed-text"

    pipeline = IngestPipeline.__new__(IngestPipeline)
    pipeline.settings = settings
    pipeline._vault = vault.resolve()
    pipeline._processor = MagicMock()
    pipeline._processor.process_document.return_value = {
        "metadata": {"title": "scanned.pdf", "file_type": ".pdf"},
        "chunks": [],
    }
    pipeline._vision_enabled = MagicMock(return_value=False)
    monkeypatch.setattr("src.core.ingest_pipeline.get_ingest_run_state", lambda: MagicMock(should_cancel=lambda: False))

    out = pipeline._ingest_file_sync(raw.resolve(), "raw/uploads/scanned.pdf")

    assert out.status == "failed"
    assert out.chunk_count == 0
    assert "no extractable text" in (out.error or "")
    manifest = load_manifest(vault / ".ingest-manifest.json")
    assert "raw/uploads/scanned.pdf" not in manifest.get("files", {})
