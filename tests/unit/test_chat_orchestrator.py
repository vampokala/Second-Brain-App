"""Chat orchestrator budget helper tests."""

from __future__ import annotations

from src.core.chat_orchestrator import allocate_budget


def test_allocate_budget_respects_floor_and_caps() -> None:
    b = allocate_budget(1000, 500, 900)
    assert b.generation >= int(1000 * 0.15)
    assert b.history <= int((1000 - int(1000 * 0.15)) * 0.4) + 1
    assert b.history + b.retrieval + b.generation >= 999
