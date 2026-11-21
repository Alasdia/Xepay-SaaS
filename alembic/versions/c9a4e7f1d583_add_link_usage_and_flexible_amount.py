"""add link usage limit and flexible amount bounds

Revision ID: c9a4e7f1d583
Revises: a3f1c9e02b7d
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9a4e7f1d583'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9e02b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # max_uses NULL = lien illimité (comportement historique, inchangé pour
    # les lignes existantes) ; 1 = usage unique ; N = quota de paiements.
    op.add_column("links", sa.Column("max_uses", sa.Integer(), nullable=True))
    # min_amount/max_amount : bornes optionnelles pour un lien à montant
    # flexible (amount IS NULL). Jamais renseignées pour un lien à montant
    # fixe, voir la validation côté LinkCreate.
    op.add_column("links", sa.Column("min_amount", sa.Float(), nullable=True))
    op.add_column("links", sa.Column("max_amount", sa.Float(), nullable=True))
    # amount/expires_at doivent devenir nullable : un lien à montant
    # flexible n'a pas de montant fixe, et un lien multi-usage peut ne
    # jamais expirer (voir create_link dans routes/lien.py).
    op.alter_column("links", "amount", existing_type=sa.Float(), nullable=True)
    op.alter_column("links", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("links", "max_amount")
    op.drop_column("links", "min_amount")
    op.drop_column("links", "max_uses")
