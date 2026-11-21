"""add bildbus tables

BildBus (création de LLC US + EIN via l'API partenaire doola, voir
backend/services/doola_service.py, backend/routes/bildbus.py,
backend/routes/webhook/doola.py) - trois tables :
- bildbus_customers : le "customer" doola (fondateur) par marchand.
- bildbus_companies : la/les LLC en formation ou formée pour ce customer.
- bildbus_webhook_logs : dédoublonnage des événements webhook doola déjà
  traités (event_id UNIQUE).

Revision ID: 549773bc35bc
Revises: f3a9c2e81b6d
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '549773bc35bc'
down_revision: Union[str, Sequence[str], None] = 'f3a9c2e81b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bildbus_customers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("xepay_merchant_id", sa.String(), nullable=False),
        sa.Column("doola_customer_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["xepay_merchant_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("xepay_merchant_id"),
        sa.UniqueConstraint("doola_customer_id"),
    )

    op.create_table(
        "bildbus_companies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("doola_company_id", sa.String(), nullable=True),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("ein_number", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["bildbus_customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doola_company_id"),
    )
    op.create_index(
        "idx_bbco_customer_id",
        "bildbus_companies",
        ["customer_id"],
    )

    op.create_table(
        "bildbus_webhook_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("bildbus_webhook_logs")
    op.drop_index("idx_bbco_customer_id", table_name="bildbus_companies")
    op.drop_table("bildbus_companies")
    op.drop_table("bildbus_customers")
