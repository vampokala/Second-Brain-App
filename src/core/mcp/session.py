"""MCP session helpers (streamable HTTP + tool calls)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol

import httpx
from pydantic import AnyUrl
from src.core.connectors.base import ConnectorError
from src.core.mcp.token_store import DbTokenStorage

from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata

logger = logging.getLogger(__name__)


class _SessionFactory(Protocol):
    def __call__(self) -> Any: ...


class _BearerAuth(httpx.Auth):
    """Static Authorization: Bearer header."""

    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


def _streamable_client():
    """Prefer the v2 name; fall back to the 1.x export."""
    try:
        from mcp.client.streamable_http import streamable_http_client as client

        return client
    except ImportError:
        from mcp.client.streamable_http import streamablehttp_client as client

        return client


@asynccontextmanager
async def open_mcp_session(
    url: str,
    auth: httpx.Auth | None = None,
    timeout_s: float = 30.0,
) -> AsyncIterator[ClientSession]:
    """Open an initialized MCP ``ClientSession`` over streamable HTTP."""
    client_fn = _streamable_client()
    # mcp 1.x takes auth=; newer SDKs take http_client=. Try both shapes.
    try:
        cm = client_fn(url, auth=auth, timeout=timeout_s)
    except TypeError:
        http_client = httpx.AsyncClient(
            auth=auth,
            timeout=httpx.Timeout(timeout_s, read=max(timeout_s, 300.0)),
            follow_redirects=True,
        )
        cm = client_fn(url, http_client=http_client)

    async with cm as streams:
        if len(streams) == 3:
            read, write, _ = streams
        else:
            read, write = streams
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_tool_json(
    session: Any,
    tool: str,
    args: dict,
    *,
    timeout_s: float = 60.0,
) -> Any:
    """Call an MCP tool and return structured/JSON content.

    Raises :class:`ConnectorError` when the tool reports an error or the
    payload cannot be parsed.
    """
    try:
        result = await session.call_tool(tool, args)
    except Exception as exc:
        raise ConnectorError(f"MCP tool {tool!r} failed: {exc}") from exc

    if getattr(result, "isError", False):
        message = _content_text(result) or "tool reported an error"
        raise ConnectorError(f"MCP tool {tool!r} error: {message}")

    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    text = _content_text(result)
    if text is None or text.strip() == "":
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConnectorError(
            f"MCP tool {tool!r} returned unparseable payload"
        ) from exc


async def build_mcp_auth(
    server: Any,
    session_factory: _SessionFactory,
    *,
    redirect_uri: str = "http://localhost:8000/mcp/oauth/callback",
) -> httpx.Auth | None:
    """Build httpx auth for an MCP server based on its ``auth_mode``."""
    mode = (getattr(server, "auth_mode", None) or "none").lower()
    if mode == "none":
        return None
    if mode == "token":
        env_name = getattr(server, "token_env", None)
        if not env_name:
            raise ConnectorError("MCP token auth requires token_env.")
        token = os.getenv(env_name) or ""
        if not token.strip():
            raise ConnectorError(f"Environment variable {env_name} is empty.")
        return _BearerAuth(token.strip())
    if mode == "oauth":
        storage = DbTokenStorage(str(server.id), session_factory)
        metadata = OAuthClientMetadata(
            client_name="Second-Brain-App",
            redirect_uris=[AnyUrl(redirect_uri)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        )
        return OAuthClientProvider(
            server_url=str(server.url),
            client_metadata=metadata,
            storage=storage,
        )
    raise ConnectorError(f"Unknown MCP auth_mode: {mode!r}")


def _content_text(result: Any) -> str | None:
    content = getattr(result, "content", None) or []
    texts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            texts.append(str(text))
        elif isinstance(block, dict) and block.get("text"):
            texts.append(str(block["text"]))
    if not texts:
        return None
    return "\n".join(texts)
