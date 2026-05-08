"""Poll Ollama and drain embed queue when the daemon returns."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from src.core.ingest_pipeline import IngestPipeline

logger = logging.getLogger(__name__)


class OllamaHealthMonitor:
    def __init__(self, base_url: str, pipeline: Optional["IngestPipeline"] = None) -> None:
        self._base = base_url.rstrip("/")
        self._pipeline = pipeline
        self._task: Optional[asyncio.Task[None]] = None
        self._stop = asyncio.Event()
        self.is_available: bool = True
        self.available_models: list[str] = []

    def attach_pipeline(self, pipeline: "IngestPipeline") -> None:
        self._pipeline = pipeline

    def snapshot(self) -> tuple[bool, list[str]]:
        return self.is_available, list(self.available_models)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        was_ok = False
        while not self._stop.is_set():
            ok = False
            models: list[str] = []
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(f"{self._base}/api/tags")
                    r.raise_for_status()
                    data = r.json()
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                ok = True
            except Exception as exc:  # noqa: BLE001
                logger.debug("Ollama health check failed: %s", exc)
            self.is_available = ok
            self.available_models = models
            if ok and not was_ok and self._pipeline:
                try:
                    n = await self._pipeline.drain_embed_queue()
                    if n:
                        logger.info("Drained %s embed queue rows after Ollama reconnect", n)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("embed queue drain failed: %s", exc)
            was_ok = ok
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                pass
