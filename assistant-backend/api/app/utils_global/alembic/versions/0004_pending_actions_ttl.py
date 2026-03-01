"""pending_actions: ttl

Revision ID: 0004_pending_actions_ttl
Revises: 0003_pending_actions_pull
Create Date: 2026-01-28
"""

from alembic import op


revision = "0004_pending_actions_ttl"
down_revision = "0003_pending_actions_pull"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pending_actions
            ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ NULL;

        CREATE INDEX IF NOT EXISTS ix_pending_actions_expires_at
            ON pending_actions (expires_at);

        -- Backfill for existing pending rows that have no TTL yet (default 1 hour)
        UPDATE pending_actions
        SET expires_at = created_at + INTERVAL '1 hour'
        WHERE status = 'pending' AND expires_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_pending_actions_expires_at;
        ALTER TABLE pending_actions DROP COLUMN IF EXISTS expires_at;
        """
    )
