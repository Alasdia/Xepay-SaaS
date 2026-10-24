"""add 2fa backup code columns to users

Revision ID: a3d7e5f9c1b8
Revises: f1a9c3e7b5d2
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3d7e5f9c1b8'
down_revision: Union[str, Sequence[str], None] = 'f1a9c3e7b5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("two_factor_backup_code_hash", sa.String(), nullable=True))
    op.add_column("users", sa.Column("two_factor_backup_code_generated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "two_factor_backup_code_generated_at")
    op.drop_column("users", "two_factor_backup_code_hash")
