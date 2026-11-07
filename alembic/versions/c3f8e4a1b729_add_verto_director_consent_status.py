"""add verto director consent status

Colonne additive uniquement - voir le plan "PARTNER_REFERRED" du
2026-11-07 (backend/services/verto_service.py, backend/routes/verto.py,
backend/routes/webhook/verto.py). VERTO_ENABLED reste à false par défaut :
cette migration ne rend rien fonctionnel en elle-même.

Revision ID: c3f8e4a1b729
Revises: f3c8a0e6b5d1
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3f8e4a1b729'
down_revision: Union[str, Sequence[str], None] = 'f3c8a0e6b5d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "profiles",
        sa.Column("verto_director_consent_status", sa.String(), nullable=True, server_default="not_sent"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("profiles", "verto_director_consent_status")
