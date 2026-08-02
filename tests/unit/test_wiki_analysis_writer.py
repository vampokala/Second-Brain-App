"""Unit tests for wiki analysis writer."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.core.wiki_analysis_writer import save_answer_to_wiki, slug_from_title


def test_slug_from_title_boundary() -> None:
    assert slug_from_title("") == "analysis"
    assert slug_from_title("Hello World!") == "hello-world"


def test_save_answer_writes_and_indexes(tmp_path: Path) -> None:
    rel = asyncio.run(
        save_answer_to_wiki(
            vault_path=tmp_path,
            title="Demo Answer",
            body_markdown="## Finding\n\nIt works.",
            sources=["wiki/sources/a.md"],
        )
    )
    assert rel.startswith("wiki/analyses/")
    path = tmp_path / rel
    assert path.is_file()
    body = path.read_text(encoding="utf-8")
    assert "Demo Answer" in body
    assert "It works." in body
    index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "## Analyses" in index
    assert "Demo Answer" in index


def test_save_answer_duplicate_slug(tmp_path: Path) -> None:
    first = asyncio.run(
        save_answer_to_wiki(
            vault_path=tmp_path,
            title="Same",
            body_markdown="one",
        )
    )
    second = asyncio.run(
        save_answer_to_wiki(
            vault_path=tmp_path,
            title="Same",
            body_markdown="two",
        )
    )
    assert first != second
    assert (tmp_path / second).is_file()
