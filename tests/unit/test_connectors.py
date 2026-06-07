"""Unit tests for the source-connector layer (mocked HTTP, no network)."""

from __future__ import annotations

import json

import httpx
import pytest
from src.core.connectors.base import SourceItem
from src.core.connectors.confluence import _html_to_text
from src.core.connectors.github import GitHubConnector
from src.core.connectors.jira import _adf_to_text, _to_jira_time
from src.core.connectors.registry import (
    DEFAULT_TOKEN_ENV,
    build_connector,
    resolve_token,
    sync_connector,
)
from src.core.connectors.slack import SlackConnector, _clean


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def ingest_text(self, relpath: str, body: str):
        self.calls.append((relpath, body))
        return {"path": relpath, "status": "ingested"}


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_source_item_markdown_and_relpath():
    item = SourceItem(
        external_id="abc123",
        title="Fix login bug",
        body_markdown="Resolved the null pointer in auth.",
        url="https://example.com/abc123",
        updated_at="2024-01-02T03:04:05Z",
        author="Jane",
        tags=["commit"],
    )
    rel = item.relpath("github", "acme/repo")
    assert rel == "raw/connectors/github/acme_repo/abc123.md"
    md = item.to_markdown("github")
    assert "source: github" in md
    assert "external_id: abc123" in md
    assert "source_url: https://example.com/abc123" in md
    assert "# Fix login bug" in md
    assert "Resolved the null pointer" in md


@pytest.mark.asyncio
async def test_github_fetch_commits_maps_and_orders():
    commits = [
        {
            "sha": "newer",
            "html_url": "https://gh/commit/newer",
            "commit": {
                "message": "Second commit\n\nbody",
                "author": {"name": "Bob", "date": "2024-02-01T00:00:00Z"},
            },
        },
        {
            "sha": "older",
            "html_url": "https://gh/commit/older",
            "commit": {
                "message": "First commit",
                "author": {"name": "Ann", "date": "2024-01-01T00:00:00Z"},
            },
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/repos/acme/repo/commits" in str(request.url)
        return httpx.Response(200, json=commits)

    conn = GitHubConnector("acme/repo", {}, token="t", client=_mock_client(handler))
    items = [i async for i in conn.fetch(None)]
    # newest-first input must be emitted ascending by updated_at
    assert [i.external_id for i in items] == ["older", "newer"]
    assert items[0].title == "First commit"
    assert items[1].title == "Second commit"


@pytest.mark.asyncio
async def test_sync_connector_advances_cursor_and_ingests():
    commits = [
        {
            "sha": "s1",
            "html_url": "u1",
            "commit": {"message": "m1", "author": {"name": "A", "date": "2024-01-01T00:00:00Z"}},
        },
        {
            "sha": "s2",
            "html_url": "u2",
            "commit": {"message": "m2", "author": {"name": "B", "date": "2024-03-01T00:00:00Z"}},
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=commits)

    pipeline = FakePipeline()
    result = await sync_connector(
        connector_type="github",
        resource_id="acme/repo",
        config={},
        cursor=None,
        pipeline=pipeline,
        token="t",
        client=_mock_client(handler),
    )
    assert result.status == "ok"
    assert result.item_count == 2
    assert result.cursor["since"] == "2024-03-01T00:00:00Z"
    assert len(pipeline.calls) == 2
    assert pipeline.calls[0][0] == "raw/connectors/github/acme_repo/s1.md"


@pytest.mark.asyncio
async def test_sync_connector_reports_failure_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="rate limited")

    pipeline = FakePipeline()
    result = await sync_connector(
        connector_type="github",
        resource_id="acme/repo",
        config={},
        cursor=None,
        pipeline=pipeline,
        token=None,
        client=_mock_client(handler),
    )
    assert result.status == "failed"
    assert result.item_count == 0
    assert pipeline.calls == []


@pytest.mark.asyncio
async def test_github_test_connection_states():
    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"full_name": "acme/repo"})

    conn = GitHubConnector("acme/repo", {}, client=_mock_client(ok_handler))
    ok, _ = await conn.test_connection()
    assert ok is True

    def notfound(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    conn2 = GitHubConnector("acme/repo", {}, client=_mock_client(notfound))
    ok2, msg2 = await conn2.test_connection()
    assert ok2 is False
    assert "not found" in msg2.lower()


def test_jira_adf_and_time_helpers():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "World"}]},
        ],
    }
    assert "Hello" in _adf_to_text(adf)
    assert "World" in _adf_to_text(adf)
    assert _adf_to_text("plain") == "plain"
    assert _to_jira_time("2024-01-02T03:04:05.000+0000") == "2024-01-02 03:04"
    assert _to_jira_time(None) is None


