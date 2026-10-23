"""add device/ip to refresh_tokens, google link, passkey credentials

Revision ID: c4f7a1e9d3b2
Revises: b7e3a1c9f204
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f7a1e9d3b2'
down_revision: Union[str, Sequence[str], None] = 'b7e3a1c9f204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("refresh_tokens", sa.Column("device", sa.String(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("ip", sa.String(), nullable=True))

    op.add_column("users", sa.Column("google_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("google_email", sa.String(), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("credential_id", sa.String(), nullable=False, unique=True),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_passkey_credentials_user_id", "passkey_credentials", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_passkey_credentials_user_id", table_name="passkey_credentials")
    op.drop_table("passkey_credentials")
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_email")
    op.drop_column("users", "google_id")
    op.drop_column("refresh_tokens", "ip")
    op.drop_column("refresh_tokens", "device")
