"""MCP server configuration + OAuth routes."""

from __future__ import annotations

import logging
import os
import uuid
from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from src.api.models_mcp import (
    McpConnectResponse,
    McpServerOut,
    McpServerUpsertBody,
    McpToolOut,
)
from src.core.mcp.errors import McpAuthError
from src.core.mcp.oauth_flow import OAuthFlowManager
from src.core.mcp.servers import PRESETS, normalize_mcp_url, resolve_preset_url
from src.core.mcp.session import build_mcp_auth, open_mcp_session
from src.core.mcp.token_store import DbTokenStorage
from src.db.models import ConnectorSyncState, McpServer
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _oauth_manager(request: Request) -> OAuthFlowManager:
    mgr = getattr(request.app.state, "mcp_oauth", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="MCP OAuth manager is not initialized.")
    return mgr


def _redirect_uri() -> str:
    return os.getenv("MCP_OAUTH_REDIRECT_URI", "http://localhost:8000/mcp/oauth/callback")


async def _is_connected(server: McpServer, mgr: OAuthFlowManager | None) -> bool:
    # auth_mode "none" (e.g. Google Workspace sidecar) is only connected after
    # a successful Connect probe writes a verification marker to token storage.
    if server.auth_mode == "token":
        env_name = server.token_env or ""
        return bool(env_name and os.getenv(env_name))
    if mgr is not None:
        status = await mgr.connection_status(str(server.id))
        return status == "connected"
    storage = DbTokenStorage(str(server.id), async_session_factory)
    return await storage.has_access_token()


def _to_out(server: McpServer, *, connected: bool) -> McpServerOut:
    preset = PRESETS.get(server.preset)
    connector_types = list(preset.connector_types) if preset else ["mcp_custom"]
    return McpServerOut(
        id=str(server.id),
        preset=server.preset,
        name=server.name,
        url=server.url,
        auth_mode=server.auth_mode,
        connected=connected,
        connector_types=connector_types,
        enabled=bool(server.enabled),
        auth_email=server.auth_email,
    )


@router.get("/servers", response_model=list[McpServerOut])
async def list_servers(request: Request) -> list[McpServerOut]:
    mgr = getattr(request.app.state, "mcp_oauth", None)
    factory = async_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(McpServer))).scalars().all()
        configured = {r.preset: r for r in rows}
        out: list[McpServerOut] = []
        for row in rows:
            connected = await _is_connected(row, mgr)
            out.append(_to_out(row, connected=connected))
        for key, preset in PRESETS.items():
            if key == "custom" or key in configured:
                continue
            url = resolve_preset_url(key) or ""
            out.append(
                McpServerOut(
                    id=f"preset:{key}",
                    preset=key,
                    name=preset.label,
                    url=url,
                    auth_mode=preset.auth_modes[0],
                    connected=False,
                    connector_types=list(preset.connector_types),
                    enabled=False,
                )
            )
        return out


