"""task_categories_and_task_category

Revision ID: 0006_task_categories
Revises: 0005_tasks
Create Date: 2026-01-29

"""

from alembic import op
import sqlalchemy as sa


revision = "0006_task_categories"
down_revision = "0005_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("category", sa.String(length=64), server_default="прочее", nullable=False))
    op.create_index(op.f("ix_tasks_category"), "tasks", ["category"], unique=False)

    op.create_table(
        "task_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "title", name="uq_task_categories_device_title"),
    )
    op.create_index(op.f("ix_task_categories_device_id"), "task_categories", ["device_id"], unique=False)
    op.create_index(op.f("ix_task_categories_title"), "task_categories", ["title"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_categories_title"), table_name="task_categories")
    op.drop_index(op.f("ix_task_categories_device_id"), table_name="task_categories")
    op.drop_table("task_categories")

    op.drop_index(op.f("ix_tasks_category"), table_name="tasks")
    op.drop_column("tasks", "category")

