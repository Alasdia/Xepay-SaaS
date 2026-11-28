"""add shopify_draft_order_payments table

Commande créée DEPUIS le dashboard Xepay pour un client du marchand
(POST /shopify/draft-orders) - jamais via le checkout Shopify
(contrairement à shopify_order_payments, qui trace une commande créée
par un vrai client ayant choisi le gateway manuel "Xepay" au checkout).
Voir models.ShopifyDraftOrderPayment et services/
shopify_order_sync_service.py::sync_draft_order_paid_with_shopify.

Revision ID: ec0a44a4c2af
Revises: a4b3bafb4dc1
Create Date: 2026-11-28 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec0a44a4c2af'
down_revision: Union[str, Sequence[str], None] = 'a4b3bafb4dc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "shopify_draft_order_payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("shop_domain", sa.String(), nullable=False),
        sa.Column("draft_order_gid", sa.String(), nullable=False),
        sa.Column("link_id", sa.String(), nullable=False),
        sa.Column("merchant_id", sa.String(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("xepay_reference", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["link_id"], ["links.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_domain", "draft_order_gid", name="uq_shopify_draft_order_payment_shop_draft"),
    )
    op.create_index("ix_shopify_draft_order_payments_shop_domain", "shopify_draft_order_payments", ["shop_domain"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_shopify_draft_order_payments_shop_domain", table_name="shopify_draft_order_payments")
    op.drop_table("shopify_draft_order_payments")
