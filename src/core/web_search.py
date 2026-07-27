"""Optional Brave web search + page fetch for chat grounding."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_MAX_SNIPPET_CHARS = 1200


@dataclass
class WebPack:
    pages_fetched: int
    context_markdown: str


async def search_and_fetch(
    query: str,
    *,
    api_key: str,
    max_pages: int = 3,
    timeout_s: float = 12.0,
) -> WebPack:
    """Search Brave and build a compact markdown context block.

    Fetches search snippets only (no full-page crawl) to keep latency demo-friendly.
    """
    key = (api_key or "").strip()
    q = (query or "").strip()
    if not key or not q:
        return WebPack(pages_fetched=0, context_markdown="")

    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    params = {"q": q, "count": max(1, min(max_pages, 5))}
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(_BRAVE_URL, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("brave_search_failed error=%s", exc)
        return WebPack(pages_fetched=0, context_markdown="")

    results = (payload.get("web") or {}).get("results") or []
    blocks: list[str] = []
    for item in results[:max_pages]:
        title = str(item.get("title") or "").strip() or "(untitled)"
        url = str(item.get("url") or "").strip()
        desc = str(item.get("description") or item.get("snippet") or "").strip()
        if len(desc) > _MAX_SNIPPET_CHARS:
            desc = desc[: _MAX_SNIPPET_CHARS - 1].rstrip() + "…"
        blocks.append(f"#### {title}\nURL: {url}\n{desc}")

    if not blocks:
        return WebPack(pages_fetched=0, context_markdown="")

    md = "### Web search results\n\n" + "\n\n".join(blocks) + "\n"
    return WebPack(pages_fetched=len(blocks), context_markdown=md)
