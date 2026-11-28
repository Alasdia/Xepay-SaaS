"""add notifications table

Centre de notifications (icône cloche, bandeau du haut -
#notifications-btn) - jusqu'ici relié à rien (voir spa/app.js, simple
showToast statique). Une ligne = un ÉVÈNEMENT PONCTUEL (ex. "produit
créé sur la boutique Shopify"), jamais une copie synchronisée d'une
donnée Shopify (le marchand préfère tout lire en direct via l'API,
voir la discussion du 2026-11-28).

Revision ID: a4b3bafb4dc1
Revises: add2c13805ac
Create Date: 2026-11-28 01:37:49.195405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4b3bafb4dc1'
down_revision: Union[str, Sequence[str], None] = 'add2c13805ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notifications_workspace_id", "notifications", ["workspace_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_notifications_workspace_id", table_name="notifications")
    op.drop_table("notifications")
