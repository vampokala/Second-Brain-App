"""Integration-style tests for MCP routes and sync orchestrator."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from src.api.routes_mcp import router as mcp_router
from src.core.connectors.mcp_atlassian import McpJiraConnector
from src.core.connectors.registry import sync_connector
from src.core.mcp.oauth_flow import OAuthFlowManager


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def ingest_text(self, relpath: str, body: str):
        self.calls.append((relpath, body))


@pytest.mark.asyncio
async def test_sync_connector_ingests_items_from_mcp_server_and_advances_cursor(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        return {
            "issues": [
                {
                    "key": "ENG-1",
                    "fields": {
                        "summary": "One",
                        "description": "d",
                        "updated": "2024-01-01T00:00:00Z",
                    },
                },
                {
                    "key": "ENG-2",
                    "fields": {
                        "summary": "Two",
                        "description": "d",
                        "updated": "2024-02-01T00:00:00Z",
                    },
                },
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)

    @asynccontextmanager
    async def opener(_url, auth=None):
        yield SimpleNamespace()

    server = SimpleNamespace(
        id=str(uuid4()),
        url="https://mcp.example/mcp",
        auth_mode="none",
        token_env=None,
    )
    pipeline = FakePipeline()
    # Patch build_connector path by calling connector.fetch via sync with injected type
    from src.core.connectors import registry as reg

    original = reg.build_connector

    def build(connector_type, resource_id, config, token=None, client=None):
        return McpJiraConnector(
            resource_id,
            config,
            token,
            server=server,
            session_opener=opener,
            session_factory=lambda: None,
        )

    monkeypatch.setattr(reg, "build_connector", build)
    result = await sync_connector(
        connector_type="mcp_jira",
        resource_id="ENG",
        config={"server_id": server.id},
        cursor=None,
        pipeline=pipeline,
    )
    monkeypatch.setattr(reg, "build_connector", original)
    assert result.status == "ok"
    assert result.item_count == 2
    assert result.cursor["since"] == "2024-02-01T00:00:00Z"
    assert len(pipeline.calls) == 2
    assert "source: mcp_jira" in pipeline.calls[0][1]


@pytest.mark.asyncio
async def test_sync_connector_reports_failed_status_when_tool_errors(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        from src.core.connectors.base import ConnectorError

        raise ConnectorError("tool blew up")

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)

    @asynccontextmanager
    async def opener(_url, auth=None):
        yield SimpleNamespace()

    server = SimpleNamespace(id=str(uuid4()), url="https://x", auth_mode="none", token_env=None)

    def build(connector_type, resource_id, config, token=None, client=None):
        return McpJiraConnector(
            resource_id,
            config,
            server=server,
            session_opener=opener,
            session_factory=lambda: None,
        )

    monkeypatch.setattr("src.core.connectors.registry.build_connector", build)
    result = await sync_connector(
        connector_type="mcp_jira",
        resource_id="ENG",
        config={},
        cursor=None,
        pipeline=FakePipeline(),
    )
    assert result.status == "failed"
    assert "tool blew up" in (result.error or "")


@pytest.mark.asyncio
async def test_resync_with_same_data_upserts_same_relpaths(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        return {
            "issues": [
                {
                    "key": "ENG-1",
                    "fields": {"summary": "One", "updated": "2024-01-01T00:00:00Z"},
                }
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)

    @asynccontextmanager
    async def opener(_url, auth=None):
        yield SimpleNamespace()

    server = SimpleNamespace(id=str(uuid4()), url="https://x", auth_mode="none", token_env=None)

    def build(connector_type, resource_id, config, token=None, client=None):
        return McpJiraConnector(
            resource_id,
            config,
            server=server,
            session_opener=opener,
            session_factory=lambda: None,
        )

    monkeypatch.setattr("src.core.connectors.registry.build_connector", build)
    pipeline = FakePipeline()
    await sync_connector(
        connector_type="mcp_jira",
        resource_id="ENG",
        config={},
        cursor=None,
        pipeline=pipeline,
    )
    await sync_connector(
        connector_type="mcp_jira",
        resource_id="ENG",
        config={},
        cursor=None,
        pipeline=pipeline,
    )
    assert pipeline.calls[0][0] == pipeline.calls[1][0]


class _MemOAuth(OAuthFlowManager):
    async def start(self, server: Any) -> str:
        self._last = str(server.id)
        # Minimal pending so connect response has state
        import asyncio
        from datetime import UTC, datetime

        from src.core.mcp.oauth_flow import PendingAuth

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        pending = PendingAuth(
            server_id=str(server.id),
            state="state-1",
            authorization_url="https://auth.example/authorize?state=state-1",
            code_future=fut,
            created_at=datetime.now(UTC),
        )
        self._pending_by_state["state-1"] = pending
        self._pending_by_server[str(server.id)] = pending
        return pending.authorization_url


@pytest.mark.asyncio
async def test_list_servers_returns_presets_unconfigured(monkeypatch):
    app = FastAPI()
    app.include_router(mcp_router)
    app.state.mcp_oauth = _MemOAuth(session_factory=lambda: None)

    class Sess:
        async def execute(self, *_a, **_k):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return None

    monkeypatch.setattr(
        "src.api.routes_mcp.async_session_factory",
        lambda: (lambda: Sess()),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/mcp/servers")
    assert res.status_code == 200
    presets = {row["preset"] for row in res.json()}
    assert "atlassian" in presets
    assert "github" in presets


@pytest.mark.asyncio
async def test_upsert_custom_server_requires_url(monkeypatch):
    app = FastAPI()
    app.include_router(mcp_router)
    app.state.mcp_oauth = _MemOAuth(session_factory=lambda: None)
    monkeypatch.setattr(
        "src.api.routes_mcp.async_session_factory",
        lambda: (lambda: MagicMock()),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/mcp/servers",
            json={"preset": "custom", "name": "X", "auth_mode": "none"},
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_callback_with_bad_state_returns_400_html():
    app = FastAPI()
    app.include_router(mcp_router)
    app.state.mcp_oauth = _MemOAuth(session_factory=lambda: None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/mcp/oauth/callback", params={"code": "c", "state": "nope"})
    assert res.status_code == 400
    assert "text/html" in res.headers.get("content-type", "")
