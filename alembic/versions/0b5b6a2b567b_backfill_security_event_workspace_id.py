"""backfill security_events.workspace_id for pre-existing rows

Les lignes créées avant l'ajout de la colonne workspace_id (migration
00d453a4dfbe) ont workspace_id=NULL, donc invisibles pour GET
/security/events (filtré sur workspace_id = workspace actif - NULL ne
correspond jamais à une égalité). Hypothèse de repli : chacune a été
créée en consultant son propre workspace (workspace_id = user_id) -
correct dans la majorité des cas, pas forcément pour les quelques
lignes générées en testant justement le changement de workspace.

Revision ID: 0b5b6a2b567b
Revises: 00d453a4dfbe
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b5b6a2b567b'
down_revision: Union[str, Sequence[str], None] = '00d453a4dfbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE security_events SET workspace_id = user_id WHERE workspace_id IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Irréversible par nature : impossible de distinguer après coup les
    # lignes qui avaient déjà workspace_id = user_id "pour de vrai" de
    # celles backfillées ici avec la même valeur par hypothèse.
    pass
