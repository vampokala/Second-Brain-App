"""Retry helpers for Docker Desktop macOS bind-mount FS quirks (EDEADLK)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# macOS Docker Desktop virtiofs/osxfs: 35=EDEADLK, also retry EAGAIN/EINTR
_RETRY_ERRNOS = frozenset({35, 11, 4})


def retry_os(
    fn: Callable[[], T],
    *,
    retries: int = 4,
    label: str = "fs_op",
) -> T:
    """Call *fn*, retrying transient OSError errno values."""
    last: OSError | None = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            return fn()
        except OSError as exc:
            last = exc
            if exc.errno not in _RETRY_ERRNOS or attempt >= attempts - 1:
                raise
            logger.warning(
                "fs_retry label=%s attempt=%s errno=%s error=%s",
                label,
                attempt + 1,
                exc.errno,
                exc,
            )
            time.sleep(0.05 * (attempt + 1))
    assert last is not None
    raise last
