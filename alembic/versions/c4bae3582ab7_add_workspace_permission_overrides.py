"""add workspace_permission_overrides table

Permissions par rôle configurables par le owner d'un workspace (voir
backend/services/permission_service.py). Une ligne par capacité
explicitement redéfinie - l'absence de ligne pour une capacité donnée
signifie "comportement par défaut" (CAPABILITY_DEFAULTS), jamais
recréée pour toutes les capacités à chaque workspace.

Revision ID: c4bae3582ab7
Revises: 0b5b6a2b567b
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4bae3582ab7'
down_revision: Union[str, Sequence[str], None] = '0b5b6a2b567b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workspace_permission_overrides",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("capability_key", sa.String(), nullable=False),
        sa.Column("min_role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_wkpo_workspace_capability",
        "workspace_permission_overrides",
        ["workspace_id", "capability_key"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_wkpo_workspace_capability", table_name="workspace_permission_overrides")
    op.drop_table("workspace_permission_overrides")
