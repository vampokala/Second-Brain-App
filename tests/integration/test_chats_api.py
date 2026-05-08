"""Chat API smoke tests (no live Postgres required)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes_chats import router as chats_router


def test_chats_list_requires_store() -> None:
    app = FastAPI()
    app.include_router(chats_router)
    c = TestClient(app)
    r = c.get("/chats")
    assert r.status_code == 503


def test_chat_search_requires_store() -> None:
    app = FastAPI()
    app.include_router(chats_router)
    c = TestClient(app)
    r = c.get("/chats/search?q=hello")
    assert r.status_code == 503
