"""Manual vault ingest routes and SSE progress."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.api.chat_prefs import load_settings_map, vision_enabled_from_rows
from src.api.models_ingest import (
    IngestItemResult,
    IngestPathsBody,
    IngestResponse,
    IngestScanPreviewResponse,
    IngestScanStartResponse,
    IngestTextBody,
    IngestUrlBody,
    ReindexResponse,
)
from src.api.sse_bus import SSEBus
from src.core.ingest_pipeline import IngestPipeline
from src.core.ingest_paths import IngestPathError, resolve_vault_ingest_path
from src.core.ingest_run_state import get_ingest_run_state
from src.core.supported_formats import SUPPORTED_EXTENSIONS, VISION_EXTENSIONS, is_supported
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class IngestCapabilities(BaseModel):
    supported_extensions: list[str]
    vision_enabled: bool
    max_upload_bytes: int | None = None
    default_provider: str | None = None
    default_model: str | None = None


class CursorAssistPrepareBody(BaseModel):
    text: str = Field(..., min_length=1)
    title: str | None = None
    relpath: str | None = None


class CursorAssistPrepareResponse(BaseModel):
    raw_rel: str
    prompt_pack: str


class CursorAssistCommitBody(BaseModel):
    raw_rel: str
    payload: dict[str, Any]
    reingest: bool = True


class CursorAssistPreviewResponse(BaseModel):
    title: str
    slug: str
    tags: list[str]
    wiki_rel: str
    summary: str


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


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    return slug or "cursor-assist"


@router.get("/ingest/capabilities", response_model=IngestCapabilities)
async def ingest_capabilities(request: Request) -> IngestCapabilities:
    vision = False
    if os.getenv("DATABASE_URL", "").strip():
        factory = async_session_factory()
        async with factory() as session:
            rows = await load_settings_map(session)
            vision = vision_enabled_from_rows(rows)
    else:
        vision = os.getenv("VISION_INGEST_ENABLED", "").strip().lower() in {"1", "true", "yes"}

    exts = sorted(SUPPORTED_EXTENSIONS - (set() if vision else VISION_EXTENSIONS))
    cfg = getattr(request.app.state, "config", None)
    provider = cfg.llm.default_provider if cfg is not None else None
    model = cfg.llm.resolve_model(provider, None) if cfg is not None and provider else None
    return IngestCapabilities(
        supported_extensions=exts,
        vision_enabled=vision,
        max_upload_bytes=50 * 1024 * 1024,
        default_provider=provider,
        default_model=model,
    )


@router.post("/ingest/cancel")
async def ingest_cancel() -> dict[str, str]:
    get_ingest_run_state().request_cancel()
    return {"status": "cancel_requested"}


@router.post("/ingest/scan", response_model=IngestScanPreviewResponse)
async def ingest_scan(request: Request) -> IngestScanPreviewResponse:
    """Dry-run vault scan: return new/changed files without ingesting."""
    pipeline = _get_pipeline(request)
    await _refresh_pipeline_vision(request, pipeline)
    return await asyncio.to_thread(pipeline.scan_preview)


@router.post("/ingest/paths", response_model=IngestScanStartResponse)
async def ingest_paths(request: Request, body: IngestPathsBody) -> IngestScanStartResponse:
    """Start background ingest for selected vault-relative paths."""
    pipeline = _get_pipeline(request)
    await _refresh_pipeline_vision(request, pipeline)
    vault = pipeline.settings.vault_path.resolve()
    vision = pipeline.is_vision_enabled()
    try:
        for raw in body.paths:
            resolve_vault_ingest_path(vault, raw, vision_enabled=vision)
    except IngestPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    selected = len({p.replace("\\", "/").strip().lstrip("/") for p in body.paths})
    paths = list(body.paths)

    async def _job() -> None:
        try:
            await pipeline.ingest_selected_paths(paths)
        except IngestPathError as exc:
            logger.warning("ingest_paths_invalid error=%s", exc)
            pipeline.emit_scan_failed(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("ingest_paths_failed error=%s", exc)
            pipeline.emit_scan_failed(str(exc))

    asyncio.create_task(_job())
    return IngestScanStartResponse(
        status="started",
        detail=f"Ingest started for {selected} file(s); watch progress events.",
        selected=selected,
    )


async def _refresh_pipeline_vision(request: Request, pipeline: IngestPipeline) -> None:
    if not os.getenv("DATABASE_URL", "").strip():
        return
    factory = async_session_factory()
    async with factory() as session:
        rows = await load_settings_map(session)
        pipeline.set_vision_enabled(vision_enabled_from_rows(rows))


@router.post("/ingest", response_model=IngestResponse)
async def ingest_files(
    request: Request,
    files: list[UploadFile] = File(default_factory=list),
) -> IngestResponse:
    pipeline = _get_pipeline(request)
    await _refresh_pipeline_vision(request, pipeline)
    vault = pipeline.settings.vault_path
    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files uploaded. Use POST /ingest/text or POST /ingest/url for other modes.",
        )
    max_bytes = 50 * 1024 * 1024
    vision = pipeline.is_vision_enabled()
    run_state = get_ingest_run_state()
    run_state.clear()
    results: list[IngestItemResult] = []
    upload_root = vault / "raw" / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    for uf in files:
        if run_state.should_cancel():
            results.append(
                IngestItemResult(
                    path=uf.filename or "upload",
                    status="cancelled",
                    chunk_count=0,
                    error="cancelled",
                )
            )
            break
        safe_name = Path(uf.filename or "upload.bin").name.replace("..", "_")
        suffix = Path(safe_name).suffix
        if not is_supported(suffix, vision_enabled=vision):
            results.append(
                IngestItemResult(
                    path=safe_name,
                    status="failed",
                    chunk_count=0,
                    error=f"unsupported extension: {suffix or '(none)'}",
                )
            )
            continue
        dest = (upload_root / safe_name).resolve()
        try:
            dest.relative_to(vault.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {uf.filename!r}") from None
        data = await uf.read()
        if len(data) > max_bytes:
            results.append(
                IngestItemResult(
                    path=safe_name,
                    status="failed",
                    chunk_count=0,
                    error=f"file exceeds max_upload_bytes ({max_bytes})",
                )
            )
            continue
        dest.write_bytes(data)
        results.append(await pipeline.ingest_file(dest))
    return IngestResponse(results=results)


@router.post("/ingest/text", response_model=IngestResponse)
async def ingest_paste(request: Request, body: IngestTextBody) -> IngestResponse:
    pipeline = _get_pipeline(request)
    get_ingest_run_state().clear()
    out = await pipeline.ingest_text(body.relpath, body.text)
    return IngestResponse(results=[out])


@router.post("/ingest/url", response_model=IngestResponse)
async def ingest_remote(request: Request, body: IngestUrlBody) -> IngestResponse:
    from src.core.url_extractor import UrlExtractError  # noqa: PLC0415

    pipeline = _get_pipeline(request)
    get_ingest_run_state().clear()
    try:
        out = await pipeline.ingest_url(str(body.url), body.relpath)
    except UrlExtractError as exc:
        status = 502 if exc.upstream else 400
        logger.warning(
            "ingest_url_failed url=%s upstream=%s error=%s",
            body.url,
            exc.upstream,
            exc,
        )
        raise HTTPException(status_code=status, detail=str(exc)) from exc
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


@router.post("/ingest/cursor-assist/prepare", response_model=CursorAssistPrepareResponse)
async def cursor_assist_prepare(request: Request, body: CursorAssistPrepareBody) -> CursorAssistPrepareResponse:
    """Browser Cursor-assist: save paste + return a prompt pack (no workspaceStorage)."""
    pipeline = _get_pipeline(request)
    vault = pipeline.settings.vault_path
    title = (body.title or "Cursor assist paste").strip()
    slug = _slugify(title)
    rel = (body.relpath or f"raw/pastes/cursor-{slug}.md").replace("\\", "/").lstrip("/")
    dest = (vault / rel).resolve()
    try:
        dest.relative_to(vault.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid relpath") from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body.text, encoding="utf-8")
    pack = (
        "# Cursor-assisted ingest pack\n\n"
        f"Source file: `{rel}`\n\n"
        "Paste the following into Cursor Chat and ask it to return JSON with keys: "
        "`slug`, `title`, `one_line_summary`, `body_markdown` (or `body_markdown_b64`), `tags`.\n\n"
        "---\n\n"
        f"{body.text[:12000]}\n"
    )
    return CursorAssistPrepareResponse(raw_rel=rel, prompt_pack=pack)


@router.post("/ingest/cursor-assist/preview", response_model=CursorAssistPreviewResponse)
async def cursor_assist_preview(body: CursorAssistCommitBody) -> CursorAssistPreviewResponse:
    payload = body.payload
    title = str(payload.get("title") or "Cursor analysis").strip()
    slug = str(payload.get("slug") or _slugify(title)).strip() or _slugify(title)
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    summary = str(payload.get("one_line_summary") or "")[:240]
    return CursorAssistPreviewResponse(
        title=title,
        slug=slug,
        tags=[str(t) for t in tags],
        wiki_rel=f"wiki/sources/cursor/{slug}.md",
        summary=summary,
    )


@router.post("/ingest/cursor-assist/commit", response_model=IngestResponse)
async def cursor_assist_commit(request: Request, body: CursorAssistCommitBody) -> IngestResponse:
    pipeline = _get_pipeline(request)
    vault = pipeline.settings.vault_path
    payload = body.payload
    title = str(payload.get("title") or "Cursor analysis").strip()
    slug = str(payload.get("slug") or _slugify(title)).strip() or _slugify(title)
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else ["cursor-assisted"]
    md = payload.get("body_markdown")
    if not md and payload.get("body_markdown_b64"):
        try:
            md = base64.b64decode(str(payload["body_markdown_b64"])).decode("utf-8", errors="replace")
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid body_markdown_b64") from exc
    if not isinstance(md, str) or not md.strip():
        raise HTTPException(status_code=400, detail="payload requires body_markdown or body_markdown_b64")

    wiki_rel = f"wiki/sources/cursor/{slug}.md"
    path = (vault / wiki_rel).resolve()
    try:
        path.relative_to(vault.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid slug path") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    meta_lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(92)+chr(34))}"',
        'type: "source"',
        f"created: {today}",
        f"updated: {today}",
        f"sources: {json.dumps([body.raw_rel])}",
        f"tags: {json.dumps([str(t) for t in tags])}",
        'ingest_mode: "cursor-assisted"',
        "---",
        "",
        md.strip(),
        "",
    ]
    path.write_text("\n".join(meta_lines), encoding="utf-8")
    if not body.reingest:
        return IngestResponse(results=[IngestItemResult(path=wiki_rel, status="ingested", chunk_count=0)])
    result = await pipeline.ingest_file(path)
    return IngestResponse(results=[result])
