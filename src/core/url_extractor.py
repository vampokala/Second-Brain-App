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


@dataclass
class ExtractedPage:
    url: str
    title: str
    text: str


def extract_url(url: str) -> ExtractedPage:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url!r}")

    headers = {"User-Agent": "SecondBrainApp/1.0"}
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers=headers) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError(f"Response exceeds {MAX_BYTES} bytes")
                chunks.append(chunk)
            raw = b"".join(chunks)
            ctype = (response.headers.get("content-type") or "").lower()
            html = raw.decode(response.encoding or "utf-8", errors="replace")

    title: Optional[str] = None
    text = ""
    if "html" in ctype or "<html" in html[:2000].lower():
        meta = trafilatura.extract_metadata(html)
        if meta is not None:
            t = getattr(meta, "title", None)
            if t:
                title = str(t).strip()
        text = (trafilatura.extract(html, url=url, include_comments=False, include_tables=False) or "").strip()
        if not text:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
    else:
        text = html.strip()

    if not text:
        raise ValueError("No extractable text from URL")

    return ExtractedPage(url=url, title=title or parsed.netloc, text=text)
