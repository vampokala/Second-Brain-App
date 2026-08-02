"""Vault clear validation (no FastAPI router deps)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.api.models_vault import VaultClearBody
from src.api.vault_clear import VaultClearValidationError, validate_vault_clear_body


def test_clear_rejects_wrong_confirm_literal() -> None:
    with pytest.raises(ValidationError):
        VaultClearBody(confirm="DELETE", clear_vault=True)  # type: ignore[arg-type]


def test_clear_rejects_empty_selection() -> None:
    body = VaultClearBody(confirm="delete")
    with pytest.raises(VaultClearValidationError, match="at least one"):
        validate_vault_clear_body(body)


def test_clear_accepts_vault_only() -> None:
    body = VaultClearBody(confirm="delete", clear_vault=True)
    validate_vault_clear_body(body)


def test_clear_accepts_memory_and_chats() -> None:
    body = VaultClearBody(confirm="delete", clear_memory=True, clear_chats=True)
    validate_vault_clear_body(body)
