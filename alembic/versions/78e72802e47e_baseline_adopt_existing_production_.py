"""baseline: adopt existing production schema

Revision ID: 78e72802e47e
Revises:
Create Date: 2026-10-02 21:16:39.964547

Cette revision est un NO-OP volontaire. Elle ne cree, ne modifie ni ne
supprime rien : son seul role est de marquer le point ou Alembic a ete
introduit dans un schema de production deja existant (adopte via
`alembic stamp head`, jamais via `alembic upgrade` sur cette base).

Genere initialement par `alembic revision --autogenerate` directement
contre la base de production (lecture seule), puis vide manuellement
avant tout commit : l'autogenerate reel proposait plusieurs changements
QUI N'ONT PAS ETE APPLIQUES et doivent faire l'objet d'une decision et
d'une migration dediee, deliberee, plus tard :

  1. api_logs.id : le modele declare `String` (ids prefixes), la colonne
     reelle en production est encore `INTEGER` (SERIAL) - le modele a du
     etre modifie apres la creation initiale de la table, jamais
     retro-applique (create_all() ne modifie jamais une table existante).
  2. users.account_id : le modele declare `nullable=False`, la colonne
     reelle est NULLABLE en production - la contrainte NOT NULL n'a
     jamais ete appliquee.
  3. withdrawals.stripe_payout_id : le modele declare un index UNIQUE
     (`unique=True, index=True`), l'index reel en production
     (`idx_withdrawals_stripe_payout_id`) n'est PAS unique et porte un
     nom different de la convention SQLAlchemy - l'unicite n'est donc
     pas reellement garantie par la base aujourd'hui.
  4. webhook_delivery_logs.webhook_id : le modele ne declare aucun
     `ondelete`, la contrainte FK reelle en production a
     `ON DELETE CASCADE` - comportement reel different de ce que
     l'ORM laisse supposer a la lecture du modele.

Egalement ignores dans cette comparaison (voir alembic/env.py,
IGNORED_TABLES / IGNORED_INDEXES) : la table `exchange_rates` (non
mappee en ORM) et les index deja identifies lors de l'audit de
performance du 2026-10-02 (presents en prod, absents du modele, ou
l'inverse) - voir env.py pour la liste exacte et leur justification.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78e72802e47e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
