"""Filesystem watcher for vault raw/ with debounced ingest."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.core.ingest_paths import should_skip_path
from src.core.supported_formats import is_supported

if TYPE_CHECKING:
    from src.core.ingest_pipeline import IngestPipeline

logger = logging.getLogger(__name__)


class _Handler(FileSystemEventHandler):
    def __init__(
        self,
        vault: Path,
        loop: asyncio.AbstractEventLoop,
        pipeline: "IngestPipeline",
        schedule_fn,
    ) -> None:
        super().__init__()
        self._vault = vault
        self._loop = loop
        self._pipeline = pipeline
        self._schedule = schedule_fn

    def _rel(self, src_path: str) -> str | None:
        path = Path(src_path)
        try:
            return str(path.resolve().relative_to(self._vault)).replace("\\", "/")
        except ValueError:
            return None

    def _dispatch_file(self, src_path: str) -> None:
        path = Path(src_path)
        if not path.is_file():
            return
        try:
            path.resolve().relative_to(self._vault)
        except ValueError:
            return
        self._loop.call_soon_threadsafe(self._schedule, path)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._dispatch_file(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._dispatch_file(event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel = self._rel(event.src_path)
        if not rel:
            return

        async def _go() -> None:
            try:
                await self._pipeline.remove_path(rel)
            except Exception as exc:  # noqa: BLE001
                logger.exception("watcher remove failed: %s", exc)

        def _fire() -> None:
            asyncio.ensure_future(_go(), loop=self._loop)

        self._loop.call_soon_threadsafe(_fire)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        rel_old = self._rel(event.src_path)
        dest = Path(event.dest_path)
        if not rel_old:
            return

        async def _go() -> None:
            try:
                await self._pipeline.remove_path(rel_old)
                if dest.is_file():
                    await self._pipeline.ingest_file(dest.resolve())
            except Exception as exc:  # noqa: BLE001
                logger.exception("watcher move failed: %s", exc)

        def _fire() -> None:
            asyncio.ensure_future(_go(), loop=self._loop)

        self._loop.call_soon_threadsafe(_fire)


class VaultWatcher:
    def __init__(
        self,
        vault_path: Path,
        pipeline: "IngestPipeline",
        debounce_ms: int,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._vault = vault_path.resolve()
        self._pipeline = pipeline
        self._debounce_s = debounce_ms / 1000.0
        self._loop = loop
        self._observer: Optional[Observer] = None
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stopped = asyncio.Event()

    def _debounce_key(self, path: Path) -> str:
        return str(path.resolve())

    def _schedule_ingest(self, path: Path) -> None:
        key = self._debounce_key(path)
        old = self._tasks.get(key)
        if old and not old.done():
            old.cancel()

        async def _run() -> None:
            try:
                await asyncio.sleep(self._debounce_s)
                p = path.resolve()
                if not p.is_file():
                    return
                if should_skip_path(p, self._vault):
                    return
                vision = self._pipeline.is_vision_enabled()
                if not is_supported(p.suffix, vision_enabled=vision):
                    return
                await self._pipeline.ingest_file(p)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("watcher ingest failed: %s", exc)
            finally:
                self._tasks.pop(key, None)

        self._tasks[key] = asyncio.create_task(_run())

    async def start(self) -> None:
        self._stopped.clear()
        handler = _Handler(self._vault, self._loop, self._pipeline, self._schedule_ingest)
        obs = Observer()
        for sub in self._pipeline.settings.vault_subdirs:
            root = self._vault / sub
            root.mkdir(parents=True, exist_ok=True)
            obs.schedule(handler, str(root), recursive=True)
        obs.start()
        self._observer = obs
        logger.info("Vault watcher started on %s (%s)", self._vault, self._pipeline.settings.vault_subdirs)

    async def stop(self) -> None:
        self._stopped.set()
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None
        for t in list(self._tasks.values()):
            if not t.done():
                t.cancel()
        self._tasks.clear()
