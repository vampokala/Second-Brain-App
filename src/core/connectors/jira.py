"""JIRA connector: index issues matching a JQL query."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator

import httpx
from src.core.connectors.base import ConnectorError, SourceConnector, SourceItem

_PAGE_SIZE = 50


def _adf_to_text(node: object) -> str:
    """Flatten Atlassian Document Format (or plain string) to text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("text", ""))
        parts = [_adf_to_text(c) for c in node.get("content", [])]
        sep = "\n" if node.get("type") in {"paragraph", "heading", "listItem"} else ""
        return sep.join(p for p in parts if p)
    if isinstance(node, list):
        return "\n".join(_adf_to_text(c) for c in node)
    return ""


class JiraConnector(SourceConnector):
    """``resource_id`` is a friendly label (e.g. project key).

    config keys: ``base_url`` (e.g. https://acme.atlassian.net), ``email``,
    ``jql`` (defaults to ``project = <resource_id>``). ``token`` is an Atlassian
    API token; auth is HTTP basic ``email:token``.
    """

    source_type = "jira"

    def __init__(
        self,
        resource_id: str,
        config: dict,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(resource_id, config, token)
        self.base_url = (config.get("base_url") or "").rstrip("/")
        self.email = config.get("email", "")
        if not self.base_url:
            raise ConnectorError("JIRA requires config.base_url.")
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.email and self.token:
            raw = f"{self.email}:{self.token}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(raw).decode()}"
        return headers

    def _make_client(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=30.0)

    def _jql(self, since: str | None) -> str:
        base = self.config.get("jql") or f"project = {self.resource_id}"
        if since:
            return f"({base}) AND updated >= '{since}' ORDER BY updated ASC"
        return f"({base}) ORDER BY updated ASC"

    async def test_connection(self) -> tuple[bool, str]:
        client = self._make_client()
        try:
            resp = await client.get(f"{self.base_url}/rest/api/3/myself", headers=self._headers())
            if resp.status_code == 200:
                name = resp.json().get("displayName", "user")
                return True, f"Authenticated as {name}"
            return False, f"Auth failed (status {resp.status_code})."
        except httpx.HTTPError as exc:
            return False, f"Network error: {exc}"
        finally:
            if self._client is None:
                await client.aclose()

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        # JIRA expects 'yyyy/MM/dd HH:mm' for updated; we store/compare ISO and
        # let the server filter loosely, then dedupe by stable relpath on ingest.
        since = (cursor or {}).get("since")
        client = self._make_client()
        start_at = 0
        try:
            while True:
                payload = {
                    "jql": self._jql(_to_jira_time(since)),
                    "startAt": start_at,
                    "maxResults": _PAGE_SIZE,
                    "fields": ["summary", "description", "updated", "reporter", "status", "issuetype"],
                }
                resp = await client.post(
                    f"{self.base_url}/rest/api/3/search",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    raise ConnectorError(f"JIRA search failed: {resp.status_code} {resp.text[:200]}")
                data = resp.json()
                issues = data.get("issues", [])
                for issue in issues:
                    fields = issue.get("fields", {})
                    key = issue.get("key", "")
                    status = (fields.get("status") or {}).get("name", "")
                    issue_type = (fields.get("issuetype") or {}).get("name", "")
                    body = _adf_to_text(fields.get("description"))
                    yield SourceItem(
                        external_id=key,
                        title=f"{key}: {fields.get('summary', '')}",
                        body_markdown=f"**Status:** {status}\n\n{body}",
                        url=f"{self.base_url}/browse/{key}",
                        updated_at=fields.get("updated", ""),
                        author=(fields.get("reporter") or {}).get("displayName"),
                        tags=[t for t in [issue_type.lower()] if t],
                    )
                start_at += len(issues)
                if not issues or start_at >= data.get("total", 0):
                    break
        finally:
            if self._client is None:
                await client.aclose()


def _to_jira_time(iso: str | None) -> str | None:
    if not iso:
        return None
    # ' 2024-01-02T03:04:05.000+0000' -> '2024-01-02 03:04'
    cleaned = iso.replace("T", " ")
    return cleaned[:16]
