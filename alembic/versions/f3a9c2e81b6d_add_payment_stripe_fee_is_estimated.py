"""add payment stripe_fee_is_estimated

Revision ID: f3a9c2e81b6d
Revises: b2d6f9a3c851
Create Date: 2026-11-18 00:00:00.000000

Distingue un stripe_fee_amount reel (destination charge, lu directement
depuis Stripe) d'une estimation (direct charge sur un compte
fees_collector="application", ou le frais Stripe reel n'est jamais
expose par transaction - voir _resolve_stripe_fee_amount dans
routes/webhook/paiement.py). Le frontend affiche cette distinction
plutot que de presenter une estimation comme un chiffre exact.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a9c2e81b6d'
down_revision: Union[str, Sequence[str], None] = 'b2d6f9a3c851'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("stripe_fee_is_estimated", sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("payments", "stripe_fee_is_estimated")
