"""add issuing_topups table

Revision ID: 9d083a3ef2a0
Revises: d9efd7c7893e
Create Date: 2026-11-11 00:00:00.000000

Même garde que 9bcf1448d373 (refresh_tokens) : backend/main.py appelle
Base.metadata.create_all() à chaque démarrage, qui peut créer cette table
(et ses index, mêmes noms que ceux déclarés dans backend/models.py) avant
que cette migration ne tourne. upgrade()/downgrade() vérifient donc
l'existence de la table avant d'agir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '9d083a3ef2a0'
down_revision: Union[str, Sequence[str], None] = 'd9efd7c7893e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "issuing_topups"
INDEX_NAMES = (
    "ix_issuing_topups_user_id",
    "ix_issuing_topups_stripe_account_id",
    "ix_issuing_topups_stripe_topup_id",
    "ix_issuing_topups_idempotency_key",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
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
    op.create_index(INDEX_NAMES[0], TABLE_NAME, ["user_id"])
    op.create_index(INDEX_NAMES[1], TABLE_NAME, ["stripe_account_id"])
    op.create_index(INDEX_NAMES[2], TABLE_NAME, ["stripe_topup_id"])
    op.create_index(INDEX_NAMES[3], TABLE_NAME, ["idempotency_key"])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return
    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE_NAME)}
    for name in reversed(INDEX_NAMES):
        if name in existing_indexes:
            op.drop_index(name, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
