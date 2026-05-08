"""Settings API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes_settings import router as settings_router
from src.db.session import get_async_session


@pytest.fixture
def settings_client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:65432/t")
    app = FastAPI()
    app.include_router(settings_router)

    fake = MagicMock()
    fake.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[])),
    )
    sess = AsyncMock()
    sess.execute = AsyncMock(return_value=fake)

    async def _dep():
        yield sess

    app.dependency_overrides[get_async_session] = _dep
    return TestClient(app)


def test_get_settings_returns_shape(settings_client):
    res = settings_client.get("/settings")
    assert res.status_code == 200
    data = res.json()
    assert "values" in data
    assert "env_override_keys" in data
