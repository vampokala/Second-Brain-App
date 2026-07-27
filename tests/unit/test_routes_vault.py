"""Vault routes: security and list wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from urllib.parse import quote

from src.api.routes_vault import router
from src.db.session import get_async_session


@pytest.fixture
def vault_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:65432/test")
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))

    app = FastAPI()
    app.include_router(router)

    fake = MagicMock()
    fake.commit = AsyncMock()
    fake.merge = AsyncMock()

    async def _exec(_stmt):  # noqa: ANN001
        m = MagicMock()
        m.all.return_value = [("raw/notes/a.md",)]
        m.scalar_one.return_value = 3
        m.scalar_one_or_none.return_value = None
        return m

    fake.execute = AsyncMock(side_effect=_exec)

    async def _sess():
        yield fake

    app.dependency_overrides[get_async_session] = _sess
    return TestClient(app), tmp_path


def test_path_traversal_rejected(vault_client):
    client, tmp_path = vault_client
    (tmp_path / "raw").mkdir(parents=True)
    (tmp_path / "raw" / "secret.md").write_text("x", encoding="utf-8")
    evil = tmp_path.parent / "outside_vault.md"
    evil.write_text("nope", encoding="utf-8")
    res = client.get("/vault/files/" + quote("../outside_vault.md", safe=""))
    assert res.status_code == 403


def test_vault_stats_includes_vault_path(vault_client, monkeypatch):
    client, tmp_path = vault_client
    monkeypatch.setenv("VAULT_HOST_PATH", "/host/shared/vault")
    res = client.get("/vault/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["vault_path"] == str(tmp_path.resolve())
    assert data["vault_host_path"] == "/host/shared/vault"
    assert "file_count" in data
    assert "chunk_count" in data


def test_read_markdown_frontmatter(vault_client):
    client, tmp_path = vault_client
    (tmp_path / "raw").mkdir(parents=True)
    (tmp_path / "raw" / "x.md").write_text("---\ntitle: T\n---\n\nBody\n", encoding="utf-8")
    res = client.get("/vault/files/raw/x.md")
    assert res.status_code == 200
    body = res.json()
    assert body["body"].strip() == "Body"
    assert body["frontmatter"]["title"] == "T"
