"""Per-connector ingestion scheduler.

A lightweight tick loop (no extra dependency, mirrors the app's janitor loop)
that triggers ``sync_connector`` for connectors whose configured interval has
elapsed. Pure helpers (:func:`is_due`, :func:`next_sync_at`) are unit-tested in
isolation; the loop itself is wired into the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


def effective_interval(sync_interval_min: int | None, global_default_min: float) -> float:
    """A connector's own interval wins; otherwise fall back to the global default."""
    if sync_interval_min and sync_interval_min > 0:
        return float(sync_interval_min)
    if global_default_min and global_default_min > 0:
        return float(global_default_min)
    return 0.0


def is_due(
    last_sync_at: datetime | None,
    interval_min: float,
    now: datetime | None = None,
) -> bool:
    """True when an enabled connector should sync now.

    ``interval_min <= 0`` means manual-only (never auto-due). A connector that
    has never synced (``last_sync_at is None``) is due as soon as it has an
    interval.
    """
    if interval_min <= 0:
        return False
    if last_sync_at is None:
        return True
    now = now or datetime.now(UTC)
    if last_sync_at.tzinfo is None:
        last_sync_at = last_sync_at.replace(tzinfo=UTC)
    return (now - last_sync_at) >= timedelta(minutes=interval_min)


def next_sync_at(
    last_sync_at: datetime | None,
    interval_min: float,
    now: datetime | None = None,
) -> datetime | None:
    """When the next auto-sync is expected, or ``None`` for manual-only."""
    if interval_min <= 0:
        return None
    if last_sync_at is None:
        return now or datetime.now(UTC)
    if last_sync_at.tzinfo is None:
        last_sync_at = last_sync_at.replace(tzinfo=UTC)
    return last_sync_at + timedelta(minutes=interval_min)


class ConnectorScheduler:
    """Owns the in-flight set so the same connector never runs concurrently."""

    def __init__(self, app, *, tick_seconds: int = 60, global_default_min: float = 0.0) -> None:
        self.app = app
        self.tick_seconds = tick_seconds
        self.global_default_min = global_default_min
        self._inflight: set[str] = set()

    async def tick(self) -> int:
        """Find due connectors and schedule them. Returns the number scheduled."""
        # Imported lazily to avoid a circular import (routes import models/registry).
        from sqlalchemy import select
        from src.api.routes_connectors import _run_sync
        from src.db.models import ConnectorSyncState
        from src.db.session import async_session_factory

        pipeline = getattr(self.app.state, "ingest_pipeline", None)
        if pipeline is None:
            return 0
        bus = getattr(self.app.state, "ingest_bus", None)
        now = datetime.now(UTC)

        factory = async_session_factory()
        snapshots: list[dict] = []
        async with factory() as session:
            rows = (
                (await session.execute(select(ConnectorSyncState).where(ConnectorSyncState.enabled.is_(True))))
                .scalars()
                .all()
            )
            for r in rows:
                cid = str(r.id)
                if cid in self._inflight:
                    continue
                interval = effective_interval(r.sync_interval_min, self.global_default_min)
                if not is_due(r.last_sync_at, interval, now):
                    continue
                snapshots.append(
                    {
                        "id": cid,
                        "connector_type": r.connector_type,
                        "resource_id": r.resource_id,
                        "config": dict(r.config or {}),
                        "cursor": dict(r.cursor or {}),
                    }
                )

        for snap in snapshots:
            self._inflight.add(snap["id"])
            asyncio.create_task(self._guarded_run(snap, pipeline, bus, _run_sync))
        return len(snapshots)

    async def _guarded_run(self, snapshot: dict, pipeline, bus, run) -> None:
        try:
            await run(snapshot, pipeline, bus)
        except Exception:
            logger.exception("scheduled sync failed for %s", snapshot.get("id"))
        finally:
            self._inflight.discard(snapshot["id"])

    async def run_until(self, stop: asyncio.Event) -> None:
        """Tick loop; exits when ``stop`` is set."""
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.tick_seconds)
            except TimeoutError:
                pass
            if stop.is_set():
                break
            try:
                await self.tick()
            except Exception:
                logger.exception("connector scheduler tick failed")
