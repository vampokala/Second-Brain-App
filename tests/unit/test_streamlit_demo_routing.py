from __future__ import annotations

from types import SimpleNamespace

import src.web.streamlit_app as streamlit_app


class _DummyRetrieval:
    def to_legacy_dict(self):
        return {
            "id": "chunk-1",
            "score": 0.91,
            "source": "hybrid",
            "confidence": 0.88,
            "metadata": {"title": "doc.md"},
            "text": "Demo preview text",
        }


def test_run_query_in_demo_mode_uses_inprocess_orchestrator(monkeypatch):
    captured = {}

    class _FakeOrchestrator:
        def run(self, req):
            captured["provider"] = req.provider
            captured["model"] = req.model
            captured["provider_api_key"] = req.provider_api_key
            return SimpleNamespace(
                query=req.query_text,
                provider=req.provider or "openai",
                model=req.model or "gpt-4o-mini",
                answer="demo answer",
                processing_time_ms=12.3,
                cached=False,
                validation_issues=[],
                citations=[{"chunk_id": "chunk-1", "resolved": True, "verification_score": 0.9}],
                retrieved=[_DummyRetrieval()],
                truthfulness=SimpleNamespace(
                    nli_faithfulness=0.8,
                    citation_groundedness=0.9,
                    uncited_claims=0,
                    score=0.85,
                ),
            )

    monkeypatch.setattr(streamlit_app, "_get_demo_orchestrator", lambda: _FakeOrchestrator())

    out = streamlit_app._run_query_in_demo_mode(
        {
            "query": "what is rag?",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "provider_api_key": "provider-key",
            "top_k": 5,
            "include_citations": True,
        }
    )

    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-4o-mini"
    assert captured["provider_api_key"] == "provider-key"
    assert out["answer"] == "demo answer"
    assert out["provider"] == "openai"
    assert out["retrieved"][0]["id"] == "chunk-1"
    assert out["truthfulness"]["score"] == 0.85


def test_run_query_via_api_uses_http_post(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"answer": "ok"}

    def _fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(streamlit_app.requests, "post", _fake_post)

    payload = {"query": "hello"}
    headers = {"Content-Type": "application/json", "X-API-Key": "k"}
    out = streamlit_app._run_query_via_api(payload, headers)

    assert out["answer"] == "ok"
    assert captured["url"] == f"{streamlit_app.API_BASE_URL}/query"
    assert captured["json"] == payload
    assert captured["headers"] == headers
    assert captured["timeout"] == 120


def test_demo_upload_mode_routes_query_via_api_with_session(monkeypatch):
    captured = {}

    monkeypatch.setattr(streamlit_app, "_DEMO_MODE", True)
    monkeypatch.setattr(streamlit_app, "_DEMO_UPLOADS_ENABLED", True)

    def _fake_get_or_create(headers):
        captured["headers"] = dict(headers)
        return "sess_123"

    def _fake_run_query_via_api(payload, headers):
        captured["payload"] = dict(payload)
        captured["headers_post"] = dict(headers)
        return {"answer": "ok"}

    monkeypatch.setattr(streamlit_app, "_get_or_create_demo_session", _fake_get_or_create)
    monkeypatch.setattr(streamlit_app, "_run_query_via_api", _fake_run_query_via_api)

    payload = {"query": "hello"}
    headers = {"Content-Type": "application/json"}
    sid = streamlit_app._get_or_create_demo_session(headers)
    payload["session_id"] = sid
    out = streamlit_app._run_query_via_api(payload, headers)
    assert out["answer"] == "ok"
    assert captured["payload"]["session_id"] == "sess_123"
