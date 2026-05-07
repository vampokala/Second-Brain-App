from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DOC_PROFILE", "demo")
    monkeypatch.setenv("DOC_DEMO_UPLOADS", "1")
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path))
    import src.api.main as api_main

    api_main = importlib.reload(api_main)
    return api_main


def test_session_lifecycle_and_query(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)

    class _FakeOut:
        query = "q"
        provider = "openai"
        model = "m"
        answer = "a"
        processing_time_ms = 1.0
        cached = False
        validation_issues = []
        citations = []
        retrieved = []
        truthfulness = None
        step_latencies = {}

    captured = {}

    def _fake_run(req):
        captured["scope"] = req.knowledge_scope
        captured["session_collection_name"] = req.session_collection_name
        return _FakeOut()

    monkeypatch.setattr(api_main._orchestrator, "run", _fake_run)
    monkeypatch.setattr(api_main, "run_ingest", lambda *args, **kwargs: {"processed_files": 1, "status": "ok"})

    client = TestClient(api_main.app)
    created = client.post("/sessions")
    assert created.status_code == 200
    sid = created.json()["session_id"]

    up = client.post(
        f"/sessions/{sid}/documents",
        files={"files": ("doc.txt", b"hello world", "text/plain")},
    )
    assert up.status_code == 200
    assert up.json()["session_id"] == sid

    details = client.get(f"/sessions/{sid}")
    assert details.status_code == 200
    assert details.json()["session_id"] == sid

    q = client.post("/query", json={"query": "hi", "session_id": sid, "knowledge_scope": "both"})
    assert q.status_code == 200
    assert captured["scope"] in {"both", "global"}

    deleted = client.delete(f"/sessions/{sid}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_session_id"] == sid
