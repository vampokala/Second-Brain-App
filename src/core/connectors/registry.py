"""Connector registry + sync orchestrator.

The orchestrator streams a connector's items through the existing
``IngestPipeline.ingest_text`` so every synced record becomes a first-class,
retrievable, citable document.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

from src.core.connectors.base import ConnectorError, SourceConnector
from src.core.connectors.confluence import ConfluenceConnector
from src.core.connectors.github import GitHubConnector
from src.core.connectors.jira import JiraConnector
from src.core.connectors.mcp_atlassian import McpConfluenceConnector, McpJiraConnector
from src.core.connectors.mcp_custom import McpCustomConnector
from src.core.connectors.mcp_github import McpGitHubConnector
from src.core.connectors.mcp_google import McpGChatConnector, McpGmailConnector
from src.core.connectors.slack import SlackConnector

logger = logging.getLogger(__name__)

CONNECTOR_TYPES: dict[str, type[SourceConnector]] = {
    "github": GitHubConnector,
    "jira": JiraConnector,
    "confluence": ConfluenceConnector,
    "slack": SlackConnector,
    "mcp_jira": McpJiraConnector,
    "mcp_confluence": McpConfluenceConnector,
    "mcp_github": McpGitHubConnector,
    "mcp_gmail": McpGmailConnector,
    "mcp_gchat": McpGChatConnector,
    "mcp_custom": McpCustomConnector,
}

DEFAULT_TOKEN_ENV: dict[str, str] = {
    "github": "GITHUB_TOKEN",
    "jira": "JIRA_API_TOKEN",
    "confluence": "CONFLUENCE_API_TOKEN",
    "slack": "SLACK_BOT_TOKEN",
}


class _Pipeline(Protocol):
    async def ingest_text(self, relpath: str, body: str): ...


@dataclass(slots=True)
class SyncResult:
    status: str  # "ok" | "failed"
    item_count: int
    cursor: dict
    error: str | None = None


def resolve_token(connector_type: str, config: dict) -> str | None:
    """Read the secret from the env var named by config (never persisted)."""
    env_name = (config or {}).get("token_env") or DEFAULT_TOKEN_ENV.get(connector_type)
    if not env_name:
        return None
    return os.getenv(env_name) or None


def build_connector(
    connector_type: str,
    resource_id: str,
    config: dict,
    token: str | None = None,
    client=None,
) -> SourceConnector:
    cls = CONNECTOR_TYPES.get(connector_type)
    if cls is None:
        raise ConnectorError(f"Unknown connector type: {connector_type!r}")
    return cls(resource_id, config or {}, token, client=client)  # type: ignore[call-arg]


async def sync_connector(
    *,
    connector_type: str,
    resource_id: str,
    config: dict,
    cursor: dict | None,
    pipeline: _Pipeline,
    token: str | None = None,
    on_progress=None,
    client=None,
) -> SyncResult:
    """Fetch items since ``cursor`` and ingest each one; advance the cursor."""
    connector = build_connector(connector_type, resource_id, config, token, client=client)
    cursor = dict(cursor or {})
    max_ts: str | None = cursor.get("since")
    count = 0
    try:
        async for item in connector.fetch(cursor):
            relpath = item.relpath(connector_type, resource_id)
            await pipeline.ingest_text(relpath, item.to_markdown(connector_type))
            count += 1
            if item.updated_at and (max_ts is None or item.updated_at > max_ts):
                max_ts = item.updated_at
            if on_progress is not None:
                on_progress(count, item)
    except ConnectorError as exc:
        logger.warning("connector sync failed (%s/%s): %s", connector_type, resource_id, exc)
        return SyncResult(status="failed", item_count=count, cursor=cursor, error=str(exc))
    except Exception as exc:
        logger.exception("connector sync error (%s/%s)", connector_type, resource_id)
        return SyncResult(status="failed", item_count=count, cursor=cursor, error=str(exc))

    new_cursor = {**cursor, "since": max_ts} if max_ts else cursor
    return SyncResult(status="ok", item_count=count, cursor=new_cursor)
