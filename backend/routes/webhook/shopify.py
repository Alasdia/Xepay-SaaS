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

MIRRORING produits/commandes/clients + cycle de vie de l'app (ajouté le
2026-11-28, demande explicite de l'utilisateur de synchroniser
pleinement avec la boutique, pas seulement réagir à app/uninstalled) -
voir models.Shopify{Product,Order,Customer}Mirror et services/
shopify_service.py::register_all_mirror_webhooks pour l'enregistrement
côté Shopify. AUCUN rapport avec l'onglet Commerce > Shopify (lecture
live via GraphQL, jamais changée) : ce mirroir est un magasin
SUPPLÉMENTAIRE.

Les webhooks RGPD obligatoires (customers/data_request, customers/
redact, shop/redact) sont REÇUS ici mais ne peuvent PAS être enregistrés
par register_all_mirror_webhooks : Shopify refuse ces 3 topics via
webhookSubscriptionCreate (vérifié le 2026-11-28, community.shopify.dev)
- configurables UNIQUEMENT via shopify.app.toml (CLI moderne, jamais
utilisé par cette app) ou la section "Compliance webhooks" du Partner
Dashboard (configuration MANUELLE, une seule fois, côté humain - coller
les 3 URLs .../customers-data-request, .../customers-redact,
.../shop-redact là-bas)."""

import hashlib
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from backend.database import SessionLocal
from backend.models import (
    Link,
    ShopifyCustomerMirror,
    ShopifyOrderMirror,
    ShopifyOrderPayment,
    ShopifyProductMirror,
    ShopifyShop,
    UserDB,
    generate_prefixed_id,
)
from backend.services.email_service import send_shopify_gdpr_request_internal_email, send_shopify_payment_link_email
from backend.services.shopify_service import (
    SHOPIFY_MANUAL_GATEWAY_NAME,
    is_valid_shop_domain,
    order_gid,
    verify_webhook_signature,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://api.xepay.finance")


async def _verify_shopify_webhook(request: Request) -> tuple[str, dict]:
    """Coeur commun à TOUS les handlers de ce fichier (orders-create
    compris, voir ci-dessous) - factorisé le 2026-11-28 lors de l'ajout
    du mirroring (10 nouveaux handlers, jamais dupliquer ces 3
    vérifications autant de fois). Lève HTTPException (401/400) sur
    signature/en-tête/JSON invalide - jamais un retour silencieux."""
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


def _parse_shopify_datetime(value):
    """Shopify envoie des dates ISO8601 avec offset explicite (ex.
    "2023-02-20T20:50:20-05:00") - datetime.fromisoformat les gère
    nativement depuis Python 3.11, jamais besoin de dateutil ici. None
    silencieux sur une valeur absente/invalide plutôt qu'une exception :
    un champ de date mal formé ne doit jamais faire échouer tout le
    mirroring d'un produit/commande/client par ailleurs valide."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _upsert_product_mirror(db, shop: str, product: dict) -> None:
    """NON VÉRIFIÉ contre un vrai payload products/create|update (même
    réserve que orders/create plus haut) - forme suivie depuis la doc
    officielle Shopify (REST legacy, toujours la forme des payloads
    webhook même en API GraphQL récente)."""
    product_id = product.get("id")
    if not product_id:
        return
    variants = product.get("variants") or []
    prices = [float(v["price"]) for v in variants if v.get("price") is not None]
    image_url = (product.get("image") or {}).get("src")

    row = (
        db.query(ShopifyProductMirror)
        .filter(ShopifyProductMirror.shop_domain == shop, ShopifyProductMirror.shopify_product_id == str(product_id))
        .first()
    )
    if not row:
        row = ShopifyProductMirror(shop_domain=shop, shopify_product_id=str(product_id))
        db.add(row)
    row.title = product.get("title")
    row.status = product.get("status")
    row.vendor = product.get("vendor")
    row.price_min = min(prices) if prices else None
    row.price_max = max(prices) if prices else None
    row.image_url = image_url
    row.shopify_created_at = _parse_shopify_datetime(product.get("created_at"))
    row.shopify_updated_at = _parse_shopify_datetime(product.get("updated_at"))
    row.raw_payload = product
    db.commit()


