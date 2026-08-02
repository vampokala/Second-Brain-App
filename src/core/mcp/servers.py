"""Preset MCP server registry."""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.core.connectors.github_host import resolve_github_mcp_url


@dataclass(frozen=True, slots=True)
class McpPreset:
    """Built-in MCP server catalog entry."""

    key: str
    label: str
    url: str | None
    auth_modes: tuple[str, ...]
    connector_types: tuple[str, ...]
    required_tools: tuple[str, ...]


def _workspace_mcp_url() -> str:
    # Prefer a host the browser can follow for OAuth (published port), not the
    # internal docker DNS name which Google/users cannot open.
    return (os.getenv("WORKSPACE_MCP_URL") or "http://host.docker.internal:8001/mcp").rstrip("/")


PRESETS: dict[str, McpPreset] = {
    "atlassian": McpPreset(
        key="atlassian",
        label="Atlassian (JIRA + Confluence)",
        url="https://mcp.atlassian.com/v1/mcp/authv2",
        auth_modes=("oauth", "token"),
        connector_types=("mcp_jira", "mcp_confluence"),
        required_tools=("searchJiraIssuesUsingJql", "searchConfluenceUsingCql"),
    ),
    "github": McpPreset(
        key="github",
        label="GitHub",
        # Default: Copilot remote MCP. Override with GITHUB_MCP_URL for a
        # self-hosted github-mcp-server (required for GitHub Enterprise Server).
        url="https://api.githubcopilot.com/mcp",
        auth_modes=("oauth", "token"),
        connector_types=("mcp_github",),
        required_tools=("list_commits",),
    ),
    "github_enterprise": McpPreset(
        key="github_enterprise",
        label="GitHub Enterprise (self-hosted MCP)",
        # No default remote URL — GHES cannot use api.githubcopilot.com.
        # Set GITHUB_MCP_URL or pass url on upsert (local github-mcp-server).
        url=None,
        auth_modes=("token", "oauth"),
        connector_types=("mcp_github",),
        required_tools=("list_commits",),
    ),
    "google_workspace": McpPreset(
        key="google_workspace",
        label="Google Workspace (Gmail + Chat)",
        url=_workspace_mcp_url(),
        # MCP OAuth 2.1 against workspace-mcp opens the Google consent screen.
        auth_modes=("oauth",),
        connector_types=("mcp_gmail", "mcp_gchat"),
        required_tools=("search_gmail_messages", "get_messages"),
    ),
    "custom": McpPreset(
        key="custom",
        label="Custom MCP server",
        url=None,
        auth_modes=("oauth", "token", "none"),
        connector_types=("mcp_custom",),
        required_tools=(),
    ),
}


def resolve_preset_url(preset_key: str, override: str | None = None) -> str | None:
    """Return the effective MCP URL for a preset, preferring an explicit override.

    Trailing slashes are stripped so the URL matches OAuth protected-resource
    metadata (required for GitHub remote MCP).
    """
    if override:
        return override.rstrip("/")
    preset = PRESETS.get(preset_key)
    if preset is None:
        return None
    if preset.key == "google_workspace":
        return _workspace_mcp_url()
    if preset.key == "github":
        return resolve_github_mcp_url(preset.url)
    if preset.key == "github_enterprise":
        # Prefer GITHUB_MCP_URL; otherwise None until the user supplies a URL.
        return resolve_github_mcp_url(None) if (os.getenv("GITHUB_MCP_URL") or "").strip() else None
    if preset.url is None:
        return None
    return preset.url.rstrip("/")


def normalize_mcp_url(url: str) -> str:
    """Normalize an MCP endpoint URL (strip trailing slash)."""
    return (url or "").rstrip("/")
