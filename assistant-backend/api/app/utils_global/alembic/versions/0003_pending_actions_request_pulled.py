"""pending_actions: request_id + pulled_at

Revision ID: 0003_pending_actions_pull
Revises: 0002_pending_actions_dedupe
Create Date: 2026-01-28
"""

from alembic import op


revision = "0003_pending_actions_pull"
down_revision = "0002_pending_actions_dedupe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pending_actions
            ADD COLUMN IF NOT EXISTS request_id VARCHAR(64) NULL,
            ADD COLUMN IF NOT EXISTS pulled_at TIMESTAMPTZ NULL;

        CREATE INDEX IF NOT EXISTS ix_pending_actions_request_id
            ON pending_actions (request_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_pending_actions_request_id;
        ALTER TABLE pending_actions
            DROP COLUMN IF EXISTS pulled_at,
            DROP COLUMN IF EXISTS request_id;
        """
    )
