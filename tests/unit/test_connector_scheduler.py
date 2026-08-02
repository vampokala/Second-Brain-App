"""Unit tests for the connector scheduler's pure logic and overlap guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from src.core.connectors.scheduler import (
    ConnectorScheduler,
    effective_interval,
    is_due,
    next_sync_at,
)

NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


def test_effective_interval_prefers_connector_then_global():
    assert effective_interval(30, 60) == 30.0
    assert effective_interval(None, 60) == 60.0
    assert effective_interval(0, 60) == 60.0
    assert effective_interval(None, 0) == 0.0


def test_is_due_manual_is_never_due():
    assert is_due(None, 0, NOW) is False
    assert is_due(NOW - timedelta(days=5), 0, NOW) is False


def test_is_due_never_synced_with_interval_is_due():
    assert is_due(None, 15, NOW) is True


def test_is_due_respects_elapsed_time():
    assert is_due(NOW - timedelta(minutes=10), 15, NOW) is False
    assert is_due(NOW - timedelta(minutes=20), 15, NOW) is True


def test_is_due_handles_naive_timestamps():
    naive = (NOW - timedelta(minutes=30)).replace(tzinfo=None)
    assert is_due(naive, 15, NOW) is True


def test_next_sync_at():
    assert next_sync_at(None, 0) is None
    assert next_sync_at(NOW, 60) == NOW + timedelta(minutes=60)
    # never-synced returns "now" so the UI shows it as imminently due
    assert next_sync_at(None, 60, NOW) == NOW


@pytest.mark.asyncio
async def test_guarded_run_clears_inflight_on_success_and_error():
    sched = ConnectorScheduler(app=object(), tick_seconds=1)

    async def ok_run(snap, pipeline, bus):
        return None

    async def boom_run(snap, pipeline, bus):
        raise RuntimeError("boom")

    sched._inflight.add("a")
    await sched._guarded_run({"id": "a"}, None, None, ok_run)
    assert "a" not in sched._inflight

    sched._inflight.add("b")
    await sched._guarded_run({"id": "b"}, None, None, boom_run)
    assert "b" not in sched._inflight
