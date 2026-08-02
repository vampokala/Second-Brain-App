"""Add connector_sync_state for external source connectors."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "003_connector_sync_state"
down_revision = "002_chat_active_leaf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_sync_state",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cursor", JSONB(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ux_connector_type_resource",
        "connector_sync_state",
        ["connector_type", "resource_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_connector_type_resource", table_name="connector_sync_state")
    op.drop_table("connector_sync_state")