@router.post("/servers", response_model=McpServerOut)
async def upsert_server(body: McpServerUpsertBody, request: Request) -> McpServerOut:
    if body.preset not in PRESETS:
        raise HTTPException(status_code=422, detail=f"Unknown preset: {body.preset!r}")
    preset = PRESETS[body.preset]
    if body.auth_mode not in preset.auth_modes:
        raise HTTPException(
            status_code=422,
            detail=f"auth_mode {body.auth_mode!r} not allowed for preset {body.preset!r}",
        )
    url = resolve_preset_url(body.preset, str(body.url) if body.url else None)
    if not url:
        raise HTTPException(
            status_code=422,
            detail=(
                "url is required for this MCP preset. "
                "For GitHub Enterprise, set GITHUB_MCP_URL or provide the "
                "self-hosted github-mcp-server URL."
            ),
        )

    name = (body.name or preset.label).strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be empty.")

    mgr = getattr(request.app.state, "mcp_oauth", None)
    factory = async_session_factory()
    async with factory() as session:
        existing = (
            await session.execute(select(McpServer).where(McpServer.preset == body.preset, McpServer.name == name))
        ).scalar_one_or_none()
        if existing is None:
            existing = McpServer(
                preset=body.preset,
                name=name,
                url=url,
                auth_mode=body.auth_mode,
                token_env=body.token_env,
                auth_email=(body.auth_email or "").strip() or None,
                enabled=True,
            )
            session.add(existing)
        else:
            existing.url = url
            existing.auth_mode = body.auth_mode
            existing.token_env = body.token_env
            existing.auth_email = (body.auth_email or "").strip() or None
            existing.enabled = True
        await session.commit()
        await session.refresh(existing)
        connected = await _is_connected(existing, mgr)
        return _to_out(existing, connected=connected)


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str) -> dict[str, str]:
    if server_id.startswith("preset:"):
        raise HTTPException(status_code=404, detail="Preset placeholder cannot be deleted.")
    try:
        sid = uuid.UUID(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="MCP server not found.") from exc

    factory = async_session_factory()
    async with factory() as session:
        row = await session.get(McpServer, sid)
        if row is None:
            raise HTTPException(status_code=404, detail="MCP server not found.")

        connectors = (await session.execute(select(ConnectorSyncState))).scalars().all()
        if any(str((c.config or {}).get("server_id") or "") == server_id for c in connectors):
            raise HTTPException(
                status_code=409,
                detail="Disconnect connectors that reference this MCP server first.",
            )

        await session.execute(delete(McpServer).where(McpServer.id == sid))
        await session.commit()
    return {"status": "deleted"}


@router.post("/servers/{server_id}/connect", response_model=McpConnectResponse)
async def connect_server(server_id: str, request: Request) -> McpConnectResponse:
    row = await _load_server(server_id)
    mgr = _oauth_manager(request)

    # Sidecar / unauthenticated MCP: probe list_tools then mark verified.
    if row.auth_mode == "none":
        try:
            async with open_mcp_session(normalize_mcp_url(row.url), auth=None) as session:
                await session.list_tools()
        except Exception as exc:
            logger.warning("mcp_sidecar_probe_failed server_id=%s error=%s", server_id, exc)
            raise HTTPException(
                status_code=502,
                detail=(
                    "MCP sidecar is not reachable at "
                    f"{row.url}. For Google Workspace, set GOOGLE_OAUTH_CLIENT_ID/SECRET "
                    "in .env and run: docker compose --profile mcp up -d workspace-mcp"
                ),
            ) from exc
        await mgr.mark_verified(str(row.id))
        return McpConnectResponse(authorization_url="", state="verified")

    if row.auth_mode == "token":
        env_name = row.token_env or ""
        if not env_name or not os.getenv(env_name):
            raise HTTPException(
                status_code=400,
                detail=f"Set {env_name or 'token_env'} in the environment or Settings before connecting.",
            )
        try:
            auth = await build_mcp_auth(row, async_session_factory, redirect_uri=_redirect_uri())
            async with open_mcp_session(normalize_mcp_url(row.url), auth=auth) as session:
                await session.list_tools()
        except Exception as exc:
            logger.warning("mcp_token_probe_failed server_id=%s error=%s", server_id, exc)
            hint = ""
            if row.preset == "atlassian":
                hint = (
                    " For personal API tokens, set auth_email (or JIRA_EMAIL) so auth uses "
                    "Basic email:token. Service-account API keys use Bearer without email."
                )
            raise HTTPException(
                status_code=502,
                detail=f"MCP token authentication failed when probing the server: {exc}.{hint}",
            ) from exc
        await mgr.mark_verified(str(row.id))
        return McpConnectResponse(authorization_url="", state="verified")

    if row.auth_mode != "oauth":
        raise HTTPException(status_code=400, detail=f"Unsupported auth_mode: {row.auth_mode!r}")

    if row.preset == "google_workspace":
        if not (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Google Workspace Connect requires a Google Cloud OAuth client. "
                    "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env "
                    "(Web application client; redirect URIs: "
                    "http://localhost:8001/oauth2callback and "
                    f"{_redirect_uri()}), then recreate: docker compose up -d --build"
                ),
            )

    # Persist a normalized URL so OAuth protected-resource metadata matches
    # (GitHub rejects .../mcp/ vs .../mcp mismatches).
    normalized = normalize_mcp_url(row.url)
    if normalized != row.url:
        factory = async_session_factory()
        async with factory() as session:
            db_row = await session.get(McpServer, row.id)
            if db_row is not None:
                db_row.url = normalized
                await session.commit()
                await session.refresh(db_row)
                row = db_row

    try:
        url = await mgr.start(row)
    except McpAuthError as exc:
        detail = str(exc)
        if row.preset == "google_workspace":
            detail = (
                f"{detail} Ensure workspace-mcp is running (docker compose --profile mcp up -d workspace-mcp) "
                "with MCP_ENABLE_OAUTH21=true and your Google OAuth client id/secret."
            )
        raise HTTPException(status_code=400, detail=detail) from exc
    state = ""
    pending = mgr._pending_by_server.get(str(row.id))
    if pending is not None:
        state = pending.state
    return McpConnectResponse(authorization_url=url, state=state)


