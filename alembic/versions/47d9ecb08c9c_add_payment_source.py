"""add payment source and stripe_metadata

Revision ID: 47d9ecb08c9c
Revises: d8fa7c4f028e
Create Date: 2026-10-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47d9ecb08c9c'
down_revision: Union[str, Sequence[str], None] = 'd8fa7c4f028e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("source", sa.String(), nullable=True))
    op.add_column("payments", sa.Column("stripe_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("payments", "stripe_metadata")
    op.drop_column("payments", "source")
