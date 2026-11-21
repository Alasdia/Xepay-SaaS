"""add bildbus_companies.last_successful_step

Dernière étape réellement réussie (draft/submitted/processing/completed)
pour une BildBusCompany - mise à jour uniquement sur les transitions de
succès (routes/bildbus.py, routes/webhook/doola.py), jamais sur un échec.
Permet au frontend d'afficher le stepper au bon endroit quand status
vaut "failed", plutôt que de supposer que l'échec a eu lieu à la
dernière étape.

Revision ID: d62dabcd6fd0
Revises: 549773bc35bc
Create Date: 2026-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd62dabcd6fd0'
down_revision: Union[str, Sequence[str], None] = '549773bc35bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("bildbus_companies", sa.Column("last_successful_step", sa.String(), nullable=True))
    # Backfill des lignes existantes (pré-migration) sur la base de leur
    # status actuel - approximation : une ligne "failed" existante n'a
    # aucune trace de son vrai point d'arrêt (c'est exactement le trou que
    # cette migration comble pour le futur), donc laissée à NULL plutôt
    # que de deviner un step au hasard.
    op.execute(
        "UPDATE bildbus_companies SET last_successful_step = status "
        "WHERE status IN ('draft', 'submitted', 'processing', 'completed')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bildbus_companies", "last_successful_step")
