"""MCP GitHub adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from src.core.connectors.base import ConnectorError, SourceItem
from src.core.connectors.mcp_base import McpSourceConnector, as_list, dig, skip_malformed

LIST_COMMITS_TOOL = "list_commits"
LIST_ISSUES_TOOL = "list_issues"


class McpGitHubConnector(McpSourceConnector):
    """Sync commits (and optionally issues) through the GitHub MCP server."""

    source_type = "mcp_github"
    preset = "github"
    required_tools: ClassVar[tuple[str, ...]] = (LIST_COMMITS_TOOL,)

    def _owner_repo(self) -> tuple[str, str]:
        parts = self.resource_id.strip("/").split("/")
        if len(parts) < 2:
            raise ConnectorError("GitHub resource_id must be owner/repo.")
        return parts[0], parts[1]

    def _commit_item(self, raw: Any) -> SourceItem | None:
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "commit_not_dict", raw)
            return None
        sha = str(raw.get("sha") or raw.get("id") or "").strip()
        message = str(dig(raw, "commit.message") or raw.get("message") or "").strip()
        updated = str(
            dig(raw, "commit.author.date")
            or dig(raw, "commit.committer.date")
            or raw.get("updated_at")
            or ""
        ).strip()
        if not sha or not updated:
            skip_malformed(self.source_type, "commit_missing_fields", raw)
            return None
        title = message.split("\n", 1)[0] or sha[:8]
        author = dig(raw, "commit.author.name") or dig(raw, "author.login")
        url = str(raw.get("html_url") or raw.get("url") or f"github://commit/{sha}")
        return SourceItem(
            external_id=sha,
            title=title,
            body_markdown=message,
            url=url,
            updated_at=updated,
            author=str(author) if author else None,
            tags=["commit"],
        )

    def _issue_item(self, raw: Any) -> SourceItem | None:
        if not isinstance(raw, dict):
            skip_malformed(self.source_type, "issue_not_dict", raw)
            return None
        number = raw.get("number") or raw.get("id")
        if number is None:
            skip_malformed(self.source_type, "issue_missing_number", raw)
            return None
        title = str(raw.get("title") or f"Issue #{number}").strip()
        updated = str(raw.get("updated_at") or raw.get("created_at") or "").strip()
        if not updated:
            skip_malformed(self.source_type, "issue_missing_updated", raw)
            return None
        body = str(raw.get("body") or "")
        url = str(raw.get("html_url") or raw.get("url") or f"github://issue/{number}")
        author = dig(raw, "user.login")
        return SourceItem(
            external_id=f"issue-{number}",
            title=title,
            body_markdown=body,
            url=url,
            updated_at=updated,
            author=str(author) if author else None,
            tags=["issue"],
        )

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        owner, repo = self._owner_repo()
        collected: list[SourceItem] = []
        async with await self._open() as session:
            args: dict[str, Any] = {"owner": owner, "repo": repo}
            if since:
                args["since"] = since
            commits = as_list(await self._call(session, LIST_COMMITS_TOOL, args))
            for raw in commits:
                item = self._commit_item(raw)
                if item is not None:
                    collected.append(item)

            if self.config.get("include_issues"):
                issue_args = {"owner": owner, "repo": repo, "state": "all"}
                if since:
                    issue_args["since"] = since
                try:
                    issues = as_list(await self._call(session, LIST_ISSUES_TOOL, issue_args))
                except Exception:
                    skip_malformed(self.source_type, "list_issues_failed")
                    issues = []
                for raw in issues:
                    item = self._issue_item(raw)
                    if item is not None:
                        collected.append(item)

        collected.sort(key=lambda i: i.updated_at)
        for item in collected:
            yield item
