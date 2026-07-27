"""MCP Atlassian adapters: JIRA and Confluence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from src.core.connectors.base import SourceItem
from src.core.connectors.mcp_base import McpSourceConnector, as_list, dig, skip_malformed

# Tool names kept as constants so a rename is a one-line fix.
JIRA_SEARCH_TOOL = "jira_search"
CONFLUENCE_SEARCH_TOOL = "confluence_search"
CONFLUENCE_GET_TOOL = "confluence_get_page"


class McpJiraConnector(McpSourceConnector):
    """Sync JIRA issues through the Atlassian MCP server."""

    source_type = "mcp_jira"
    preset = "atlassian"
    required_tools: ClassVar[tuple[str, ...]] = (JIRA_SEARCH_TOOL,)

    def _build_jql(self, since: str | None) -> str:
        base = self.config.get("jql") or f"project = {self.resource_id}"
        extra = (self.config.get("jql_extra") or "").strip()
        if extra:
            base = f"({base}) AND ({extra})"
        if since:
            return f'({base}) AND updated >= "{since}" ORDER BY updated ASC'
        return f"({base}) ORDER BY updated ASC"

    def _to_item(self, raw: Any) -> SourceItem | None:
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "not_a_dict", raw)
            return None
        key = str(raw.get("key") or raw.get("id") or "").strip()
        fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else raw
        if not isinstance(fields, dict):
            fields = {}
        summary = str(fields.get("summary") or raw.get("summary") or key).strip()
        if not key:
            skip_malformed(self.source_type, "missing_key", raw)
            return None
        description = fields.get("description") or raw.get("description") or ""
        if isinstance(description, dict):
            description = str(description)
        updated = str(fields.get("updated") or raw.get("updated") or "").strip()
        if not updated:
            skip_malformed(self.source_type, "missing_updated", raw)
            return None
        status = dig(fields, "status.name") or fields.get("status") or ""
        issuetype = dig(fields, "issuetype.name") or fields.get("issuetype") or ""
        url = str(raw.get("url") or raw.get("self") or f"jira://{key}")
        author = dig(fields, "assignee.displayName") or dig(fields, "reporter.displayName")
        tags = [t for t in (str(status) if status else "", str(issuetype) if issuetype else "") if t]
        title = f"{key}: {summary}" if summary and summary != key else key
        body = f"{summary}\n\n{description}".strip()
        return SourceItem(
            external_id=key,
            title=title,
            body_markdown=body,
            url=url,
            updated_at=updated,
            author=str(author) if author else None,
            tags=tags,
        )

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        next_token: str | None = None
        async with await self._open() as session:
            while True:
                args: dict[str, Any] = {
                    "jql": self._build_jql(since),
                    "maxResults": int(self.config.get("page_size") or 50),
                }
                if next_token:
                    args["nextPageToken"] = next_token
                payload = await self._call(session, JIRA_SEARCH_TOOL, args)
                items = as_list(payload)
                for raw in items:
                    item = self._to_item(raw)
                    if item is not None:
                        yield item
                if isinstance(payload, dict):
                    next_token = payload.get("nextPageToken") or payload.get("next_page_token")
                    if next_token:
                        continue
                break


class McpConfluenceConnector(McpSourceConnector):
    """Sync Confluence pages through the Atlassian MCP server."""

    source_type = "mcp_confluence"
    preset = "atlassian"
    required_tools: ClassVar[tuple[str, ...]] = (CONFLUENCE_SEARCH_TOOL,)

    def _build_cql(self, since: str | None) -> str:
        base = f'space = "{self.resource_id}" AND type = page'
        if since:
            return f'{base} AND lastmodified >= "{since}" ORDER BY lastmodified ASC'
        return f"{base} ORDER BY lastmodified ASC"

    def _to_item(self, raw: Any, body: str = "") -> SourceItem | None:
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "not_a_dict", raw)
            return None
        page_id = str(raw.get("id") or "").strip()
        if not page_id and isinstance(raw.get("content"), dict):
            page_id = str(raw["content"].get("id") or "").strip()
        if not page_id:
            page_id = str(raw.get("page_id") or "").strip()
        title = str(raw.get("title") or dig(raw, "content.title") or page_id).strip()
        updated = str(
            raw.get("lastmodified")
            or raw.get("updated_at")
            or dig(raw, "version.when")
            or dig(raw, "history.lastUpdated.when")
            or ""
        ).strip()
        if not page_id or not updated:
            skip_malformed(self.source_type, "missing_id_or_updated", raw)
            return None
        url = str(raw.get("url") or raw.get("_links", {}).get("webui") or f"confluence://{page_id}")
        text = body or str(raw.get("body") or raw.get("excerpt") or raw.get("content_text") or "")
        return SourceItem(
            external_id=page_id,
            title=title or page_id,
            body_markdown=text,
            url=url,
            updated_at=updated,
            tags=["confluence", self.resource_id],
        )

    async def _enrich_page(self, session: Any, raw: Any) -> tuple[Any, str]:
        body = ""
        if not isinstance(raw, dict):
            return raw, body
        page_id = str(raw.get("id") or dig(raw, "content.id") or "")
        if not page_id:
            return raw, body
        try:
            detail = await self._call(session, CONFLUENCE_GET_TOOL, {"page_id": page_id})
        except Exception:
            skip_malformed(self.source_type, "get_page_failed", raw)
            return raw, body
        if not isinstance(detail, dict):
            return raw, body
        body = str(
            detail.get("body")
            or dig(detail, "body.storage.value")
            or detail.get("content")
            or ""
        )
        return {**raw, **detail}, body

    def _next_page_token(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        token = payload.get("cursor") or payload.get("next") or payload.get("nextPageToken")
        return str(token) if token else None

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        next_token: str | None = None
        async with await self._open() as session:
            while True:
                args: dict[str, Any] = {
                    "query": self._build_cql(since),
                    "limit": int(self.config.get("page_size") or 25),
                }
                if next_token:
                    args["cursor"] = next_token
                payload = await self._call(session, CONFLUENCE_SEARCH_TOOL, args)
                for raw in as_list(payload):
                    enriched, body = await self._enrich_page(session, raw)
                    item = self._to_item(enriched, body=body)
                    if item is not None:
                        yield item
                next_token = self._next_page_token(payload)
                if not next_token:
                    break