@router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    if error:
        return HTMLResponse(_callback_html(ok=False, message=error), status_code=400)
    if not code or not state:
        return HTMLResponse(
            _callback_html(ok=False, message="Missing code or state."),
            status_code=400,
        )
    mgr = _oauth_manager(request)
    try:
        await mgr.deliver_callback(state, code)
    except McpAuthError as exc:
        return HTMLResponse(_callback_html(ok=False, message=str(exc)), status_code=400)
    return HTMLResponse(_callback_html(ok=True, message="Connected — you can close this window."))


@router.get("/servers/{server_id}/status", response_model=McpServerOut)
async def server_status(server_id: str, request: Request) -> McpServerOut:
    row = await _load_server(server_id)
    mgr = getattr(request.app.state, "mcp_oauth", None)
    connected = await _is_connected(row, mgr)
    return _to_out(row, connected=connected)


@router.get("/servers/{server_id}/tools", response_model=list[McpToolOut])
async def list_tools(server_id: str) -> list[McpToolOut]:
    row = await _load_server(server_id)
    try:
        auth = await build_mcp_auth(row, async_session_factory, redirect_uri=_redirect_uri())
        async with open_mcp_session(row.url, auth=auth) as session:
            result = await session.list_tools()
    except Exception as exc:
        logger.warning("mcp_list_tools_failed server_id=%s error=%s", server_id, exc)
        raise HTTPException(status_code=502, detail=f"Unable to list tools: {exc}") from exc

    tools = getattr(result, "tools", None) or []
    out: list[McpToolOut] = []
    for tool in tools:
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
        if hasattr(schema, "model_dump"):
            schema = schema.model_dump()
        out.append(
            McpToolOut(
                name=str(getattr(tool, "name", "")),
                description=str(getattr(tool, "description", "") or ""),
                input_schema=dict(schema) if isinstance(schema, dict) else {},
            )
        )
    return out


async def _load_server(server_id: str) -> McpServer:
    if server_id.startswith("preset:"):
        raise HTTPException(
            status_code=400,
            detail="Register the preset via POST /mcp/servers before connecting.",
        )
    try:
        sid = uuid.UUID(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="MCP server not found.") from exc
    factory = async_session_factory()
    async with factory() as session:
        row = await session.get(McpServer, sid)
        if row is None:
            raise HTTPException(status_code=404, detail="MCP server not found.")
        return row


def _callback_html(*, ok: bool, message: str) -> str:
    title = "Connected" if ok else "Connection failed"
    safe = escape(message)
    return (
        "<!DOCTYPE html><html><head><title>"
        f"{title}</title></head><body style='font-family:system-ui;padding:2rem'>"
        f"<h1>{title}</h1><p>{safe}</p>"
        "<script>window.setTimeout(()=>window.close(),1500)</script>"
        "</body></html>"
    )
