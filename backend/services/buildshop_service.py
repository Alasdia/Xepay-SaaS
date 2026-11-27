"""Buildshop — provisioning automatisé des boutiques "prêtes à l'emploi"
AVANT leur transfert à un marchand (demande du 2026-11-27, suite de la
discussion d'architecture sur le même sujet) : la création du "Client
Transfer Store" lui-même, l'activation du moyen de paiement manuel
"Xepay" et l'installation OAuth de l'app Xepay restent MANUELLES -
confirmé IMPOSSIBLE à automatiser via l'API publique Shopify
aujourd'hui (aucune API pour "Create transfer store"/"Transfer a store
to a client", confirmé par un employé Shopify sur community.shopify.dev ;
aucune API pour créer un moyen de paiement manuel arbitraire, confirmé
contre la doc REST PaymentGateway ; aucune installation d'app sans le
clic de consentement OAuth, interdit par Shopify pour raisons de
conformité) - gérées par l'équipe interne Xepay. Ce module ne prend le
relais qu'UNE FOIS ces 3 étapes faites à la main (shop_domain connu,
app installée -> ShopifyShop.access_token en main).

Ce module ne touche JAMAIS une boutique déjà rattachée à un marchand
réel (ShopifyShop.merchant_id non NULL) - le garde-fou vit côté
routes/shopify.py (_require_buildshop_shop), jamais dupliqué ici : les
fonctions ci-dessous reçoivent déjà un (shop, access_token) déjà validés
par l'appelant.

Theme + catalogue + webhook sont chacun IDEMPOTENTS (relire avant de
créer) - un second appel de provisioning sur la même boutique (retry
après échec partiel) ne doit jamais dupliquer quoi que ce soit, même
principe que register_order_webhook (shopify_service.py)."""

import logging
import os

from backend.services.shopify_service import (
    ShopifyAPIError,
    create_product,
    create_theme_from_url,
    find_products_by_title,
    is_order_webhook_registered,
    list_products,
    list_themes,
    register_order_webhook,
)

logger = logging.getLogger(__name__)

# URL publique d'un ZIP de thème "prêt à l'emploi" hébergé par Xepay -
# JAMAIS un chemin local : Shopify télécharge lui-même ce ZIP depuis ses
# propres serveurs (voir create_theme_from_url/themeCreate), il doit
# donc être accessible publiquement en HTTPS. Vide par défaut : un
# provisioning sans cette variable configurée SAUTE l'étape thème
# plutôt que d'échouer (voir provision_theme) - le catalogue/webhook
# restent utiles même sans thème personnalisé.
BUILDSHOP_THEME_ZIP_URL = os.getenv("BUILDSHOP_THEME_ZIP_URL")
# Nom EXACT posé sur le thème créé - sert aussi de clé d'idempotence
# (provision_theme/get_buildshop_readiness cherchent un thème portant
# CE nom plutôt que de se fier à son id, jamais stocké côté Xepay).
BUILDSHOP_THEME_NAME = os.getenv("BUILDSHOP_THEME_NAME", "Xepay Buildshop")

# Catalogue de base injecté sur CHAQUE boutique Buildshop - volontairement
# générique/placeholder (le marchand remplacera par son propre catalogue
# après transfert) : juste assez pour qu'une boutique "prête à l'emploi"
# ne soit jamais vide au premier coup d'œil. Contenu produit, modifiable
# directement ici - jamais une variable d'environnement (trop de champs
# structurés pour ça).
BASE_CATALOG = [
    {
        "title": "Produit exemple 1",
        "description": "Produit de démonstration - à remplacer par votre propre catalogue après le transfert.",
        "price": 19.99,
        "status": "DRAFT",
    },
    {
        "title": "Produit exemple 2",
        "description": "Produit de démonstration - à remplacer par votre propre catalogue après le transfert.",
        "price": 29.99,
        "status": "DRAFT",
    },
    {
        "title": "Produit exemple 3",
        "description": "Produit de démonstration - à remplacer par votre propre catalogue après le transfert.",
        "price": 49.99,
        "status": "DRAFT",
    },
]


async def provision_theme(shop: str, access_token: str) -> dict:
    """Idempotent : si un thème nommé BUILDSHOP_THEME_NAME existe déjà
    sur cette boutique, le renvoie tel quel plutôt que d'en recréer un
    second. ASYNCHRONE côté Shopify même en cas de création réelle - un
    retour {"status": "created"} ne veut PAS dire "prêt", voir
    get_buildshop_readiness pour le suivi processing/processingFailed."""
    if not BUILDSHOP_THEME_ZIP_URL:
        logger.warning("Buildshop : BUILDSHOP_THEME_ZIP_URL non configurée, étape thème ignorée pour %s", shop)
        return {"status": "skipped", "reason": "BUILDSHOP_THEME_ZIP_URL non configurée"}

    existing = [t for t in await list_themes(shop, access_token) if t.get("name") == BUILDSHOP_THEME_NAME]
    if existing:
        return {"status": "already_exists", "theme": existing[0]}

    theme = await create_theme_from_url(
        shop, access_token, BUILDSHOP_THEME_ZIP_URL, name=BUILDSHOP_THEME_NAME, role="UNPUBLISHED"
    )
    return {"status": "created", "theme": theme}


