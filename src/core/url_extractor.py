"""Fetch and normalize article HTML into plain text (trafilatura primary, HTML fallback)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_BYTES = 5_242_880  # 5 MB
TIMEOUT_S = 30.0


class UrlExtractError(ValueError):
    """Client-facing failure while fetching or extracting a remote URL."""

    def __init__(self, message: str, *, upstream: bool = False) -> None:
        super().__init__(message)
        self.upstream = upstream


@dataclass
class ExtractedPage:
    url: str
    title: str
    text: str


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise UrlExtractError(f"Invalid URL: {url!r}")


def _fetch_bytes(url: str) -> tuple[bytes, str, str | None]:
    headers = {"User-Agent": "SecondBrainApp/1.0"}
    try:
        with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers=headers) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise UrlExtractError(f"Response exceeds {MAX_BYTES} bytes")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                ctype = (response.headers.get("content-type") or "").lower()
                encoding = response.encoding
    except UrlExtractError:
        raise
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise UrlExtractError(
            f"Remote URL returned HTTP {status}",
            upstream=True,
        ) from exc
    except httpx.TimeoutException as exc:
        raise UrlExtractError("Timed out fetching URL", upstream=True) from exc
    except httpx.HTTPError as exc:
        raise UrlExtractError(f"Failed to fetch URL: {exc}", upstream=True) from exc
    return raw, ctype, encoding


def _extract_html(html: str, url: str) -> tuple[Optional[str], str]:
    title: Optional[str] = None
    meta = trafilatura.extract_metadata(html)
    if meta is not None:
        t = getattr(meta, "title", None)
        if t:
            title = str(t).strip()
    text = (
        trafilatura.extract(html, url=url, include_comments=False, include_tables=False) or ""
    ).strip()
    if text:
        return title, text
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return title, soup.get_text(separator="\n", strip=True)


def extract_url(url: str) -> ExtractedPage:
    _validate_url(url)
    parsed = urlparse(url)
    raw, ctype, encoding = _fetch_bytes(url)
    html = raw.decode(encoding or "utf-8", errors="replace")

    title: Optional[str] = None
    text = ""
    if "html" in ctype or "<html" in html[:2000].lower():
        title, text = _extract_html(html, url)
    else:
        text = html.strip()

    if not text:
        raise UrlExtractError("No extractable text from URL")

    return ExtractedPage(url=url, title=title or parsed.netloc, text=text)
