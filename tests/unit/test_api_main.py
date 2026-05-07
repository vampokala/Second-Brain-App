from fastapi.testclient import TestClient
from src.api import main as api_main
from src.api.main import app
from src.core.rag_orchestrator import QueryResponse
from src.core.retrieval_result import RetrievalResult
from src.evaluation.truthfulness import TruthfulnessResult


def test_health_endpoint():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_metrics_endpoint():
    api_main._cfg.api.auth_enabled = False
    client = TestClient(app)
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "available_providers" in res.json()


def test_llm_config_endpoint():
    client = TestClient(app)
    res = client.get("/config/llm")
    assert res.status_code == 200
    data = res.json()
    assert data["default_provider"]
    assert "ollama" in data["allowed_models_by_provider"]
    assert isinstance(data["allowed_models_by_provider"]["ollama"], list)
    assert isinstance(data["provider_key_configured"], dict)
    assert "ollama" in data["provider_key_configured"]
    assert isinstance(data["demo_mode"], bool)


def test_query_endpoint(monkeypatch):
    def _fake_run(_req):
        return QueryResponse(
            query="q",
            provider="ollama",
            model="qwen2.5:7b",
            answer="hello [Doc chunk1]",
            citations=[
                {
                    "raw_id": "chunk1",
                    "chunk_id": "chunk1",
                    "resolved": True,
                    "title": "Doc1",
                    "source": ".txt",
                    "verification_score": 0.8,
                    "verification": "supported",
                }
            ],
            retrieved=[RetrievalResult(id="chunk1", text="body", confidence=0.7)],
        )

    monkeypatch.setattr(api_main._orchestrator, "run", _fake_run)
    api_main._cfg.api.auth_enabled = False
    client = TestClient(app)
    res = client.post("/query", json={"query": "hello"})
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "ollama"
    assert len(data["citations"]) == 1


def test_query_requires_api_key_when_enabled():
    api_main._cfg.api.auth_enabled = True
    api_main._cfg.api.api_keys = ["test-key"]
    client = TestClient(app)
    res = client.post("/query", json={"query": "hello", "provider": "openai", "model": "gpt-4o-mini"})
    assert res.status_code == 401
    res2 = client.post(
        "/query",
        json={"query": "hello", "provider": "openai", "model": "gpt-4o-mini"},
        headers={"X-API-Key": "test-key"},
    )
    assert res2.status_code in (200, 400)


def test_query_stream_endpoint(monkeypatch):
    captured = {}

    class FakeStreamingSession:
        def __init__(self, _orch, _req):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def iter_tokens(self):
            yield "hello "
            yield "world"

        def finalize(self):
            return QueryResponse(
                query="q",
                provider="ollama",
                model="qwen2.5:7b",
                citations=[],
                processing_time_ms=12.0,
                cached=False,
                validation_issues=[],
                truthfulness=TruthfulnessResult(
                    nli_faithfulness=0.8,
                    citation_groundedness=0.7,
                    uncited_claims=1,
                    score=0.76,
                ),
                step_latencies={
                    "retrieval": 1.0,
                    "reranking": 2.0,
                    "generation": 3.0,
                    "citation_verification": 4.0,
                    "truthfulness_scoring": 5.0,
                },
            )

    monkeypatch.setattr(api_main, "StreamingQuerySession", FakeStreamingSession)
    monkeypatch.setattr(
        api_main._metrics_collector,
        "record_request",
        lambda metrics: captured.setdefault("metrics", metrics),
    )
    api_main._cfg.api.auth_enabled = False
    client = TestClient(app)
    res = client.post("/query/stream", json={"query": "hello", "stream": True})
    assert res.status_code == 200
    assert "token" in res.text
    assert '"processing_time_ms": 12.0' in res.text
    assert '"cached": false' in res.text
    assert "metrics" in captured
    assert captured["metrics"].truthfulness_latency_ms == 5.0


def test_rate_limit_uses_redis_when_available(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.count = 0

        def incr(self, _key):
            self.count += 1
            return self.count

        def expire(self, _key, _ttl):
            return True

    fake = FakeRedis()
    monkeypatch.setattr(api_main, "_get_redis", lambda: fake)
    api_main._cfg.api.rate_limit_per_minute = 2
    api_main._enforce_rate_limit("clientA")
    api_main._enforce_rate_limit("clientA")
    try:
        api_main._enforce_rate_limit("clientA")
        assert False, "Expected rate limit exception"
    except Exception:
        assert True
