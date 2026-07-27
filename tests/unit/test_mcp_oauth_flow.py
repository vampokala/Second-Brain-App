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


def _server(sid: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=sid or str(uuid.uuid4()), url="https://mcp.example/mcp")


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
async def test_deliver_callback_resolves_pending_flow_when_state_matches():
    async def runner(_url: str, provider: _FakeProvider) -> None:
        await provider.redirect_handler("https://auth.example/authorize?state=st1")
        code, state = await provider.callback_handler()
        assert code == "the-code"
        assert state == "st1"

    mgr = OAuthFlowManager(
        session_factory=lambda: None,
        provider_factory=_FakeProvider,
        connect_runner=runner,
    )
    server = _server()
    await mgr.start(server)
    server_id = await mgr.deliver_callback("st1", "the-code")
    assert server_id == str(server.id)
    await asyncio.sleep(0)


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
async def test_second_start_for_same_server_cancels_first_pending():
    async def runner(_url: str, provider: _FakeProvider) -> None:
        await provider.redirect_handler(
            f"https://auth.example/authorize?state={id(provider)}"
        )
        try:
            await provider.callback_handler()
        except asyncio.CancelledError:
            return

    mgr = OAuthFlowManager(
        session_factory=lambda: None,
        provider_factory=_FakeProvider,
        connect_runner=runner,
    )
    server = _server()
    await mgr.start(server)
    await mgr.start(server)
    assert len([p for p in mgr._pending_by_server.values() if p.server_id == str(server.id)]) == 1


@pytest.mark.asyncio
async def test_connection_status_prefers_tokens_over_pending(monkeypatch):
    """Regression: UI timed out because status stayed pending after OAuth succeeded."""

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
