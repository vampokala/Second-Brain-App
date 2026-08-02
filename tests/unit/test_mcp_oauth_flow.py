"""Unit tests for OAuthFlowManager."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from src.core.mcp.errors import McpAuthError
from src.core.mcp.oauth_flow import OAuthFlowManager


class _FakeProvider:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.redirect_handler = kwargs["redirect_handler"]
        self.callback_handler = kwargs["callback_handler"]


def _server(
    sid: str | None = None,
    *,
    preset: str = "atlassian",
    url: str = "https://mcp.example/mcp",
) -> SimpleNamespace:
    return SimpleNamespace(id=sid or str(uuid.uuid4()), url=url, preset=preset)


@pytest.mark.asyncio
async def test_start_returns_authorization_url_when_redirect_captured(monkeypatch):
    async def runner(_url: str, provider: _FakeProvider) -> None:
        await provider.redirect_handler("https://auth.example/authorize?state=abc123")

    class _Storage:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        async def has_access_token(self) -> bool:
            return False

    monkeypatch.setattr("src.core.mcp.oauth_flow.DbTokenStorage", _Storage)
    mgr = OAuthFlowManager(
        session_factory=lambda: None,
        provider_factory=_FakeProvider,
        connect_runner=runner,
    )
    server = _server()
    url = await mgr.start(server)
    assert "authorize" in url
    assert await mgr.connection_status(str(server.id)) == "pending"


@pytest.mark.asyncio
async def test_github_oauth_requires_client_credentials(monkeypatch):
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_SECRET", raising=False)
    mgr = OAuthFlowManager(session_factory=lambda: None, provider_factory=_FakeProvider)
    with pytest.raises(McpAuthError, match=r"GITHUB_OAUTH_CLIENT_ID|API token"):
        await mgr.start(_server(preset="github", url="https://api.githubcopilot.com/mcp"))


@pytest.mark.asyncio
async def test_github_oauth_returns_authorize_url_immediately(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.delenv("GITHUB_HOST", raising=False)
    mgr = OAuthFlowManager(session_factory=lambda: None, provider_factory=_FakeProvider)
    url = await mgr.start(_server(preset="github", url="https://api.githubcopilot.com/mcp"))
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=cid" in url


@pytest.mark.asyncio
async def test_github_enterprise_oauth_uses_github_host(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("GITHUB_HOST", "https://github.company.com")
    mgr = OAuthFlowManager(session_factory=lambda: None, provider_factory=_FakeProvider)
    url = await mgr.start(_server(preset="github_enterprise", url="http://localhost:8080/mcp"))
    assert url.startswith("https://github.company.com/login/oauth/authorize?")


@pytest.mark.asyncio
async def test_github_callback_exchanges_token(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "csecret")

    saved: dict[str, Any] = {}

    class _Storage:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        async def has_access_token(self) -> bool:
            return bool(saved.get("access_token"))

        async def set_tokens(self, tokens: Any) -> None:
            saved["access_token"] = tokens.access_token

    class _Resp:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"access_token": "gho_test", "token_type": "bearer", "scope": "repo"}

    class _Client:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *a: Any) -> None:
            return None

        async def post(self, *a: Any, **k: Any) -> _Resp:
            return _Resp()

    monkeypatch.setattr("src.core.mcp.oauth_flow.DbTokenStorage", _Storage)
    monkeypatch.setattr("src.core.mcp.oauth_flow.httpx.AsyncClient", _Client)

    mgr = OAuthFlowManager(session_factory=lambda: None, provider_factory=_FakeProvider)
    server = _server(preset="github", url="https://api.githubcopilot.com/mcp")
    url = await mgr.start(server)
    state = url.split("state=")[1].split("&")[0]
    await mgr.deliver_callback(state, "the-code")
    await asyncio.sleep(0.05)
    assert saved.get("access_token") == "gho_test"
    assert await mgr.connection_status(str(server.id)) == "connected"


@pytest.mark.asyncio
async def test_deliver_callback_raises_when_state_unknown():
    mgr = OAuthFlowManager(session_factory=lambda: None, provider_factory=_FakeProvider)
    with pytest.raises(McpAuthError, match="Unknown or expired"):
        await mgr.deliver_callback("missing", "code")


@pytest.mark.asyncio
async def test_deliver_callback_raises_when_pending_expired_past_ttl():
    async def runner(_url: str, provider: _FakeProvider) -> None:
        await provider.redirect_handler("https://auth.example/authorize?state=old")

    mgr = OAuthFlowManager(
        session_factory=lambda: None,
        provider_factory=_FakeProvider,
        connect_runner=runner,
    )
    server = _server()
    await mgr.start(server)
    pending = mgr._pending_by_state["old"]
    pending.created_at = datetime.now(UTC) - timedelta(seconds=mgr.PENDING_TTL_S + 5)
    with pytest.raises(McpAuthError, match="expired"):
        await mgr.deliver_callback("old", "code")


@pytest.mark.asyncio
async def test_connection_status_prefers_tokens_over_pending(monkeypatch):
    async def runner(_url: str, provider: _FakeProvider) -> None:
        await provider.redirect_handler("https://auth.example/authorize?state=st3")

    tokens_ready = {"ok": False}

    class _Storage:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        async def has_access_token(self) -> bool:
            return tokens_ready["ok"]

    monkeypatch.setattr("src.core.mcp.oauth_flow.DbTokenStorage", _Storage)
    mgr = OAuthFlowManager(
        session_factory=lambda: None,
        provider_factory=_FakeProvider,
        connect_runner=runner,
    )
    server = _server()
    await mgr.start(server)
    assert await mgr.connection_status(str(server.id)) == "pending"
    tokens_ready["ok"] = True
    assert await mgr.connection_status(str(server.id)) == "connected"
