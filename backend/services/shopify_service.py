"""Pont Shopify pour l'app "Xepay Sync" (voir routes/shopify.py,
models.ShopifyShop) - orchestration des paiements Xepay et liaison des
commandes/factures aux métadonnées Stripe Connect pour une boutique
Shopify connectée.

NON VÉRIFIÉ contre un vrai appel sandbox (contrairement à
services/doola_service.py, qui a pu être vérifié avec de vraies clés) :
aucune app Shopify Partner n'existe encore pour ce projet. L'algorithme
de vérification HMAC OAuth et le endpoint d'échange de code ci-dessous
suivent l'implémentation de référence documentée par Shopify
(shopify.dev/docs/apps/auth/oauth) - à re-vérifier dès que de vraies
clés SHOPIFY_CLIENT_ID/SHOPIFY_CLIENT_SECRET sont disponibles, même
démarche que doola (doc d'abord, inspection de vrais appels ensuite).

Client HTTP asynchrone (httpx.AsyncClient), même convention que
doola_service.py - PAS de retry automatique ici contrairement à
_request() côté doola : un "code" d'autorisation OAuth est à usage
UNIQUE, le rejouer après un éventuel timeout côté client (qui aurait pu
malgré tout être traité côté Shopify) consommerait un code déjà utilisé
et renverrait une erreur non représentative - une seule tentative, à
l'appelant (routes/shopify.py) de renvoyer une erreur claire (502) sans
retenter automatiquement."""

import base64
import hashlib
import hmac
import logging
import os
import re
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOPIFY_REDIRECT_URI = os.getenv("SHOPIFY_REDIRECT_URI", "https://api.xepay.finance/auth/shopify/callback")
# Doit rester IDENTIQUE aux scopes déclarés dans le Partner Dashboard pour
# "Xepay Sync" - read_customers/write_customers ajoutés le 2026-11-24.
# IMPORTANT : ce changement ne s'applique QU'AUX NOUVELLES autorisations -
# une boutique
# déjà connectée (Connect0/Connect1) garde le token émis avec l'ANCIEN
# jeu de scopes tel quel ; elle doit être reconnectée (GET /shopify/
# install, Paramètres > Shopify) pour que Shopify émette un nouveau
# token couvrant read_customers (OAuth Shopify : le scope d'un token
# déjà émis ne s'étend jamais rétroactivement, re-consentement
# obligatoire). Un scope demandé ici mais absent du Partner Dashboard
# ferait échouer /admin/oauth/authorize côté Shopify.
SHOPIFY_SCOPES = os.getenv(
    "SHOPIFY_SCOPES",
    "read_orders,write_orders,read_products,write_products,read_customers,write_customers",
)
SHOPIFY_TIMEOUT_SECONDS = 10
# Version d'API Admin GraphQL - voir shopify.dev, une release stable par
# trimestre (format AAAA-MM). Doit être mise à jour périodiquement (Shopify
# retire les anciennes versions ~1 an après leur sortie), jamais "latest"
# en dur (casserait silencieusement si Shopify change le schéma).
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-01")
# URL de callback du webhook orders/create (routes/webhook/shopify.py) -
# enregistrée automatiquement (register_order_webhook) juste après chaque
# échange OAuth réussi, jamais à configurer à la main dans le Partner
# Dashboard (contrairement à SHOPIFY_REDIRECT_URI, qui EST dans le Partner
# Dashboard - ce sont deux URLs différentes, pas à confondre).
SHOPIFY_ORDERS_WEBHOOK_URL = os.getenv(
    "SHOPIFY_ORDERS_WEBHOOK_URL", "https://api.xepay.finance/webhook/shopify/orders-create"
)
# Nom EXACT de la méthode de paiement manuelle que le marchand doit créer
# lui-même dans Settings > Payments > Manual payment methods de son admin
# Shopify (aucune API ne permet de la créer, voir le docstring de routes/
# webhook/shopify.py) - seules les commandes payées avec une méthode
# portant CE nom (payment_gateway_names, insensible à la casse) déclenchent
# la création d'un lien Xepay ; toute autre méthode manuelle (COD, virement
# bancaire...) existante par ailleurs chez le marchand est ignorée.
SHOPIFY_MANUAL_GATEWAY_NAME = os.getenv("SHOPIFY_MANUAL_GATEWAY_NAME", "Xepay")

# Domaine Shopify valide : sous-domaine alphanumérique (+ tirets) de
# myshopify.com UNIQUEMENT - vérifié avant toute requête sortante vers
# https://{shop}/admin/oauth/access_token (construite à partir de "shop",
# fourni par le client/Shopify dans la query string) : sans cette
# validation, un "shop" arbitraire dans l'URL de callback permettrait une
# SSRF (POST du code + du client_secret vers un hôte choisi par
# l'attaquant) - jamais fait confiance à "shop" tel quel.
_SHOP_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*\.myshopify\.com$")


