"""Initial schema for Second-Brain-App."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "bm25_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE bm25_snapshot ADD CONSTRAINT bm25_snapshot_singleton CHECK (id = 1)")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_id", sa.String(512), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("file_type", sa.String(64), nullable=True),
        sa.Column("tags", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_chunks_chunk_id", "document_chunks", ["chunk_id"], unique=True)
    op.create_index("ix_document_chunks_source", "document_chunks", ["source_path"])
    op.create_index(
        "ix_document_chunks_embedding",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "chats",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("knowledge_scope", sa.String(32), nullable=False, server_default="vault"),
        sa.Column("summary_cache", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_search", "messages", ["search_vector"], postgresql_using="gin")

    op.create_table(
        "message_citations",
        sa.Column("message_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("chunk_id", sa.String(256), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "embed_queue",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ingest_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("details", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "vault_files",
        sa.Column("path", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("file_type", sa.String(32), nullable=True),
        sa.Column("tags", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mtime", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("vault_files")
    op.drop_table("ingest_events")
    op.drop_table("embed_queue")
    op.drop_table("app_settings")
    op.drop_table("message_citations")
    op.drop_index("ix_messages_search", table_name="messages")
    op.drop_table("messages")
    op.drop_table("chats")
    op.drop_index("ix_document_chunks_embedding", table_name="document_chunks")
    op.drop_index("ix_document_chunks_source", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("bm25_snapshot")