async def provision_catalog(shop: str, access_token: str, catalog: list[dict] | None = None) -> dict:
    """Idempotent PAR PRODUIT (titre exact) - un retry après échec
    partiel ne recrée jamais les produits déjà présents, seulement ceux
    manquants. "catalog" permet d'injecter un catalogue différent de
    BASE_CATALOG (voir POST /buildshop/provision, routes/shopify.py) -
    même forme de champs que ShopifyProductUpsertRequest."""
    items = catalog if catalog is not None else BASE_CATALOG
    created, skipped = [], []
    for item in items:
        existing = await find_products_by_title(shop, access_token, item["title"])
        if existing:
            skipped.append({"title": item["title"], "existing_id": existing[0]["id"]})
            continue
        product = await create_product(
            shop, access_token,
            title=item["title"],
            description=item.get("description"),
            price=item.get("price"),
            status=item.get("status", "DRAFT"),
        )
        created.append(product)
    return {"created": created, "skipped_existing": skipped}


async def provision_webhook(shop: str, access_token: str) -> dict:
    """Mince wrapper autour de register_order_webhook (DÉJÀ idempotent,
    voir shopify_service.py) - ajouté uniquement pour renvoyer un statut
    structuré cohérent avec provision_theme/provision_catalog, jamais
    une seconde vérification redondante."""
    if await is_order_webhook_registered(shop, access_token):
        return {"status": "already_registered"}
    await register_order_webhook(shop, access_token)
    return {"status": "created"}


async def get_buildshop_readiness(shop: str, access_token: str) -> list[dict]:
    """Même forme {"key","label","status","detail"} que GET /shopify/
    readiness (routes/shopify.py, le rapport merchant-facing) pour
    rester cohérent si un jour affiché côté outillage interne - mais ce
    N'EST PAS cette route : GET /buildshop/readiness est gatée par la
    clé interne Buildshop, jamais une capacité de workspace (aucun
    marchand n'est rattaché à une boutique pré-transfert). Toujours un
    VRAI appel Shopify (jamais une déduction depuis un état mémorisé),
    même principe que shopify_readiness."""
    # Chaque check est ISOLÉ dans son propre try/except (même principe
    # que shopify_readiness, routes/shopify.py) : un appel Shopify en
    # échec (réseau, throttling...) ne doit jamais faire disparaître les
    # 2 AUTRES checks, qui restent informatifs même si l'un d'eux a
    # échoué.
    checks = []

    if not BUILDSHOP_THEME_ZIP_URL:
        checks.append({
            "key": "theme", "label": "Thème", "status": "skipped",
            "detail": "BUILDSHOP_THEME_ZIP_URL non configurée - étape ignorée.",
        })
    else:
        try:
            themes = [t for t in await list_themes(shop, access_token) if t.get("name") == BUILDSHOP_THEME_NAME]
            if not themes:
                checks.append({
                    "key": "theme", "label": "Thème", "status": "error",
                    "detail": "Aucun thème Buildshop trouvé - relancer POST /buildshop/provision.",
                })
            else:
                theme = themes[0]
                if theme.get("processingFailed"):
                    checks.append({"key": "theme", "label": "Thème", "status": "error", "detail": "Le traitement du thème a échoué côté Shopify."})
                elif theme.get("processing"):
                    checks.append({"key": "theme", "label": "Thème", "status": "warning", "detail": "Thème encore en cours de traitement côté Shopify - réessayer dans quelques instants."})
                else:
                    checks.append({"key": "theme", "label": "Thème", "status": "ok", "detail": f"Prêt (rôle {theme.get('role')}) - publication (themePublish) non automatisée, décision manuelle."})
        except ShopifyAPIError:
            logger.exception("Buildshop : échec vérification thème pour %s", shop)
            checks.append({"key": "theme", "label": "Thème", "status": "error", "detail": "Impossible de vérifier (erreur Shopify)."})

    try:
        products = await list_products(shop, access_token)
        expected = len(BASE_CATALOG)
        if len(products) >= expected:
            checks.append({"key": "catalog", "label": "Catalogue", "status": "ok", "detail": f"{len(products)} produit(s) présent(s)."})
        else:
            checks.append({"key": "catalog", "label": "Catalogue", "status": "warning", "detail": f"{len(products)}/{expected} produit(s) attendu(s) - relancer POST /buildshop/provision."})
    except ShopifyAPIError:
        logger.exception("Buildshop : échec vérification catalogue pour %s", shop)
        checks.append({"key": "catalog", "label": "Catalogue", "status": "error", "detail": "Impossible de vérifier (erreur Shopify)."})

    try:
        registered = await is_order_webhook_registered(shop, access_token)
        checks.append({
            "key": "orders_webhook", "label": "Webhook commandes", "status": "ok" if registered else "error",
            "detail": "Enregistré." if registered else "Non enregistré - relancer POST /buildshop/provision.",
        })
    except ShopifyAPIError:
        logger.exception("Buildshop : échec vérification webhook pour %s", shop)
        checks.append({"key": "orders_webhook", "label": "Webhook commandes", "status": "error", "detail": "Impossible de vérifier (erreur Shopify)."})

    return checks
