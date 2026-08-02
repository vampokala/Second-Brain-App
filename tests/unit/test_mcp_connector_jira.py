"""Unit tests for MCP JIRA connector mapping."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from src.core.connectors.base import ConnectorError
from src.core.connectors.mcp_atlassian import (
    JIRA_SEARCH_TOOL,
    RESOURCES_TOOL,
    McpJiraConnector,
    resolve_cloud_id,
)


class _Session:
    def __init__(self, payloads: list[Any], tools: list[str] | None = None) -> None:
        self.payloads = list(payloads)
        self.tools = tools or [JIRA_SEARCH_TOOL, RESOURCES_TOOL]
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return SimpleNamespace(tools=[SimpleNamespace(name=t) for t in self.tools])

    async def call_tool(self, name: str, args: dict):
        self.calls.append((name, args))
        if not self.payloads:
            return SimpleNamespace(structuredContent={"issues": []}, isError=False, content=[])
        payload = self.payloads.pop(0)
        return SimpleNamespace(structuredContent=payload, isError=False, content=[])


def _opener(session: _Session):
    @asynccontextmanager
    async def open_session(_url: str, auth=None):
        yield session

    return open_session


def _connector(session: _Session, **config: Any) -> McpJiraConnector:
    server = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        url="https://mcp.example/mcp",
        auth_mode="none",
        token_env=None,
    )
    return McpJiraConnector(
        "ENG",
        {"server_id": str(server.id), **config},
        server=server,
        session_opener=_opener(session),
        session_factory=lambda: None,
    )


def _patch_call(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        result = await session.call_tool(tool, args)
        return result.structuredContent

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)


_CLOUD = {"resources": [{"id": "cloud-1", "url": "https://acme.atlassian.net"}]}


@pytest.mark.asyncio
async def test_fetch_maps_issue_payload_to_source_items_in_ascending_updated_order(monkeypatch):
    _patch_call(monkeypatch)

    payload = {
        "issues": [
            {
                "key": "ENG-2",
                "fields": {
                    "summary": "Second",
                    "description": "b",
                    "updated": "2024-02-01T00:00:00Z",
                    "status": {"name": "Done"},
                    "issuetype": {"name": "Bug"},
                },
            },
            {
                "key": "ENG-1",
                "fields": {
                    "summary": "First",
                    "description": "a",
                    "updated": "2024-01-01T00:00:00Z",
                    "status": {"name": "Open"},
                    "issuetype": {"name": "Task"},
                },
            },
        ]
    }
    payload["issues"] = sorted(payload["issues"], key=lambda i: i["fields"]["updated"])
    session = _Session([_CLOUD, payload])
    conn = _connector(session)
    items = [i async for i in conn.fetch(None)]
    assert [i.external_id for i in items] == ["ENG-1", "ENG-2"]
    assert items[0].title.startswith("ENG-1")
    assert "Open" in items[0].tags
    assert session.calls[0][0] == RESOURCES_TOOL
    assert session.calls[1][0] == JIRA_SEARCH_TOOL
    assert session.calls[1][1]["cloudId"] == "cloud-1"


@pytest.mark.asyncio
async def test_fetch_includes_since_from_cursor_in_tool_args(monkeypatch):
    _patch_call(monkeypatch)
    session = _Session([_CLOUD, {"issues": []}])
    conn = _connector(session)
    _ = [i async for i in conn.fetch({"since": "2024-01-01"})]
    search_call = next(c for c in session.calls if c[0] == JIRA_SEARCH_TOOL)
    assert "2024-01-01" in search_call[1]["jql"]
    assert search_call[1]["cloudId"] == "cloud-1"


@pytest.mark.asyncio
async def test_fetch_uses_config_cloud_id_without_resources_call(monkeypatch):
    _patch_call(monkeypatch)
    session = _Session([{"issues": []}])
    conn = _connector(session, cloud_id="cfg-cloud")
    _ = [i async for i in conn.fetch(None)]
    assert all(c[0] != RESOURCES_TOOL for c in session.calls)
    assert session.calls[0][1]["cloudId"] == "cfg-cloud"


@pytest.mark.asyncio
async def test_fetch_yields_nothing_when_result_empty(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        if tool == RESOURCES_TOOL:
            return _CLOUD
        return {"issues": []}

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    session = _Session([])
    conn = _connector(session)
    items = [i async for i in conn.fetch(None)]
    assert items == []


@pytest.mark.asyncio
async def test_fetch_skips_malformed_item_and_continues(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        if tool == RESOURCES_TOOL:
            return _CLOUD
        return {
            "issues": [
                {"key": "BAD"},
                {
                    "key": "ENG-3",
                    "fields": {
                        "summary": "Ok",
                        "description": "",
                        "updated": "2024-03-01T00:00:00Z",
                    },
                },
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    session = _Session([])
    conn = _connector(session)
    items = [i async for i in conn.fetch(None)]
    assert [i.external_id for i in items] == ["ENG-3"]


@pytest.mark.asyncio
async def test_fetch_follows_pagination_token_until_exhausted(monkeypatch):
    pages = [
        _CLOUD,
        {
            "issues": [
                {
                    "key": "ENG-1",
                    "fields": {"summary": "a", "updated": "2024-01-01T00:00:00Z"},
                }
            ],
            "nextPageToken": "p2",
        },
        {
            "issues": [
                {
                    "key": "ENG-2",
                    "fields": {"summary": "b", "updated": "2024-02-01T00:00:00Z"},
                }
            ]
        },
    ]

    async def fake_call(session, tool, args, timeout_s=60.0):
        return pages.pop(0)

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    session = _Session([])
    conn = _connector(session)
    items = [i async for i in conn.fetch(None)]
    assert [i.external_id for i in items] == ["ENG-1", "ENG-2"]


@pytest.mark.asyncio
async def test_resolve_cloud_id_matches_site_url_hint():
    async def call_tool(_session, _tool, _args):
        return {
            "resources": [
                {"id": "other", "url": "https://other.atlassian.net"},
                {"id": "match", "url": "https://acme.atlassian.net"},
            ]
        }

    cloud_id = await resolve_cloud_id(None, {"site_url": "https://acme.atlassian.net"}, call_tool)
    assert cloud_id == "match"


@pytest.mark.asyncio
async def test_resolve_cloud_id_raises_when_no_resources():
    async def call_tool(_session, _tool, _args):
        return {"resources": []}

    with pytest.raises(ConnectorError, match="cloudId"):
        await resolve_cloud_id(None, {}, call_tool)


@pytest.mark.asyncio
async def test_test_connection_ok_when_required_tools_listed(monkeypatch):
    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    session = _Session([], tools=[JIRA_SEARCH_TOOL, "other"])
    conn = _connector(session)
    ok, msg = await conn.test_connection()
    assert ok is True
    assert "tools" in msg.lower()


@pytest.mark.asyncio
async def test_test_connection_fails_when_tool_missing(monkeypatch):
    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    session = _Session([], tools=["other"])
    conn = _connector(session)
    ok, msg = await conn.test_connection()
    assert ok is False
    assert JIRA_SEARCH_TOOL in msg


@pytest.mark.asyncio
async def test_source_item_relpath_stable_across_resyncs(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        if tool == RESOURCES_TOOL:
            return _CLOUD
        return {
            "issues": [
                {
                    "key": "ENG-9",
                    "fields": {"summary": "x", "updated": "2024-01-01T00:00:00Z"},
                }
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    session = _Session([])
    conn = _connector(session)
    items = [i async for i in conn.fetch(None)]
    assert items[0].relpath("mcp_jira", "ENG") == items[0].relpath("mcp_jira", "ENG")
