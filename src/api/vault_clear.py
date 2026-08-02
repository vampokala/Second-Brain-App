"""Vault clear request validation helpers."""

from __future__ import annotations

from src.api.models_vault import VaultClearBody


class VaultClearValidationError(ValueError):
    """Raised when clear request is invalid."""


def validate_vault_clear_body(body: VaultClearBody) -> None:
    if body.confirm != "delete":
        raise VaultClearValidationError("confirm must be exactly 'delete'")
    if not (body.clear_vault or body.clear_memory or body.clear_chats):
        raise VaultClearValidationError("Select at least one target to clear")
