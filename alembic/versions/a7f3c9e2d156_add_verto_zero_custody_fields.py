"""add verto zero-custody withdrawal fields

Architecture "Zero-Custody" des retraits (Stripe Connect -> wallet USD
Verto -> compte bancaire local UEMOA du marchand) - voir
backend/services/verto_service.py, backend/routes/webhook/verto.py.

Revision ID: a7f3c9e2d156
Revises: d8e1f4b2c930
Create Date: 2026-10-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3c9e2d156'
down_revision: Union[str, Sequence[str], None] = 'd8e1f4b2c930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("profiles", sa.Column("verto_company_id", sa.String(), nullable=True))
    op.create_index("ix_profiles_verto_company_id", "profiles", ["verto_company_id"])
    op.add_column("profiles", sa.Column("verto_wallet_id", sa.String(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column(
            "verto_onboarding_status",
            sa.String(),
            nullable=True,
            server_default="not_started",
        ),
    )
    op.add_column("profiles", sa.Column("verto_usd_account_number", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("verto_usd_bank_code", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("verto_usd_bank_name", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("stripe_external_account_id", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("beneficiary_bank_iban", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("beneficiary_bank_name", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("verto_beneficiary_id", sa.String(), nullable=True))

    op.add_column("withdrawals", sa.Column("verto_transfer_id", sa.String(), nullable=True))
    op.create_index("ix_withdrawals_verto_transfer_id", "withdrawals", ["verto_transfer_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_withdrawals_verto_transfer_id", table_name="withdrawals")
    op.drop_column("withdrawals", "verto_transfer_id")

    op.drop_column("profiles", "verto_beneficiary_id")
    op.drop_column("profiles", "beneficiary_bank_name")
    op.drop_column("profiles", "beneficiary_bank_iban")
    op.drop_column("profiles", "stripe_external_account_id")
    op.drop_column("profiles", "verto_usd_bank_name")
    op.drop_column("profiles", "verto_usd_bank_code")
    op.drop_column("profiles", "verto_usd_account_number")
    op.drop_column("profiles", "verto_onboarding_status")
    op.drop_column("profiles", "verto_wallet_id")
    op.drop_index("ix_profiles_verto_company_id", table_name="profiles")
    op.drop_column("profiles", "verto_company_id")
