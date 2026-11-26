"""add buildness llc credits

buildness_llc_credits - le marchand paie Xepay 500 USD (compte Stripe
plateforme, voir backend/routes/buildness_payment.py) AVANT de pouvoir
déclencher /buildness/onboard. Une ligne = un paiement confirmé
(checkout.session.completed), statut "paid_unused" jusqu'à ce qu'il
serve réellement à former une LLC (create_company a réussi), puis
"consumed" - jamais consommé sur un échec doola, pour que le marchand
puisse réessayer sans repayer.

Revision ID: 5b7c36e20af4
Revises: c9a4e7f1d583
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b7c36e20af4'
down_revision: Union[str, Sequence[str], None] = 'c9a4e7f1d583'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "buildness_llc_credits",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("buildness_company_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["buildness_company_id"], ["buildness_companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_checkout_session_id"),
    )
    op.create_index(
        "idx_bnllccr_workspace_status",
        "buildness_llc_credits",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_bnllccr_workspace_status", table_name="buildness_llc_credits")
    op.drop_table("buildness_llc_credits")
