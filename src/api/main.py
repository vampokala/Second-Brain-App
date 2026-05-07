"""FastAPI application for citation-aware querying."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, Iterator, cast

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from redis import Redis
from redis.exceptions import RedisError
from src.api.models import (
    CitationModel,
    HealthModel,
    LLMConfigModel,
    MetricsModel,
    QueryRequestModel,
    QueryResponseModel,
    RetrievedChunkModel,
    TruthfulnessModel,
)
from src.core.observability import get_observer
from src.core.rag_orchestrator import (
    COLLECTION_NAME,
    QueryRequest,
    QueryResponse,
    RAGOrchestrator,
    StreamingQuerySession,
)
from src.monitoring.metrics import RequestMetrics, get_metrics_collector
from src.utils.config import load_config
from src.web import session_corpus
from src.web.ingestion_service import (
    MAX_FILE_BYTES,
    MAX_FILES_PER_SESSION,
    MAX_SESSION_BYTES,
    run_ingest,
    save_uploaded_files,
)

_cfg = load_config("config.yaml")
_orchestrator = RAGOrchestrator(_cfg)
_metrics_collector = get_metrics_collector()
_rate_window: Dict[str, Deque[float]] = defaultdict(deque)
_redis_client: "Redis | None" = None
# Redis is a base dependency in this project; keep a feature flag for defensive gating.
_REDIS_AVAILABLE = True
_logger = logging.getLogger("api.audit")


def _frontend_origins() -> list[str]:
    raw = os.getenv("DOC_FRONTEND_ORIGINS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    if os.getenv("DOC_PROFILE", "").strip().lower() == "demo":
        return ["*"]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


def _demo_uploads_enabled() -> bool:
    return (
        os.getenv("DOC_PROFILE", "").strip().lower() == "demo"
        and os.getenv("DOC_DEMO_UPLOADS", "0").strip() == "1"
    )


@asynccontextmanager
async def _lifespan(_: FastAPI):
    stop = asyncio.Event()

    async def _janitor_loop() -> None:
        while not stop.is_set():
            try:
                session_corpus.janitor_sweep()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(_janitor_loop())
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        with suppress(Exception):
            await task


app = FastAPI(title="Doc Ingestion Citation API", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_client_key(request: Request, api_key: str | None) -> str:
    if api_key:
        return f"key:{api_key}"
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "ip:unknown"


def _audit_log(event: str, request: Request, **fields: object) -> None:
    payload = {
        "event": event,
        "path": request.url.path,
        "method": request.method,
        "client_ip": request.client.host if request.client else "unknown",
        "ts": int(time.time()),
    }
    payload.update(fields)
    _logger.info(json.dumps(payload, separators=(",", ":")))


def _get_redis() -> "Redis | None":
    global _redis_client
    if not _REDIS_AVAILABLE or not _cfg.api.redis_rate_limit_enabled:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = Redis.from_url(_cfg.api.redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except (RedisError, Exception):
        return None


def _enforce_rate_limit(client_key: str) -> None:
    limit = int(_cfg.api.rate_limit_per_minute)
    redis_client = _get_redis()
    if redis_client is not None:
        now_bucket = int(time.time() // 60)
        redis_key = f"ratelimit:{client_key}:{now_bucket}"
        try:
            current = int(cast(Any, redis_client.incr(redis_key)))
            if current == 1:
                redis_client.expire(redis_key, 120)
            if current > limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return
        except RedisError:
            # fallback to in-memory limiter when Redis has transient issues
            pass
    now = time.time()
    q = _rate_window[client_key]
    while q and (now - q[0]) > 60.0:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    q.append(now)


def _is_local_provider(provider: str | None) -> bool:
    selected = (provider or _cfg.llm.default_provider or "").strip().lower()
    if selected == "claude":
        selected = "anthropic"
    return selected == "ollama"


def _verify_auth(api_key: str | None, provider: str | None = None) -> None:
    if not _cfg.api.auth_enabled:
        return
    if os.getenv("DOC_PROFILE", "").strip().lower() == "demo":
        return
    # Local Ollama queries do not require API auth by default.
    if _is_local_provider(provider):
        return
    valid_keys = _cfg.api.resolved_api_keys()
    if not valid_keys:
        # secure-by-default for production paths
        raise HTTPException(status_code=503, detail="API auth enabled but no keys configured")
    if not api_key or api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _retrieved_chunks_json(final: QueryResponse) -> list[dict[str, Any]]:
    """Serialize retrieval results for SSE / JSON (same shape as non-streaming QueryResponseModel)."""
    out: list[dict[str, Any]] = []
    for item in final.retrieved:
        legacy = item.to_legacy_dict()
        out.append(
            RetrievedChunkModel(
                id=legacy["id"],
                score=float(legacy.get("score") or 0.0),
                source=str(legacy.get("source") or "hybrid"),
                confidence=float(legacy.get("confidence") or 0.0),
                metadata=dict(legacy.get("metadata") or {}),
                preview=(legacy.get("text") or "")[:240],
            ).model_dump(),
        )
    return out


def _calculate_cost(provider: str, model: str, answer_tokens: int = 0, query_tokens: int = 0) -> float:
    """Calculate USD cost of request based on tokens and provider pricing.

    Rough estimates — update as provider pricing changes.
    """
    if provider == "openai":
        return answer_tokens * 0.000002 + query_tokens * 0.000001
    elif provider == "anthropic":
        return answer_tokens * 0.0000024 + query_tokens * 0.0000008
    elif provider == "gemini":
        return answer_tokens * 0.000001 + query_tokens * 0.0000005
    else:
        return 0.0


def _build_request_metrics(request_id: str, out: QueryResponse) -> RequestMetrics:
    """Build metrics with explicit cache-hit step latency semantics."""
    step_latencies = out.step_latencies or {}
    is_cached = bool(out.cached)
    return RequestMetrics(
        request_id=request_id,
        total_latency_ms=out.processing_time_ms,
        retrieval_latency_ms=None if is_cached else step_latencies.get("retrieval", 0.0),
        reranking_latency_ms=None if is_cached else step_latencies.get("reranking", 0.0),
        generation_latency_ms=None if is_cached else step_latencies.get("generation", 0.0),
        citation_latency_ms=None if is_cached else step_latencies.get("citation_verification", 0.0),
        truthfulness_latency_ms=None if is_cached else step_latencies.get("truthfulness_scoring", 0.0),
        cost_usd=_calculate_cost(out.provider, out.model),
        citation_groundedness=out.truthfulness.citation_groundedness if out.truthfulness else 0.0,
        nli_faithfulness=out.truthfulness.nli_faithfulness if out.truthfulness else 0.0,
        uncited_claims=out.truthfulness.uncited_claims if out.truthfulness else 0,
        timestamp=datetime.utcnow().isoformat(),
        cached=is_cached,
    )


@app.get("/health", response_model=HealthModel)
def health() -> HealthModel:
    return HealthModel(status="ok", collection=COLLECTION_NAME)


@app.get("/config/llm", response_model=LLMConfigModel)
def llm_config() -> LLMConfigModel:
    """Allowed providers/models and defaults from server config (for UI dropdowns)."""
    llm = _cfg.llm
    provider_key_configured = {
        provider: llm.provider_has_key(provider)
        for provider in llm.allowed_models_by_provider.keys()
    }
    return LLMConfigModel(
        default_provider=llm.default_provider,
        default_model_by_provider=dict(llm.default_model_by_provider),
        allowed_models_by_provider={k: list(v) for k, v in llm.allowed_models_by_provider.items()},
        provider_key_configured=provider_key_configured,
        demo_mode=os.getenv("DOC_PROFILE", "").strip().lower() == "demo",
    )


@app.get("/metrics", response_model=MetricsModel)
def metrics(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> MetricsModel:
    # no request object here; audit logs are captured in protected endpoints with request context
    _verify_auth(x_api_key, provider="metrics")
    return MetricsModel(
        cache_ttl_seconds=int(_cfg.generation.cache_ttl),
        available_providers=sorted(_cfg.llm.allowed_models_by_provider.keys()),
    )


def _session_summary(session: session_corpus.SessionCorpus) -> dict[str, Any]:
    files = []
    for p in sorted(session.upload_dir.glob("*")):
        if p.is_file():
            files.append({"name": p.name, "size_bytes": p.stat().st_size})
    touched_path = session.upload_dir.parent / ".touched"
    mtime = touched_path.stat().st_mtime if touched_path.exists() else time.time()
    ttl = session_corpus._session_ttl_seconds()
    expires_at = int(mtime + ttl)
    return {
        "session_id": session.session_id,
        "files": files,
        "total_bytes": session_corpus.total_bytes(session),
        "max_session_bytes": MAX_SESSION_BYTES,
        "max_files": MAX_FILES_PER_SESSION,
        "expires_at": expires_at,
    }


def _raise_sessions_demo_disabled() -> None:
    """Avoid POST /sessions falling through to StaticFiles (which responds with 405)."""
    raise HTTPException(
        status_code=404,
        detail=(
            "Demo sessions are disabled on this server. "
            "Set DOC_PROFILE=demo and DOC_DEMO_UPLOADS=1 on the API process."
        ),
    )


if _demo_uploads_enabled():
    @app.post("/sessions")
    def create_session(response: Response) -> dict[str, Any]:
        sid = session_corpus.new_session_id()
        session = session_corpus.get_or_create(sid)
        session_corpus.touch(sid)
        expires_at = int(time.time() + session_corpus._session_ttl_seconds())
        response.headers["X-Demo-Session-Id"] = sid
        return {"session_id": session.session_id, "expires_at": expires_at}


    @app.get("/sessions/{sid}")
    def get_session(sid: str, response: Response) -> dict[str, Any]:
        session = session_corpus.get_or_create(sid)
        session_corpus.touch(sid)
        response.headers["X-Demo-Session-Id"] = sid
        return _session_summary(session)


    @app.post("/sessions/{sid}/documents")
    def upload_session_documents(
        sid: str,
        request: Request,
        files: list[UploadFile] = File(default_factory=list),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _verify_auth(x_api_key, provider="uploads")
        client_key = _resolve_client_key(request, x_api_key)
        _enforce_rate_limit(client_key)

        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        session = session_corpus.get_or_create(sid)
        existing = session_corpus.total_bytes(session)

        class _UploadBlob:
            def __init__(self, name: str, payload: bytes) -> None:
                self.name = name
                self._payload = payload

            def getvalue(self) -> bytes:
                return self._payload

        staged_objs = []
        for f in files:
            payload = f.file.read()
            staged_objs.append(_UploadBlob(f.filename or "unknown", payload))
        staged = save_uploaded_files(
            str(session.upload_dir),
            staged_objs,
            existing_bytes=existing,
            max_files=MAX_FILES_PER_SESSION,
            max_file_bytes=MAX_FILE_BYTES,
            max_session_bytes=MAX_SESSION_BYTES,
        )
        run_ingest(
            str(session.upload_dir),
            bm25_index_path=str(session.bm25_index_path),
            collection_name=session.collection_name,
            chroma_path=str(session.chroma_path),
        )
        session_corpus.touch(sid)
        return {"session_id": sid, "results": [r.__dict__ for r in staged], **_session_summary(session)}


    @app.delete("/sessions/{sid}")
    def delete_session(sid: str, response: Response) -> dict[str, Any]:
        session_corpus.delete_session(sid)
        new_sid = session_corpus.new_session_id()
        session_corpus.get_or_create(new_sid)
        session_corpus.touch(new_sid)
        response.headers["X-Demo-Session-Id"] = new_sid
        return {"deleted_session_id": sid, "session_id": new_sid}


else:
    # Register these so session paths are not handled by the SPA/static mount below.
    @app.post("/sessions")
    def _sessions_off_create():
        _raise_sessions_demo_disabled()

    @app.get("/sessions/{sid}")
    def _sessions_off_get(_sid: str):
        _raise_sessions_demo_disabled()

    @app.post("/sessions/{sid}/documents")
    def _sessions_off_documents(_sid: str):
        _raise_sessions_demo_disabled()

    @app.delete("/sessions/{sid}")
    def _sessions_off_delete(_sid: str):
        _raise_sessions_demo_disabled()


@app.post("/query", response_model=QueryResponseModel)
def query(
    req: QueryRequestModel,
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> QueryResponseModel:
    request_id = str(uuid.uuid4())
    try:
        _verify_auth(x_api_key, req.provider)
    except HTTPException as exc:
        _audit_log("auth_failed", request, status=exc.status_code, reason=exc.detail)
        raise
    client_key = _resolve_client_key(request, x_api_key)
    _enforce_rate_limit(client_key)
    _audit_log("auth_success", request, client_key=client_key)
    session_kwargs: dict[str, Any] = {}
    knowledge_scope = (req.knowledge_scope or "global").strip().lower()
    if req.session_id:
        if not _demo_uploads_enabled():
            raise HTTPException(status_code=400, detail="Session querying is only enabled in demo uploads mode")
        session = session_corpus.get_or_create(req.session_id)
        if not session.upload_dir.exists():
            raise HTTPException(status_code=404, detail="Session not found")
        session_corpus.touch(req.session_id)
        has_uploads = any(p.is_file() for p in session.upload_dir.glob("*"))
        if knowledge_scope == "session" and not has_uploads:
            raise HTTPException(status_code=409, detail="No uploaded documents in this session yet. Upload first.")
        if knowledge_scope == "both" and not has_uploads:
            knowledge_scope = "global"
        session_kwargs = {
            "session_bm25_index_path": str(session.bm25_index_path),
            "session_collection_name": session.collection_name,
            "session_chroma_path": str(session.chroma_path),
            "knowledge_scope": knowledge_scope,
        }
    try:
        out = _orchestrator.run(
            QueryRequest(
                query_text=req.query,
                top_k=req.top_k,
                use_llm=req.use_llm,
                use_rerank=req.use_rerank,
                stream=req.stream,
                provider=req.provider,
                model=req.model,
                provider_api_key=req.provider_api_key,
                reranker_model=req.reranker_model,
                include_citations=req.include_citations,
                **session_kwargs,
            )
        )
    except Exception as exc:  # keep API error shape stable
        _audit_log("query_failed", request, client_key=client_key, error=str(exc))
        _logger.exception("query_failed provider=%s model=%s client_key=%s", req.provider, req.model, client_key)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_log(
        "query_success",
        request,
        client_key=client_key,
        provider=out.provider,
        model=out.model,
        latency_ms=round(out.processing_time_ms, 2),
        cached=out.cached,
    )

    retrieved = []
    for item in out.retrieved:
        legacy = item.to_legacy_dict()
        retrieved.append(
            RetrievedChunkModel(
                id=legacy["id"],
                score=float(legacy.get("score") or 0.0),
                source=str(legacy.get("source") or "hybrid"),
                confidence=float(legacy.get("confidence") or 0.0),
                metadata=dict(legacy.get("metadata") or {}),
                preview=(legacy.get("text") or "")[:240],
            )
        )

    truthfulness_model = None
    if out.truthfulness is not None:
        t = out.truthfulness
        truthfulness_model = TruthfulnessModel(
            nli_faithfulness=t.nli_faithfulness,
            citation_groundedness=t.citation_groundedness,
            uncited_claims=t.uncited_claims,
            score=t.score,
        )

    citation_models = [CitationModel.model_validate(c) for c in out.citations]

    _metrics_collector.record_request(_build_request_metrics(request_id, out))

    observer = get_observer()
    background_tasks.add_task(observer.flush_async)

    return QueryResponseModel(
        query=out.query,
        provider=out.provider,
        model=out.model,
        answer=out.answer,
        processing_time_ms=out.processing_time_ms,
        cached=out.cached,
        validation_issues=out.validation_issues,
        citations=citation_models,
        retrieved=retrieved,
        truthfulness=truthfulness_model,
    )


@app.post("/query/stream")
def query_stream(
    req: QueryRequestModel,
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> StreamingResponse:
    try:
        _verify_auth(x_api_key, req.provider)
    except HTTPException as exc:
        _audit_log("auth_failed", request, status=exc.status_code, reason=exc.detail)
        raise
    client_key = _resolve_client_key(request, x_api_key)
    _enforce_rate_limit(client_key)
    _audit_log("stream_auth_success", request, client_key=client_key)
    session_kwargs: dict[str, Any] = {}
    knowledge_scope = (req.knowledge_scope or "global").strip().lower()
    if req.session_id:
        if not _demo_uploads_enabled():
            raise HTTPException(status_code=400, detail="Session querying is only enabled in demo uploads mode")
        session = session_corpus.get_or_create(req.session_id)
        if not session.upload_dir.exists():
            raise HTTPException(status_code=404, detail="Session not found")
        session_corpus.touch(req.session_id)
        has_uploads = any(p.is_file() for p in session.upload_dir.glob("*"))
        if knowledge_scope == "session" and not has_uploads:
            raise HTTPException(status_code=409, detail="No uploaded documents in this session yet. Upload first.")
        if knowledge_scope == "both" and not has_uploads:
            knowledge_scope = "global"
        session_kwargs = {
            "session_bm25_index_path": str(session.bm25_index_path),
            "session_collection_name": session.collection_name,
            "session_chroma_path": str(session.chroma_path),
            "knowledge_scope": knowledge_scope,
        }

    def _gen() -> Iterator[str]:
        request_id = str(uuid.uuid4())
        try:
            stream_req = QueryRequest(
                query_text=req.query,
                top_k=req.top_k,
                use_llm=req.use_llm,
                use_rerank=req.use_rerank,
                stream=True,
                provider=req.provider,
                model=req.model,
                provider_api_key=req.provider_api_key,
                reranker_model=req.reranker_model,
                include_citations=req.include_citations,
                **session_kwargs,
            )
            with StreamingQuerySession(_orchestrator, stream_req) as session:
                for piece in session.iter_tokens():
                    yield f"data: {json.dumps({'type': 'token', 'text': piece})}\n\n"
                final = session.finalize()
            _audit_log(
                "stream_success",
                request,
                client_key=client_key,
                provider=final.provider,
                model=final.model,
            )
            final_payload: dict[str, Any] = {
                "type": "final",
                "citations": final.citations,
                "retrieved": _retrieved_chunks_json(final),
                "truthfulness": final.truthfulness.to_dict() if final.truthfulness is not None else None,
                "provider": final.provider,
                "model": final.model,
                "processing_time_ms": final.processing_time_ms,
                "cached": final.cached,
                "validation_issues": final.validation_issues,
            }
            _metrics_collector.record_request(_build_request_metrics(request_id, final))
            yield f"data: {json.dumps(final_payload)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            _audit_log("stream_failed", request, client_key=client_key, error=str(exc))
            _logger.exception("stream_failed provider=%s model=%s client_key=%s", req.provider, req.model, client_key)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/observability/dashboard")
def observability_dashboard(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Return real-time observability metrics for dashboarding."""
    _verify_auth(x_api_key, provider="metrics")
    return _metrics_collector.get_dashboard_metrics()


_ui_static = Path(__file__).resolve().parent.parent.parent / "static"
if _ui_static.is_dir() and (_ui_static / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_ui_static), html=True), name="ui")
