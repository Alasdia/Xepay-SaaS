"""add stripe issuing account fields

Compte Stripe Connect dédié à Issuing (dashboard: none), distinct de
profiles.stripe_account_id (Express, paiements/payouts) - voir
backend/services/stripe_issuing_service.py, backend/routes/issuing.py.

Revision ID: d8e1f4b2c930
Revises: c4bae3582ab7
Create Date: 2026-11-06 00:00:00.000000

Note : chaîné directement sur c4bae3582ab7 (dernière migration commitée au
moment où ce travail a démarré), pas sur a7f3c9e2d156 (migration Verto
zero-custody, toujours non commitée en parallèle) - les deux features sont
indépendantes et ne doivent pas être couplées au déploiement.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e1f4b2c930'
down_revision: Union[str, Sequence[str], None] = 'c4bae3582ab7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("profiles", sa.Column("stripe_issuing_account_id", sa.String(), nullable=True))
    op.create_index("ix_profiles_stripe_issuing_account_id", "profiles", ["stripe_issuing_account_id"])
    op.add_column("profiles", sa.Column("stripe_issuing_program_id", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("profiles", "stripe_issuing_program_id")
    op.drop_index("ix_profiles_stripe_issuing_account_id", table_name="profiles")
    op.drop_column("profiles", "stripe_issuing_account_id")
