"""Unit tests for rolling memory file helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.core.rolling_memory import load_memory_excerpt, memory_path, write_memory


def test_write_and_load_memory(tmp_path: Path) -> None:
    asyncio.run(write_memory(tmp_path, "Prefer concise answers."))
    assert memory_path(tmp_path).is_file()
    assert "concise" in load_memory_excerpt(tmp_path)


def test_load_missing_memory_empty(tmp_path: Path) -> None:
    assert load_memory_excerpt(tmp_path) == ""


def test_load_memory_truncates(tmp_path: Path) -> None:
    asyncio.run(write_memory(tmp_path, "x" * 5000))
    excerpt = load_memory_excerpt(tmp_path, max_chars=100)
    assert len(excerpt) <= 100
    assert excerpt.endswith("…")