class ShopifyAPIError(RuntimeError):
    """Erreur Shopify non récupérable - porte le status_code et le corps
    de réponse brut pour que l'appelant (routes/shopify.py) distingue un
    problème de validation (code déjà utilisé/expiré) d'une vraie panne
    côté Shopify."""

    def __init__(self, status_code: int | None, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Shopify a répondu {status_code}: {body[:500]}")


class ShopifyRateLimitError(ShopifyAPIError):
    """Sous-classe de ShopifyAPIError - levée spécifiquement sur un
    throttling GraphQL (coût de requête dépassé, voir shopify.dev/docs/
    api/usage/limits), jamais sur une vraie panne. Permet à l'appelant
    (routes/shopify.py) de renvoyer un 429 explicite ("réessayez dans
    quelques secondes") plutôt que le 502 générique d'une erreur Shopify
    non récupérable - distinction utile uniquement pour les nouveaux
    endpoints de lecture (products/orders/customers), qui peuvent être
    appelés bien plus souvent qu'un orderMarkAsPaid/register_order_webhook
    (un par paiement) et donc plus susceptibles de heurter la limite."""


class ShopifyScopeError(ShopifyAPIError):
    """Sous-classe de ShopifyAPIError - levée sur un VRAI refus Shopify
    par scope manquant (extensions.code == "ACCESS_DENIED" dans les
    errors GraphQL, confirmé contre shopify.dev/docs/apps/build/
    shopifyql/graphql-admin-api/errors-limits-and-performance le
    2026-11-24). Remplace l'ancienne vérification has_customers_scope/
    has_write_customers_scope basée sur ShopifyShop.scope (la chaîne
    renvoyée par l'échange OAuth) : prouvé PEU FIABLE le même jour -
    une boutique réelle avait read_orders/read_products fonctionnels en
    pratique alors que cette même chaîne ne les listait pas non plus.
    Seul un VRAI refus Shopify (ce type d'exception) doit désormais
    faire foi, jamais une déduction à partir du scope stocké."""


def is_valid_shop_domain(shop: str) -> bool:
    return bool(_SHOP_DOMAIN_RE.match(shop or ""))


def build_authorize_url(shop: str, state: str) -> str:
    """URL vers laquelle rediriger le NAVIGATEUR (jamais un appel serveur
    sortant - pas de risque SSRF ici) pour démarrer/reprendre le
    consentement OAuth Shopify - construite UNIQUEMENT depuis routes/
    shopify.py après is_valid_shop_domain(shop). "state" doit être un
    jeton signé (voir security.create_shopify_state_token) : Shopify le
    renvoie tel quel au callback, qui le revérifie pour se protéger d'un
    CSRF sur le flux d'installation (voir routes/shopify.py)."""
    params = {
        "client_id": SHOPIFY_CLIENT_ID,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": SHOPIFY_REDIRECT_URI,
        "state": state,
    }
    return f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"


def verify_hmac(params: dict) -> bool:
    """Vérifie la signature "hmac" envoyée par Shopify sur le callback
    OAuth (GET /auth/shopify/callback) - algorithme documenté par
    Shopify : retirer "hmac" (et "signature", héritée de l'ancien schéma)
    des paramètres, trier les clés restantes par ordre alphabétique,
    joindre en "clé=valeur" séparés par "&", puis comparer le HMAC-SHA256
    hex digest de cette chaîne (clé = SHOPIFY_CLIENT_SECRET) à la valeur
    du paramètre "hmac" - hmac.compare_digest (temps constant), jamais
    une simple égalité de chaînes (même raison que _verify_signature,
    routes/webhook/doola.py)."""
    received = params.get("hmac")
    if not SHOPIFY_CLIENT_SECRET or not received:
        return False

    filtered = {k: v for k, v in params.items() if k not in ("hmac", "signature")}
    message = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    expected = hmac.new(
        SHOPIFY_CLIENT_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received)


async def exchange_code_for_token(shop: str, code: str) -> dict:
    """POST https://{shop}/admin/oauth/access_token - échange le "code"
    d'autorisation contre un token Admin PERMANENT (shpat_...), voir
    routes/shopify.py pour le stockage (chiffré) côté Xepay. "shop" doit
    avoir déjà été validé par is_valid_shop_domain() avant cet appel -
    jamais appelé directement avec une valeur non vérifiée."""
    url = f"https://{shop}/admin/oauth/access_token"
    body = {
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "code": code,
    }

    try:
        async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=body, headers={"Accept": "application/json"})
    except (httpx.TimeoutException, httpx.TransportError) as e:
        logger.warning("Shopify POST /admin/oauth/access_token (%s) : erreur réseau (%s)", shop, e)
        raise ShopifyAPIError(None, str(e)) from e

    if 200 <= response.status_code < 300:
        return response.json()

    # Jamais le corps complet en warning si jamais Shopify devait un jour y
    # faire écho (il ne le fait pas aujourd'hui) - même prudence que
    # _LOGGED_BODY_MAX_CHARS côté doola_service, mais ici le secret
    # (client_secret) n'est de toute façon JAMAIS dans la réponse, seul le
    # "code" envoyé pourrait l'être, qui est déjà consommé/sans valeur après
    # cet appel.
    logger.warning(
        "Shopify POST /admin/oauth/access_token (%s) : %d - %s",
        shop, response.status_code, response.text[:500],
    )
    raise ShopifyAPIError(response.status_code, response.text)


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Vérifie l'en-tête "X-Shopify-Hmac-Sha256" d'un webhook Admin
    (orders/create, voir routes/webhook/shopify.py) - ALGORITHME DIFFÉRENT
    de verify_hmac() ci-dessus (qui ne s'applique qu'au callback OAuth,
    sur des paramètres de query string, en hex) : ici c'est un
    HMAC-SHA256 du corps BRUT de la requête, encodé en BASE64 (jamais hex),
    toujours avec SHOPIFY_CLIENT_SECRET (le "shared secret" de l'app, le
    même pour toutes les boutiques - confirmé par la doc Shopify, pas une
    clé par boutique)."""
    if not SHOPIFY_CLIENT_SECRET or not signature_header:
        return False
    expected = base64.b64encode(
        hmac.new(SHOPIFY_CLIENT_SECRET.encode(), raw_body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature_header)


def order_gid(order_id) -> str:
    return f"gid://shopify/Order/{order_id}"


async def _admin_graphql(shop: str, access_token: str, query: str, variables: dict | None = None) -> dict:
    """POST https://{shop}/admin/api/{SHOPIFY_API_VERSION}/graphql.json -
    coeur commun à register_order_webhook/mark_order_as_paid. "shop" doit
    déjà avoir été validé par is_valid_shop_domain() par l'appelant (même
    règle anti-SSRF que exchange_code_for_token) - jamais revalidé ici."""
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    body = {"query": query, "variables": variables or {}}

    try:
        async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=body, headers=headers)
    except (httpx.TimeoutException, httpx.TransportError) as e:
        logger.warning("Shopify GraphQL (%s) : erreur réseau (%s)", shop, e)
        raise ShopifyAPIError(None, str(e)) from e

    if response.status_code != 200:
        logger.warning("Shopify GraphQL (%s) : %d - %s", shop, response.status_code, response.text[:500])
        raise ShopifyAPIError(response.status_code, response.text)

    data = response.json()
    if data.get("errors"):
        # Erreurs GraphQL de premier niveau (requête malformée, token
        # invalide/révoqué, scope manquant) - distinctes des userErrors
        # métier renvoyées DANS payload.data (voir mark_order_as_paid), qui
        # elles restent un 200 GraphQL classique.
        errors = data["errors"]
        if any((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errors):
            logger.warning("Shopify GraphQL (%s) : throttled", shop)
            raise ShopifyRateLimitError(200, str(errors))
        if any((e.get("extensions") or {}).get("code") == "ACCESS_DENIED" for e in errors):
            logger.warning("Shopify GraphQL (%s) : accès refusé (scope manquant) - %s", shop, errors)
            raise ShopifyScopeError(200, str(errors))
        logger.warning("Shopify GraphQL (%s) : erreurs %s", shop, errors)
        raise ShopifyAPIError(200, str(errors))
    return data.get("data") or {}


async def _find_order_webhook_subscription_id(shop: str, access_token: str) -> str | None:
    """Liste les abonnements webhook ORDERS_CREATE et renvoie l'id de
    celui qui pointe vers SHOPIFY_ORDERS_WEBHOOK_URL, ou None - factorisé
    le 2026-11-25 (utilisé par register_order_webhook ET par le rapport
    de préparation Buildshop, routes/shopify.py::shopify_readiness, qui
    lui ne fait QUE lire, jamais créer)."""
    existing = await _admin_graphql(
        shop, access_token,
        """
        query {
          webhookSubscriptions(first: 50, topics: [ORDERS_CREATE]) {
            edges { node { id endpoint { __typename ... on WebhookHttpEndpoint { callbackUrl } } } }
          }
        }
        """,
    )
    edges = (existing.get("webhookSubscriptions") or {}).get("edges") or []
    for edge in edges:
        node = edge.get("node") or {}
        endpoint = node.get("endpoint") or {}
        if endpoint.get("callbackUrl") == SHOPIFY_ORDERS_WEBHOOK_URL:
            return node.get("id")
    return None


async def is_order_webhook_registered(shop: str, access_token: str) -> bool:
    """Lecture PURE (jamais de création) - voir
    _find_order_webhook_subscription_id. Utilisée par le rapport de
    préparation Buildshop pour afficher l'état réel sans effet de bord."""
    return bool(await _find_order_webhook_subscription_id(shop, access_token))


