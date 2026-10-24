"""add created_at to workspace_users

Revision ID: e8b2c6a1f7d4
Revises: c4f7a1e9d3b2
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b2c6a1f7d4'
down_revision: Union[str, Sequence[str], None] = 'c4f7a1e9d3b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("workspace_users", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workspace_users", "created_at")
