"""Tests for wiki stub writer."""

from __future__ import annotations

import asyncio
from pathlib import Path

import frontmatter
import pytest

from src.core import wiki_stub_writer as ws


def test_write_stub_creates_expected_layout(tmp_path: Path) -> None:
    vault = tmp_path
    raw = vault / "raw" / "Foo" / "bar.md"
    raw.parent.mkdir(parents=True)
    raw.write_text(
        "---\ntitle: T\n---\n\nFirst paragraph here.\n\nSecond.\n",
        encoding="utf-8",
    )

    async def _run() -> Path:
        return await ws.write_stub(raw, vault, summary="")

    stub = asyncio.run(_run())
    assert stub == vault / "wiki" / "sources" / "foo" / "bar.md"
    data = frontmatter.load(stub)
    assert data.metadata.get("auto") is True
    assert data.metadata.get("type") == "source"
    assert data.metadata.get("sources") == ["raw/Foo/bar.md"]
    assert "First paragraph here." in (data.content or "")


def test_stub_preserves_when_auto_removed(tmp_path: Path) -> None:
    vault = tmp_path
    raw = vault / "raw" / "s" / "x.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("# H\n\nBody\n", encoding="utf-8")

    asyncio.run(ws.write_stub(raw, vault, ""))
    stub = vault / "wiki" / "sources" / "s" / "x.md"
    manual = stub.read_text(encoding="utf-8")
    manual = manual.replace("auto: true", "auto: false")
    stub.write_text(manual, encoding="utf-8")
    asyncio.run(ws.write_stub(raw, vault, ""))
    data = frontmatter.load(stub)
    assert data.metadata.get("auto") is False


def test_concurrent_writes_same_section(tmp_path: Path) -> None:
    vault = tmp_path
    vault.joinpath("raw/a").mkdir(parents=True)

    async def one(name: str) -> Path:
        p = vault / "raw/a" / f"{name}.md"
        p.write_text(f"# {name}\n\nHi {name}.\n", encoding="utf-8")
        return await ws.write_stub(p, vault, "")

    async def _all() -> list[Path]:
        return await asyncio.gather(*[one(str(i)) for i in range(5)])

    paths = asyncio.run(_all())
    assert len({p.resolve() for p in paths}) == 5
    for p in paths:
        assert p.is_file()