async def register_order_webhook(shop: str, access_token: str) -> None:
    """Enregistre (une seule fois par boutique) le webhook orders/create
    vers SHOPIFY_ORDERS_WEBHOOK_URL - appelée depuis routes/shopify.py
    juste après un échange OAuth réussi, ET depuis le rapport de
    préparation Buildshop (POST /shopify/readiness/fix-webhook) comme
    SEULE action corrective automatisable - idempotente par construction
    (voir _find_order_webhook_subscription_id : ne crée rien si CETTE
    URL figure déjà, une ré-installation ou un second appel ne doit
    jamais créer un second abonnement - Shopify livrerait alors CHAQUE
    commande deux fois, créant deux Link Xepay pour la même commande
    malgré la UniqueConstraint de ShopifyOrderPayment, qui ne protège
    que contre un DOUBLE-TRAITEMENT d'un même événement, pas contre deux
    abonnements distincts générant chacun leur propre événement)."""
    if await _find_order_webhook_subscription_id(shop, access_token):
        return

    result = await _admin_graphql(
        shop, access_token,
        """
        mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
          webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
            webhookSubscription { id }
            userErrors { field message }
          }
        }
        """,
        {
            "topic": "ORDERS_CREATE",
            "webhookSubscription": {"callbackUrl": SHOPIFY_ORDERS_WEBHOOK_URL, "format": "JSON"},
        },
    )
    user_errors = (result.get("webhookSubscriptionCreate") or {}).get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))


