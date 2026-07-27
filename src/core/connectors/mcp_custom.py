"""Generic MCP connector: user-specified tool + field map."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar

from src.core.connectors.base import ConnectorError, SourceItem
from src.core.connectors.mcp_base import McpSourceConnector, as_list, dig, skip_malformed


def _substitute_since(value: Any, since: str | None) -> Any:
    if isinstance(value, str):
        return value.replace("{since}", since or "")
    if isinstance(value, dict):
        return {k: _substitute_since(v, since) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_since(v, since) for v in value]
    return value


class McpCustomConnector(McpSourceConnector):
    """Call an arbitrary MCP tool and map results to SourceItems."""

    source_type = "mcp_custom"
    preset = "custom"
    required_tools: ClassVar[tuple[str, ...]] = ()

    def _field_map(self) -> dict[str, str]:
        raw = self.config.get("field_map") or {}
        if not isinstance(raw, dict):
            return {}
        return {str(k): str(v) for k, v in raw.items()}

    def _to_item(self, raw: Any, field_map: dict[str, str]) -> SourceItem | None:
        if isinstance(raw, str):
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            return SourceItem(
                external_id=digest,
                title=raw[:80] or digest,
                body_markdown=raw,
                url=f"mcp-custom://{digest}",
                updated_at=now,
                tags=["mcp_custom"],
            )
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "unsupported_item_type", raw)
            return None

        def pick(key: str, default: str = "") -> str:
            path = field_map.get(key, key)
            value = dig(raw, path)
            if value is None:
                value = raw.get(key, default)
            return str(value or default).strip()

        external_id = pick("id") or pick("external_id")
        title = pick("title") or external_id
        body = pick("body") or pick("content") or ""
        url = pick("url") or f"mcp-custom://{external_id or 'item'}"
        updated = pick("updated_at") or pick("updated")
        if not external_id or not updated:
            skip_malformed(self.source_type, "missing_id_or_updated", raw)
            return None
        return SourceItem(
            external_id=external_id,
            title=title or external_id,
            body_markdown=body,
            url=url,
            updated_at=updated,
            tags=["mcp_custom"],
        )

    def _parse_tool_args(self, since: str | None) -> dict:
        tool_args = self.config.get("tool_args") or {}
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except json.JSONDecodeError as exc:
                raise ConnectorError("mcp_custom tool_args must be valid JSON.") from exc
        if not isinstance(tool_args, dict):
            raise ConnectorError("mcp_custom tool_args must be a JSON object.")
        return _substitute_since(tool_args, since)

    def _extract_items(self, payload: Any, items_path: str) -> list[Any]:
        if not items_path:
            return as_list(payload)
        extracted = dig(payload, items_path)
        if extracted is None:
            raise ConnectorError(f"mcp_custom items_path {items_path!r} not found in tool result.")
        return as_list(extracted)

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        tool_name = str(self.config.get("tool_name") or "").strip()
        if not tool_name:
            raise ConnectorError("mcp_custom requires config.tool_name.")
        since = (cursor or {}).get("since")
        args = self._parse_tool_args(since)
        items_path = str(self.config.get("items_path") or "").strip()
        field_map = self._field_map()

        async with await self._open() as session:
            payload = await self._call(session, tool_name, args)
            if isinstance(payload, str):
                item = self._to_item(payload, field_map)
                if item is not None:
                    yield item
                return
            for raw in self._extract_items(payload, items_path):
                item = self._to_item(raw, field_map)
                if item is not None:
                    yield item
