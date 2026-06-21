"""convert order status to postgres enum

Revision ID: 002_convert_order_status_to_enum
Revises: 001_initial
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers
revision = '002_convert_order_status_to_enum'
down_revision = '001_initial'
branch_labels = None
depends_on = None


order_status_enum = ENUM(
    'NEW', 'SCHEDULED', 'ARRIVED', 'IN_PROGRESS', 'ACQUIRED',
    'TO_REPORT', 'REPORTING', 'SIGNED', 'ISSUED', 'CANCELLED',
    name='order_status',
    create_type=False,
)


def upgrade() -> None:
    # 1. Создаём Postgres enum-тип
    order_status_enum.create(op.get_bind())

    # 2. Удаляем старый DEFAULT, иначе Postgres не приведёт varchar-default к enum
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")

    # 3. Меняем тип колонки orders.status с VARCHAR на order_status
    op.alter_column(
        'orders',
        'status',
        existing_type=sa.String(length=20),
        type_=order_status_enum,
        postgresql_using='status::order_status',
        existing_nullable=False,
    )

    # 4. Восстанавливаем DEFAULT в терминах enum
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'NEW'")


def downgrade() -> None:
    # 1. Удаляем enum-default перед обратной конвертацией
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")

    # 2. Возвращаем колонку к VARCHAR(20)
    op.alter_column(
        'orders',
        'status',
        existing_type=order_status_enum,
        type_=sa.String(length=20),
        postgresql_using='status::text::varchar(20)',
        existing_nullable=False,
    )

    # 3. Восстанавливаем varchar DEFAULT
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'NEW'")

    # 4. Удаляем enum-тип
    order_status_enum.drop(op.get_bind())
