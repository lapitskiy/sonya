"""pending_actions

Revision ID: 0001_pending_actions
Revises: 
Create Date: 2026-01-28
"""

from alembic import op


revision = "0001_pending_actions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safe for environments where create_all() already created the table.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_actions (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR(128) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            payload JSONB NOT NULL,
            ack JSONB NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_pending_actions_device_id ON pending_actions (device_id);
        CREATE INDEX IF NOT EXISTS ix_pending_actions_status ON pending_actions (status);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pending_actions;")
