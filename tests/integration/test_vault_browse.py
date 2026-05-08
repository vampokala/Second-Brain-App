"""Vault browse integration smoke."""

from __future__ import annotations

from src.api.main import app


def test_vault_routes_registered() -> None:
    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p.startswith("/vault/") for p in paths)