# =========================================================
# Mirroring produits/commandes/clients (ajouté le 2026-11-28, demande
# EXPLICITE de l'utilisateur de synchroniser pleinement - pas
# uniquement réagir au cycle de vie de l'app - après confirmation que
# ça revient sur le principe du 2026-11-24 "jamais de copie locale,
# toujours lu en direct" pour l'onglet Commerce > Shopify, QUI RESTE
# INCHANGÉ : ce mirroir est un magasin SUPPLÉMENTAIRE, voir
# models.Shopify{Product,Order,Customer}Mirror).
#
# ORDERS_CREATE n'apparaît PAS dans SHOPIFY_MIRROR_WEBHOOK_TOPICS :
# déjà géré par register_order_webhook/SHOPIFY_ORDERS_WEBHOOK_URL
# ci-dessus - jamais une 2e souscription vers une 2e URL pour le même
# topic (le handler existant mirrore désormais EN PLUS de sa logique
# Link Xepay, voir routes/webhook/shopify.py).
#
# Les 3 topics RGPD (customers/data_request, customers/redact,
# shop/redact) n'y apparaissent PAS non plus, pour une raison
# DIFFÉRENTE - vérifié le 2026-11-28 (community.shopify.dev) :
# Shopify REFUSE ces 3 topics via webhookSubscriptionCreate, ils ne
# sont configurables QUE via shopify.app.toml (CLI moderne, jamais
# utilisé par cette app - OAuth manuel historique) ou la section
# "Compliance webhooks" du Partner Dashboard (configuration MANUELLE,
# une seule fois, côté humain) - voir les routes dédiées dans
# routes/webhook/shopify.py et le message à l'utilisateur sur les URLs
# à y coller.
SHOPIFY_WEBHOOK_BASE_URL = os.getenv("SHOPIFY_WEBHOOK_BASE_URL", "https://api.xepay.finance/webhook/shopify")

SHOPIFY_MIRROR_WEBHOOK_TOPICS = {
    "ORDERS_UPDATE": f"{SHOPIFY_WEBHOOK_BASE_URL}/orders-update",
    "PRODUCTS_CREATE": f"{SHOPIFY_WEBHOOK_BASE_URL}/products-create",
    "PRODUCTS_UPDATE": f"{SHOPIFY_WEBHOOK_BASE_URL}/products-update",
    "PRODUCTS_DELETE": f"{SHOPIFY_WEBHOOK_BASE_URL}/products-delete",
    "CUSTOMERS_CREATE": f"{SHOPIFY_WEBHOOK_BASE_URL}/customers-create",
    "CUSTOMERS_UPDATE": f"{SHOPIFY_WEBHOOK_BASE_URL}/customers-update",
    "CUSTOMERS_DELETE": f"{SHOPIFY_WEBHOOK_BASE_URL}/customers-delete",
    "APP_UNINSTALLED": f"{SHOPIFY_WEBHOOK_BASE_URL}/app-uninstalled",
}


