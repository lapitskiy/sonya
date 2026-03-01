"""pending_actions: contract + dedupe

Revision ID: 0002_pending_actions_dedupe
Revises: 0001_pending_actions
Create Date: 2026-01-28
"""

from alembic import op


revision = "0002_pending_actions_dedupe"
down_revision = "0001_pending_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pending_actions
            ADD COLUMN IF NOT EXISTS action_type VARCHAR(64) NOT NULL DEFAULT 'unknown',
            ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(128) NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_actions_device_dedupe
            ON pending_actions (device_id, dedupe_key)
            WHERE dedupe_key IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS uq_pending_actions_device_dedupe;
        ALTER TABLE pending_actions
            DROP COLUMN IF EXISTS dedupe_key,
            DROP COLUMN IF EXISTS action_type;
        """
    )
