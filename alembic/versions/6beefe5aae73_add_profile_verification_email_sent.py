"""add verification_email_sent to profiles

Revision ID: 6beefe5aae73
Revises: 2cc2dc7f0883
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6beefe5aae73'
down_revision: Union[str, Sequence[str], None] = '2cc2dc7f0883'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("profiles", sa.Column("verification_email_sent", sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("profiles", "verification_email_sent")