def _upsert_order_mirror(db, shop: str, order: dict) -> None:
    """Mirroring GÉNÉRIQUE - TOUTE commande, quelle que soit sa méthode
    de paiement (contrairement à ShopifyOrderPayment, qui ne trace QUE
    les commandes payées via la méthode manuelle "Xepay" + le Link
    Xepay associé, logique totalement indépendante - voir
    shopify_orders_create_webhook ci-dessous, qui appelle les deux)."""
    order_id = order.get("id")
    if not order_id:
        return
    amount = order.get("total_price")

    row = (
        db.query(ShopifyOrderMirror)
        .filter(ShopifyOrderMirror.shop_domain == shop, ShopifyOrderMirror.shopify_order_id == str(order_id))
        .first()
    )
    if not row:
        row = ShopifyOrderMirror(shop_domain=shop, shopify_order_id=str(order_id))
        db.add(row)
    row.name = order.get("name")
    row.financial_status = order.get("financial_status")
    row.fulfillment_status = order.get("fulfillment_status")
    row.cancelled_at = _parse_shopify_datetime(order.get("cancelled_at"))
    row.total_price = float(amount) if amount is not None else None
    row.currency = order.get("currency")
    row.customer_email = (order.get("email") or order.get("contact_email") or "").strip() or None
    row.shopify_created_at = _parse_shopify_datetime(order.get("created_at"))
    row.shopify_updated_at = _parse_shopify_datetime(order.get("updated_at"))
    row.raw_payload = order
    db.commit()


def _upsert_customer_mirror(db, shop: str, customer: dict) -> None:
    customer_id = customer.get("id")
    if not customer_id:
        return
    total_spent = customer.get("total_spent")

    row = (
        db.query(ShopifyCustomerMirror)
        .filter(ShopifyCustomerMirror.shop_domain == shop, ShopifyCustomerMirror.shopify_customer_id == str(customer_id))
        .first()
    )
    if not row:
        row = ShopifyCustomerMirror(shop_domain=shop, shopify_customer_id=str(customer_id))
        db.add(row)
    row.first_name = customer.get("first_name")
    row.last_name = customer.get("last_name")
    row.email = customer.get("email")
    row.phone = customer.get("phone")
    row.orders_count = customer.get("orders_count")
    row.total_spent = float(total_spent) if total_spent is not None else None
    row.shopify_created_at = _parse_shopify_datetime(customer.get("created_at"))
    row.shopify_updated_at = _parse_shopify_datetime(customer.get("updated_at"))
    row.raw_payload = customer
    db.commit()


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
    shop, order = await _verify_shopify_webhook(request)

    order_id = order.get("id")
    if not order_id:
        raise HTTPException(status_code=400, detail="Commande sans id")

    # Mirroring GÉNÉRIQUE (ajouté le 2026-11-28) - TOUTE commande,
    # AVANT le filtre métier ci-dessous qui ne concerne que la
    # génération d'un lien Xepay pour le gateway manuel "Xepay". Session
    # DB indépendante, commitée/fermée immédiatement - jamais mêlée à la
    # transaction Link/ShopifyOrderPayment plus bas (dont le rollback
    # sur IntegrityError ne doit jamais défaire ce mirroring, qui n'a
    # rien à voir avec cette logique).
    mirror_db = SessionLocal()
    try:
        _upsert_order_mirror(mirror_db, shop, order)
    finally:
        mirror_db.close()

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


# =========================================================
# Mirroring produits/clients + orders/update (ajouté le 2026-11-28) -
# voir le docstring en tête de fichier. Chaque handler : vérifie
# signature/en-tête/JSON (_verify_shopify_webhook), upsert dans sa
# propre session DB (jamais partagée entre handlers), renvoie toujours
# {"ok": True} même si la ressource référencée est inconnue (idempotent,
# jamais une erreur sur un simple "rien à faire").
# =========================================================

@router.post("/webhook/shopify/products-create")
async def shopify_products_create_webhook(request: Request):
    shop, product = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        _upsert_product_mirror(db, shop, product)
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/products-update")
async def shopify_products_update_webhook(request: Request):
    shop, product = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        _upsert_product_mirror(db, shop, product)
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/products-delete")
async def shopify_products_delete_webhook(request: Request):
    # Payload MINIMAL pour ce topic (confirmé par la doc officielle
    # Shopify) - uniquement {"id": ...}, jamais les autres champs du
    # produit.
    shop, payload = await _verify_shopify_webhook(request)
    product_id = payload.get("id")
    if product_id:
        db = SessionLocal()
        try:
            db.query(ShopifyProductMirror).filter(
                ShopifyProductMirror.shop_domain == shop,
                ShopifyProductMirror.shopify_product_id == str(product_id),
            ).delete()
            db.commit()
        finally:
            db.close()
    return {"ok": True}


