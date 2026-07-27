"""Preset MCP server registry."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
    return (os.getenv("WORKSPACE_MCP_URL") or "http://workspace-mcp:8000/mcp").rstrip("/")


PRESETS: dict[str, McpPreset] = {
    "atlassian": McpPreset(
        key="atlassian",
        label="Atlassian (JIRA + Confluence)",
        url="https://mcp.atlassian.com/v1/mcp/authv2",
        auth_modes=("oauth", "token"),
        connector_types=("mcp_jira", "mcp_confluence"),
        required_tools=("jira_search", "confluence_search"),
    ),
    "github": McpPreset(
        key="github",
        label="GitHub",
        # No trailing slash — must match OAuth protected-resource metadata
        # (https://api.githubcopilot.com/.well-known/oauth-protected-resource/mcp).
        url="https://api.githubcopilot.com/mcp",
        auth_modes=("oauth", "token"),
        connector_types=("mcp_github",),
        required_tools=("list_commits",),
    ),
    "google_workspace": McpPreset(
        key="google_workspace",
        label="Google Workspace (Gmail + Chat)",
        url=_workspace_mcp_url(),
        auth_modes=("none",),
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
    if preset.url is None:
        return None
    return preset.url.rstrip("/")


def normalize_mcp_url(url: str) -> str:
    """Normalize an MCP endpoint URL (strip trailing slash)."""
    return (url or "").rstrip("/")
