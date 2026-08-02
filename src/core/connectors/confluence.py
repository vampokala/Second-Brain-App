"""Confluence connector: index pages from a space."""

from __future__ import annotations

import base64
import re
from collections.abc import AsyncIterator

import httpx
from src.core.connectors.base import ConnectorError, SourceConnector, SourceItem

_PAGE_SIZE = 50
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def _html_to_text(html: str) -> str:
    """Cheap storage-format → text. Good enough for retrieval/embedding."""
    if not html:
        return ""
    text = html.replace("</p>", "\n\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = _TAG_RE.sub("", text)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    return _WS_RE.sub("\n\n", text).strip()


class ConfluenceConnector(SourceConnector):
    """``resource_id`` is the space key.

    config keys: ``base_url`` (e.g. https://acme.atlassian.net), ``email``.
    ``token`` is an Atlassian API token; auth is HTTP basic ``email:token``.
    """

    source_type = "confluence"

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
            raise ConnectorError("Confluence requires config.base_url.")
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.email and self.token:
            raw = f"{self.email}:{self.token}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(raw).decode()}"
        return headers

    def _make_client(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=30.0)

    async def test_connection(self) -> tuple[bool, str]:
        client = self._make_client()
        try:
            resp = await client.get(
                f"{self.base_url}/wiki/rest/api/space/{self.resource_id}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return True, f"Reachable space: {self.resource_id}"
            if resp.status_code in (401, 403):
                return False, "Authentication failed (check email/token)."
            if resp.status_code == 404:
                return False, "Space not found (check space key)."
            return False, f"Unexpected status {resp.status_code}."
        except httpx.HTTPError as exc:
            return False, f"Network error: {exc}"
        finally:
            if self._client is None:
                await client.aclose()

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        client = self._make_client()
        start = 0
        try:
            while True:
                params = {
                    "spaceKey": self.resource_id,
                    "expand": "body.storage,version",
                    "start": start,
                    "limit": _PAGE_SIZE,
                    "type": "page",
                }
                resp = await client.get(
                    f"{self.base_url}/wiki/rest/api/content",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    raise ConnectorError(f"Confluence content failed: {resp.status_code} {resp.text[:200]}")
                data = resp.json()
                results = data.get("results", [])
                for page in results:
                    version = page.get("version", {})
                    when = version.get("when", "")
                    # Client-side incremental filter (API lacks a simple 'since').
                    if since and when and when <= since:
                        continue
                    body = _html_to_text((page.get("body", {}).get("storage", {}) or {}).get("value", ""))
                    page_id = page.get("id", "")
                    yield SourceItem(
                        external_id=page_id,
                        title=page.get("title", ""),
                        body_markdown=body,
                        url=f"{self.base_url}/wiki/spaces/{self.resource_id}/pages/{page_id}",
                        updated_at=when,
                        author=(version.get("by") or {}).get("displayName"),
                        tags=["page"],
                    )
                start += len(results)
                if not results or start >= data.get("size", 0) + start and len(results) < _PAGE_SIZE:
                    break
                if len(results) < _PAGE_SIZE:
                    break
        finally:
            if self._client is None:
                await client.aclose()
