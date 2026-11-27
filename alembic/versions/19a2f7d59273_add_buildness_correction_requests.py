"""add buildness correction requests

buildness_correction_requests - doola n'expose aucun endpoint PUT/PATCH
pour modifier une société déjà créée, et leur mécanisme de "required
actions" est exclusivement réactif (vérifié le 2026-11-27 contre leur
doc API + Embedded SDK + spec OpenAPI). doola n'a de relation directe
qu'avec Xepay, jamais avec nos marchands : une ligne ici trace une
demande de correction à relayer manuellement par un humain côté Xepay
vers leur support, jamais une mise à jour automatique.

Revision ID: 19a2f7d59273
Revises: 5b7c36e20af4
Create Date: 2026-11-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19a2f7d59273'
down_revision: Union[str, Sequence[str], None] = '5b7c36e20af4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "buildness_correction_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("field_label", sa.String(), nullable=False),
        sa.Column("requested_value", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["buildness_companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_bncorr_workspace_status",
        "buildness_correction_requests",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_bncorr_workspace_status", table_name="buildness_correction_requests")
    op.drop_table("buildness_correction_requests")
