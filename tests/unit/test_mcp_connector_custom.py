"""Unit tests for MCP custom + GitHub + Gmail connectors."""

# ruff: noqa: E501

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from src.core.connectors.base import ConnectorError
from src.core.connectors.mcp_custom import McpCustomConnector
from src.core.connectors.mcp_github import McpGitHubConnector
from src.core.connectors.mcp_google import McpGmailConnector
from src.core.connectors.registry import CONNECTOR_TYPES, build_connector
from src.core.mcp.servers import PRESETS


def _server():
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000099",
        url="https://mcp.example/mcp",
        auth_mode="none",
        token_env=None,
    )


def _opener(payload):
    class Session:
        async def list_tools(self):
            return SimpleNamespace(
                tools=[SimpleNamespace(name="list_commits"), SimpleNamespace(name="search_gmail_messages")]
            )

        async def call_tool(self, name, args):
            return SimpleNamespace(structuredContent=payload, isError=False, content=[])

    @asynccontextmanager
    async def open_session(_url, auth=None):
        yield Session()

    return open_session


@pytest.mark.asyncio
async def test_github_fetch_maps_commits(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        return {
            "commits": [
                {
                    "sha": "abc",
                    "html_url": "u",
                    "commit": {
                        "message": "Hello\n\nbody",
                        "author": {"name": "Ann", "date": "2024-01-02T00:00:00Z"},
                    },
                }
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    conn = McpGitHubConnector(
        "acme/repo",
        {"server_id": "x"},
        server=_server(),
        session_opener=_opener({}),
        session_factory=lambda: None,
    )
    items = [i async for i in conn.fetch(None)]
    assert items[0].external_id == "abc"
    assert items[0].title == "Hello"


@pytest.mark.asyncio
async def test_gmail_fetch_builds_after_query(monkeypatch):
    captured = {}

    async def fake_call(session, tool, args, timeout_s=60.0):
        captured.update(args)
        return {
            "messages": [
                {
                    "id": "m1",
                    "subject": "Hi",
                    "snippet": "body",
                    "internalDate": "1704067200000",
                }
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    conn = McpGmailConnector(
        "label:starred",
        {"server_id": "x"},
        server=_server(),
        session_opener=_opener({}),
        session_factory=lambda: None,
    )
    items = [i async for i in conn.fetch({"since": "2024-01-01T00:00:00Z"})]
    assert "after:2024/01/01" in captured["query"]
    assert items[0].external_id == "m1"


@pytest.mark.asyncio
async def test_fetch_maps_items_via_field_map(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        return {
            "results": [
                {
                    "nid": "1",
                    "name": "Title",
                    "text": "Body",
                    "link": "http://x",
                    "when": "2024-01-01T00:00:00Z",
                }
            ]
        }

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    conn = McpCustomConnector(
        "res",
        {
            "server_id": "x",
            "tool_name": "search",
            "tool_args": {"q": "{since}"},
            "items_path": "results",
            "field_map": {
                "id": "nid",
                "title": "name",
                "body": "text",
                "url": "link",
                "updated_at": "when",
            },
        },
        server=_server(),
        session_opener=_opener({}),
        session_factory=lambda: None,
    )
    items = [i async for i in conn.fetch({"since": "2024-01-01"})]
    assert items[0].external_id == "1"
    assert items[0].title == "Title"


@pytest.mark.asyncio
async def test_fetch_substitutes_since_placeholder_in_args(monkeypatch):
    captured = {}

    async def fake_call(session, tool, args, timeout_s=60.0):
        captured.update(args)
        return []

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    conn = McpCustomConnector(
        "res",
        {"server_id": "x", "tool_name": "search", "tool_args": {"q": "after:{since}"}},
        server=_server(),
        session_opener=_opener({}),
        session_factory=lambda: None,
    )
    _ = [i async for i in conn.fetch({"since": "S"})]
    assert captured["q"] == "after:S"


@pytest.mark.asyncio
async def test_fetch_wraps_plain_string_result_as_single_item(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        return "hello world"

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    conn = McpCustomConnector(
        "res",
        {"server_id": "x", "tool_name": "echo", "tool_args": {}},
        server=_server(),
        session_opener=_opener({}),
        session_factory=lambda: None,
    )
    items = [i async for i in conn.fetch(None)]
    assert len(items) == 1
    assert "hello world" in items[0].body_markdown


@pytest.mark.asyncio
async def test_fetch_raises_connector_error_when_items_path_missing(monkeypatch):
    async def fake_call(session, tool, args, timeout_s=60.0):
        return {"other": []}

    monkeypatch.setattr("src.core.connectors.mcp_base.call_tool_json", fake_call)

    async def _no_auth(*a, **k):
        return None

    monkeypatch.setattr("src.core.connectors.mcp_base.build_mcp_auth", _no_auth)
    conn = McpCustomConnector(
        "res",
        {
            "server_id": "x",
            "tool_name": "search",
            "tool_args": {},
            "items_path": "missing.path",
        },
        server=_server(),
        session_opener=_opener({}),
        session_factory=lambda: None,
    )
    with pytest.raises(ConnectorError, match="items_path"):
        _ = [i async for i in conn.fetch(None)]


def test_all_mcp_types_registered_in_connector_types():
    for key in ("mcp_jira", "mcp_confluence", "mcp_github", "mcp_gmail", "mcp_gchat", "mcp_custom"):
        assert key in CONNECTOR_TYPES


def test_build_connector_constructs_mcp_type_without_token():
    conn = build_connector("mcp_custom", "r", {"tool_name": "t", "server_id": "s"})
    assert conn.source_type == "mcp_custom"


def test_legacy_types_still_registered():
    for key in ("github", "jira", "confluence", "slack"):
        assert key in CONNECTOR_TYPES


def test_presets_have_urls_except_custom_and_ghes():
    for key, preset in PRESETS.items():
        if key in {"custom", "github_enterprise"}:
            assert preset.url is None
        else:
            assert preset.url


def test_github_preset_url_has_no_trailing_slash(monkeypatch):
    """Trailing slash breaks GitHub OAuth protected-resource metadata matching."""
    from src.core.mcp.servers import normalize_mcp_url, resolve_preset_url

    monkeypatch.delenv("GITHUB_MCP_URL", raising=False)
    assert not PRESETS["github"].url.endswith("/")
    assert resolve_preset_url("github") == "https://api.githubcopilot.com/mcp"
    assert normalize_mcp_url("https://api.githubcopilot.com/mcp/") == ("https://api.githubcopilot.com/mcp")


def test_github_enterprise_preset_resolves_mcp_url_from_env(monkeypatch):
    from src.core.mcp.servers import resolve_preset_url

    monkeypatch.delenv("GITHUB_MCP_URL", raising=False)
    assert resolve_preset_url("github_enterprise") is None
    monkeypatch.setenv("GITHUB_MCP_URL", "http://ghes-mcp:8080/mcp")
    assert resolve_preset_url("github_enterprise") == "http://ghes-mcp:8080/mcp"
    assert resolve_preset_url("github_enterprise", "http://override/mcp") == "http://override/mcp"


def test_preset_connector_types_all_exist_in_registry():
    for preset in PRESETS.values():
        for ctype in preset.connector_types:
            assert ctype in CONNECTOR_TYPES


def test_google_workspace_preset_uses_oauth():
    preset = PRESETS["google_workspace"]
    assert preset.auth_modes == ("oauth",)
    assert "mcp_gmail" in preset.connector_types


def test_atlassian_preset_uses_rovo_tool_names():
    tools = PRESETS["atlassian"].required_tools
    assert "searchJiraIssuesUsingJql" in tools
    assert "searchConfluenceUsingCql" in tools
    assert "jira_search" not in tools
