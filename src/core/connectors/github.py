"""GitHub connector: index commit messages (and optionally issues) from a repo."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from src.core.connectors.base import ConnectorError, SourceConnector, SourceItem
from src.core.connectors.github_host import resolve_github_api_base

_PAGE_SIZE = 100


class GitHubConnector(SourceConnector):
    """``resource_id`` is ``"owner/repo"``.

    config keys: ``base_url`` (REST API root — ``https://api.github.com`` or
    ``https://github.company.com/api/v3``), ``branch``, ``include_issues`` (bool).
    Defaults follow ``GITHUB_API_URL`` / ``GITHUB_HOST`` when set.
    ``token`` is a read-only PAT (optional for public repos on github.com).
    """

    source_type = "github"

    def __init__(
        self,
        resource_id: str,
        config: dict,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(resource_id, config, token)
        if "/" not in resource_id:
            raise ConnectorError("GitHub resource must be 'owner/repo'.")
        self.owner, self.repo = resource_id.split("/", 1)
        self.base_url = resolve_github_api_base(config)
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _make_client(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=30.0, headers=self._headers())

    async def test_connection(self) -> tuple[bool, str]:
        client = self._make_client()
        try:
            resp = await client.get(f"{self.base_url}/repos/{self.owner}/{self.repo}")
            if resp.status_code == 200:
                return True, f"Reachable: {self.owner}/{self.repo}"
            if resp.status_code == 404:
                return False, "Repository not found (check name or token scope)."
            if resp.status_code in (401, 403):
                return False, "Authentication failed or rate-limited (check token)."
            return False, f"Unexpected status {resp.status_code}."
        except httpx.HTTPError as exc:
            return False, f"Network error: {exc}"
        finally:
            if self._client is None:
                await client.aclose()

    async def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        since = (cursor or {}).get("since")
        client = self._make_client()
        try:
            async for item in self._fetch_commits(client, since):
                yield item
            if self.config.get("include_issues"):
                async for item in self._fetch_issues(client, since):
                    yield item
        finally:
            if self._client is None:
                await client.aclose()

    async def _fetch_commits(self, client: httpx.AsyncClient, since: str | None) -> AsyncIterator[SourceItem]:
        page = 1
        collected: list[SourceItem] = []
        while True:
            params: dict[str, object] = {"per_page": _PAGE_SIZE, "page": page}
            if since:
                params["since"] = since
            if self.config.get("branch"):
                params["sha"] = self.config["branch"]
            resp = await client.get(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/commits",
                params=params,
                headers=self._headers(),
            )
            if resp.status_code != 200:
                raise ConnectorError(f"GitHub commits failed: {resp.status_code} {resp.text[:200]}")
            batch = resp.json()
            if not batch:
                break
            for c in batch:
                commit = c.get("commit", {})
                message = commit.get("message", "")
                author = (commit.get("author") or {}).get("name")
                updated = (commit.get("author") or {}).get("date", "")
                sha = c.get("sha", "")
                title = message.splitlines()[0] if message else sha[:12]
                collected.append(
                    SourceItem(
                        external_id=sha,
                        title=title,
                        body_markdown=message,
                        url=c.get("html_url", ""),
                        updated_at=updated,
                        author=author,
                        tags=["commit"],
                    )
                )
            if len(batch) < _PAGE_SIZE:
                break
            page += 1
        # GitHub returns newest-first; emit ascending so the cursor advances.
        for item in sorted(collected, key=lambda i: i.updated_at):
            yield item

    async def _fetch_issues(self, client: httpx.AsyncClient, since: str | None) -> AsyncIterator[SourceItem]:
        page = 1
        while True:
            params: dict[str, object] = {"per_page": _PAGE_SIZE, "page": page, "state": "all"}
            if since:
                params["since"] = since
            resp = await client.get(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/issues",
                params=params,
                headers=self._headers(),
            )
            if resp.status_code != 200:
                raise ConnectorError(f"GitHub issues failed: {resp.status_code} {resp.text[:200]}")
            batch = resp.json()
            if not batch:
                break
            for issue in batch:
                is_pr = "pull_request" in issue
                yield SourceItem(
                    external_id=f"issue-{issue.get('number')}",
                    title=issue.get("title", ""),
                    body_markdown=issue.get("body") or "",
                    url=issue.get("html_url", ""),
                    updated_at=issue.get("updated_at", ""),
                    author=(issue.get("user") or {}).get("login"),
                    tags=["pull_request" if is_pr else "issue"],
                )
            if len(batch) < _PAGE_SIZE:
                break
            page += 1
