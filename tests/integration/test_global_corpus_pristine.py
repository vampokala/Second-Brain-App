from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def _sha(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_session_ingest_does_not_touch_global_bm25(monkeypatch, tmp_path):
    monkeypatch.setenv("DOC_PROFILE", "demo")
    monkeypatch.setenv("DOC_DEMO_UPLOADS", "1")
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path / "sessions"))
    import src.api.main as api_main

    api_main = importlib.reload(api_main)
    global_bm25 = Path("data/embeddings/bm25_index.json")
    before = _sha(global_bm25)
    monkeypatch.setattr(api_main, "run_ingest", lambda *args, **kwargs: {"processed_files": 1, "status": "ok"})

    client = TestClient(api_main.app)
    sid = client.post("/sessions").json()["session_id"]
    resp = client.post(
        f"/sessions/{sid}/documents",
        files={"files": ("doc.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 200
    after = _sha(global_bm25)
    assert before == after
