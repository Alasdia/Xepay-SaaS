"""add payment charge_type

Les paiements par lien passent de destination charge à direct charge
(voir backend/services/stripe_service.py, create_checkout_session) - le
PaymentIntent vit désormais sur le compte connecté du marchand, plus sur
la plateforme, ce qui donne un reçu Stripe au nom du marchand (branding
settings.branding) au lieu de Xepay.

payment.link_id n'était jusqu'ici plus utilisable comme signal pour
distinguer destination charge (paiement par lien) de direct charge
(facture/abonnement) - voir backend/routes/payout.py (remboursement) et
backend/routes/webhook/paiement.py, qui s'appuyaient dessus. Un paiement
par lien peut désormais être l'un ou l'autre : charge_type devient le
seul signal fiable, posé explicitement à la création de chaque Payment
(paiement.py pour les liens, webhook/stripe.py pour factures/abonnements),
jamais déduit de link_id ensuite.

Revision ID: d9efd7c7893e
Revises: d4a7c2e9f031
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9efd7c7893e'
down_revision: Union[str, Sequence[str], None] = 'd4a7c2e9f031'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("charge_type", sa.String(), nullable=True))
    # Backfill des lignes déjà en base : avant ce changement, link_id rempli
    # <=> destination charge (paiement par lien), link_id NULL <=> direct
    # charge (facture/abonnement) - vrai à 100% pour toute ligne existante,
    # plus après ce déploiement (un paiement par lien peut désormais être
    # l'un ou l'autre). Dernière utilisation légitime de ce proxy : il est
    # ensuite remplacé partout par charge_type, posé explicitement.
    op.execute(
        "UPDATE payments SET charge_type = CASE WHEN link_id IS NOT NULL "
        "THEN 'destination' ELSE 'direct' END"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("payments", "charge_type")
