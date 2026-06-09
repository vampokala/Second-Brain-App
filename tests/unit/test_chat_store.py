"""Chat store imports."""

from __future__ import annotations

from src.core.chat_store import NewMessage


def test_new_message_fields() -> None:
    m = NewMessage(role="user", content="hi", parent_id=None)
    assert m.role == "user"
    assert m.retrieved is None


def test_new_message_carries_retrieved_chunks() -> None:
    chunks = [{"id": "c1", "score": 0.5, "source": "raw/a.md", "preview": "x"}]
    m = NewMessage(role="assistant", content="ans", retrieved=chunks)
    assert m.retrieved == chunks
