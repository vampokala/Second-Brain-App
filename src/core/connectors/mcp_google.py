"""MCP Google Workspace adapters: Gmail and Google Chat."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar

from src.core.connectors.base import SourceItem
from src.core.connectors.mcp_base import McpSourceConnector, as_list, dig, skip_malformed

GMAIL_SEARCH_TOOL = "search_gmail_messages"
GMAIL_GET_TOOL = "get_gmail_message_content"
GCHAT_MESSAGES_TOOL = "get_messages"


def _since_to_gmail_after(since: str | None) -> str | None:
    if not since:
        return None
    try:
        dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        return dt.strftime("%Y/%m/%d")
    except ValueError:
        return since[:10].replace("-", "/") if len(since) >= 10 else None


class McpGmailConnector(McpSourceConnector):
    """Sync Gmail messages matching a query/label through workspace-mcp."""

    source_type = "mcp_gmail"
    preset = "google_workspace"
    required_tools: ClassVar[tuple[str, ...]] = (GMAIL_SEARCH_TOOL,)

    def _build_query(self, since: str | None) -> str:
        base = (self.resource_id or "").strip() or "in:inbox"
        after = _since_to_gmail_after(since)
        if after:
            return f"{base} after:{after}"
        return base

    def _to_item(self, raw: Any) -> SourceItem | None:
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "not_a_dict", raw)
            return None
        msg_id = str(raw.get("id") or raw.get("message_id") or "").strip()
        subject = str(raw.get("subject") or raw.get("title") or "(no subject)").strip()
        updated = str(raw.get("internalDate") or raw.get("date") or raw.get("updated_at") or "").strip()
        # Gmail internalDate is often epoch ms
        if updated.isdigit():
            try:
                ms = int(updated)
                if ms > 10_000_000_000:
                    ms //= 1000
                updated = datetime.fromtimestamp(ms, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, OSError):
                skip_malformed(self.source_type, "bad_internal_date", raw)
                return None
        if not msg_id or not updated:
            skip_malformed(self.source_type, "missing_id_or_date", raw)
            return None
        body = str(raw.get("body") or raw.get("snippet") or raw.get("text") or "")
        url = str(raw.get("url") or f"https://mail.google.com/mail/u/0/#inbox/{msg_id}")
        author = str(raw.get("from") or dig(raw, "payload.headers.from") or "") or None
        return SourceItem(
            external_id=msg_id,
            title=subject,
            body_markdown=body,
            url=url,
            updated_at=updated,
            author=author,
            tags=["gmail"],
        )

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        query = self._build_query(since)
        async with await self._open() as session:
            payload = await self._call(
                session,
                GMAIL_SEARCH_TOOL,
                {"query": query, "max_results": int(self.config.get("page_size") or 50)},
            )
            for raw in as_list(payload):
                if isinstance(raw, dict) and not (raw.get("body") or raw.get("snippet")):
                    msg_id = str(raw.get("id") or "")
                    if msg_id:
                        try:
                            detail = await self._call(
                                session,
                                GMAIL_GET_TOOL,
                                {"message_id": msg_id},
                            )
                            if isinstance(detail, dict):
                                raw = {**raw, **detail}
                        except Exception:
                            skip_malformed(self.source_type, "get_message_failed", raw)
                item = self._to_item(raw)
                if item is not None:
                    yield item


class McpGChatConnector(McpSourceConnector):
    """Sync Google Chat space messages through workspace-mcp."""

    source_type = "mcp_gchat"
    preset = "google_workspace"
    required_tools: ClassVar[tuple[str, ...]] = (GCHAT_MESSAGES_TOOL,)

    def _to_item(self, raw: Any) -> SourceItem | None:
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "not_a_dict", raw)
            return None
        msg_id = str(raw.get("name") or raw.get("id") or "").strip()
        text = str(raw.get("text") or raw.get("body") or raw.get("argumentText") or "").strip()
        updated = str(raw.get("createTime") or raw.get("lastUpdateTime") or raw.get("updated_at") or "").strip()
        if not msg_id or not updated:
            skip_malformed(self.source_type, "missing_id_or_time", raw)
            return None
        author = dig(raw, "sender.displayName") or dig(raw, "sender.name")
        title = (text[:80] + "…") if len(text) > 80 else (text or msg_id)
        url = str(raw.get("url") or f"gchat://{msg_id}")
        return SourceItem(
            external_id=msg_id.replace("/", "_"),
            title=title,
            body_markdown=text,
            url=url,
            updated_at=updated,
            author=str(author) if author else None,
            tags=["gchat", self.resource_id],
        )

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        args: dict[str, Any] = {"space_id": self.resource_id}
        if since:
            args["since"] = since
        async with await self._open() as session:
            payload = await self._call(session, GCHAT_MESSAGES_TOOL, args)
            items = [self._to_item(raw) for raw in as_list(payload)]
            valid = [i for i in items if i is not None]
            valid.sort(key=lambda i: i.updated_at)
            for item in valid:
                yield item
