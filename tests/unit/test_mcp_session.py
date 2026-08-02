"""Unit tests for MCP session helpers."""

# ruff: noqa: S106

from __future__ import annotations

from types import SimpleNamespace

import pytest
from src.core.connectors.base import ConnectorError
from src.core.mcp.session import _BasicAuth, _BearerAuth, build_mcp_auth, call_tool_json


class _FakeResult:
    def __init__(self, *, structured=None, text=None, is_error=False) -> None:
        self.structuredContent = structured
        self.isError = is_error
        self.content = [SimpleNamespace(text=text)] if text is not None else []


class _FakeSession:
    def __init__(self, result) -> None:
        self._result = result

    async def call_tool(self, _name: str, _args: dict):
        return self._result


@pytest.mark.asyncio
async def test_call_tool_json_returns_structured_content_when_present():
    session = _FakeSession(_FakeResult(structured={"issues": [{"key": "A-1"}]}))
    out = await call_tool_json(session, "jira_search", {})
    assert out == {"issues": [{"key": "A-1"}]}


@pytest.mark.asyncio
async def test_call_tool_json_parses_text_content_as_json_fallback():
    session = _FakeSession(_FakeResult(text='{"ok": true}'))
    out = await call_tool_json(session, "tool", {})
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_call_tool_json_raises_connector_error_when_result_is_error():
    session = _FakeSession(_FakeResult(text="boom", is_error=True))
    with pytest.raises(ConnectorError, match="error"):
        await call_tool_json(session, "bad", {})


@pytest.mark.asyncio
async def test_call_tool_json_raises_connector_error_when_payload_unparseable():
    session = _FakeSession(_FakeResult(text="not-json"))
    with pytest.raises(ConnectorError, match="unparseable"):
        await call_tool_json(session, "tool", {})


@pytest.mark.asyncio
async def test_call_tool_json_returns_empty_list_for_empty_content():
    session = _FakeSession(_FakeResult())
    out = await call_tool_json(session, "tool", {})
    assert out == []


@pytest.mark.asyncio
async def test_build_mcp_auth_uses_env_bearer_when_token_mode(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    server = SimpleNamespace(id="1", url="https://x", auth_mode="token", token_env="GITHUB_TOKEN", preset="github")
    auth = await build_mcp_auth(server, lambda: None)
    assert isinstance(auth, _BearerAuth)


@pytest.mark.asyncio
async def test_build_mcp_auth_uses_basic_for_atlassian_with_email(monkeypatch):
    monkeypatch.setenv("JIRA_API_TOKEN", "atl_token")
    server = SimpleNamespace(
        id="1",
        url="https://mcp.atlassian.com/v1/mcp",
        auth_mode="token",
        token_env="JIRA_API_TOKEN",
        preset="atlassian",
        auth_email="you@acme.com",
    )
    auth = await build_mcp_auth(server, lambda: None)
    assert isinstance(auth, _BasicAuth)


@pytest.mark.asyncio
async def test_build_mcp_auth_atlassian_falls_back_to_bearer_without_email(monkeypatch):
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("ATLASSIAN_EMAIL", raising=False)
    monkeypatch.setenv("JIRA_API_TOKEN", "svc_key")
    server = SimpleNamespace(
        id="1",
        url="https://mcp.atlassian.com/v1/mcp",
        auth_mode="token",
        token_env="JIRA_API_TOKEN",
        preset="atlassian",
        auth_email=None,
    )
    auth = await build_mcp_auth(server, lambda: None)
    assert isinstance(auth, _BearerAuth)


@pytest.mark.asyncio
async def test_build_mcp_auth_returns_none_when_auth_mode_none():
    server = SimpleNamespace(id="1", url="https://x", auth_mode="none", token_env=None)
    assert await build_mcp_auth(server, lambda: None) is None
