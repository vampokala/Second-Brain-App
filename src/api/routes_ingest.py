"""Manual vault ingest routes and SSE progress."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sse_starlette.sse import EventSourceResponse

from src.api.models_ingest import (
    IngestItemResult,
    IngestResponse,
    IngestTextBody,
    IngestUrlBody,
    ReindexResponse,
)
from src.api.sse_bus import SSEBus
from src.core.ingest_pipeline import IngestPipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


def _get_pipeline(request: Request) -> IngestPipeline:
    p = getattr(request.app.state, "ingest_pipeline", None)
    if p is None:
        raise HTTPException(
            status_code=503,
            detail="Vault ingest is not configured (set DATABASE_URL and VECTOR_BACKEND=pgvector).",
        )
    return p


def _get_bus(request: Request) -> SSEBus:
    b = getattr(request.app.state, "ingest_bus", None)
    if b is None:
        raise HTTPException(status_code=503, detail="Ingest event bus unavailable.")
    return b


@router.post("/ingest", response_model=IngestResponse)
async def ingest_files(
    request: Request,
    files: list[UploadFile] = File(default_factory=list),
) -> IngestResponse:
    pipeline = _get_pipeline(request)
    vault = pipeline.settings.vault_path
    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files uploaded. Use POST /ingest/text or POST /ingest/url for other modes.",
        )
    results: list[IngestItemResult] = []
    upload_root = vault / "raw" / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    for uf in files:
        safe_name = Path(uf.filename or "upload.bin").name.replace("..", "_")
        dest = (upload_root / safe_name).resolve()
        try:
            dest.relative_to(vault.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {uf.filename!r}") from None
        data = await uf.read()
        dest.write_bytes(data)
        results.append(await pipeline.ingest_file(dest))
    return IngestResponse(results=results)


@router.post("/ingest/text", response_model=IngestResponse)
async def ingest_paste(request: Request, body: IngestTextBody) -> IngestResponse:
    pipeline = _get_pipeline(request)
    out = await pipeline.ingest_text(body.relpath, body.text)
    return IngestResponse(results=[out])


@router.post("/ingest/url", response_model=IngestResponse)
async def ingest_remote(request: Request, body: IngestUrlBody) -> IngestResponse:
    pipeline = _get_pipeline(request)
    out = await pipeline.ingest_url(str(body.url), body.relpath)
    return IngestResponse(results=[out])


@router.post("/reindex", response_model=ReindexResponse)
async def reindex(request: Request) -> ReindexResponse:
    pipeline = _get_pipeline(request)

    async def _job() -> None:
        try:
            await pipeline.reindex_atomic()
        except Exception as exc:  # noqa: BLE001
            logger.exception("reindex failed: %s", exc)

    asyncio.create_task(_job())
    return ReindexResponse(status="started")


@router.get("/events/ingest")
async def ingest_events(request: Request) -> Any:
    bus = _get_bus(request)

    async def _gen():
        queue = await bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield {"comment": "ping"}
                    continue
                yield {"data": json.dumps(msg)}
        finally:
            await bus.unsubscribe(queue)

    return EventSourceResponse(_gen())


@router.post("/admin/reindex-sync", response_model=ReindexResponse)
async def reindex_sync(request: Request) -> ReindexResponse:
    """Blocking reindex for tests; prefer POST /reindex in production."""
    pipeline = _get_pipeline(request)
    try:
        await pipeline.reindex_atomic()
        return ReindexResponse(status="ok")
    except Exception as exc:  # noqa: BLE001
        logger.exception("reindex failed")
        return ReindexResponse(status="failed", detail=str(exc))

