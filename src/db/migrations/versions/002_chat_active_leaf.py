"""Add chats.active_leaf_id for conversation branching."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "002_chat_active_leaf"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("active_leaf_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_chats_active_leaf_messages",
        "chats",
        "messages",
        ["active_leaf_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chats_active_leaf_messages", "chats", type_="foreignkey")
    op.drop_column("chats", "active_leaf_id")
