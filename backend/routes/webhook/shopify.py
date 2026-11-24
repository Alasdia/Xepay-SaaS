"""Webhook Shopify orders/create - reçoit les commandes payées avec la
méthode de paiement MANUELLE "Payer via Xepay" (voir services/
shopify_service.SHOPIFY_MANUAL_GATEWAY_NAME) et génère le lien de
paiement Xepay correspondant (voir services/shopify_order_sync_service.py
pour la suite - marquage payé côté Shopify une fois le Link réglé).

CONTEXTE PRODUIT (demande du 2026-11-24) : un marchand veut encaisser ses
commandes Shopify via un lien de paiement Xepay plutôt que Shopify
Payments. Shopify n'autorise un moyen de paiement tiers à apparaître dans
SON checkout natif qu'au travers du programme "Payments Apps" (review/
certification - hors périmètre, gros chantier). Le contournement 100%
gratuit et officiellement supporté par Shopify : une méthode de paiement
MANUELLE (Settings > Payments > Manual payment methods dans l'admin
Shopify - gratuite sur tous les plans, confirmé par la doc officielle,
AUCUNE API ne permet de la créer, le marchand doit la configurer à la
main, une seule fois). Un client qui la choisit au checkout crée une
commande financial_status="pending" ; ce webhook la détecte et génère un
lien Xepay, envoyé par email (les instructions de checkout Shopify sont
STATIQUES, pas de lien dynamique par commande possible nativement - voir
send_shopify_payment_link_email, services/email_service.py).

NON VÉRIFIÉ contre un vrai webhook Shopify (aucune vraie commande n'a
encore été créée sur Connect1 avec une méthode "Xepay") - l'algorithme de
signature (X-Shopify-Hmac-Sha256, base64) et la forme du payload orders/
create suivent la documentation officielle Shopify, vérifiés ici
uniquement par simulation (voir le script de test). À confirmer par une
vraie commande test sur Connect1 une fois la méthode manuelle créée."""

import hashlib
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from backend.database import SessionLocal
from backend.models import Link, ShopifyOrderPayment, ShopifyShop, UserDB, generate_prefixed_id
from backend.services.email_service import send_shopify_payment_link_email
from backend.services.shopify_service import (
    SHOPIFY_MANUAL_GATEWAY_NAME,
    is_valid_shop_domain,
    order_gid,
    verify_webhook_signature,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://api.xepay.finance")


def _uses_xepay_gateway(order: dict) -> bool:
    """payment_gateway_names (liste, une commande peut en théorie en avoir
    plusieurs) doit contenir EXACTEMENT le nom configuré par le marchand
    (SHOPIFY_MANUAL_GATEWAY_NAME), comparé insensible à la casse - sinon
    cette commande relève d'une AUTRE méthode manuelle du même marchand
    (COD, virement...) ou de Shopify Payments, jamais pour nous."""
    names = order.get("payment_gateway_names") or []
    target = SHOPIFY_MANUAL_GATEWAY_NAME.strip().lower()
    return any(str(n).strip().lower() == target for n in names)


@router.post("/webhook/shopify/orders-create")
async def shopify_orders_create_webhook(request: Request):
    raw_body = await request.body()

    if not verify_webhook_signature(raw_body, request.headers.get("X-Shopify-Hmac-Sha256")):
        raise HTTPException(status_code=401, detail="Signature invalide")

    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop or not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="En-tête X-Shopify-Shop-Domain manquant ou invalide")

    try:
        order = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="JSON invalide")

    order_id = order.get("id")
    if not order_id:
        raise HTTPException(status_code=400, detail="Commande sans id")

    # Ignoré (200, jamais une erreur - Shopify livre CE webhook pour
    # TOUTES les commandes, pas seulement celles qui nous intéressent) :
    # déjà payée, ou pas payée avec "notre" méthode manuelle.
    if order.get("financial_status") != "pending" or not _uses_xepay_gateway(order):
        return {"ok": True, "ignored": True}

    db = SessionLocal()
    try:
        shop_row = db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).first()
        if not shop_row or not shop_row.merchant_id:
            # Boutique inconnue, ou connue mais jamais rattachée à un
            # marchand Xepay (voir GET /shopify/install, routes/shopify.py)
            # - rien à faire tant que ce rattachement n'existe pas.
            logger.warning(
                "Commande Shopify %s (%s) ignorée : boutique non rattachée à un marchand Xepay",
                order_id, shop,
            )
            return {"ok": True, "ignored": True}

        merchant_id = shop_row.merchant_id
        owner = db.query(UserDB).filter(UserDB.id == merchant_id).first()
        if not owner:
            logger.warning("Commande Shopify %s (%s) ignorée : marchand %s introuvable", order_id, shop, merchant_id)
            return {"ok": True, "ignored": True}

        amount = order.get("total_price")
        currency = order.get("currency") or "USD"
        customer_email = (order.get("email") or order.get("contact_email") or "").strip() or None
        order_name = order.get("name") or f"#{order_id}"

        raw_token = generate_prefixed_id("pl")
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        pay_url = f"{PUBLIC_API_URL}/pay/{raw_token}"

        link = Link(
            id=generate_prefixed_id("lk"),
            token=hashed_token,
            user_id=merchant_id,
            email=owner.email,
            name=f"Commande Shopify {order_name}",
            amount=float(amount) if amount is not None else None,
            currency=str(currency).upper(),
            url=pay_url,
            created_at=datetime.now(timezone.utc),
            active=True,
            # Pas d'expiration (contrairement au défaut de create_link pour
            # un lien à usage unique, routes/lien.py) : un client peut
            # mettre du temps à ouvrir l'email ci-dessous, rien ne justifie
            # de limiter ce lien à 30 minutes comme un lien créé à la main
            # dans le dashboard.
            expires_at=None,
            max_uses=1,
            link_metadata={
                "workspace_id": merchant_id,
                "user_id": merchant_id,
                "xepay_type": "shopify_order_payment",
                "shopify_shop_domain": shop,
                "shopify_order_id": str(order_id),
            },
            source="shopify",
        )
        db.add(link)
        db.flush()

        db.add(ShopifyOrderPayment(
            shop_domain=shop,
            shopify_order_id=str(order_id),
            shopify_order_gid=order_gid(order_id),
            link_id=link.id,
            merchant_id=merchant_id,
        ))
        db.commit()
    except IntegrityError:
        # UniqueConstraint(shop_domain, shopify_order_id) : livraison
        # dupliquée du même webhook (retry Shopify) - jamais un second
        # Link pour la même commande, même principe que
        # BuildnessWebhookLog.event_id (routes/webhook/doola.py).
        db.rollback()
        db.close()
        return {"ok": True}
    except Exception:
        db.rollback()
        db.close()
        logger.exception("Échec traitement commande Shopify %s (%s)", order_id, shop)
        raise HTTPException(status_code=500, detail="Erreur interne")

    try:
        if customer_email:
            send_shopify_payment_link_email(customer_email, order_name, amount, currency, pay_url)
        else:
            logger.warning("Commande Shopify %s (%s) sans email client : lien %s non envoyé", order_id, shop, link.id)
    except Exception:
        # Best-effort, même convention que l'envoi de facture PDF dans
        # process_checkout_session_payment (webhook/paiement.py) : le Link
        # existe déjà et reste consultable depuis le dashboard Xepay du
        # marchand même si cet envoi échoue.
        logger.exception("Échec envoi email lien Xepay pour la commande Shopify %s (%s)", order_id, shop)
    finally:
        db.close()

    return {"ok": True}
