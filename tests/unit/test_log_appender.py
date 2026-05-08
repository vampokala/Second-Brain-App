"""Tests for wiki log appender."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from src.core.log_appender import append_log


def test_append_creates_log_with_header(tmp_path: Path) -> None:
    vault = tmp_path
    asyncio.run(append_log(vault, "raw/a.md", kind="auto-ingest"))
    logf = vault / "wiki" / "log.md"
    text = logf.read_text(encoding="utf-8")
    assert "# Wiki activity log" in text
    day = date.today().isoformat()
    assert f"## [{day}] auto-ingest | raw/a.md" in text


def test_dedup_same_day(tmp_path: Path) -> None:
    vault = tmp_path
    asyncio.run(append_log(vault, "raw/b.md"))
    asyncio.run(append_log(vault, "raw/b.md"))
    text = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    assert text.count("raw/b.md") == 1


def test_concurrent_appends(tmp_path: Path) -> None:
    vault = tmp_path

    async def one(i: int) -> None:
        await append_log(vault, f"raw/f{i}.md")

    async def _all() -> None:
        await asyncio.gather(*[one(i) for i in range(20)])

    asyncio.run(_all())
    text = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    for i in range(20):
        assert text.count(f"raw/f{i}.md") == 1
