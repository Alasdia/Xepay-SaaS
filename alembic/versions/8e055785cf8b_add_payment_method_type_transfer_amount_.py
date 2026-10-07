"""add payment method type, transfer amount reversed, payout failure message

Revision ID: 8e055785cf8b
Revises: 0135c8bde6c5
Create Date: 2026-10-05 17:48:58.280160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e055785cf8b'
down_revision: Union[str, Sequence[str], None] = '0135c8bde6c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("payment_method_type", sa.String(), nullable=True))
    op.add_column("payments", sa.Column("transfer_amount_reversed", sa.Float(), nullable=True))
    op.add_column("withdrawals", sa.Column("payout_failure_message", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("withdrawals", "payout_failure_message")
    op.drop_column("payments", "transfer_amount_reversed")
    op.drop_column("payments", "payment_method_type")
