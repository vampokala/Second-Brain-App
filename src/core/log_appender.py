"""Append deduplicated ingest lines to wiki/log.md."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path

from src.core.fs_retry import retry_os

logger = logging.getLogger(__name__)

_log_lock = asyncio.Lock()
_seen: set[tuple[str, str, str]] = set()


async def append_log(vault_path: Path, file_relpath: str, kind: str = "auto-ingest") -> None:
    """Append '## [YYYY-MM-DD] <kind> | <file>' to wiki/log.md if not already present today.

    Single asyncio.Lock prevents concurrent write races on burst ingest.
    Failures are logged and swallowed so ingest is not aborted by log I/O.
    """
    vault_path = vault_path.resolve()
    log_path = vault_path / "wiki" / "log.md"
    day = date.today().isoformat()
    rel = relorpath_key(file_relpath)

    async with _log_lock:
        key = (day, rel, kind)
        if key in _seen:
            return

        def _append_sync() -> None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            header = "# Wiki activity log\n\n"
            if not log_path.is_file():
                retry_os(lambda: log_path.write_text(header, encoding="utf-8"), label="log_init")

            text = retry_os(
                lambda: log_path.read_text(encoding="utf-8", errors="replace"),
                label="log_read",
            )
            line = f"## [{day}] {kind} | {rel}"
            if line in text:
                return
            if not text.endswith("\n"):
                text += "\n"
            text += f"\n{line}\n"
            retry_os(lambda: log_path.write_text(text, encoding="utf-8"), label="log_write")

        try:
            await asyncio.to_thread(_append_sync)
            _seen.add(key)
        except OSError as exc:
            logger.warning("append_log_failed path=%s error=%s", log_path, exc)


def relorpath_key(file_relpath: str) -> str:
    return file_relpath.replace("\\", "/").lstrip("/")