async def _list_webhook_subscriptions(shop: str, access_token: str) -> list[dict]:
    """Lecture PURE de TOUTES les souscriptions actives (tous topics
    confondus, contrairement à _find_order_webhook_subscription_id qui
    filtre sur ORDERS_CREATE uniquement) - factorisée pour
    register_all_mirror_webhooks, qui doit connaître l'état de TOUS
    les topics de SHOPIFY_MIRROR_WEBHOOK_TOPICS en UN SEUL appel
    GraphQL plutôt qu'un par topic."""
    result = await _admin_graphql(
        shop, access_token,
        """
        query {
          webhookSubscriptions(first: 50) {
            edges { node { topic endpoint { __typename ... on WebhookHttpEndpoint { callbackUrl } } } }
          }
        }
        """,
    )
    edges = (result.get("webhookSubscriptions") or {}).get("edges") or []
    return [e["node"] for e in edges]


async def register_all_mirror_webhooks(shop: str, access_token: str) -> dict:
    """Idempotent (même principe que register_order_webhook) : relit
    TOUTES les souscriptions existantes UNE SEULE FOIS puis ne crée que
    les topics de SHOPIFY_MIRROR_WEBHOOK_TOPICS encore absents - jamais
    un abonnement en double. Chaque création est TENTÉE INDÉPENDAMMENT
    (best-effort par topic, voir la boucle) : un scope manquant sur UN
    topic (ex. write_customers insuffisant pour CUSTOMERS_*) ne doit
    jamais empêcher les autres topics de s'enregistrer, et ne doit
    jamais faire échouer tout l'appel OAuth qui suit cette fonction
    (shopify_callback, routes/shopify.py)."""
    existing = await _list_webhook_subscriptions(shop, access_token)
    existing_callback_by_topic = {}
    for node in existing:
        endpoint = node.get("endpoint") or {}
        existing_callback_by_topic[node.get("topic")] = endpoint.get("callbackUrl")

    created, failed = [], []
    for topic, callback_url in SHOPIFY_MIRROR_WEBHOOK_TOPICS.items():
        if existing_callback_by_topic.get(topic) == callback_url:
            continue
        try:
            result = await _admin_graphql(
                shop, access_token,
                """
                mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
                  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
                    webhookSubscription { id }
                    userErrors { field message }
                  }
                }
                """,
                {"topic": topic, "webhookSubscription": {"callbackUrl": callback_url, "format": "JSON"}},
            )
            user_errors = (result.get("webhookSubscriptionCreate") or {}).get("userErrors") or []
            if user_errors:
                failed.append({"topic": topic, "error": str(user_errors)})
            else:
                created.append(topic)
        except ShopifyAPIError as e:
            logger.warning("Echec souscription webhook %s pour %s : %s", topic, shop, e)
            failed.append({"topic": topic, "error": str(e)})
    return {"created": created, "failed": failed}


