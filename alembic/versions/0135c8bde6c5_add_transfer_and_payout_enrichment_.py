"""add transfer and payout enrichment fields

Revision ID: 0135c8bde6c5
Revises: 2a85bb1f7732
Create Date: 2026-10-04 21:33:46.894447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0135c8bde6c5'
down_revision: Union[str, Sequence[str], None] = '2a85bb1f7732'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("transfer_destination", sa.String(), nullable=True))
    op.add_column("payments", sa.Column("transfer_reversed", sa.Boolean(), nullable=True))
    op.add_column("payments", sa.Column("transfer_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("withdrawals", sa.Column("payout_method", sa.String(), nullable=True))
    op.add_column("withdrawals", sa.Column("payout_arrival_date", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("withdrawals", "payout_arrival_date")
    op.drop_column("withdrawals", "payout_method")
    op.drop_column("payments", "transfer_created_at")
    op.drop_column("payments", "transfer_reversed")
    op.drop_column("payments", "transfer_destination")
