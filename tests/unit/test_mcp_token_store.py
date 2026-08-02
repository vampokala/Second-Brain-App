"""Unit tests for DbTokenStorage."""

# ruff: noqa: S105, S106

from __future__ import annotations

import uuid
from typing import Any

import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from src.core.mcp.token_store import DbTokenStorage


class _FakeSession:
    def __init__(self, store: dict[uuid.UUID, Any]) -> None:
        self._store = store
        self._pending: list[Any] = []

    async def get(self, _model: Any, key: uuid.UUID) -> Any:
        return self._store.get(key)

    def add(self, row: Any) -> None:
        self._pending.append(row)

    async def delete(self, row: Any) -> None:
        self._store.pop(row.server_id, None)

    async def commit(self) -> None:
        for row in self._pending:
            self._store[row.server_id] = row
        self._pending.clear()

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


def _session_factory(store: dict[uuid.UUID, Any]):
    """Mimic ``async_session_factory``: call once for maker, again for session."""

    class Maker:
        def __call__(self) -> _FakeSession:
            return _FakeSession(store)

    def factory() -> Maker:
        return Maker()

    return factory


@pytest.mark.asyncio
async def test_get_tokens_returns_none_when_never_saved():
    storage = DbTokenStorage(str(uuid.uuid4()), _session_factory({}))
    assert await storage.get_tokens() is None


@pytest.mark.asyncio
async def test_set_tokens_then_get_round_trips_all_fields():
    sid = uuid.uuid4()
    store: dict[uuid.UUID, Any] = {}
    storage = DbTokenStorage(str(sid), _session_factory(store))
    await storage.set_tokens(
        OAuthToken(
            access_token="access",
            token_type="Bearer",
            expires_in=3600,
            scope="read",
            refresh_token="refresh",
        )
    )
    tokens = await storage.get_tokens()
    assert tokens is not None
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.scope == "read"
    assert tokens.expires_in is not None and tokens.expires_in <= 3600


@pytest.mark.asyncio
async def test_set_tokens_twice_overwrites_previous():
    sid = uuid.uuid4()
    store: dict[uuid.UUID, Any] = {}
    storage = DbTokenStorage(str(sid), _session_factory(store))
    await storage.set_tokens(OAuthToken(access_token="one", token_type="Bearer"))
    await storage.set_tokens(OAuthToken(access_token="two", token_type="Bearer"))
    tokens = await storage.get_tokens()
    assert tokens is not None
    assert tokens.access_token == "two"


@pytest.mark.asyncio
async def test_client_info_round_trip_preserves_dcr_credentials():
    sid = uuid.uuid4()
    store: dict[uuid.UUID, Any] = {}
    storage = DbTokenStorage(str(sid), _session_factory(store))
    info = OAuthClientInformationFull(
        client_id="cid",
        client_secret="csecret",
        redirect_uris=[AnyUrl("http://localhost:8000/mcp/oauth/callback")],
    )
    await storage.set_client_info(info)
    loaded = await storage.get_client_info()
    assert loaded is not None
    assert loaded.client_id == "cid"
    assert loaded.client_secret == "csecret"


@pytest.mark.asyncio
async def test_deleting_server_cascades_token_row():
    sid = uuid.uuid4()
    store: dict[uuid.UUID, Any] = {}
    storage = DbTokenStorage(str(sid), _session_factory(store))
    await storage.set_tokens(OAuthToken(access_token="x", token_type="Bearer"))
    assert await storage.has_access_token() is True
    await storage.clear()
    assert await storage.has_access_token() is False
    assert await storage.get_tokens() is None
