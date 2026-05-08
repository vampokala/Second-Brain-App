"""Chat store imports."""

from __future__ import annotations

from src.core.chat_store import NewMessage


def test_new_message_fields() -> None:
    m = NewMessage(role="user", content="hi", parent_id=None)
    assert m.role == "user"
