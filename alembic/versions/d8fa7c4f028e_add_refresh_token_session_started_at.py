"""add refresh_tokens.session_started_at for absolute 30-day session cap

Revision ID: d8fa7c4f028e
Revises: 9bcf1448d373
Create Date: 2026-10-11 00:00:00.000000

session_started_at fixe la limite de session ABSOLUE (30 jours,
ABSOLUTE_SESSION_MAX_DAYS dans backend/security.py) : posé une seule fois à
la connexion initiale, puis propagé tel quel à chaque jeton enfant créé par
une rotation (backend/services/refresh_token_service.py) — jamais
réinitialisé, pour que la rotation ne puisse jamais repousser cette limite.

NOT NULL avec server_default=now() : fonctionne que la table soit vide ou
contienne déjà des lignes (aucune ne devrait exister à ce stade, la
migration précédente venant d'introduire la table), sans étape de backfill
manuelle. Idempotent comme 9bcf1448d373 : Base.metadata.create_all() ne
modifie jamais une table existante pour y ajouter une colonne (contrairement
à la création d'une table entière), donc le risque de course avec
create_all() ne s'applique pas ici — la vérification ci-dessous protège
seulement contre une ré-application accidentelle de cette migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'd8fa7c4f028e'
down_revision: Union[str, Sequence[str], None] = '9bcf1448d373'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "refresh_tokens"
COLUMN_NAME = "session_started_at"


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME in existing_columns:
        return
    op.add_column(
        TABLE_NAME,
        sa.Column(
            COLUMN_NAME,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # server_default n'a de sens que pour l'INSERT côté base (et le
    # backfill ci-dessus) ; l'application pose toujours la valeur
    # explicitement (backend/services/refresh_token_service.py), donc pas
    # besoin de le garder après coup.
    op.alter_column(TABLE_NAME, COLUMN_NAME, server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in existing_columns:
        return
    op.drop_column(TABLE_NAME, COLUMN_NAME)
