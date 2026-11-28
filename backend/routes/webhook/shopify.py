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
vraie commande test sur Connect1 une fois la méthode manuelle créée.

CYCLE DE VIE DE L'APP (app/uninstalled, ajouté le 2026-11-28) - AUCUN
mirroring de données Shopify (produits/commandes/clients) ici : le
marchand préfère explicitement tout lire en direct via l'API, jamais
une copie côté Xepay (discussion du 2026-11-28, revient sur un
chantier de mirroring complet construit puis annulé le même jour) -
voir models.ShopifyShop.uninstalled_at, seul état propre à Xepay
introduit.

Les 3 webhooks RGPD obligatoires (customers/data_request, customers/
redact, shop/redact) ont été envisagés puis RETIRÉS le 2026-11-28 :
confirmé que Shopify ne les impose qu'aux apps listées sur l'App Store
("Custom apps for a single store are not required to implement GDPR
webhooks") - "Xepay Sync" n'y est jamais soumise, et sans aucune
donnée Shopify mirorée, ces 3 webhooks n'auraient eu aucune action
réelle à accomplir (juste un email interne disant "rien à faire") -
jamais ajoutés pour cette raison.

CENTRE DE NOTIFICATIONS (products/create, customers/create, +
extension d'orders/create ci-dessous - ajouté le 2026-11-28, demande
explicite de l'utilisateur) - voir models.Notification/services/
notification_service.py : signale au marchand qu'un produit/client/
commande a été créé DIRECTEMENT sur sa boutique Shopify (jamais depuis
le dashboard Xepay, qui lui utilise les toasts - distinction
explicite). Chaque notification est un ÉVÈNEMENT PONCTUEL (titre/
résumé figés au moment reçu), JAMAIS une copie synchronisée du
produit/client/commande - toujours cohérent avec le refus du mirroring
complet (discussion du 2026-11-28)."""

import hashlib
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from backend.database import SessionLocal
from backend.models import Link, ShopifyOrderPayment, ShopifyShop, UserDB, generate_prefixed_id
from backend.services.email_service import send_shopify_payment_link_email
from backend.services.notification_service import create_notification
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


def _resolve_shop_merchant_id(db, shop: str) -> str | None:
    """Résout le workspace Xepay rattaché à cette boutique (ou None si
    inconnue/jamais rattachée - voir GET /shopify/install, routes/
    shopify.py) - factorisé le 2026-11-28 pour les 3 handlers du
    centre de notifications (orders/create étendu ci-dessous +
    products/create + customers/create), jamais utilisé pour créer une
    copie du produit/client/commande, seulement pour savoir à QUEL
    workspace adresser la notification."""
    shop_row = db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).first()
    if not shop_row or not shop_row.merchant_id:
        return None
    return shop_row.merchant_id


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

    # Notification (ajoutée le 2026-11-28) - TOUTE commande créée sur la
    # boutique, indépendamment de son mode de paiement (contrairement à
    # la génération de lien Xepay plus bas, qui ne concerne QUE le
    # gateway manuel "Xepay") - session DB indépendante, commitée/
    # fermée immédiatement, jamais mêlée à la transaction Link/
    # ShopifyOrderPayment plus bas.
    notif_db = SessionLocal()
    try:
        merchant_id = _resolve_shop_merchant_id(notif_db, shop)
        if merchant_id:
            order_name = order.get("name") or f"#{order_id}"
            amount = order.get("total_price")
            currency = order.get("currency") or ""
            create_notification(
                notif_db, merchant_id, "shopify_order_created",
                f"Nouvelle commande {order_name} sur votre boutique Shopify",
                f"{amount} {currency}".strip() if amount is not None else None,
            )
    finally:
        notif_db.close()

    # Ignoré (200, jamais une erreur - Shopify livre CE webhook pour
    # TOUTES les commandes, pas seulement celles qui nous intéressent) :
    # déjà payée, ou pas payée avec "notre" méthode manuelle. La
    # notification ci-dessus a déjà été créée pour TOUTE commande, ce
    # filtre ne concerne QUE la génération d'un lien Xepay.
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


async def _verify_shopify_webhook(request: Request) -> tuple[str, dict]:
    """Coeur commun au handler ci-dessous (ajouté le 2026-11-28) -
    jamais appliqué rétroactivement à shopify_orders_create_webhook
    plus haut (hors périmètre de ce chantier). Lève HTTPException
    (401/400) sur signature/en-tête/JSON invalide - jamais un retour
    silencieux."""
    raw_body = await request.body()
    if not verify_webhook_signature(raw_body, request.headers.get("X-Shopify-Hmac-Sha256")):
        raise HTTPException(status_code=401, detail="Signature invalide")
    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop or not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="En-tête X-Shopify-Shop-Domain manquant ou invalide")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="JSON invalide")
    return shop, payload


@router.post("/webhook/shopify/app-uninstalled")
async def shopify_app_uninstalled_webhook(request: Request):
    """SEUL signal de désinstallation (voir models.ShopifyShop,
    uninstalled_at) - access_token n'est JAMAIS vidé (contrainte
    explicite du modèle), juste marqué obsolète. _get_connected_shop
    (routes/shopify.py) exclut désormais cette boutique de "connectée"
    partout - une ré-installation (shopify_callback) remet
    uninstalled_at à NULL automatiquement. AUCUNE donnée Shopify
    (produits/commandes/clients) touchée ici - rien n'en est mirroré."""
    shop, _payload = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        shop_row = db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).first()
        if shop_row:
            shop_row.uninstalled_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/products-create")
async def shopify_products_create_webhook(request: Request):
    """Centre de notifications (models.Notification, ajouté le
    2026-11-28) - crée UN évènement ponctuel ("ce produit a été créé"),
    JAMAIS une copie synchronisée du produit (voir le docstring en tête
    de fichier) : title/description sont un résumé figé au moment
    reçu, jamais relus/mis à jour ensuite."""
    shop, product = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        merchant_id = _resolve_shop_merchant_id(db, shop)
        if merchant_id:
            title = product.get("title") or "Produit sans titre"
            create_notification(
                db, merchant_id, "shopify_product_created",
                "Nouveau produit sur votre boutique Shopify", title,
            )
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/customers-create")
async def shopify_customers_create_webhook(request: Request):
    """Centre de notifications (models.Notification, ajouté le
    2026-11-28) - même principe que products/create ci-dessus, jamais
    une copie synchronisée du client."""
    shop, customer = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        merchant_id = _resolve_shop_merchant_id(db, shop)
        if merchant_id:
            name = " ".join(filter(None, [customer.get("first_name"), customer.get("last_name")])).strip()
            name = name or customer.get("email") or "Client"
            create_notification(
                db, merchant_id, "shopify_customer_created",
                "Nouveau client sur votre boutique Shopify", name,
            )
    finally:
        db.close()
    return {"ok": True}
