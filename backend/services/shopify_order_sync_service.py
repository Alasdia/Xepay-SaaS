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

from backend.models import ShopifyDraftOrderPayment, ShopifyOrderPayment, ShopifyShop
from backend.security import decrypt_secret
from backend.services.notification_service import create_notification
from backend.services.shopify_service import ShopifyAPIError, complete_draft_order, mark_order_as_paid

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


def sync_draft_order_paid_with_shopify(db: Session, link, xepay_reference: str) -> None:
    """Pendant de sync_order_paid_with_shopify ci-dessus pour une commande
    créée DEPUIS le dashboard Xepay (voir models.ShopifyDraftOrderPayment,
    POST /shopify/draft-orders) - complete_draft_order (draftOrderComplete)
    marque la commande payée côté Shopify, inventaire décompté. Même
    garantie "ne lève jamais" que sync_order_paid_with_shopify : un souci
    Shopify ne doit jamais remettre en cause le paiement Xepay déjà
    crédité.

    create_notification en plus (demande explicite du 2026-11-28: "le
    marchand doit comprendre que cette commande... est payée via un
    lien xepay") - le marchand voit cette commande apparaître payée
    dans son admin Shopify SANS que paymentGatewayNames ne mentionne
    Xepay (complete_draft_order est appelée sans paymentGatewayId) ;
    cette notification est le seul canal qui le lui confirme sans
    ambiguïté. Volontairement APRÈS le commit du paiement ci-dessous,
    dans son propre try/except : un échec de notification ne doit
    jamais faire perdre le marquage déjà committé."""
    draft_order_payment = (
        db.query(ShopifyDraftOrderPayment)
        .filter(ShopifyDraftOrderPayment.link_id == link.id)
        .first()
    )
    if not draft_order_payment or draft_order_payment.completed_at:
        return

    shop_row = (
        db.query(ShopifyShop)
        .filter(ShopifyShop.shop_domain == draft_order_payment.shop_domain)
        .first()
    )
    if not shop_row or not shop_row.access_token:
        logger.warning(
            "Commande Shopify (draft %s, %s) payée côté Xepay mais boutique introuvable/sans token",
            draft_order_payment.draft_order_gid, draft_order_payment.shop_domain,
        )
        return

    try:
        access_token = decrypt_secret(shop_row.access_token)
        asyncio.run(complete_draft_order(
            draft_order_payment.shop_domain, access_token, draft_order_payment.draft_order_gid
        ))
    except ShopifyAPIError:
        logger.exception(
            "Échec draftOrderComplete pour la commande Shopify (draft %s, %s)",
            draft_order_payment.draft_order_gid, draft_order_payment.shop_domain,
        )
        return
    except Exception:
        logger.exception(
            "Erreur inattendue lors de la complétion de la commande Shopify (draft %s, %s)",
            draft_order_payment.draft_order_gid, draft_order_payment.shop_domain,
        )
        return

    draft_order_payment.completed_at = datetime.now(timezone.utc)
    draft_order_payment.xepay_reference = xepay_reference
    db.commit()

    try:
        create_notification(
            db, draft_order_payment.merchant_id, "shopify_draft_order_paid",
            "Commande Shopify payée via Xepay",
            "Cette commande, créée depuis votre dashboard Xepay, vient d'être payée par le client via un lien Xepay.",
        )
    except Exception:
        logger.exception(
            "Échec notification de paiement pour la commande Shopify (draft %s, %s)",
            draft_order_payment.draft_order_gid, draft_order_payment.shop_domain,
        )
