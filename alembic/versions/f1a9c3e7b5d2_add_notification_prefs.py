"""add notification_prefs to users

Revision ID: f1a9c3e7b5d2
Revises: e8b2c6a1f7d4
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a9c3e7b5d2'
down_revision: Union[str, Sequence[str], None] = 'e8b2c6a1f7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("notification_prefs", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "notification_prefs")
