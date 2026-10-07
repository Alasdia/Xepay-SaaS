"""add payment stripe_fee_amount

Revision ID: 2a85bb1f7732
Revises: 1aafee7b5c75
Create Date: 2026-10-04 13:59:42.510837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a85bb1f7732'
down_revision: Union[str, Sequence[str], None] = '1aafee7b5c75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("stripe_fee_amount", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("payments", "stripe_fee_amount")
