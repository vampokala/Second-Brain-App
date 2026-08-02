"""VaultStats model includes vault path fields."""

from __future__ import annotations

from src.api.models_vault import VaultStats


def test_vault_stats_includes_path_fields() -> None:
    stats = VaultStats(
        file_count=1,
        chunk_count=2,
        last_ingest_at=None,
        embed_model="nomic-embed-text",
        vault_path="/vault",
        vault_host_path="/Users/demo/Second-Brain",
    )
    dumped = stats.model_dump()
    assert dumped["vault_path"] == "/vault"
    assert dumped["vault_host_path"] == "/Users/demo/Second-Brain"


def test_vault_stats_host_path_optional() -> None:
    stats = VaultStats(
        file_count=0,
        chunk_count=0,
        embed_model="x",
        vault_path="/vault",
    )
    assert stats.vault_host_path is None
