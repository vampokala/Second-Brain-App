"""Unit tests for grounding mode instructions."""

from __future__ import annotations

from src.core.prompt_modes import mode_instructions


def test_corpus_only_zero_hits_warns() -> None:
    text = mode_instructions("corpus_only", False, 0, False)
    assert "did not surface matches" in text


def test_corpus_plus_web() -> None:
    text = mode_instructions("corpus_only", True, 3, True)
    assert "two" in text.lower()
    assert "3" in text


def test_web_only() -> None:
    text = mode_instructions("allow_general", True, 0, True)
    assert "Corpus retrieval is **off**" in text


def test_neither() -> None:
    text = mode_instructions("allow_general", False, 0, False)
    assert "general reasoning" in text
