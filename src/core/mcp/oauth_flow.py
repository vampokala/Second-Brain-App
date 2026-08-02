"""Browser OAuth flow bridge for MCP remote servers."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from pydantic import AnyUrl
from src.core.connectors.github_host import is_github_enterprise, resolve_github_oauth_urls
from src.core.mcp.errors import McpAuthError
from src.core.mcp.token_store import DbTokenStorage

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata, OAuthToken

logger = logging.getLogger(__name__)

FlowKind = Literal["mcp_sdk", "github_app"]

# GitHub remote MCP does not support Dynamic Client Registration. OAuth only
# works with a pre-registered GitHub OAuth App (client id + secret).
# Authorize/token URLs are resolved from GITHUB_HOST (Enterprise) or github.com.
_GITHUB_DEFAULT_SCOPES = "repo read:org read:user user:email"


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
    flow_kind: FlowKind = "mcp_sdk"


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
        preset = getattr(server, "preset", "") or ""
        if preset == "github" or preset == "github_enterprise" or _is_github_mcp_url(str(getattr(server, "url", ""))):
            return await self.start_github(server)
        return await self._start_mcp_sdk(server)

    async def start_github(self, server: Any) -> str:
        """GitHub remote MCP OAuth via a pre-registered OAuth App (no DCR)."""
        client_id = (os.getenv("GITHUB_OAUTH_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("GITHUB_OAUTH_CLIENT_SECRET") or "").strip()
        if not client_id or not client_secret:
            host_hint = (
                " Register the OAuth App on your GitHub Enterprise host " "(GITHUB_HOST) when using GHES / ghe.com."
                if is_github_enterprise()
                else ""
            )
            raise McpAuthError(
                "GitHub remote MCP does not support browser OAuth without a "
                "pre-registered GitHub OAuth App (no Dynamic Client Registration). "
                "Use “Use API token” with GITHUB_TOKEN, or set "
                "GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET in .env "
                f"(callback URL must be your MCP_OAUTH_REDIRECT_URI).{host_hint}"
            )

        authorize_url, _token_url = resolve_github_oauth_urls()
        server_id = str(server.id)
        async with self._lock:
            await self._cancel_pending_for_server(server_id)
            state = secrets.token_urlsafe(24)
            scopes = (os.getenv("GITHUB_OAUTH_SCOPES") or _GITHUB_DEFAULT_SCOPES).strip()
            params = {
                "client_id": client_id,
                "redirect_uri": self._redirect_uri,
                "scope": scopes,
                "state": state,
                "allow_signup": "false",
            }
            auth_url = f"{authorize_url}?{urlencode(params)}"
            code_future: asyncio.Future[tuple[str, str | None]] = asyncio.get_running_loop().create_future()
            pending = PendingAuth(
                server_id=server_id,
                state=state,
                authorization_url=auth_url,
                code_future=code_future,
                flow_kind="github_app",
            )
            self._pending_by_state[state] = pending
            self._pending_by_server[server_id] = pending
            task = asyncio.create_task(self._complete_github_oauth(pending, client_id, client_secret))
            pending.task = task
            self._cleanup_tasks.add(task)
            task.add_done_callback(self._cleanup_tasks.discard)

        logger.info(
            "mcp_github_oauth_started server_id=%s enterprise=%s",
            server_id,
            is_github_enterprise(),
        )
        return auth_url

    async def _complete_github_oauth(
        self,
        pending: PendingAuth,
        client_id: str,
        client_secret: str,
    ) -> None:
        try:
            code, _state = await pending.code_future
            _authorize_url, token_url = resolve_github_oauth_urls()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    token_url,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": code,
                        "redirect_uri": self._redirect_uri,
                    },
                )
            payload = resp.json()
            if resp.status_code >= 400 or payload.get("error"):
                detail = payload.get("error_description") or payload.get("error") or resp.text
                raise McpAuthError(f"GitHub token exchange failed: {detail}")
            access = str(payload.get("access_token") or "").strip()
            if not access:
                raise McpAuthError("GitHub token exchange returned no access_token.")
            storage = DbTokenStorage(pending.server_id, self._session_factory)
            await storage.set_tokens(
                OAuthToken(
                    access_token=access,
                    token_type=str(payload.get("token_type") or "Bearer"),
                    scope=str(payload.get("scope") or "") or None,
                    refresh_token=None,
                    expires_in=None,
                )
            )
            logger.info("mcp_github_oauth_token_saved server_id=%s", pending.server_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "mcp_github_oauth_failed server_id=%s error=%s",
                pending.server_id,
                exc,
            )
        finally:
            await self._drop_pending(pending)

    async def _start_mcp_sdk(self, server: Any) -> str:
        """Atlassian-style remote MCP OAuth via the MCP Python SDK (supports DCR)."""
        server_id = str(server.id)
        async with self._lock:
            await self._cancel_pending_for_server(server_id)

            auth_url_holder: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            code_future: asyncio.Future[tuple[str, str | None]] = asyncio.get_running_loop().create_future()
            flow_state = secrets.token_urlsafe(16)

            async def redirect_handler(url: str) -> None:
                oauth_state = _state_from_auth_url(url) or flow_state
                pending = PendingAuth(
                    server_id=server_id,
                    state=oauth_state,
                    authorization_url=url,
                    code_future=code_future,
                    flow_kind="mcp_sdk",
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

            placeholder = PendingAuth(
                server_id=server_id,
                state=flow_state,
                authorization_url="",
                code_future=code_future,
                task=task,
                flow_kind="mcp_sdk",
            )
            self._pending_by_state[flow_state] = placeholder
            self._pending_by_server[server_id] = placeholder

        try:
            url = await asyncio.wait_for(auth_url_holder, timeout=30.0)
        except TimeoutError as exc:
            await self._cancel_pending_for_server(server_id)
            raise McpAuthError(
                "Timed out waiting for OAuth authorization URL. "
                "The MCP server may not support Dynamic Client Registration."
            ) from exc

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
        logger.info(
            "mcp_oauth_callback_delivered server_id=%s flow=%s",
            pending.server_id,
            pending.flow_kind,
        )
        if pending.flow_kind == "mcp_sdk":
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
        """Return ``connected`` | ``pending`` | ``disconnected`` for a server."""
        self._purge_expired()
        storage = DbTokenStorage(str(server_id), self._session_factory)
        if await storage.has_access_token():
            return "connected"
        pending = self._pending_by_server.get(str(server_id))
        if pending is not None and not self._is_expired(pending):
            return "pending"
        return "disconnected"

    async def mark_verified(self, server_id: str) -> None:
        """Record a successful non-OAuth connectivity check (sidecar / token)."""
        storage = DbTokenStorage(str(server_id), self._session_factory)
        await storage.set_tokens(
            OAuthToken(access_token="verified", token_type="Bearer")  # noqa: S106
        )

    async def clear_pending(self, server_id: str) -> None:
        await self._cancel_pending_for_server(str(server_id))

    async def _default_connect(self, url: str, provider: OAuthClientProvider) -> None:
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


def _is_github_mcp_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "githubcopilot.com" in host or host == "api.github.com"
