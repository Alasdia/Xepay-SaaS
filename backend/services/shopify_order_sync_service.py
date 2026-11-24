"""Synchronisation du statut payé vers Shopify, une fois qu'un Link Xepay
créé pour une commande Shopify (voir routes/webhook/shopify.py,
models.ShopifyOrderPayment) est réellement payé - appelée depuis
process_checkout_session_payment (routes/webhook/paiement.py), juste
après que le paiement Xepay lui-même soit déjà committé.

sync_order_paid_with_shopify() est volontairement SYNCHRONE (comme son
appelant, qui tourne dans un thread pool - voir le docstring de
process_checkout_session_payment) et ne lève JAMAIS : un problème côté
Shopify (token révoqué, commande déjà marquée payée manuellement par le
marchand, panne réseau...) ne doit jamais remettre en cause le paiement
Xepay déjà crédité au wallet du marchand - best-effort, même logique que
l'envoi de facture PDF/email dans process_checkout_session_payment."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models import ShopifyOrderPayment, ShopifyShop
from backend.security import decrypt_secret
from backend.services.shopify_service import ShopifyAPIError, mark_order_as_paid

logger = logging.getLogger(__name__)


def sync_order_paid_with_shopify(db: Session, link, xepay_reference: str) -> None:
    order_payment = (
        db.query(ShopifyOrderPayment)
        .filter(ShopifyOrderPayment.link_id == link.id)
        .first()
    )
    if not order_payment or order_payment.marked_paid_at:
        return

    shop_row = (
        db.query(ShopifyShop)
        .filter(ShopifyShop.shop_domain == order_payment.shop_domain)
        .first()
    )
    if not shop_row or not shop_row.access_token:
        logger.warning(
            "Commande Shopify %s (%s) payée côté Xepay mais boutique introuvable/sans token",
            order_payment.shopify_order_id, order_payment.shop_domain,
        )
        return

    try:
        access_token = decrypt_secret(shop_row.access_token)
        # asyncio.run() : sûr ici car process_checkout_session_payment
        # tourne dans un thread du pool (BackgroundTasks sur une fonction
        # def, pas async def) - jamais appelé depuis l'event loop
        # principal, donc aucune boucle asyncio déjà en cours dans CE
        # thread (asyncio.run lèverait sinon RuntimeError).
        asyncio.run(mark_order_as_paid(
            order_payment.shop_domain, access_token, order_payment.shopify_order_id
        ))
    except ShopifyAPIError:
        logger.exception(
            "Échec orderMarkAsPaid pour la commande Shopify %s (%s)",
            order_payment.shopify_order_id, order_payment.shop_domain,
        )
        return
    except Exception:
        logger.exception(
            "Erreur inattendue lors du marquage payé de la commande Shopify %s (%s)",
            order_payment.shopify_order_id, order_payment.shop_domain,
        )
        return

    order_payment.marked_paid_at = datetime.now(timezone.utc)
    order_payment.xepay_reference = xepay_reference
    db.commit()
