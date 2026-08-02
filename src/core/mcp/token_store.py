"""DB-backed OAuth token storage for MCP clients."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from src.db.models import McpOAuthToken

from mcp.client.auth import TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

logger = logging.getLogger(__name__)


class _SessionFactory(Protocol):
    def __call__(self) -> Any: ...


def _parse_server_id(server_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(server_id))
    except ValueError as exc:
        raise ValueError(f"invalid MCP server id: {server_id!r}") from exc


class DbTokenStorage(TokenStorage):
    """Persist MCP OAuth tokens and DCR client info keyed by server id."""

    def __init__(self, server_id: str, session_factory: _SessionFactory) -> None:
        self.server_id = str(server_id)
        self._server_uuid = _parse_server_id(server_id)
        self._session_factory = session_factory

    async def get_tokens(self) -> OAuthToken | None:
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpOAuthToken, self._server_uuid)
            if row is None or not row.access_token:
                return None
            expires_in: int | None = None
            if row.expires_at is not None:
                expires_in = max(0, int((row.expires_at - datetime.now(UTC)).total_seconds()))
            return OAuthToken(
                access_token=row.access_token,
                token_type="Bearer",  # noqa: S106 — OAuth token_type, not a password
                expires_in=expires_in,
                scope=row.scope,
                refresh_token=row.refresh_token,
            )

    async def set_tokens(self, tokens: OAuthToken) -> None:
        expires_at: datetime | None = None
        if tokens.expires_in is not None:
            expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens.expires_in))
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpOAuthToken, self._server_uuid)
            if row is None:
                row = McpOAuthToken(
                    server_id=self._server_uuid,
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    expires_at=expires_at,
                    scope=tokens.scope,
                    client_info={},
                )
                session.add(row)
            else:
                row.access_token = tokens.access_token
                row.refresh_token = tokens.refresh_token
                row.expires_at = expires_at
                row.scope = tokens.scope
                row.updated_at = datetime.now(UTC)
            await session.commit()
        logger.info("mcp_tokens_saved server_id=%s", self.server_id)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpOAuthToken, self._server_uuid)
            if row is None or not row.client_info:
                return None
            try:
                return OAuthClientInformationFull.model_validate(row.client_info)
            except Exception as exc:
                logger.warning(
                    "mcp_client_info_invalid server_id=%s error=%s",
                    self.server_id,
                    exc,
                )
                return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        payload = client_info.model_dump(mode="json")
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpOAuthToken, self._server_uuid)
            if row is None:
                row = McpOAuthToken(
                    server_id=self._server_uuid,
                    access_token="",
                    refresh_token=None,
                    expires_at=None,
                    scope=None,
                    client_info=payload,
                )
                session.add(row)
            else:
                row.client_info = payload
                row.updated_at = datetime.now(UTC)
            await session.commit()

    async def has_access_token(self) -> bool:
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpOAuthToken, self._server_uuid)
            return bool(row and row.access_token)

    async def clear(self) -> None:
        factory = self._session_factory()
        async with factory() as session:
            row = await session.get(McpOAuthToken, self._server_uuid)
            if row is not None:
                await session.delete(row)
                await session.commit()
