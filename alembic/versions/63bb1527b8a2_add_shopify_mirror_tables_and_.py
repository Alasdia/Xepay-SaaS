"""add shopify mirror tables and uninstalled_at

Mirroring produits/commandes/clients Shopify par webhooks (demande
explicite de l'utilisateur de synchroniser pleinement avec la boutique,
pas seulement réagir au cycle de vie de l'app) - voir models.
Shopify{Product,Order,Customer}Mirror et routes/webhook/shopify.py.
AUCUN rapport avec l'onglet Commerce > Shopify (lecture live via
GraphQL, jamais changée) : ce mirroir est un magasin SUPPLÉMENTAIRE.

shopify_shops.uninstalled_at : seul signal de désinstallation (webhook
app/uninstalled) - access_token n'est jamais vidé (contrainte
explicite du modèle), juste marqué obsolète.

Revision ID: 63bb1527b8a2
Revises: 19a2f7d59273
Create Date: 2026-11-28 00:53:15.906310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63bb1527b8a2'
down_revision: Union[str, Sequence[str], None] = '19a2f7d59273'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("shopify_shops", sa.Column("uninstalled_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "shopify_product_mirrors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("shop_domain", sa.String(), nullable=False),
        sa.Column("shopify_product_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("shopify_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shopify_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_domain", "shopify_product_id", name="uq_shopify_product_mirror_shop_product"),
    )
    op.create_index("idx_spm_shop_domain", "shopify_product_mirrors", ["shop_domain"])

    op.create_table(
        "shopify_order_mirrors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("shop_domain", sa.String(), nullable=False),
        sa.Column("shopify_order_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("financial_status", sa.String(), nullable=True),
        sa.Column("fulfillment_status", sa.String(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("customer_email", sa.String(), nullable=True),
        sa.Column("shopify_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shopify_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_domain", "shopify_order_id", name="uq_shopify_order_mirror_shop_order"),
    )
    op.create_index("idx_som_shop_domain", "shopify_order_mirrors", ["shop_domain"])

    op.create_table(
        "shopify_customer_mirrors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("shop_domain", sa.String(), nullable=False),
        sa.Column("shopify_customer_id", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("orders_count", sa.Integer(), nullable=True),
        sa.Column("total_spent", sa.Float(), nullable=True),
        sa.Column("shopify_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shopify_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_domain", "shopify_customer_id", name="uq_shopify_customer_mirror_shop_customer"),
    )
    op.create_index("idx_scm_shop_domain", "shopify_customer_mirrors", ["shop_domain"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_scm_shop_domain", table_name="shopify_customer_mirrors")
    op.drop_table("shopify_customer_mirrors")
    op.drop_index("idx_som_shop_domain", table_name="shopify_order_mirrors")
    op.drop_table("shopify_order_mirrors")
    op.drop_index("idx_spm_shop_domain", table_name="shopify_product_mirrors")
    op.drop_table("shopify_product_mirrors")
    op.drop_column("shopify_shops", "uninstalled_at")
