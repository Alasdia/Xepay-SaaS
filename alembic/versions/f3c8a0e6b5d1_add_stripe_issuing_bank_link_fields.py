"""add stripe issuing bank link fields

Rechargement de la carte Issuing depuis le wallet USD Verto déjà existant
du marchand - voir backend/routes/issuing.py, backend/routes/webhook/verto.py.

Revision ID: f3c8a0e6b5d1
Revises: a7f3c9e2d156
Create Date: 2026-11-06 00:00:00.000000

Note : chaîné sur a7f3c9e2d156 (ajout des colonnes verto_* sur profiles)
parce que backend/routes/issuing.py lit désormais
profile.verto_usd_account_number/verto_usd_bank_code pour le lien
bancaire du rechargement de carte - ces colonnes doivent exister en base
pour que CE code (déjà branché, accessible) ne plante pas sur toute
requête Profile. Le reste de la fonctionnalité Verto (onboarding,
webhook, routes API) n'est volontairement pas déployé avec ceci (pas de
câblage main.py) - seules ces colonnes, additives et inoffensives.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c8a0e6b5d1'
down_revision: Union[str, Sequence[str], None] = 'a7f3c9e2d156'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("profiles", sa.Column("stripe_issuing_bank_source_id", sa.String(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("stripe_issuing_bank_status", sa.String(), nullable=True, server_default="not_started"),
    )
    op.add_column("profiles", sa.Column("stripe_issuing_bank_pending_amounts", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("stripe_issuing_bank_link_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("profiles", "stripe_issuing_bank_link_started_at")
    op.drop_column("profiles", "stripe_issuing_bank_pending_amounts")
    op.drop_column("profiles", "stripe_issuing_bank_status")
    op.drop_column("profiles", "stripe_issuing_bank_source_id")
