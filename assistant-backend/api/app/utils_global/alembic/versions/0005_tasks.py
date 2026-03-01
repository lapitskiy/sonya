"""tasks

Revision ID: 0005_tasks
Revises: b94b8fa86dae
Create Date: 2026-01-29

"""

from alembic import op
import sqlalchemy as sa


revision = "0005_tasks"
down_revision = "b94b8fa86dae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("urgent", sa.Boolean(), nullable=False),
        sa.Column("important", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_device_id"), "tasks", ["device_id"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_urgent"), "tasks", ["urgent"], unique=False)
    op.create_index(op.f("ix_tasks_important"), "tasks", ["important"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_important"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_urgent"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_device_id"), table_name="tasks")
    op.drop_table("tasks")

