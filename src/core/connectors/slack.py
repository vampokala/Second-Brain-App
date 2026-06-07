"""Slack connector: index channel messages (and thread replies)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import httpx
from src.core.connectors.base import ConnectorError, SourceConnector, SourceItem

_API = "https://slack.com/api"
_PAGE = 200
# <http://x|label> -> label ; <http://x> -> http://x ; <@U123>/<#C1|name> left readable
_LINK_RE = re.compile(r"<(https?://[^|>]+)\|([^>]+)>")
_BARE_LINK_RE = re.compile(r"<(https?://[^>]+)>")
_CHAN_RE = re.compile(r"<#[A-Z0-9]+\|([^>]+)>")


def _clean(text: str) -> str:
    if not text:
        return ""
    text = _LINK_RE.sub(r"\2", text)
    text = _BARE_LINK_RE.sub(r"\1", text)
    text = _CHAN_RE.sub(r"#\1", text)
    return text.strip()


class SlackConnector(SourceConnector):
    """``resource_id`` is a Slack channel ID (e.g. ``C0123ABC``).

    config keys: ``base_url`` (default api.slack.com), ``include_threads`` (bool,
    default True), ``workspace_url`` (optional, for building permalinks).
    ``token`` is a Slack **bot token** (``xoxb-…``) with ``channels:history`` and
    ``channels:read`` scopes; auth is ``Authorization: Bearer``.
    """

    source_type = "slack"

    def __init__(
        self,
        resource_id: str,
        config: dict,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(resource_id, config, token)
        self.base_url = (config.get("base_url") or _API).rstrip("/")
        self.workspace_url = (config.get("workspace_url") or "").rstrip("/")
        self.include_threads = config.get("include_threads", True)
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _make_client(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=30.0)

    def _permalink(self, ts: str) -> str:
        if not self.workspace_url:
            return ""
        return f"{self.workspace_url}/archives/{self.resource_id}/p{ts.replace('.', '')}"

    async def test_connection(self) -> tuple[bool, str]:
        client = self._make_client()
        try:
            resp = await client.get(f"{self.base_url}/auth.test", headers=self._headers())
            data = resp.json() if resp.status_code == 200 else {}
            if data.get("ok"):
                return True, f"Authenticated to {data.get('team', 'workspace')}"
            return False, f"Slack auth failed: {data.get('error') or resp.status_code}"
        except httpx.HTTPError as exc:
            return False, f"Network error: {exc}"
        finally:
            if self._client is None:
                await client.aclose()

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")  # Slack ts of the newest item last seen
        client = self._make_client()
        next_cursor: str | None = None
        try:
            while True:
                params: dict[str, object] = {"channel": self.resource_id, "limit": _PAGE}
                if since:
                    params["oldest"] = since
                if next_cursor:
                    params["cursor"] = next_cursor
                resp = await client.get(
                    f"{self.base_url}/conversations.history",
                    params=params,
                    headers=self._headers(),
                )
                data = resp.json() if resp.status_code == 200 else {}
                if not data.get("ok"):
                    raise ConnectorError(f"Slack history failed: {data.get('error') or resp.status_code}")
                for msg in data.get("messages", []):
                    if msg.get("subtype") and not msg.get("text"):
                        continue
                    item = await self._build_item(client, msg)
                    if item is not None:
                        yield item
                next_cursor = (data.get("response_metadata") or {}).get("next_cursor")
                if not next_cursor:
                    break
        finally:
            if self._client is None:
                await client.aclose()

    async def _build_item(self, client: httpx.AsyncClient, msg: dict) -> SourceItem | None:
        ts = msg.get("ts", "")
        if not ts:
            return None
        text = _clean(msg.get("text", ""))
        author = msg.get("user") or msg.get("username")
        body_parts = [text]

        is_thread_parent = msg.get("thread_ts") == ts and int(msg.get("reply_count") or 0) > 0
        if self.include_threads and is_thread_parent:
            replies = await self._fetch_replies(client, ts)
            for r in replies:
                r_text = _clean(r.get("text", ""))
                r_author = r.get("user") or r.get("username") or "unknown"
                if r_text:
                    body_parts.append(f"\n↳ reply by {r_author}: {r_text}")

        body = "\n".join(p for p in body_parts if p).strip()
        if not body:
            return None
        title = (text.splitlines()[0] if text else f"message {ts}")[:80]
        return SourceItem(
            external_id=ts,
            title=title,
            body_markdown=body,
            url=self._permalink(ts),
            updated_at=ts,  # Slack ts; lexicographically comparable for the cursor
            author=author,
            tags=["thread" if is_thread_parent else "message"],
        )

    async def _fetch_replies(self, client: httpx.AsyncClient, thread_ts: str) -> list[dict]:
        resp = await client.get(
            f"{self.base_url}/conversations.replies",
            params={"channel": self.resource_id, "ts": thread_ts, "limit": _PAGE},
            headers=self._headers(),
        )
        data = resp.json() if resp.status_code == 200 else {}
        if not data.get("ok"):
            return []
        # First element is the parent message; replies follow.
        return list(data.get("messages", [])[1:])
