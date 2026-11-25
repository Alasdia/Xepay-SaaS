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
    ShopifyOrderPayment,
    ShopifyProductUpsertRequest,
    ShopifyShop,
    WorkspaceUser,
)
from backend.routes.buildness import _get_latest_company
from backend.security import create_shopify_state_token, decode_shopify_state_token, decrypt_secret, encrypt_secret
from backend.services.shopify_service import (
    SHOPIFY_CLIENT_ID,
    ShopifyAPIError,
    ShopifyRateLimitError,
    ShopifyScopeError,
    build_authorize_url,
    cancel_order,
    create_customer,
    create_product,
    exchange_code_for_token,
    get_shop_info,
    is_order_webhook_registered,
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

    # "state" OPTIONNEL (revenu en arrière le 2026-11-24 - rendu
    # obligatoire par erreur précédemment) : CORRIGÉ après avoir constaté
    # que access_token ne se mettait JAMAIS à jour en base lors d'une
    # ré-autorisation déclenchée nativement par Shopify (le bandeau
    # "nouvelle version disponible, mettre à jour les autorisations" qui
    # apparaît automatiquement dans l'admin Shopify après la publication
    # d'une nouvelle version de l'app) - ce flux natif ne passe JAMAIS
    # par GET /shopify/install (seul émetteur du state signé), donc
    # aucun state valide n'accompagne son callback. Avec state
    # obligatoire, cette route rejetait alors SYSTÉMATIQUEMENT ce
    # callback (400 "state manquant") avant même d'écrire quoi que ce
    # soit en base - exactement le symptôme observé ("le token ne se met
    # jamais à jour"), quelle que soit la méthode utilisée côté Shopify.
    #
    # La vraie protection anti-forgerie de ce callback reste verify_hmac
    # ci-dessus (déjà obligatoire) : elle prouve que la requête vient
    # réellement de Shopify (signée avec SHOPIFY_CLIENT_SECRET), que le
    # state soit présent ou non. state ne sert plus qu'à résoudre
    # OPPORTUNÉMENT le merchant_id quand le flux est bien passé par
    # /shopify/install (voir handle_shopify_app_entry/shopify_install) -
    # absent ou invalide, merchant_id reste simplement NULL/inchangé,
    # jamais une erreur bloquante.
    state = params.get("state")
    merchant_id = None
    if state:
        decoded_state = decode_shopify_state_token(state)
        if decoded_state:
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
    celle réellement rattachée à ce workspace.

    Trié par updated_at (PAS installed_at, corrigé le 2026-11-24) :
    installed_at n'est posé qu'une seule fois, à la création de la
    ligne, jamais retouché ensuite (contrairement à updated_at,
    onupdate=... - voir models.ShopifyShop) - si ce workspace a plus
    d'une ligne ShopifyShop (ex. deux boutiques de test connectées à
    des moments différents), trier par installed_at aurait toujours
    renvoyé la boutique créée EN PREMIER/DERNIER selon l'ordre, jamais
    celle réellement rafraîchie le plus récemment (scope/token mis à
    jour via un reconsentement OAuth, qui ne change QUE updated_at) -
    symptôme observé : un scope qui semblait ne jamais se mettre à
    jour, alors qu'une AUTRE ligne, non affichée, l'était bien."""
    shop_row = (
        db.query(ShopifyShop)
        .filter(ShopifyShop.merchant_id == workspace_id)
        .order_by(ShopifyShop.updated_at.desc())
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
    except ShopifyScopeError:
        raise HTTPException(status_code=409, detail="Le scope read_products n'est pas accordé - reconnectez la boutique")
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
    except ShopifyScopeError:
        raise HTTPException(status_code=409, detail="Le scope read_orders n'est pas accordé - reconnectez la boutique")
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
    # PLUS de pré-vérification sur ShopifyShop.scope (has_customers_scope,
    # retirée le 2026-11-24 - prouvée peu fiable : une boutique réelle
    # avait read_orders/read_products fonctionnels alors que cette même
    # chaîne ne les listait pas non plus). On tente l'appel réel et on
    # ne renvoie 409 QUE si Shopify le refuse vraiment (ShopifyScopeError,
    # extensions.code=="ACCESS_DENIED") - jamais une déduction a priori.
    try:
        customers = await list_customers(shop_row.shop_domain, decrypt_secret(shop_row.access_token))
    except ShopifyScopeError:
        # 409 (pas 404/403) : la boutique EST bien connectée, c'est
        # spécifiquement le scope client que Shopify refuse - le
        # frontend affiche un message dédié (voir renderShopify,
        # commerce.js), sans jamais bloquer products/orders qui restent
        # indépendants de ce scope.
        raise HTTPException(
            status_code=409,
            detail="Le scope read_customers n'est pas accordé - reconnectez la boutique après l'avoir ajouté au Partner Dashboard",
        )
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
    if not any([data.first_name, data.last_name, data.email, data.phone]):
        raise HTTPException(status_code=400, detail="Au moins un nom, email ou téléphone est requis")
    # PLUS de pré-vérification sur ShopifyShop.scope - voir shopify_customers
    # ci-dessus pour la raison (has_write_customers_scope retirée, prouvée
    # peu fiable). On tente l'appel réel, 409 UNIQUEMENT si Shopify refuse
    # vraiment (ShopifyScopeError - except SPÉCIFIQUE, placé AVANT le
    # except ShopifyAPIError générique ci-dessous, sinon ce dernier
    # l'intercepterait en premier puisque ShopifyScopeError en est une
    # sous-classe).
    try:
        customer = await create_customer(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token),
            data.first_name, data.last_name, data.email, data.phone,
        )
    except ShopifyScopeError:
        raise HTTPException(
            status_code=409,
            detail="Le scope write_customers n'est pas accordé - reconnectez la boutique après l'avoir ajouté au Partner Dashboard",
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
    try:
        customer = await update_customer(
            shop_row.shop_domain, decrypt_secret(shop_row.access_token), customer_id,
            data.first_name, data.last_name, data.email, data.phone,
        )
    except ShopifyScopeError:
        raise HTTPException(
            status_code=409,
            detail="Le scope write_customers n'est pas accordé - reconnectez la boutique après l'avoir ajouté au Partner Dashboard",
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
    except ShopifyScopeError:
        raise HTTPException(status_code=409, detail="Le scope write_products n'est pas accordé - reconnectez la boutique")
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
    except ShopifyScopeError:
        raise HTTPException(status_code=409, detail="Le scope write_products n'est pas accordé - reconnectez la boutique")
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
    except ShopifyScopeError:
        raise HTTPException(status_code=409, detail="Le scope write_orders n'est pas accordé - reconnectez la boutique")
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


# =========================================================
# "Buildshop" - rapport de préparation technique de la boutique (demande
# du 2026-11-25) : AUCUNE UI/thème/design, uniquement la lecture d'état
# réel (jamais ShopifyShop.scope, voir PR #107) et UNE SEULE action
# corrective, l'enregistrement du webhook orders/create - idempotent et
# sans risque. Devise/fuseau horaire/taxes/marchés restent des SIGNAUX
# affichés pour action manuelle du marchand, jamais corrigés
# automatiquement (devise/fuseau horaire sont de toute façon en lecture
# seule côté API Shopify, vérifié le 2026-11-25 - voir get_shop_info).
# =========================================================

def _check(key: str, label: str, status: str, detail: str) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail}


@router.get("/shopify/readiness")
async def shopify_readiness(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("view_shopify_data")),
):
    """Rapport de préparation technique - chaque item est vérifié par un
    VRAI appel Shopify (jamais une déduction depuis une colonne stockée,
    leçon de PR #107). Purement en LECTURE - aucun effet de bord, voir
    POST /shopify/readiness/fix-webhook pour la seule action corrective
    disponible."""
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    shop = shop_row.shop_domain
    token = decrypt_secret(shop_row.access_token)

    checks = []

    # Webhook orders/create - seul item avec une action corrective (voir
    # POST /shopify/readiness/fix-webhook).
    try:
        registered = await is_order_webhook_registered(shop, token)
        checks.append(_check(
            "orders_webhook", "Webhook commandes",
            "ok" if registered else "warning",
            "Enregistré - les commandes Shopify génèrent bien un lien Xepay." if registered
            else "Non enregistré - aucune commande ne générera de lien Xepay tant que ce n'est pas corrigé.",
        ))
    except ShopifyAPIError:
        logger.exception("Échec vérification webhook orders/create pour %s", shop)
        checks.append(_check("orders_webhook", "Webhook commandes", "error", "Impossible de vérifier (erreur Shopify)."))

    # Devise/fuseau horaire - SIGNAL uniquement, jamais corrigé (lecture
    # seule côté API, voir get_shop_info).
    shop_legal_name = None
    try:
        info = await get_shop_info(shop, token)
        currency = info.get("currencyCode")
        currency_ok = currency == "USD"
        checks.append(_check(
            "currency", "Devise de la boutique",
            "ok" if currency_ok else "warning",
            f"{currency or '—'}" + ("" if currency_ok else " - une LLC US encaisse généralement en USD ; à corriger manuellement dans l'admin Shopify si besoin (non modifiable via l'API)."),
        ))
        checks.append(_check(
            "timezone", "Fuseau horaire de la boutique", "ok",
            f"{info.get('ianaTimezone') or '—'} - purement informatif, non modifiable via l'API.",
        ))
        raw_legal_name = (info.get("shopAddress") or {}).get("company")
        shop_legal_name = raw_legal_name.strip() if isinstance(raw_legal_name, str) and raw_legal_name.strip() else None
    except ShopifyAPIError:
        logger.exception("Échec récupération des infos boutique pour %s", shop)
        checks.append(_check("currency", "Devise de la boutique", "error", "Impossible de vérifier (erreur Shopify)."))

    # L'objet de ce check est l'entité juridique RÉELLEMENT enregistrée
    # sur la boutique Shopify (shopAddress.company, lu depuis l'API
    # juste au-dessus) - elle doit toujours être affichée, que Xepay ait
    # ou non une LLC Buildness en base. La LLC Buildness n'est qu'un
    # second terme de comparaison, jamais la donnée principale -
    # corrigé le 2026-11-25 (la première version gatait l'affichage de
    # l'entité Shopify sur l'existence d'une LLC Xepay, inversant
    # l'objectif du check).
    company = _get_latest_company(db, membership.workspace_id)
    company_formed = company and company.status == "completed"

    if shop_legal_name and company_formed:
        names_match = shop_legal_name.lower() == company.company_name.strip().lower()
        checks.append(_check(
            "llc_alignment", "Entité juridique de la boutique",
            "ok" if names_match else "warning",
            (f"Correspondance confirmée - \"{shop_legal_name}\" (entité Shopify) = \"{company.company_name}\" ({company.state}, EIN {company.ein_number or 'non renseigné'})."
             if names_match else
             f"Entité enregistrée sur Shopify : \"{shop_legal_name}\". LLC Buildness : \"{company.company_name}\" ({company.state}) - ne correspond pas, mettez à jour l'adresse de facturation dans l'admin Shopify (Paramètres > Détails de la boutique) avant la passation."),
        ))
    elif shop_legal_name and company:
        checks.append(_check(
            "llc_alignment", "Entité juridique de la boutique", "warning",
            f"Entité enregistrée sur Shopify : \"{shop_legal_name}\". LLC Buildness \"{company.company_name}\" pas encore formée (statut : {company.status}) - comparaison impossible tant que le dossier n'est pas finalisé.",
        ))
    elif shop_legal_name:
        checks.append(_check(
            "llc_alignment", "Entité juridique de la boutique", "warning",
            f"Entité enregistrée sur Shopify : \"{shop_legal_name}\". Aucune LLC Buildness trouvée côté Xepay pour ce workspace - aucune comparaison possible.",
        ))
    elif company_formed:
        checks.append(_check(
            "llc_alignment", "Entité juridique de la boutique", "warning",
            f"LLC Buildness formée (\"{company.company_name}\", {company.state}) mais aucune entreprise renseignée dans l'adresse de facturation Shopify - complétez-la dans l'admin Shopify pour vérifier la correspondance.",
        ))
    else:
        checks.append(_check(
            "llc_alignment", "Entité juridique de la boutique", "warning",
            "Aucune entité renseignée dans l'adresse de facturation Shopify, et aucune LLC Buildness trouvée côté Xepay pour ce workspace.",
        ))

    # Accès réel confirmé (tentative directe, jamais une déduction depuis
    # le scope stocké - PR #107).
    try:
        products_data = await list_products(shop, token)
        if products_data:
            checks.append(_check("products_access", "Catalogue produits", "ok", f"{len(products_data)} produit(s) configuré(s)."))
        else:
            checks.append(_check("products_access", "Catalogue produits", "warning", "Aucun produit configuré - ajoutez au moins un produit avant la passation."))
    except ShopifyScopeError:
        checks.append(_check("products_access", "Catalogue produits", "warning", "Scope read_products refusé par Shopify."))
    except ShopifyAPIError:
        logger.exception("Échec list_products (readiness) pour %s", shop)
        checks.append(_check("products_access", "Catalogue produits", "error", "Impossible de vérifier (erreur Shopify)."))

    try:
        orders_data = await list_orders(shop, token)
        checks.append(_check("orders_access", "Accès aux commandes", "ok", f"{len(orders_data)} commande(s) lue(s) (0 est normal pour une boutique neuve)."))
    except ShopifyScopeError:
        checks.append(_check("orders_access", "Accès aux commandes", "warning", "Scope read_orders refusé par Shopify."))
    except ShopifyAPIError:
        logger.exception("Échec list_orders (readiness) pour %s", shop)
        checks.append(_check("orders_access", "Accès aux commandes", "error", "Impossible de vérifier (erreur Shopify)."))

    try:
        await list_customers(shop, token)
        checks.append(_check("customers_access", "Accès aux clients", "ok", "Lecture réussie."))
    except ShopifyScopeError:
        checks.append(_check("customers_access", "Accès aux clients", "warning", "Scope read_customers refusé par Shopify."))
    except ShopifyAPIError:
        logger.exception("Échec list_customers (readiness) pour %s", shop)
        checks.append(_check("customers_access", "Accès aux clients", "error", "Impossible de vérifier (erreur Shopify)."))

    # Preuve RÉELLE d'encaissement de bout en bout - CORRIGÉ le
    # 2026-11-25 : l'ancienne version devinait depuis
    # Order.paymentGatewayNames (l'historique Shopify), un signal fragile
    # qui ne distinguait pas "jamais essayé" de "essayé mais jamais payé".
    # ShopifyOrderPayment (notre propre table, alimentée par le webhook
    # orders/create - routes/webhook/shopify.py) donne la preuve exacte :
    # marked_paid_at renseigné = webhook -> lien Xepay -> paiement ->
    # orderMarkAsPaid ont TOUS réellement fonctionné pour cette boutique.
    total_xepay_orders = db.query(ShopifyOrderPayment).filter(ShopifyOrderPayment.shop_domain == shop).count()
    paid_xepay_orders = db.query(ShopifyOrderPayment).filter(
        ShopifyOrderPayment.shop_domain == shop, ShopifyOrderPayment.marked_paid_at.isnot(None)
    ).count()
    if paid_xepay_orders > 0:
        checks.append(_check(
            "xepay_payment_flow", "Flux de paiement Xepay", "ok",
            f"Validé de bout en bout - {paid_xepay_orders} commande(s) réellement payée(s) via \"Xepay\" et confirmée(s) sur Shopify (orderMarkAsPaid).",
        ))
    elif total_xepay_orders > 0:
        checks.append(_check(
            "xepay_payment_flow", "Flux de paiement Xepay", "warning",
            f"{total_xepay_orders} commande(s) créée(s) avec la méthode \"Xepay\" mais aucune encore payée - complétez un paiement test avant la passation pour valider tout le flux.",
        ))
    else:
        checks.append(_check(
            "xepay_payment_flow", "Flux de paiement Xepay", "warning",
            "Aucune commande \"Xepay\" détectée - passez une commande test avec cette méthode pour valider le flux (création du lien, paiement, confirmation Shopify) avant la passation.",
        ))

    # Zones de livraison / marchés / taxes de base - AUCUN contrôle API
    # fiable retenu (schéma deliveryProfiles multi-niveaux, ET Shopify
    # crée de toute façon un profil de livraison par défaut sur TOUTE
    # nouvelle boutique - "au moins un profil existe" ne serait donc pas
    # un signal informatif). Checklist déclarative : jamais "ok"
    # automatiquement, toujours un rappel d'action manuelle.
    checks.append(_check(
        "shipping_markets_taxes", "Livraison / marchés / taxes", "warning",
        "Non automatisable - vérifiez manuellement vos zones de livraison, marchés et taxes de base dans l'admin Shopify (Paramètres > Livraison, Paramètres > Taxes) avant la passation.",
    ))

    # Statut global de passation - pure agrégation des checks ci-dessus,
    # aucun nouvel appel Shopify.
    has_error = any(c["status"] == "error" for c in checks)
    has_warning = any(c["status"] == "warning" for c in checks)
    overall_status = "needs_attention" if (has_error or has_warning) else "ready"
    outstanding = [c["label"] for c in checks if c["status"] in ("warning", "error")]

    return {"shop_domain": shop, "status": overall_status, "outstanding": outstanding, "checks": checks}


@router.post("/shopify/readiness/fix-webhook")
async def shopify_readiness_fix_webhook(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_shopify_data")),
):
    """SEULE action corrective du rapport de préparation - idempotente
    (voir register_order_webhook/_find_order_webhook_subscription_id) :
    rejouer cette action sans risque, jamais de doublon d'abonnement."""
    shop_row = _get_connected_shop(db, membership.workspace_id)
    if not shop_row:
        raise HTTPException(status_code=404, detail="Aucune boutique Shopify connectée")
    try:
        await register_order_webhook(shop_row.shop_domain, decrypt_secret(shop_row.access_token))
    except ShopifyScopeError:
        raise HTTPException(status_code=409, detail="Le scope write_orders n'est pas accordé - reconnectez la boutique")
    except ShopifyRateLimitError:
        raise HTTPException(status_code=429, detail="Limite Shopify atteinte, réessayez dans quelques secondes")
    except ShopifyAPIError:
        logger.exception("Échec fix-webhook pour %s", shop_row.shop_domain)
        raise HTTPException(status_code=502, detail="Impossible d'enregistrer le webhook")
    logger.info("Webhook orders/create vérifié/réparé pour %s (workspace %s)", shop_row.shop_domain, membership.workspace_id)
    return {"shop_domain": shop_row.shop_domain, "ok": True}
