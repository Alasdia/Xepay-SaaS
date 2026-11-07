"""add verto company id unique constraint

Filet de sécurité DB contre le double sous-compte Verto (découpage en
étapes du 2026-11-07, voir backend/routes/verto.py). UNIQUE sur une
colonne nullable autorise plusieurs NULL en Postgres (comportement
standard) - sans impact sur les profils n'ayant pas démarré l'onboarding.

Revision ID: d4a7c2e9f031
Revises: c3f8e4a1b729
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4a7c2e9f031'
down_revision: Union[str, Sequence[str], None] = 'c3f8e4a1b729'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint("uq_profiles_verto_company_id", "profiles", ["verto_company_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_profiles_verto_company_id", "profiles", type_="unique")
