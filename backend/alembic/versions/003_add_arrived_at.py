"""add arrived_at column to orders

Revision ID: 003_add_arrived_at
Revises: 002_convert_order_status_to_enum
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "003_add_arrived_at"
down_revision = "002_convert_order_status_to_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "arrived_at")
