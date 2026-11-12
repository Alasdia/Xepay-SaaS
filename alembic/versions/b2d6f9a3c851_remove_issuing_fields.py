"""remove issuing topups table and stripe issuing profile fields

Revision ID: b2d6f9a3c851
Revises: a1c5e8f2b647
Create Date: 2026-11-12 00:00:00.000000

Issuing (compte dédié par marchand + rechargement Verto + solde Issuing
classique) est abandonné en même temps que Treasury for platforms -
même raison structurelle (présence physique US exigée par Stripe pour la
capacité card_issuing, incompatible avec les comptes connectés Xepay).
Annule 9d083a3ef2a0, d8e1f4b2c930 et f3c8a0e6b5d1 (gardées en place,
d'autres migrations les référencent comme down_revision) pour les
environnements où elles avaient déjà tourné ; gardes d'existence par
idempotence, même principe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b2d6f9a3c851'
down_revision: Union[str, Sequence[str], None] = 'a1c5e8f2b647'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "issuing_topups"
TABLE_INDEX_NAMES = (
    "ix_issuing_topups_user_id",
    "ix_issuing_topups_stripe_account_id",
    "ix_issuing_topups_stripe_topup_id",
    "ix_issuing_topups_idempotency_key",
)

PROFILE_COLUMNS = (
    "stripe_issuing_account_id",
    "stripe_issuing_program_id",
    "stripe_issuing_bank_source_id",
    "stripe_issuing_bank_status",
    "stripe_issuing_bank_pending_amounts",
    "stripe_issuing_bank_link_started_at",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE_NAME in inspector.get_table_names():
        existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE_NAME)}
        for name in reversed(TABLE_INDEX_NAMES):
            if name in existing_indexes:
                op.drop_index(name, table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)

    existing_columns = {c["name"] for c in inspector.get_columns("profiles")}
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("profiles")}
    if "stripe_issuing_account_id" in existing_columns:
        if "ix_profiles_stripe_issuing_account_id" in existing_indexes:
            op.drop_index("ix_profiles_stripe_issuing_account_id", table_name="profiles")
    for column in PROFILE_COLUMNS:
        if column in existing_columns:
            op.drop_column("profiles", column)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_columns = {c["name"] for c in inspector.get_columns("profiles")}
    if "stripe_issuing_account_id" not in existing_columns:
        op.add_column("profiles", sa.Column("stripe_issuing_account_id", sa.String(), nullable=True))
        op.create_index("ix_profiles_stripe_issuing_account_id", "profiles", ["stripe_issuing_account_id"])
    if "stripe_issuing_program_id" not in existing_columns:
        op.add_column("profiles", sa.Column("stripe_issuing_program_id", sa.String(), nullable=True))
    if "stripe_issuing_bank_source_id" not in existing_columns:
        op.add_column("profiles", sa.Column("stripe_issuing_bank_source_id", sa.String(), nullable=True))
    if "stripe_issuing_bank_status" not in existing_columns:
        op.add_column(
            "profiles",
            sa.Column("stripe_issuing_bank_status", sa.String(), nullable=True, server_default="not_started"),
        )
    if "stripe_issuing_bank_pending_amounts" not in existing_columns:
        op.add_column("profiles", sa.Column("stripe_issuing_bank_pending_amounts", sa.JSON(), nullable=True))
    if "stripe_issuing_bank_link_started_at" not in existing_columns:
        op.add_column("profiles", sa.Column("stripe_issuing_bank_link_started_at", sa.DateTime(), nullable=True))

    if TABLE_NAME in inspector.get_table_names():
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("stripe_account_id", sa.String(), nullable=False),
        sa.Column("stripe_topup_id", sa.String(), nullable=True),
        sa.Column("stripe_source_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failure_message", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_topup_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(TABLE_INDEX_NAMES[0], TABLE_NAME, ["user_id"])
    op.create_index(TABLE_INDEX_NAMES[1], TABLE_NAME, ["stripe_account_id"])
    op.create_index(TABLE_INDEX_NAMES[2], TABLE_NAME, ["stripe_topup_id"])
    op.create_index(TABLE_INDEX_NAMES[3], TABLE_NAME, ["idempotency_key"])
