"""drop company info columns from profiles

Les colonnes ajoutées par 58bd1909b6c9 n'ont jamais été exposées en
production (aucun commit intermédiaire ne les utilisait) - remplacées
dans le même cycle de travail par Paramètres > Entreprise, qui lit les
informations déjà fournies à Stripe (GET /stripe/business-details) au
lieu d'un formulaire local dupliqué.

Revision ID: 4119af091eb2
Revises: 58bd1909b6c9
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4119af091eb2'
down_revision: Union[str, Sequence[str], None] = '58bd1909b6c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("profiles", "country")
    op.drop_column("profiles", "city")
    op.drop_column("profiles", "postal_code")
    op.drop_column("profiles", "address")
    op.drop_column("profiles", "vat_number")
    op.drop_column("profiles", "registration_number")
    op.drop_column("profiles", "legal_form")
    op.drop_column("profiles", "company_name")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("profiles", sa.Column("company_name", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("legal_form", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("registration_number", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("vat_number", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("address", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("postal_code", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("city", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("country", sa.String(), nullable=True))
