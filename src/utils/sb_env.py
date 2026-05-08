"""Second-Brain-App environment settings (vault, Postgres, vector backend)."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecondBrainSettings(BaseSettings):
    """Loaded from environment; used when DATABASE_URL is set for vault + pgvector mode."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://secondbrain:localdev@localhost:5432/secondbrain",
        description="Async SQLAlchemy URL (asyncpg driver)",
    )
    database_url_sync: str = Field(
        default="postgresql://secondbrain:localdev@localhost:5432/secondbrain",
        description="Sync SQLAlchemy URL for RAG path (psycopg2)",
    )
    vault_path: Path = Field(default=Path("/vault"))
    vault_subdirs: list[str] = Field(default_factory=lambda: ["raw", "wiki"])
    vector_backend: str = Field(default="pgvector", description="pgvector or chromadb")
    embed_model: str = Field(default="nomic-embed-text", alias="EMBED_MODEL")
    llm_default_model: str = Field(default="llama3.1:8b", alias="LLM_DEFAULT_MODEL")
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    ollama_keep_alive: str = Field(default="5m", alias="OLLAMA_KEEP_ALIVE")
    max_ingest_workers: int = Field(default=2, alias="MAX_INGEST_WORKERS")
    watcher_debounce_ms: int = Field(default=5000, alias="WATCHER_DEBOUNCE_MS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    def is_second_brain_enabled(self) -> bool:
        """When True, RAG loads BM25 + vectors from Postgres / vault paths."""
        return bool(os.getenv("DATABASE_URL", "").strip()) or bool(
            os.getenv("SECOND_BRAIN_ENABLED", "").strip() in ("1", "true", "yes")
        )


def load_second_brain_settings() -> SecondBrainSettings:
    """Build settings with DATABASE_URL driving sync URL if only async URL provided."""
    s = SecondBrainSettings()
    async_url = os.getenv("DATABASE_URL", "").strip()
    if async_url:
        sync_url = async_url.replace("postgresql+asyncpg://", "postgresql://")
        object.__setattr__(s, "database_url", async_url)
        object.__setattr__(s, "database_url_sync", os.getenv("DATABASE_URL_SYNC", sync_url))
    vault = os.getenv("VAULT_PATH", "").strip()
    if vault:
        object.__setattr__(s, "vault_path", Path(vault))
    return s
