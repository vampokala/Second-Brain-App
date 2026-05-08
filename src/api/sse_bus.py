"""In-process pub/sub for ingest SSE fan-out."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

MAX_QUEUE = 200


class SSEBus:
    def __init__(self) -> None:
        self._subs: list[asyncio.Queue[dict[str, Any]]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_QUEUE)
        async with self._lock:
            self._subs.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, payload: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    _ = q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    async def iter_queue(self, q: asyncio.Queue[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await q.get()
            yield item
