"""add workspace_id to security_events

Revision ID: 00d453a4dfbe
Revises: 6beefe5aae73
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00d453a4dfbe'
down_revision: Union[str, Sequence[str], None] = '6beefe5aae73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("security_events", sa.Column("workspace_id", sa.String(), nullable=True))
    op.create_index("idx_security_events_workspace_id", "security_events", ["workspace_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_security_events_workspace_id", table_name="security_events")
    op.drop_column("security_events", "workspace_id")