def test_confluence_html_to_text():
    html = "<p>Hello &amp; welcome</p><p>Second &lt;line&gt;</p>"
    text = _html_to_text(html)
    assert "Hello & welcome" in text
    assert "Second <line>" in text
    assert "<p>" not in text


def test_registry_build_and_token_resolution(monkeypatch):
    assert DEFAULT_TOKEN_ENV["github"] == "GITHUB_TOKEN"
    monkeypatch.setenv("GITHUB_TOKEN", "secret-pat")
    assert resolve_token("github", {}) == "secret-pat"
    monkeypatch.setenv("MY_CUSTOM", "xyz")
    assert resolve_token("github", {"token_env": "MY_CUSTOM"}) == "xyz"
    conn = build_connector("github", "acme/repo", {}, "t")
    assert conn.source_type == "github"


def test_build_connector_unknown_type_raises():
    with pytest.raises(Exception):
        build_connector("telegram", "x", {}, None)


def test_slack_clean_unwraps_links_and_channels():
    assert _clean("see <https://x.com|the docs>") == "see the docs"
    assert _clean("raw <https://x.com>") == "raw https://x.com"
    assert _clean("in <#C1|general> now") == "in #general now"


@pytest.mark.asyncio
async def test_slack_fetch_messages_with_thread_replies():
    history = {
        "ok": True,
        "messages": [
            {
                "ts": "1700000002.0001",
                "user": "U1",
                "text": "Parent msg",
                "thread_ts": "1700000002.0001",
                "reply_count": 2,
            },
            {"ts": "1700000001.0001", "user": "U2", "text": "Standalone"},
        ],
        "response_metadata": {"next_cursor": ""},
    }
    replies = {
        "ok": True,
        "messages": [
            {"ts": "1700000002.0001", "user": "U1", "text": "Parent msg"},
            {"ts": "1700000002.0100", "user": "U3", "text": "First reply"},
            {"ts": "1700000002.0200", "user": "U4", "text": "Second reply"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("conversations.history"):
            return httpx.Response(200, json=history)
        if path.endswith("conversations.replies"):
            return httpx.Response(200, json=replies)
        return httpx.Response(404, json={"ok": False, "error": "not_found"})

    conn = SlackConnector(
        "C1", {"workspace_url": "https://acme.slack.com"}, token="xoxb-x", client=_mock_client(handler)
    )
    items = [i async for i in conn.fetch(None)]
    assert len(items) == 2
    parent = next(i for i in items if i.external_id == "1700000002.0001")
    assert "First reply" in parent.body_markdown
    assert "Second reply" in parent.body_markdown
    assert parent.tags == ["thread"]
    assert parent.url == "https://acme.slack.com/archives/C1/p17000000020001"
    assert parent.relpath("slack", "C1") == "raw/connectors/slack/C1/1700000002.0001.md"


@pytest.mark.asyncio
async def test_slack_history_error_raises_in_sync():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "channel_not_found"})

    pipeline = FakePipeline()
    result = await sync_connector(
        connector_type="slack",
        resource_id="C1",
        config={},
        cursor=None,
        pipeline=pipeline,
        token="xoxb-x",
        client=_mock_client(handler),
    )
    assert result.status == "failed"
    assert "channel_not_found" in (result.error or "")


@pytest.mark.asyncio
async def test_slack_test_connection_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "team": "Acme", "user": "bot"})

    conn = SlackConnector("C1", {}, token="xoxb-x", client=_mock_client(handler))
    ok, msg = await conn.test_connection()
    assert ok is True
    assert "Acme" in msg


def test_jira_search_json_shape_is_serializable():
    # guard: ensure our fixture-style dicts round-trip (sanity for CI mocks)
    payload = {"jql": "project = X", "issues": []}
    assert json.loads(json.dumps(payload))["jql"] == "project = X"
