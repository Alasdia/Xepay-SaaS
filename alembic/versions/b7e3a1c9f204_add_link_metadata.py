"""add link_metadata

Revision ID: b7e3a1c9f204
Revises: 47d9ecb08c9c
Create Date: 2026-10-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3a1c9f204'
down_revision: Union[str, Sequence[str], None] = '47d9ecb08c9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("links", sa.Column("link_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("links", "link_metadata")
