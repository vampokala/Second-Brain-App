from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DOC_PROFILE", "demo")
    monkeypatch.setenv("DOC_DEMO_UPLOADS", "1")
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path))
    import src.api.main as api_main

    return importlib.reload(api_main)


def test_session_scope_requires_uploads(monkeypatch, tmp_path):
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

    monkeypatch.setattr(api_main._orchestrator, "run", lambda req: _FakeOut())
    client = TestClient(api_main.app)
    sid = client.post("/sessions").json()["session_id"]
    resp = client.post("/query", json={"query": "x", "session_id": sid, "knowledge_scope": "session"})
    assert resp.status_code == 409


def test_both_scope_degrades_to_global_without_uploads(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    captured = {}

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

    def _fake_run(req):
        captured["scope"] = req.knowledge_scope
        return _FakeOut()

    monkeypatch.setattr(api_main._orchestrator, "run", _fake_run)
    client = TestClient(api_main.app)
    sid = client.post("/sessions").json()["session_id"]
    resp = client.post("/query", json={"query": "x", "session_id": sid, "knowledge_scope": "both"})
    assert resp.status_code == 200
    assert captured["scope"] == "global"