async def mark_order_as_paid(shop: str, access_token: str, order_id) -> dict:
    """Mutation orderMarkAsPaid - requiert UNIQUEMENT le scope write_orders
    (déjà accordé par le Partner Dashboard pour "Xepay Sync", confirmé
    par la doc officielle shopify.dev le 2026-11-24) - aucun coût, aucune
    app de paiement certifiée nécessaire. Ne fonctionne que sur une
    commande au solde impayé positif et pas déjà financial_status=PAID
    (Shopify renvoie sinon une userError, voir sync_order_paid_with_shopify
    pour comment l'appelant la traite)."""
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation orderMarkAsPaid($input: OrderMarkAsPaidInput!) {
          orderMarkAsPaid(input: $input) {
            order { id displayFinancialStatus }
            userErrors { field message }
          }
        }
        """,
        {"input": {"id": order_gid(order_id)}},
    )
    payload = result.get("orderMarkAsPaid") or {}
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    return payload.get("order") or {}


# =========================================================
# Lecture directe (onglet "Shopify" de Commerce, voir routes/shopify.py)
# =========================================================
# Pur passthrough vers l'API Admin Shopify - AUCUNE table miroir côté
# Xepay, AUCUN objet Stripe créé à partir de ces données (demande
# explicite du 2026-11-24). Une seule page par appel (COMMERCE_PAGE_SIZE
# items, triés du plus récent au plus ancien quand l'objet le permet) -
# pas d'auto-pagination profonde comme register_order_webhook/
# mark_order_as_paid n'en ont pas besoin : ces trois endpoints peuvent
# être appelés bien plus souvent (à chaque ouverture de l'onglet
# Commerce), inutile de multiplier les appels Shopify au-delà de ce que
# l'UI affiche réellement (même principe que les onglets Stripe de
# Commerce, qui chargent au plus 100 lignes en un seul appel).
COMMERCE_PAGE_SIZE = 50


async def get_shop_info(shop: str, access_token: str) -> dict:
    """GET infos de boutique (nom, devise, fuseau horaire) - EN LECTURE
    SEULE : vérifié le 2026-11-25 (doc officielle shopify.dev) qu'AUCUNE
    mutation Admin API ne permet de modifier currencyCode/ianaTimezone
    (fixés à la création de la boutique, modifiables uniquement à la
    main dans l'admin Shopify, parfois même plus du tout après la
    première vente). Utilisée par le rapport de préparation Buildshop
    (routes/shopify.py::shopify_readiness) comme SIGNAL de cohérence
    avec la LLC du marchand, jamais comme cible d'une correction
    automatique - voir les garde-fous documentés sur cette route."""
    result = await _admin_graphql(
        shop, access_token,
        """
        query {
          shop {
            name
            currencyCode
            ianaTimezone
            myshopifyDomain
            shopAddress { company address1 address2 city province zip country }
          }
        }
        """,
    )
    return result.get("shop") or {}


async def list_products(shop: str, access_token: str) -> list[dict]:
    """GET produits - titre, statut, stock total, image, fourchette de
    prix (priceRangeV2 : min/max des variantes, jamais un prix unique -
    un produit a au moins une variante, parfois plusieurs à prix
    différents)."""
    result = await _admin_graphql(
        shop, access_token,
        """
        query($first: Int!) {
          products(first: $first, sortKey: UPDATED_AT, reverse: true) {
            edges {
              node {
                id
                title
                status
                totalInventory
                featuredImage { url }
                priceRangeV2 {
                  minVariantPrice { amount currencyCode }
                  maxVariantPrice { amount currencyCode }
                }
              }
            }
          }
        }
        """,
        {"first": COMMERCE_PAGE_SIZE},
    )
    edges = (result.get("products") or {}).get("edges") or []
    return [e["node"] for e in edges]


async def list_orders(shop: str, access_token: str) -> list[dict]:
    """GET commandes - statut financier/livraison, montant total (devise
    de la boutique), client, date - triées de la plus récente à la plus
    ancienne. cancelledAt (null si pas annulée) : seul champ fiable pour
    savoir si "Annuler" doit être proposée côté UI (routes/shopify.py,
    POST /shopify/orders/{id}/cancel) - displayFinancialStatus/
    displayFulfillmentStatus ne reflètent pas forcément l'annulation.
    paymentGatewayNames (camelCase ici, PAS payment_gateway_names comme
    dans le payload REST du webhook orders/create - deux schémas
    différents, voir routes/webhook/shopify.py) : utilisé par le rapport
    de préparation Buildshop pour détecter la méthode "Xepay"."""
    result = await _admin_graphql(
        shop, access_token,
        """
        query($first: Int!) {
          orders(first: $first, sortKey: CREATED_AT, reverse: true) {
            edges {
              node {
                id
                name
                displayFinancialStatus
                displayFulfillmentStatus
                cancelledAt
                createdAt
                paymentGatewayNames
                totalPriceSet { shopMoney { amount currencyCode } }
                customer { displayName email }
              }
            }
          }
        }
        """,
        {"first": COMMERCE_PAGE_SIZE},
    )
    edges = (result.get("orders") or {}).get("edges") or []
    return [e["node"] for e in edges]


async def list_customers(shop: str, access_token: str) -> list[dict]:
    """GET clients - nom, email, nombre de commandes, total dépensé,
    date de création. AUCUNE vérification préalable du scope ici (voir
    ShopifyScopeError plus haut, et le docstring de routes/shopify.py::
    shopify_customers) : un appel sans ce scope échoue côté Shopify avec
    une vraie erreur ACCESS_DENIED, détectée par _admin_graphql - ne
    JAMAIS présupposer l'accès à partir de ShopifyShop.scope, prouvé peu
    fiable le 2026-11-24 (une boutique réelle avait read_orders/
    read_products fonctionnels alors que cette même chaîne ne les
    listait pas non plus)."""
    result = await _admin_graphql(
        shop, access_token,
        """
        query($first: Int!) {
          customers(first: $first, sortKey: UPDATED_AT, reverse: true) {
            edges {
              node {
                id
                displayName
                firstName
                lastName
                email
                phone
                numberOfOrders
                amountSpent { amount currencyCode }
                createdAt
              }
            }
          }
        }
        """,
        {"first": COMMERCE_PAGE_SIZE},
    )
    edges = (result.get("customers") or {}).get("edges") or []
    return [e["node"] for e in edges]


# =========================================================
# Écriture (demande du 2026-11-24, après l'ajout de read_customers/
# write_customers au Partner Dashboard) - signatures vérifiées contre la
# doc officielle shopify.dev le même jour, PAS testées contre un vrai
# appel (aucune app Shopify Partner ne peut être pilotée depuis ce
# sandbox - voir le docstring en tête de fichier). customerCreate/
# productCreate/orderCancel ont chacun leurs propres limites
# documentées, reprises dans les docstrings ci-dessous plutôt que
# redécouvertes en prod.
# =========================================================

def customer_gid(customer_id) -> str:
    return f"gid://shopify/Customer/{customer_id}"


def product_gid(product_id) -> str:
    return f"gid://shopify/Product/{product_id}"


def _customer_input(first_name=None, last_name=None, email=None, phone=None) -> dict:
    """CustomerInput (customerCreate/customerUpdate) - seuls les champs
    non None sont inclus, pour qu'un PATCH partiel (update_customer)
    n'écrase jamais un champ non fourni avec null côté Shopify."""
    data = {}
    if first_name is not None:
        data["firstName"] = first_name
    if last_name is not None:
        data["lastName"] = last_name
    if email is not None:
        data["email"] = email
    if phone is not None:
        data["phone"] = phone
    return data


