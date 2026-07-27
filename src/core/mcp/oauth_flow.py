"""Browser OAuth flow bridge for MCP remote servers."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl
from src.core.mcp.errors import McpAuthError
from src.core.mcp.token_store import DbTokenStorage

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata

logger = logging.getLogger(__name__)


class _SessionFactory(Protocol):
    def __call__(self) -> Any: ...


@dataclass(slots=True)
class PendingAuth:
    """In-flight OAuth authorization awaiting the browser callback."""

    server_id: str
    state: str
    authorization_url: str
    code_future: asyncio.Future[tuple[str, str | None]]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task: asyncio.Task[None] | None = None


class OAuthFlowManager:
    """Singleton-style manager hung on ``app.state.mcp_oauth``."""

    PENDING_TTL_S = 600

    def __init__(
        self,
        *,
        session_factory: _SessionFactory,
        redirect_uri: str = "http://localhost:8000/mcp/oauth/callback",
        client_name: str = "Second-Brain-App",
        provider_factory: Callable[..., OAuthClientProvider] | None = None,
        connect_runner: Callable[[str, OAuthClientProvider], Any] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._redirect_uri = redirect_uri
        self._client_name = client_name
        self._provider_factory = provider_factory or OAuthClientProvider
        self._connect_runner = connect_runner
        self._pending_by_state: dict[str, PendingAuth] = {}
        self._pending_by_server: dict[str, PendingAuth] = {}
        self._cleanup_tasks: set[asyncio.Task[None]] = set()
        self._lock = asyncio.Lock()

    async def start(self, server: Any) -> str:
        """Begin OAuth for ``server`` and return the authorization URL."""
        server_id = str(server.id)
        async with self._lock:
            await self._cancel_pending_for_server(server_id)

            auth_url_holder: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            code_future: asyncio.Future[tuple[str, str | None]] = (
                asyncio.get_running_loop().create_future()
            )
            flow_state = secrets.token_urlsafe(16)

            async def redirect_handler(url: str) -> None:
                oauth_state = _state_from_auth_url(url) or flow_state
                pending = PendingAuth(
                    server_id=server_id,
                    state=oauth_state,
                    authorization_url=url,
                    code_future=code_future,
                )
                self._pending_by_state[oauth_state] = pending
                self._pending_by_server[server_id] = pending
                if not auth_url_holder.done():
                    auth_url_holder.set_result(url)

            async def callback_handler() -> tuple[str, str | None]:
                return await code_future

            storage = DbTokenStorage(server_id, self._session_factory)
            metadata = OAuthClientMetadata(
                client_name=self._client_name,
                redirect_uris=[AnyUrl(self._redirect_uri)],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
            )
            provider = self._provider_factory(
                server_url=str(server.url),
                client_metadata=metadata,
                storage=storage,
                redirect_handler=redirect_handler,
                callback_handler=callback_handler,
            )

            if self._connect_runner is not None:
                task = asyncio.create_task(self._connect_runner(str(server.url), provider))
            else:
                task = asyncio.create_task(self._default_connect(str(server.url), provider))

            # Placeholder pending until redirect_handler fires with the real URL/state.
            placeholder = PendingAuth(
                server_id=server_id,
                state=flow_state,
                authorization_url="",
                code_future=code_future,
                task=task,
            )
            self._pending_by_state[flow_state] = placeholder
            self._pending_by_server[server_id] = placeholder

        try:
            url = await asyncio.wait_for(auth_url_holder, timeout=30.0)
        except TimeoutError as exc:
            await self._cancel_pending_for_server(server_id)
            raise McpAuthError("Timed out waiting for OAuth authorization URL.") from exc

        pending = self._pending_by_server.get(server_id)
        if pending is not None:
            pending.task = task
            pending.authorization_url = url
        logger.info("mcp_oauth_started server_id=%s", server_id)
        return url

    async def deliver_callback(self, state: str, code: str) -> str:
        """Resolve a pending flow with the browser callback values."""
        self._purge_expired()
        pending = self._pending_by_state.get(state)
        if pending is None:
            raise McpAuthError(f"Unknown or expired OAuth state: {state!r}")
        age = (datetime.now(UTC) - pending.created_at).total_seconds()
        if age > self.PENDING_TTL_S:
            await self._drop_pending(pending)
            raise McpAuthError("OAuth flow expired; please connect again.")
        if pending.code_future.done():
            raise McpAuthError("OAuth code already delivered for this flow.")
        pending.code_future.set_result((code, state))
        logger.info("mcp_oauth_callback_delivered server_id=%s", pending.server_id)
        # Drop the pending index after a short delay so connection_status can
        # flip to connected once tokens are written by the OAuth provider.
        task = asyncio.create_task(self._cleanup_after_callback(pending))
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)
        return pending.server_id

    async def _cleanup_after_callback(self, pending: PendingAuth) -> None:
        try:
            if pending.task is not None:
                await asyncio.wait_for(asyncio.shield(pending.task), timeout=60.0)
        except Exception as exc:
            logger.warning(
                "mcp_oauth_post_callback_cleanup server_id=%s error=%s",
                pending.server_id,
                exc,
            )
        finally:
            await self._drop_pending(pending)

    async def connection_status(self, server_id: str) -> str:
        """Return ``connected`` | ``pending`` | ``disconnected`` for a server.

        Tokens win over an in-flight pending flow so the UI can flip to
        Connected as soon as the browser callback completes (even while the
        background MCP session task is still winding down).
        """
        self._purge_expired()
        storage = DbTokenStorage(str(server_id), self._session_factory)
        if await storage.has_access_token():
            return "connected"
        pending = self._pending_by_server.get(str(server_id))
        if pending is not None and not self._is_expired(pending):
            return "pending"
        return "disconnected"

    async def mark_verified(self, server_id: str) -> None:
        """Record a successful non-OAuth connectivity check (sidecar probe)."""
        from mcp.shared.auth import OAuthToken

        storage = DbTokenStorage(str(server_id), self._session_factory)
        await storage.set_tokens(
            OAuthToken(access_token="verified", token_type="Bearer")  # noqa: S106
        )

    async def clear_pending(self, server_id: str) -> None:
        await self._cancel_pending_for_server(str(server_id))

    async def _default_connect(self, url: str, provider: OAuthClientProvider) -> None:
        """Trigger the OAuth auth flow by opening an MCP session."""
        from src.core.mcp.session import open_mcp_session

        try:
            async with open_mcp_session(url, auth=provider):
                pass
        except Exception as exc:
            logger.warning("mcp_oauth_connect_failed url=%s error=%s", url, exc)

    async def _cancel_pending_for_server(self, server_id: str) -> None:
        existing = self._pending_by_server.get(server_id)
        if existing is None:
            return
        if not existing.code_future.done():
            existing.code_future.cancel()
        if existing.task is not None and not existing.task.done():
            existing.task.cancel()
        await self._drop_pending(existing)

    async def _drop_pending(self, pending: PendingAuth) -> None:
        self._pending_by_state.pop(pending.state, None)
        current = self._pending_by_server.get(pending.server_id)
        if current is pending:
            self._pending_by_server.pop(pending.server_id, None)

    def _is_expired(self, pending: PendingAuth) -> bool:
        age = (datetime.now(UTC) - pending.created_at).total_seconds()
        return age > self.PENDING_TTL_S

    def _purge_expired(self) -> None:
        expired = [p for p in self._pending_by_state.values() if self._is_expired(p)]
        for pending in expired:
            self._pending_by_state.pop(pending.state, None)
            current = self._pending_by_server.get(pending.server_id)
            if current is pending:
                self._pending_by_server.pop(pending.server_id, None)


def _state_from_auth_url(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
        values = qs.get("state") or []
        return values[0] if values else None
    except Exception:
        return None
