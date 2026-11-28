"""add shopify shop uninstalled_at

Seul signal de désinstallation (webhook app/uninstalled, voir
routes/webhook/shopify.py) - access_token n'est jamais vidé (contrainte
explicite déjà en place), juste marqué obsolète. AUCUNE table de
mirroring de données Shopify (le marchand préfère explicitement tout
lire en direct via l'API, jamais une copie côté Xepay - voir la
discussion du 2026-11-28).

Revision ID: add2c13805ac
Revises: 19a2f7d59273
Create Date: 2026-11-28 01:03:44.509756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add2c13805ac'
down_revision: Union[str, Sequence[str], None] = '19a2f7d59273'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("shopify_shops", sa.Column("uninstalled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("shopify_shops", "uninstalled_at")
