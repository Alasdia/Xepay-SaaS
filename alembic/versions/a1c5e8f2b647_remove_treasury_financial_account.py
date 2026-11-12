"""remove treasury financial account column and received_credits table

Revision ID: a1c5e8f2b647
Revises: 9d083a3ef2a0
Create Date: 2026-11-12 00:00:00.000000

Treasury for platforms (prototype du 2026-11-11) est abandonné - Stripe
exige une présence physique US incompatible avec les comptes connectés
Xepay. Cette migration annule d9f843b10d81 (supprimée, elle créait ces
mêmes objets) pour les environnements où elle avait déjà tourné ; gardes
d'existence par idempotence, même principe que les migrations qu'elle
annule.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a1c5e8f2b647'
down_revision: Union[str, Sequence[str], None] = '9d083a3ef2a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "treasury_received_credits"
INDEX_NAMES = (
    "ix_treasury_received_credits_user_id",
    "ix_treasury_received_credits_stripe_account_id",
    "ix_treasury_received_credits_financial_account_id",
    "ix_treasury_received_credits_stripe_received_credit_id",
    "ix_treasury_received_credits_idempotency_key",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE_NAME in inspector.get_table_names():
        existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE_NAME)}
        for name in reversed(INDEX_NAMES):
            if name in existing_indexes:
                op.drop_index(name, table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)

    existing_columns = {c["name"] for c in inspector.get_columns("profiles")}
    if "stripe_financial_account_id" in existing_columns:
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("profiles")}
        if "ix_profiles_stripe_financial_account_id" in existing_indexes:
            op.drop_index("ix_profiles_stripe_financial_account_id", table_name="profiles")
        op.drop_column("profiles", "stripe_financial_account_id")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_columns = {c["name"] for c in inspector.get_columns("profiles")}
    if "stripe_financial_account_id" not in existing_columns:
        op.add_column(
            "profiles",
            sa.Column("stripe_financial_account_id", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_profiles_stripe_financial_account_id", "profiles", ["stripe_financial_account_id"]
        )

    if TABLE_NAME in inspector.get_table_names():
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("stripe_account_id", sa.String(), nullable=False),
        sa.Column("financial_account_id", sa.String(), nullable=False),
        sa.Column("stripe_received_credit_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failure_code", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_received_credit_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(INDEX_NAMES[0], TABLE_NAME, ["user_id"])
    op.create_index(INDEX_NAMES[1], TABLE_NAME, ["stripe_account_id"])
    op.create_index(INDEX_NAMES[2], TABLE_NAME, ["financial_account_id"])
    op.create_index(INDEX_NAMES[3], TABLE_NAME, ["stripe_received_credit_id"])
    op.create_index(INDEX_NAMES[4], TABLE_NAME, ["idempotency_key"])
