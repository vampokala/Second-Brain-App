"""Add auth_email to mcp_servers for Atlassian Basic token auth."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007_mcp_auth_email"
down_revision = "006_mcp_servers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("auth_email", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_servers", "auth_email")
