from pathlib import Path

import src.web.ingestion_service as ingestion_service
from src.web.ingestion_service import run_ingest, save_uploaded_files


class DummyUpload:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


def test_save_uploaded_files_writes_supported_files(tmp_path):
    upload = DummyUpload("sample.txt", b"hello world")
    out = save_uploaded_files(str(tmp_path), [upload])
    assert out[0].status == "queued"
    saved_path = Path(out[0].message)
    assert saved_path.exists()


def test_save_uploaded_files_rejects_unsupported(tmp_path):
    upload = DummyUpload("sample.exe", b"binary")
    out = save_uploaded_files(str(tmp_path), [upload])
    assert out[0].status == "failed"


def test_save_uploaded_files_enforces_caps(tmp_path):
    uploads = [DummyUpload("a.txt", b"abc"), DummyUpload("b.txt", b"def"), DummyUpload("c.txt", b"ghi")]
    out = save_uploaded_files(
        str(tmp_path),
        uploads,
        existing_bytes=0,
        max_files=2,
        max_file_bytes=10,
        max_session_bytes=10,
    )
    assert out[0].status == "queued"
    assert out[1].status == "queued"
    assert out[2].status == "rejected"
    assert out[2].message == "file_count_cap"


def test_save_uploaded_files_rejects_magic_mismatch(tmp_path):
    upload = DummyUpload("bad.pdf", b"not-a-real-pdf")
    out = save_uploaded_files(str(tmp_path), [upload], max_file_bytes=1024, max_files=2, max_session_bytes=4096)
    assert out[0].status == "rejected"
    assert out[0].message == "type_mismatch"


def test_run_ingest_forwards_overrides(monkeypatch, tmp_path):
    captured = {}
    f = tmp_path / "x.md"
    f.write_text("hello", encoding="utf-8")

    def _fake_ingest(upload_dir, **kwargs):
        captured["upload_dir"] = upload_dir
        captured.update(kwargs)
        return None

    monkeypatch.setattr(ingestion_service, "ingest", _fake_ingest)
    out = run_ingest(
        str(tmp_path),
        bm25_index_path=str(tmp_path / "bm25.json"),
        collection_name="sess_test",
        chroma_path=str(tmp_path / "chroma"),
    )
    assert out["status"] == "ok"
    assert captured["bm25_index_path"].endswith("bm25.json")
    assert captured["collection_name"] == "sess_test"
