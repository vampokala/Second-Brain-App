"""Unit tests for chat personas."""

from __future__ import annotations

from src.core.personas import (
    DEFAULT_CHAT_PERSONA,
    build_persona_system_section,
    normalize_chat_persona,
    persona_addon_applied,
    persona_display,
    resolved_student_grade_token,
)


def test_normalize_unknown_persona_defaults() -> None:
    assert normalize_chat_persona("nope") == DEFAULT_CHAT_PERSONA
    assert normalize_chat_persona("") == DEFAULT_CHAT_PERSONA


def test_student_grade_display_and_token() -> None:
    assert resolved_student_grade_token("K") == "K"
    assert resolved_student_grade_token("7") == "7"
    assert resolved_student_grade_token("99") == "9"
    assert persona_display(persona_id="student", student_grade="7") == "Student · Grade 7"


def test_persona_section_includes_addon() -> None:
    section = build_persona_system_section(
        persona_id="software_engineer",
        addon="Prefer Rust examples.",
    )
    assert "### User persona" in section
    assert "software engineer" in section.lower()
    assert "### User-provided persona notes" in section
    assert "Prefer Rust examples." in section
    assert persona_addon_applied("Prefer Rust examples.") is True
    assert persona_addon_applied("  ") is False
