"""Connector configuration + sync routes.

Sync runs as a background task; progress is published on the shared ingest
SSE bus (``GET /events/ingest``), reusing the existing stream the UI listens to.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import delete, select, update
from src.api.models_connectors import (
    ConnectorOut,
    ConnectorSyncResponse,
    ConnectorTestResult,
    ConnectorUpsertBody,
)
from src.api.settings_secrets import strip_connector_secrets
from src.core.connectors.base import ConnectorError
from src.core.connectors.registry import build_connector, resolve_token, sync_connector
from src.core.connectors.scheduler import next_sync_at
from src.db.models import ConnectorSyncState
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])


def _sanitize_config(config: dict) -> dict:
    """Never echo a raw secret if one was accidentally posted into config."""
    redacted = dict(config or {})
    for key in ("token", "api_token", "password", "secret"):
        if key in redacted:
            redacted[key] = "***"
    return redacted


def _to_out(row: ConnectorSyncState) -> ConnectorOut:
    interval = float(row.sync_interval_min or 0)
    return ConnectorOut(
        id=str(row.id),
        connector_type=row.connector_type,
        resource_id=row.resource_id,
        config=_sanitize_config(row.config or {}),
        enabled=row.enabled,
        sync_interval_min=row.sync_interval_min,
        cursor=row.cursor,
        last_sync_at=row.last_sync_at,
        next_sync_at=next_sync_at(row.last_sync_at, interval) if row.enabled else None,
        last_status=row.last_status,
        last_error=row.last_error,
        item_count=row.item_count or 0,
    )


def _require_pipeline(request: Request):
    pipeline = getattr(request.app.state, "ingest_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Connectors require the vault pipeline (set DATABASE_URL and VECTOR_BACKEND=pgvector).",
        )
    return pipeline


async def _load(session, connector_id: str) -> ConnectorSyncState:
    row = await session.get(ConnectorSyncState, connector_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connector not found.")
    return row


@router.get("", response_model=list[ConnectorOut])
async def list_connectors() -> list[ConnectorOut]:
    factory = async_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(ConnectorSyncState))).scalars().all()
        return [_to_out(r) for r in rows]


@router.post("", response_model=ConnectorOut)
async def upsert_connector(body: ConnectorUpsertBody) -> ConnectorOut:
    factory = async_session_factory()
    safe_config = strip_connector_secrets(body.config)
    async with factory() as session:
        existing = (
            await session.execute(
                select(ConnectorSyncState).where(
                    ConnectorSyncState.connector_type == body.connector_type,
                    ConnectorSyncState.resource_id == body.resource_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = ConnectorSyncState(
                connector_type=body.connector_type,
                resource_id=body.resource_id,
                config=safe_config,
                enabled=body.enabled,
                sync_interval_min=body.sync_interval_min,
            )
            session.add(existing)
        else:
            existing.config = safe_config
            existing.enabled = body.enabled
            existing.sync_interval_min = body.sync_interval_min
        await session.commit()
        await session.refresh(existing)
        return _to_out(existing)


@router.delete("/{connector_id}")
async def delete_connector(connector_id: str) -> dict[str, str]:
    factory = async_session_factory()
    async with factory() as session:
        await _load(session, connector_id)
        await session.execute(delete(ConnectorSyncState).where(ConnectorSyncState.id == connector_id))
        await session.commit()
    return {"status": "deleted"}


@router.post("/{connector_id}/test", response_model=ConnectorTestResult)
async def test_connector(connector_id: str) -> ConnectorTestResult:
    factory = async_session_factory()
    async with factory() as session:
        row = await _load(session, connector_id)
        token = resolve_token(row.connector_type, row.config or {})
        try:
            connector = build_connector(row.connector_type, row.resource_id, row.config or {}, token)
            ok, message = await connector.test_connection()
        except ConnectorError as exc:
            return ConnectorTestResult(ok=False, message=str(exc))
        return ConnectorTestResult(ok=ok, message=message)


@router.post("/{connector_id}/sync", response_model=ConnectorSyncResponse)
async def sync_now(connector_id: str, request: Request) -> ConnectorSyncResponse:
    pipeline = _require_pipeline(request)
    bus = getattr(request.app.state, "ingest_bus", None)

    factory = async_session_factory()
    async with factory() as session:
        row = await _load(session, connector_id)
        if not row.enabled:
            return ConnectorSyncResponse(status="failed", detail="Connector is disabled.")
        snapshot = {
            "id": str(row.id),
            "connector_type": row.connector_type,
            "resource_id": row.resource_id,
            "config": dict(row.config or {}),
            "cursor": dict(row.cursor or {}),
        }

    asyncio.create_task(_run_sync(snapshot, pipeline, bus))
    return ConnectorSyncResponse(status="started")


@router.get("/{connector_id}/status", response_model=ConnectorOut)
async def connector_status(connector_id: str) -> ConnectorOut:
    factory = async_session_factory()
    async with factory() as session:
        row = await _load(session, connector_id)
        return _to_out(row)


async def _run_sync(snapshot: dict, pipeline, bus) -> None:
    ctype = snapshot["connector_type"]
    resource = snapshot["resource_id"]
    token = resolve_token(ctype, snapshot["config"])

    def _progress(count: int, item) -> None:
        if bus is not None:
            bus.publish(
                {
                    "file_path": f"{ctype}:{resource}",
                    "event_type": "connector_sync",
                    "status": "processing",
                    "details": {"count": count, "title": item.title[:120]},
                }
            )

    if bus is not None:
        bus.publish(
            {
                "file_path": f"{ctype}:{resource}",
                "event_type": "connector_sync",
                "status": "started",
                "details": {},
            }
        )

    result = await sync_connector(
        connector_type=ctype,
        resource_id=resource,
        config=snapshot["config"],
        cursor=snapshot["cursor"],
        pipeline=pipeline,
        token=token,
        on_progress=_progress,
    )

    factory = async_session_factory()
    async with factory() as session:
        await session.execute(
            update(ConnectorSyncState)
            .where(ConnectorSyncState.id == snapshot["id"])
            .values(
                cursor=result.cursor,
                last_sync_at=datetime.now(UTC),
                last_status=result.status,
                last_error=result.error,
                item_count=result.item_count,
            )
        )
        await session.commit()

    if bus is not None:
        bus.publish(
            {
                "file_path": f"{ctype}:{resource}",
                "event_type": "connector_sync",
                "status": result.status,
                "details": {"count": result.item_count, "error": result.error},
            }
        )