@router.post("/webhook/shopify/customers-create")
async def shopify_customers_create_webhook(request: Request):
    shop, customer = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        _upsert_customer_mirror(db, shop, customer)
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/customers-update")
async def shopify_customers_update_webhook(request: Request):
    shop, customer = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        _upsert_customer_mirror(db, shop, customer)
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/customers-delete")
async def shopify_customers_delete_webhook(request: Request):
    shop, payload = await _verify_shopify_webhook(request)
    customer_id = payload.get("id")
    if customer_id:
        db = SessionLocal()
        try:
            db.query(ShopifyCustomerMirror).filter(
                ShopifyCustomerMirror.shop_domain == shop,
                ShopifyCustomerMirror.shopify_customer_id == str(customer_id),
            ).delete()
            db.commit()
        finally:
            db.close()
    return {"ok": True}


@router.post("/webhook/shopify/orders-update")
async def shopify_orders_update_webhook(request: Request):
    shop, order = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        _upsert_order_mirror(db, shop, order)
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhook/shopify/app-uninstalled")
async def shopify_app_uninstalled_webhook(request: Request):
    """SEUL signal de désinstallation (voir models.ShopifyShop,
    uninstalled_at) - access_token n'est JAMAIS vidé (contrainte
    explicite du modèle), juste marqué obsolète. _get_connected_shop
    (routes/shopify.py) exclut désormais cette boutique de "connectée"
    partout - une ré-installation (shopify_callback) remet
    uninstalled_at à NULL automatiquement."""
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


# =========================================================
# RGPD obligatoire (ajouté le 2026-11-28) - voir le docstring en tête
# de fichier pour pourquoi ces 3 topics ne peuvent PAS être enregistrés
# par register_all_mirror_webhooks (refusés par webhookSubscriptionCreate,
# configuration MANUELLE requise côté Partner Dashboard). NON VÉRIFIÉ
# contre un vrai payload (même réserve que orders/create en tête de
# fichier) - forme suivie depuis la doc officielle Shopify.
# =========================================================

@router.post("/webhook/shopify/customers-data-request")
async def shopify_customers_data_request_webhook(request: Request):
    """AUCUNE automatisation possible : compiler et transmettre les
    données d'un client à sa demande est un acte humain, jamais
    déductible d'un simple webhook - alerte l'équipe Xepay par email
    (voir send_shopify_gdpr_request_internal_email), jamais plus."""
    shop, payload = await _verify_shopify_webhook(request)
    logger.warning("RGPD customers/data_request reçu pour %s", shop)
    try:
        send_shopify_gdpr_request_internal_email(shop, "customers/data_request", payload)
    except Exception:
        logger.exception("Échec notification RGPD customers/data_request pour %s", shop)
    return {"ok": True}


@router.post("/webhook/shopify/customers-redact")
async def shopify_customers_redact_webhook(request: Request):
    """Supprime le mirroir client correspondant - la notification email
    (best-effort, dans son propre try/except) ne doit JAMAIS empêcher
    cette suppression de committer, l'inverse serait un vrai problème
    de conformité RGPD."""
    shop, payload = await _verify_shopify_webhook(request)
    customer_id = (payload.get("customer") or {}).get("id")
    if customer_id:
        db = SessionLocal()
        try:
            db.query(ShopifyCustomerMirror).filter(
                ShopifyCustomerMirror.shop_domain == shop,
                ShopifyCustomerMirror.shopify_customer_id == str(customer_id),
            ).delete()
            db.commit()
        finally:
            db.close()
    try:
        send_shopify_gdpr_request_internal_email(shop, "customers/redact", payload)
    except Exception:
        logger.exception("Échec notification RGPD customers/redact pour %s", shop)
    return {"ok": True}


@router.post("/webhook/shopify/shop-redact")
async def shopify_shop_redact_webhook(request: Request):
    """Purge COMPLÈTE (envoyé par Shopify ~48h après une désinstallation,
    voir app/uninstalled ci-dessus) : les 3 mirroirs + la ligne
    ShopifyShop elle-même. Ne touche JAMAIS ShopifyOrderPayment/Link -
    ce sont les PROPRES registres financiers de Xepay (paiements/liens
    réellement émis), pas une copie de données Shopify, hors périmètre
    RGPD de cette boutique Shopify précise."""
    shop, payload = await _verify_shopify_webhook(request)
    db = SessionLocal()
    try:
        db.query(ShopifyProductMirror).filter(ShopifyProductMirror.shop_domain == shop).delete()
        db.query(ShopifyOrderMirror).filter(ShopifyOrderMirror.shop_domain == shop).delete()
        db.query(ShopifyCustomerMirror).filter(ShopifyCustomerMirror.shop_domain == shop).delete()
        db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).delete()
        db.commit()
    finally:
        db.close()
    try:
        send_shopify_gdpr_request_internal_email(shop, "shop/redact", payload)
    except Exception:
        logger.exception("Échec notification RGPD shop/redact pour %s", shop)
    return {"ok": True}