async def create_customer(shop: str, access_token: str, first_name=None, last_name=None, email=None, phone=None) -> dict:
    """customerCreate - Shopify exige au moins un moyen de contact
    (email/phone/nom), vérifié côté appelant (routes/shopify.py), pas
    ici."""
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation customerCreate($input: CustomerInput!) {
          customerCreate(input: $input) {
            customer { id firstName lastName email phone createdAt }
            userErrors { field message }
          }
        }
        """,
        {"input": _customer_input(first_name, last_name, email, phone)},
    )
    payload = result.get("customerCreate") or {}
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    return payload.get("customer") or {}


async def update_customer(shop: str, access_token: str, customer_id, first_name=None, last_name=None, email=None, phone=None) -> dict:
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation customerUpdate($input: CustomerInput!) {
          customerUpdate(input: $input) {
            customer { id firstName lastName email phone createdAt }
            userErrors { field message }
          }
        }
        """,
        {"input": {"id": customer_gid(customer_id), **_customer_input(first_name, last_name, email, phone)}},
    )
    payload = result.get("customerUpdate") or {}
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    return payload.get("customer") or {}


async def create_product(shop: str, access_token: str, title: str, description: str | None, price: float | None, status: str) -> dict:
    """productCreate - NE CRÉE QU'UNE SEULE VARIANTE et n'accepte pas son
    prix directement (confirmé le 2026-11-24) : si "price" est fourni,
    un second appel (productVariantsBulkUpdate) fixe le prix de cette
    variante par défaut juste après. Le STOCK (inventaire) reste hors
    périmètre - nécessiterait un emplacement (location) + un appel
    distinct (inventoryAdjustQuantities), jamais implémenté ici."""
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation productCreate($input: ProductCreateInput!) {
          productCreate(input: $input) {
            product {
              id
              title
              status
              variants(first: 1) { edges { node { id } } }
            }
            userErrors { field message }
          }
        }
        """,
        {"input": {"title": title, "descriptionHtml": description or "", "status": status}},
    )
    payload = result.get("productCreate") or {}
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    product = payload.get("product") or {}

    if price is not None:
        variant_edges = ((product.get("variants") or {}).get("edges")) or []
        if variant_edges:
            variant_id = variant_edges[0]["node"]["id"]
            await _admin_graphql(
                shop, access_token,
                """
                mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
                  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                    userErrors { field message }
                  }
                }
                """,
                {"productId": product["id"], "variants": [{"id": variant_id, "price": str(price)}]},
            )
    return product


async def update_product(shop: str, access_token: str, product_id, title=None, description=None, status=None) -> dict:
    """productUpdate - prix/stock non modifiables ici, même limite que
    create_product (voir son docstring)."""
    input_data = {"id": product_gid(product_id)}
    if title is not None:
        input_data["title"] = title
    if description is not None:
        input_data["descriptionHtml"] = description
    if status is not None:
        input_data["status"] = status
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation productUpdate($input: ProductInput!) {
          productUpdate(input: $input) {
            product { id title status }
            userErrors { field message }
          }
        }
        """,
        {"input": input_data},
    )
    payload = result.get("productUpdate") or {}
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    return payload.get("product") or {}


