"""Add per-connector sync_interval_min for the ingestion scheduler."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004_connector_schedule"
down_revision = "003_connector_sync_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connector_sync_state",
        sa.Column("sync_interval_min", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connector_sync_state", "sync_interval_min")
