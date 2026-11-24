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

NON VÉRIFIÉ contre un vrai aller-retour Shopify (installation réelle
depuis l'admin, consentement, redirection) - une vraie app Shopify
Partner existe désormais ("Xepay Sync", clés en prod), mais ce
sandbox de développement n'a pas d'accès réseau à l'admin Shopify ni de
navigateur pour suivre le consentement OAuth réel : vérifié ici
uniquement par simulation (DB jetable + hmac recalculé + échange de
code mocké, voir le script de test), jamais par un vrai appel. À
confirmer par le marchand sur la boutique Connect1."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ShopifyShop
from backend.security import create_shopify_state_token, decode_shopify_state_token, encrypt_secret
from backend.services.shopify_service import (
    SHOPIFY_CLIENT_ID,
    ShopifyAPIError,
    build_authorize_url,
    exchange_code_for_token,
    is_valid_shop_domain,
    verify_hmac,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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


def handle_shopify_app_entry(params: dict, db: Session) -> Response:
    shop = params.get("shop")
    if not shop or not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="Domaine shop invalide")

    if not verify_hmac(params):
        raise HTTPException(status_code=401, detail="Signature hmac invalide")

    existing = db.query(ShopifyShop).filter(ShopifyShop.shop_domain == shop).first()
    if existing and existing.access_token:
        return HTMLResponse(_embedded_connected_html(shop))

    # Pas encore de token pour cette boutique (première installation ou
    # scopes révoqués/ré-installation) : on lance/reprend le consentement
    # OAuth. state signé (create_shopify_state_token) - revérifié par
    # shopify_callback ci-dessous, seule protection CSRF du flux (aucune
    # session serveur n'existe à ce stade pour stocker un nonce
    # autrement, voir security.py).
    state = create_shopify_state_token("")
    return RedirectResponse(url=build_authorize_url(shop, state))


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

    # Redirige vers l'admin Shopify de la boutique (jamais vers
    # app.xepay.finance) : une app embarquée doit rester embarquée après
    # le consentement OAuth - Shopify recharge alors l'iframe sur l'URL
    # d'application (GET /, voir handle_shopify_app_entry ci-dessus), qui
    # trouvera cette fois un ShopifyShop.access_token et affichera la
    # page connectée au lieu de relancer l'OAuth (pas de boucle). Jamais
    # le token (ni son préfixe) dans cette URL ni dans un log.
    return RedirectResponse(url=f"https://{shop}/admin/apps/{SHOPIFY_CLIENT_ID}")
