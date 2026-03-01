"""tasks: due_date (day tasks)

Revision ID: 0007_tasks_due_date
Revises: 0006_task_categories
Create Date: 2026-02-02

"""

from alembic import op
import sqlalchemy as sa


revision = "0007_tasks_due_date"
down_revision = "0006_task_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("due_date", sa.Date(), nullable=True))
    op.create_index(op.f("ix_tasks_due_date"), "tasks", ["due_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_due_date"), table_name="tasks")
    op.drop_column("tasks", "due_date")

