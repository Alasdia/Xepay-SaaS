"""Routes OAuth Shopify pour l'app "Xepay Sync" (voir services/
shopify_service.py, models.ShopifyShop) - dédiées et séparées des routes
/login et /auth/google/... existantes (routes/users.py, backend/auth.py) :
ni importées depuis ces fichiers, ni ajoutées dans l'un d'eux, pour ne
jamais faire dépendre ce flux Shopify de leur logique de session
(cookies/CSRF) - callback et entrée embarquée sont des appels
serveur-à-navigateur sans cookie Xepay, comme /auth/google/callback
l'est déjà pour Google, mais dans leur propre fichier plutôt que mélangés
au même router.

handle_shopify_app_entry() : logique de GET / (voir backend/main.py,
home()) quand "shop" est présent - c'est l'URL d'application telle
qu'enregistrée dans le Partner Dashboard pour "Xepay Sync"
(https://api.xepay.finance, sans sous-chemin), donc Shopify charge
directement la racine du backend depuis l'iframe embarqué de l'admin,
jamais /auth/shopify/... pour ce premier contact. Trouvé le 2026-11-24 :
"/" n'était pas exemptée du middleware de session Xepay
(middleware/log_middleware.py), qui renvoyait {"error":"Unauthorized"}
avant même d'atteindre cette logique - corrigé côté middleware, cette
fonction gère la logique métier (déjà installé ? sinon, lance l'OAuth).

CORRIGÉ le 2026-11-24 (après déploiement réel + rechargement de "Xepay
Sync" sur la boutique de test Connect1) : handle_shopify_app_entry
renvoyait un 302 HTTP classique vers /admin/oauth/authorize en réponse
à une requête chargée DANS l'iframe de l'admin Shopify. Shopify interdit
d'afficher ses propres pages admin.shopify.com à l'intérieur d'une
iframe (X-Frame-Options: deny, anti-clickjacking côté Shopify) - la
navigation échouait donc avec "admin.shopify.com n'autorise pas la
connexion" (+ une erreur postMessage secondaire, App Bridge ne
complétant jamais son handshake avec le parent). Toute redirection vers
une page Shopify (admin.oauth.authorize) depuis une requête qui PEUT
être embarquée doit donc être faite en JS sur window.top (voir
_oauth_redirect_html), jamais via un Location HTTP - voir
handle_shopify_app_entry. Le callback (/auth/shopify/callback), lui,
s'exécute TOUJOURS en top-level (Shopify ne rend jamais son écran de
consentement OAuth dans une iframe, quoi que fasse l'app), donc son
302 final vers /admin/apps/{client_id} reste un Location HTTP normal -
jamais besoin du même contournement là.

NON VÉRIFIÉ contre un vrai aller-retour Shopify complet (consentement
réel, redirection) - une vraie app Shopify Partner existe ("Xepay
Sync", clés en prod), mais ce sandbox de développement n'a pas de
navigateur pour suivre le consentement OAuth réel : vérifié ici par
simulation (DB jetable + hmac recalculé + échange de code mocké, voir
le script de test), jamais par un vrai appel. À confirmer par le
marchand sur Connect1."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.middleware.authorization import require_capability
from backend.models import (
    ShopifyCustomerUpsertRequest,
    ShopifyOrderCancelRequest,
    ShopifyProductUpsertRequest,
    ShopifyShop,
    WorkspaceUser,
)
from backend.security import create_shopify_state_token, decode_shopify_state_token, decrypt_secret, encrypt_secret
from backend.services.shopify_service import (
    SHOPIFY_CLIENT_ID,
    ShopifyAPIError,
    ShopifyRateLimitError,
    build_authorize_url,
    cancel_order,
    create_customer,
    create_product,
    exchange_code_for_token,
    has_customers_scope,
    has_write_customers_scope,
    is_valid_shop_domain,
    list_customers,
    list_orders,
    list_products,
    register_order_webhook,
    update_customer,
    update_product,
    verify_hmac,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _frame_ancestors_header(shop: str) -> dict:
    """Content-Security-Policy frame-ancestors : autorise EXPLICITEMENT
    Shopify à afficher nos pages dans son iframe (admin.shopify.com ET le
    domaine {shop} historique) - recommandé par Shopify pour toute page
    d'app embarquée. N'a aucun rapport avec le blocage observé sur
    Connect1 (qui venait de NOUS en train de tenter d'afficher LEUR
    domaine dans l'iframe, pas l'inverse) mais c'est la même famille de
    règle anti-clickjacking, posée ici par rigueur plutôt que de laisser
    le navigateur appliquer un défaut implicite."""
    return {"Content-Security-Policy": f"frame-ancestors https://{shop} https://admin.shopify.com;"}


def _embedded_connected_html(shop: str) -> str:
    """Page minimale servie DANS l'iframe Shopify quand la boutique est
    déjà connectée (ShopifyShop.access_token présent) - le meta
    "shopify-api-key" + app-bridge.js sont requis par Shopify pour
    qu'une app embarquée reste valide dans son iframe (sans ça, Shopify
    affiche sa propre erreur "app non embarquée correctement"). Pas
    encore de vrai tableau de bord embarqué ici (hors périmètre de ce
    correctif, qui ne visait qu'à débloquer l'ouverture de l'app) -
    seulement la confirmation que la connexion a réussi."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="shopify-api-key" content="{SHOPIFY_CLIENT_ID}">
<script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
<title>Xepay Sync</title>
</head>
<body style="font-family:-apple-system,sans-serif;padding:2rem;color:#1a1a1a;">
<h2>Xepay Sync est connecté</h2>
<p>La boutique <strong>{shop}</strong> est synchronisée avec Xepay.</p>
</body>
</html>"""


def _oauth_redirect_html(authorize_url: str) -> str:
    """Page de "breakout" hors iframe - voir le docstring en tête de
    fichier pour l'incident Connect1 du 2026-11-24 qui a motivé ce
    correctif. JAMAIS un 302 HTTP classique ici : cette page est 200 OK
    et son SEUL contenu utile est ce script, qui fait naviguer la fenêtre
    de PLUS HAUT NIVEAU (window.top, jamais self si on est dans l'iframe)
    vers l'écran de consentement OAuth Shopify - admin.shopify.com refuse
    d'être affiché À L'INTÉRIEUR d'une iframe (X-Frame-Options: deny),
    donc seule la fenêtre de plus haut niveau peut s'y rendre.
    json.dumps() : échappe correctement authorize_url pour une injection
    sûre dans le <script>, même si l'URL (construite par urlencode, voir
    build_authorize_url) ne contient déjà aucun caractère dangereux."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Xepay Sync</title></head>
<body>
<script>
(function() {{
  var url = {json.dumps(authorize_url)};
  if (window.top === window.self) {{
    window.location.assign(url);
  }} else {{
    window.top.location.assign(url);
  }}
}})();
</script>
</body>
</html>"""


def handle_shopify_app_entry(params: dict, db: Session) -> Response:
    shop = params.get("shop")
    if not shop or not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="Domaine shop invalide")

    if not verify_hmac(params):
        raise HTTPException(status_code=401, detail="Signature hmac invalide")

    headers = _frame_ancestors_header(shop)

    existing = db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).first()
    if existing and existing.access_token:
        return HTMLResponse(_embedded_connected_html(shop), headers=headers)

    # Pas encore de token pour cette boutique (première installation ou
    # scopes révoqués/ré-installation) : on lance/reprend le consentement
    # OAuth. state signé (create_shopify_state_token) - revérifié par
    # shopify_callback ci-dessous, seule protection CSRF du flux (aucune
    # session serveur n'existe à ce stade pour stocker un nonce
    # autrement, voir security.py). La redirection elle-même passe par
    # _oauth_redirect_html (breakout JS), PAS un RedirectResponse - voir
    # le docstring en tête de fichier.
    state = create_shopify_state_token("")
    authorize_url = build_authorize_url(shop, state)
    return HTMLResponse(_oauth_redirect_html(authorize_url), headers=headers)


@router.get("/auth/shopify/callback")
async def shopify_callback(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    shop = params.get("shop")
    code = params.get("code")

    if not shop or not code or not params.get("hmac"):
        raise HTTPException(status_code=400, detail="Paramètres shop/code/hmac manquants")

    # Validé AVANT tout usage de "shop" dans une URL sortante (voir
    # is_valid_shop_domain, anti-SSRF) - un domaine hors *.myshopify.com
    # est rejeté ici, jamais seulement loggé.
    if not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="Domaine shop invalide")

    if not verify_hmac(params):
        raise HTTPException(status_code=401, detail="Signature hmac invalide")

    # "state" désormais OBLIGATOIRE et revérifié : c'est l'unique
    # protection CSRF du flux d'installation (voir handle_shopify_app_entry
    # ci-dessus, seul émetteur) - toute installation légitime passe par
    # cette fonction avant d'arriver ici, donc un callback SANS state
    # signé valide n'est jamais un vrai aller-retour Shopify initié par
    # Xepay. merchant_id (si le jeton porte un "sub" non vide) résout le
    # workspace Xepay à lier - vide pour l'instant (aucune route
    # authentifiée n'émet encore ce jeton avec un vrai merchant_id, voir
    # le docstring de security.create_shopify_state_token), donc
    # ShopifyShop.merchant_id reste NULL sans bloquer l'enregistrement.
    state = params.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="Paramètre state manquant")
    decoded_state = decode_shopify_state_token(state)
    if not decoded_state:
        raise HTTPException(status_code=401, detail="state invalide ou expiré")
    merchant_id = decoded_state.get("sub") or None

    try:
        token_data = await exchange_code_for_token(shop, code)
    except ShopifyAPIError as e:
        logger.warning("Échec échange code Shopify pour %s : %s", shop, e.status_code)
        raise HTTPException(status_code=502, detail="Échec de l'échange avec Shopify") from e

    access_token = token_data.get("access_token")
    if not access_token:
        # Jamais le corps de token_data dans un log/une exception : même en
        # cas de réponse 2xx malformée, il peut contenir shpat_... - voir
        # tête de fichier.
        logger.warning("Réponse Shopify 2xx sans access_token pour %s", shop)
        raise HTTPException(status_code=502, detail="Réponse Shopify inattendue")

    encrypted_token = encrypt_secret(access_token)
    scope = token_data.get("scope")

    existing = db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).first()
    if existing:
        existing.access_token = encrypted_token
        existing.scope = scope
        if merchant_id:
            existing.merchant_id = merchant_id
    else:
        db.add(ShopifyShop(
            shop_domain=shop,
            merchant_id=merchant_id,
            access_token=encrypted_token,
            scope=scope,
        ))
    db.commit()

    # Enregistrement du webhook orders/create - UNIQUEMENT best-effort :
    # un échec ici (réseau, token déjà invalidé juste après coup...) ne
    # doit jamais faire échouer le callback OAuth lui-même, qui a déjà
    # réussi et déjà committé le token. Sans ce webhook, "Payer via
    # Xepay" (voir routes/webhook/shopify.py) ne recevra simplement
    # jamais de commande - un échec silencieux de SYNCHRONISATION, pas de
    # l'installation.
    try:
        await register_order_webhook(shop, access_token)
    except ShopifyAPIError:
        logger.exception("Échec de l'enregistrement du webhook orders/create pour %s", shop)

    # Redirige vers l'admin Shopify de la boutique (jamais vers
    # app.xepay.finance) : une app embarquée doit rester embarquée après
    # le consentement OAuth - Shopify recharge alors l'iframe sur l'URL
    # d'application (GET /, voir handle_shopify_app_entry ci-dessus), qui
    # trouvera cette fois un ShopifyShop.access_token et affichera la
    # page connectée au lieu de relancer l'OAuth (pas de boucle). Jamais
    # le token (ni son préfixe) dans cette URL ni dans un log.
    return RedirectResponse(url=f"https://{shop}/admin/apps/{SHOPIFY_CLIENT_ID}")


@router.get("/shopify/install")
def shopify_install(
    shop: str,
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_integration")),
):
    """Point d'entrée authentifié (Paramètres > Intégrations côté SPA,
    voir frontend/pages/spa/views/parametres.js) - RATTACHE réellement
    la boutique au marchand : contrairement à handle_shopify_app_entry
    (déclenchée par Shopify lui-même, qui ne connaît aucun merchant_id
    Xepay), cette route tourne dans une session Xepay authentifiée et
    peut donc signer le "state" avec le VRAI workspace_id
    (membership.workspace_id), que shopify_callback lira pour poser
    ShopifyShop.merchant_id.

    PAS un breakout iframe ici (contrairement à handle_shopify_app_entry)
    : cette page n'est JAMAIS chargée dans l'iframe Shopify - le marchand
    clique un lien depuis app.xepay.finance (fenêtre top-level normale),
    donc un Location HTTP classique vers /admin/oauth/authorize fonctionne
    sans aucun problème X-Frame-Options (voir le docstring en tête de
    fichier pour l'incident Connect1 - il ne concernait QUE le cas
    embarqué)."""
    if not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="Domaine shop invalide (attendu : boutique.myshopify.com)")

    state = create_shopify_state_token(membership.workspace_id)
    return RedirectResponse(url=build_authorize_url(shop, state))


@router.get("/shopify/status")
def shopify_status(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_integration")),
):
    """Statut de connexion pour CE workspace (Paramètres > Intégrations) -
    ne renvoie jamais le token, même chiffré."""
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        return {"connected": False}
    return {"connected": True, "shop_domain": shop_row.shop_domain, "scope": shop_row.scope}


def _get_connected_shop(db: Session, workspace_id: str) -> ShopifyShop | None:
    """Résout la boutique connectée pour CE workspace - jamais par un
    "shop" fourni par le client (contrairement à handle_shopify_app_entry/
    shopify_callback, qui eux répondent à Shopify lui-même) : les
    endpoints de lecture ci-dessous (products/orders/customers) ne
    doivent jamais pouvoir lire les données d'une AUTRE boutique que
    celle réellement rattachée à ce workspace."""
    shop_row = (
        db.query(ShopifyShop)
        .filter(ShopifyShop.merchant_id == workspace_id)
        .order_by(ShopifyShop.installed_at.desc())
        .first()
    )
    if not shop_row or not shop_row.access_token:
        return None
    return shop_row


# =========================================================
# Onglet "Shopify" de Commerce (voir frontend/pages/spa/views/
# commerce.js, renderShopify) - lecture DIRECTE depuis l'API Admin
# Shopify, demandée explicitement le 2026-11-24 : AUCUNE table miroir
# côté Xepay, AUCUN objet Stripe créé à partir de ces données - voir
# services/shopify_service.py (list_products/list_orders/list_customers,
# section dédiée). require_capability("view_shopify_data") (manager,
# même niveau que les onglets Stripe de Commerce) - distinct de
# "manage_shopify_integration" (owner), réservée à la connexion/
# déconnexion elle-même.
# =========================================================

@router.get("/shopify/products")
async def shopify_products(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("view_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    try:
        products = await list_products(shop_row.shop_domain, decrypt_secret(shop_row.access_token))
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError:
        logger.exception("Échec list_products pour %s", shop_row.shop_domain)
        raise HTTPException(status_code=502, detail="Impossible de récupérer les produits Shopify")
    return {"shop_domain": shop_row.shop_domain, "data": products}


@router.get("/shopify/orders")
async def shopify_orders(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("view_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    try:
        orders = await list_orders(shop_row.shop_domain, decrypt_secret(shop_row.access_token))
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError:
        logger.exception("Échec list_orders pour %s", shop_row.shop_domain)
        raise HTTPException(status_code=502, detail="Impossible de récupérer les commandes Shopify")
    return {"shop_domain": shop_row.shop_domain, "data": orders}


@router.get("/shopify/customers")
async def shopify_customers(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("view_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    if not has_customers_scope(shop_row.scope):
        # 409 (pas 404/403) : la boutique EST bien connectée, c'est
        # spécifiquement le scope client qui manque - jamais un échec
        # silencieux ni une tentative d'appel Shopify qui échouerait de
        # toute façon (voir has_customers_scope, services/
        # shopify_service.py) - le frontend affiche un message dédié
        # (voir renderShopify, commerce.js), sans jamais bloquer
        # products/orders qui restent indépendants de ce scope.
        raise HTTPException(
            status_code=409,
            detail="Le scope read_customers n'est pas accordé - reconnectez la boutique après l'avoir ajouté au Partner Dashboard",
        )
    try:
        customers = await list_customers(shop_row.shop_domain, decrypt_secret(shop_row.access_token))
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError:
        logger.exception("Échec list_customers pour %s", shop_row.shop_domain)
        raise HTTPException(status_code=502, detail="Impossible de récupérer les clients Shopify")
    return {"shop_domain": shop_row.shop_domain, "data": customers}


# =========================================================
# Écriture (demande du 2026-11-24) - require_capability("manage_shopify_data")
# (manager, même niveau que manage_stripe_billing côté Commerce Stripe) -
# distincte de "view_shopify_data" (lecture) et "manage_shopify_integration"
# (owner, connexion elle-même). Mêmes codes d'erreur que les endpoints de
# lecture (404/409/429/502) + 400 sur une userError Shopify (validation -
# jamais une vraie panne, voir chaque except ShopifyAPIError plus bas qui
# NE distingue PAS 400 vs 502 pour l'instant : _admin_graphql ne porte pas
# cette distinction côté exception, voir son docstring).
# =========================================================

@router.post("/shopify/customers")
async def shopify_create_customer(
    data: ShopifyCustomerUpsertRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    if not has_write_customers_scope(shop_row.scope):
        raise HTTPException(
            status_code=409,
            detail="Le scope write_customers n'est pas accordé - reconnectez la boutique après l'avoir ajouté au Partner Dashboard",
        )
    if not any([data.first_name, data.last_name, data.email, data.phone]):
        raise HTTPException(status_code=400, detail="Au moins un nom, email ou téléphone est requis")
    try:
        customer = await create_customer(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token),
            data.first_name, data.last_name, data.email, data.phone,
        )
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError as e:
        logger.warning("Échec customerCreate pour %s : %s", shop_row.shop_domain, e.body)
        raise HTTPException(status_code=400, detail="Shopify a refusé la création de ce client")
    return {"shop_domain": shop_row.shop_domain, "data": customer}


@router.patch("/shopify/customers/{customer_id}")
async def shopify_update_customer(
    customer_id: str,
    data: ShopifyCustomerUpsertRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    if not has_write_customers_scope(shop_row.scope):
        raise HTTPException(
            status_code=409,
            detail="Le scope write_customers n'est pas accordé - reconnectez la boutique après l'avoir ajouté au Partner Dashboard",
        )
    try:
        customer = await update_customer(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token), customer_id,
            data.first_name, data.last_name, data.email, data.phone,
        )
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError as e:
        logger.warning("Échec customerUpdate pour %s : %s", shop_row.shop_domain, e.body)
        raise HTTPException(status_code=400, detail="Shopify a refusé la modification de ce client")
    return {"shop_domain": shop_row.shop_domain, "data": customer}


@router.post("/shopify/products")
async def shopify_create_product(
    data: ShopifyProductUpsertRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    try:
        product = await create_product(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token),
            data.title, data.description, data.price, data.status,
        )
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError as e:
        logger.warning("Échec productCreate pour %s : %s", shop_row.shop_domain, e.body)
        raise HTTPException(status_code=400, detail="Shopify a refusé la création de ce produit")
    return {"shop_domain": shop_row.shop_domain, "data": product}


@router.patch("/shopify/products/{product_id}")
async def shopify_update_product(
    product_id: str,
    data: ShopifyProductUpsertRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    try:
        product = await update_product(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token), product_id,
            data.title, data.description, data.status,
        )
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError as e:
        logger.warning("Échec productUpdate pour %s : %s", shop_row.shop_domain, e.body)
        raise HTTPException(status_code=400, detail="Shopify a refusé la modification de ce produit")
    return {"shop_domain": shop_row.shop_domain, "data": product}


@router.post("/shopify/orders/{order_id}/cancel")
async def shopify_cancel_order(
    order_id: str,
    data: ShopifyOrderCancelRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_data")),
):
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    try:
        job = await cancel_order(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token), order_id,
            data.reason, data.restock, data.notify_customer, data.staff_note,
        )
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError as e:
        logger.warning("Échec orderCancel pour %s : %s", shop_row.shop_domain, e.body)
        raise HTTPException(status_code=400, detail="Shopify a refusé l'annulation de cette commande")
    # orderCancel est ASYNCHRONE côté Shopify (voir cancel_order,
    # services/shopify_service.py) - "job" porte id/done, done vaut
    # presque toujours false ici : c'est une annulation LANCÉE, pas
    # confirmée. Le frontend doit l'afficher comme telle.
    return {"shop_domain": shop_row.shop_domain, "job": job}
