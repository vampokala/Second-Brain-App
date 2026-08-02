"""Shared base for MCP-backed SourceConnector implementations."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, ClassVar

from src.core.connectors.base import ConnectorError, SourceConnector
from src.core.mcp.session import build_mcp_auth, call_tool_json, open_mcp_session
from src.db.models import McpServer
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

SessionOpener = Callable[..., AbstractAsyncContextManager[Any]]


class McpSourceConnector(SourceConnector):
    """Base class for connectors that pull data through an MCP server."""

    preset: ClassVar[str] = ""
    required_tools: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        resource_id: str,
        config: dict,
        token: str | None = None,
        client: Any = None,
        session_factory: Any = None,
        session_opener: SessionOpener | None = None,
        server: McpServer | None = None,
    ) -> None:
        super().__init__(resource_id, config, token)
        self._client = client  # unused; kept for registry call-arg parity
        self._session_factory = session_factory or async_session_factory
        self._session_opener = session_opener or open_mcp_session
        self._server_override = server

    async def _load_server(self) -> McpServer:
        if self._server_override is not None:
            return self._server_override
        server_id = (self.config or {}).get("server_id")
        if not server_id:
            raise ConnectorError("MCP connector requires config.server_id.")
        try:
            sid = uuid.UUID(str(server_id))
        except ValueError as exc:
            raise ConnectorError(f"Invalid MCP server_id: {server_id!r}") from exc
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpServer, sid)
            if row is None:
                raise ConnectorError(f"MCP server {server_id!r} not found.")
            return row

    async def _open(self) -> AbstractAsyncContextManager[Any]:
        server = await self._load_server()
        auth = await build_mcp_auth(server, self._session_factory)
        return self._session_opener(server.url, auth=auth)

    async def test_connection(self) -> tuple[bool, str]:
        try:
            async with await self._open() as session:
                result = await session.list_tools()
                names = {str(getattr(t, "name", "")) for t in (getattr(result, "tools", None) or [])}
                missing = [t for t in self.required_tools if t not in names]
                if missing:
                    return False, f"Missing required tools: {', '.join(missing)}"
                return True, f"Connected ({len(names)} tools available)"
        except ConnectorError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"MCP connection failed: {exc}"

    async def _call(self, session: Any, tool: str, args: dict) -> Any:
        return await call_tool_json(session, tool, args)


def dig(payload: Any, path: str) -> Any:
    """Walk a dotted path into nested dict/list structures."""
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else None
            continue
        return None
    return current


def as_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("issues", "results", "items", "messages", "commits", "values", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return [payload]


def skip_malformed(connector: str, reason: str, raw: Any = None) -> None:
    logger.warning(
        "mcp_item_skipped connector=%s reason=%s raw_type=%s",
        connector,
        reason,
        type(raw).__name__ if raw is not None else "none",
    )
