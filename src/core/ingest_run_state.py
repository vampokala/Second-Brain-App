"""Thread-safe ingest cancel flag and progress callback holder."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[dict[str, Any]], None]


class IngestRunState:
    """Tracks cooperative cancel requests and optional progress callbacks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel_requested = False
        self._progress_callback: ProgressCallback | None = None

    def request_cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True

    def clear(self) -> None:
        with self._lock:
            self._cancel_requested = False
            self._progress_callback = None

    def should_cancel(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def set_progress_callback(self, callback: ProgressCallback | None) -> None:
        with self._lock:
            self._progress_callback = callback

    def emit_progress(self, payload: dict[str, Any]) -> None:
        with self._lock:
            callback = self._progress_callback
        if callback is not None:
            callback(payload)


_STATE = IngestRunState()


def get_ingest_run_state() -> IngestRunState:
    return _STATE
