"""In-memory TTL cache for generation results."""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from src.core.generator import GenerationResult


def cache_key(
    query: str,
    model: str,
    top_k: int,
    *,
    provider: str = "ollama",
    use_rerank: bool = True,
    reranker_model: str = "",
    corpus_fingerprint: str = "documents",
    response_mode: str = "sync",
) -> str:
    """response_mode distinguishes streaming vs non-streaming cache entries (must not collide)."""
    raw = "\n".join(
        [
            query,
            provider,
            model,
            str(top_k),
            str(use_rerank),
            reranker_model,
            corpus_fingerprint,
            response_mode,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ResponseCache:
    """Simple process-local cache with TTL."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[GenerationResult, float]] = {}

    def get(self, key: str) -> Optional[GenerationResult]:
        if self.ttl_seconds <= 0:
            return None
        item = self._store.get(key)
        if not item:
            return None
        result, expires_at = item
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return result

    def set(self, key: str, result: GenerationResult) -> None:
        if self.ttl_seconds <= 0:
            return
        self._store[key] = (result, time.monotonic() + float(self.ttl_seconds))

    def clear(self) -> None:
        self._store.clear()
