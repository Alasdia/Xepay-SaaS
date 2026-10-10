"""add refresh_tokens table for cookie-based session renewal

Revision ID: 9bcf1448d373
Revises: 8e055785cf8b
Create Date: 2026-10-10 00:00:00.000000

Idempotence (revue finale) : backend/main.py appelle
Base.metadata.create_all() sans condition à CHAQUE démarrage de l'appli —
c'est ainsi que la quasi-totalité des tables de ce projet ont historiquement
été créées en production (voir le docstring de la révision baseline
78e72802e47e), Alembic n'ayant été introduit qu'après coup. C'est la
PREMIERE migration de ce projet à faire un véritable op.create_table :
sans garde, si l'appli redémarre avec le nouveau modèle AVANT que cette
migration ne soit appliquée, create_all() crée la table (et ses index, de
mêmes noms que ceux déclarés dans le modèle) de son côté, et
`alembic upgrade head` échoue ensuite avec "la relation existe déjà" —
Alembic n'a aucun moyen de savoir qu'elle a été créée par un autre canal.
upgrade()/downgrade() vérifient donc l'existence de la table avant d'agir :
jamais de perte de données, jamais de recréation, juste un no-op si
create_all() est arrivé en premier.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '9bcf1448d373'
down_revision: Union[str, Sequence[str], None] = '8e055785cf8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "refresh_tokens"
INDEX_NAMES = ("idx_refresh_token_hash", "idx_refresh_token_family", "idx_refresh_token_user")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME in inspector.get_table_names():
        # create_all() a devancé cette migration (l'appli a redémarré avec
        # le nouveau modèle avant l'upgrade) : table et index déjà créés,
        # à l'identique, par le même backend/models.py. Rien à recréer.
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.String(), nullable=True),
    )
    op.create_index(INDEX_NAMES[0], TABLE_NAME, ["token_hash"])
    op.create_index(INDEX_NAMES[1], TABLE_NAME, ["family_id"])
    op.create_index(INDEX_NAMES[2], TABLE_NAME, ["user_id"])


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