# =========================================================
# Thèmes + recherche de produit par titre (Buildshop - voir services/
# buildshop_service.py, routes/shopify.py section "Buildshop") - utilisé
# UNIQUEMENT pour les boutiques pré-transfert provisionnées par l'équipe
# Xepay (ShopifyShop.merchant_id NULL), jamais pour une boutique déjà
# rattachée à un marchand - garde-fou côté routes/shopify.py, jamais ici
# (ces fonctions reçoivent déjà shop/access_token validés par l'appelant,
# même convention que le reste de ce fichier).
# =========================================================

async def create_theme_from_url(shop: str, access_token: str, source_url: str, name: str | None = None, role: str = "UNPUBLISHED") -> dict:
    """themeCreate - ASYNCHRONE côté Shopify (confirmé le 2026-11-27
    contre shopify.dev/docs/api/admin-graphql/latest/mutations/
    themecreate) : la réponse porte un thème avec processing=true juste
    après cet appel, jamais un thème déjà prêt à l'emploi - voir
    list_themes pour le suivi processing/processingFailed, jamais
    supposé terminé ici. role ne peut valoir QUE "UNPUBLISHED" ou
    "DEVELOPMENT" pour un nouveau thème (confirmé contre la même doc) -
    jamais "MAIN" directement : publier (themePublish) est une décision
    humaine distincte, hors périmètre de cette fonction."""
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation themeCreate($source: URL!, $name: String, $role: ThemeRole) {
          themeCreate(source: $source, name: $name, role: $role) {
            theme { id name role processing processingFailed }
            userErrors { field message }
          }
        }
        """,
        {"source": source_url, "name": name, "role": role},
    )
    payload = result.get("themeCreate") or {}
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    return payload.get("theme") or {}


async def list_themes(shop: str, access_token: str) -> list[dict]:
    """Lecture PURE - sert à la fois à l'idempotence (provision_theme,
    buildshop_service.py : ne jamais recréer un thème déjà présent sous
    le même nom) et au suivi processing/processingFailed
    (get_buildshop_readiness, buildshop_service.py)."""
    result = await _admin_graphql(
        shop, access_token,
        """
        query {
          themes(first: 20) {
            edges { node { id name role processing processingFailed } }
          }
        }
        """,
    )
    edges = (result.get("themes") or {}).get("edges") or []
    return [e["node"] for e in edges]


async def find_products_by_title(shop: str, access_token: str, title: str) -> list[dict]:
    """Lecture PURE - vérification d'idempotence pour provision_catalog
    (buildshop_service.py) : ne jamais créer un second produit du même
    titre sur un appel répété (retry après échec partiel). Échappe les
    guillemets du titre dans le filtre "query" Shopify (syntaxe de
    recherche dédiée, PAS du GraphQL - un titre contenant déjà un
    guillemet casserait sinon ce filtre)."""
    escaped = (title or "").replace('"', '\\"')
    result = await _admin_graphql(
        shop, access_token,
        """
        query($search: String!) {
          products(first: 5, query: $search) {
            edges { node { id title status } }
          }
        }
        """,
        {"search": f'title:"{escaped}"'},
    )
    edges = (result.get("products") or {}).get("edges") or []
    return [e["node"] for e in edges]


async def cancel_order(shop: str, access_token: str, order_id, reason: str, restock: bool, notify_customer: bool = False, staff_note: str | None = None) -> dict:
    """orderCancel - ASYNCHRONE côté Shopify (confirmé le 2026-11-24) :
    la réponse porte un "job" (id/done), jamais la commande annulée
    directement - aucun polling implémenté ici (hors périmètre), le
    retour expose donc job.id/job.done tels que Shopify les renvoie à
    cet instant (done vaut presque toujours false juste après l'appel),
    à l'appelant (routes/shopify.py) de le présenter comme "annulation
    lancée", jamais "commande annulée" avec certitude."""
    variables = {
        "orderId": order_gid(order_id),
        "reason": reason,
        "restock": restock,
        "notifyCustomer": notify_customer,
    }
    if staff_note is not None:
        variables["staffNote"] = staff_note
    result = await _admin_graphql(
        shop, access_token,
        """
        mutation orderCancel($orderId: ID!, $reason: OrderCancelReason!, $restock: Boolean!, $notifyCustomer: Boolean, $staffNote: String) {
          orderCancel(orderId: $orderId, reason: $reason, restock: $restock, notifyCustomer: $notifyCustomer, staffNote: $staffNote) {
            job { id done }
            orderCancelUserErrors { field message }
          }
        }
        """,
        variables,
    )
    payload = result.get("orderCancel") or {}
    user_errors = payload.get("orderCancelUserErrors") or []
    if user_errors:
        raise ShopifyAPIError(200, str(user_errors))
    return payload.get("job") or {}
