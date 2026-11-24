"""Route OAuth Shopify pour l'app "Xepay Sync" (voir services/
shopify_service.py, models.ShopifyShop) - callback UNIQUEMENT, route
dédiée et séparée des routes /login et /auth/google/... existantes
(routes/users.py, backend/auth.py) : ni importée depuis ces fichiers, ni
ajoutée dans l'un d'eux, pour ne jamais faire dépendre ce flux Shopify
de leur logique de session (cookies/CSRF) - le callback Shopify est un
appel serveur-à-navigateur sans cookie Xepay, comme /auth/google/callback
l'est déjà pour Google, mais dans son propre fichier plutôt que mélangé
au même router.

NON VÉRIFIÉ contre un vrai appel Shopify (voir le docstring de
shopify_service.py) - implémenté strictement depuis la documentation
officielle, pas encore testé en conditions réelles faute de clés
SHOPIFY_CLIENT_ID/SHOPIFY_CLIENT_SECRET."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ShopifyShop
from backend.security import decode_shopify_state_token, encrypt_secret
from backend.services.shopify_service import (
    ShopifyAPIError,
    exchange_code_for_token,
    is_valid_shop_domain,
    verify_hmac,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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

    # "state" optionnel : si présent ET signé par Xepay (voir
    # security.create_shopify_state_token - aucune route ne l'émet encore,
    # c'est la future étape de lancement de l'installation), résout le
    # workspace Xepay à lier. Absent ou invalide => merchant_id reste
    # None, jamais une erreur bloquante : la boutique est enregistrée
    # quand même (voir ShopifyShop.merchant_id, nullable).
    merchant_id = None
    state = params.get("state")
    if state:
        decoded = decode_shopify_state_token(state)
        if decoded:
            merchant_id = decoded.get("sub")

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

    # Jamais le token (ni son prefixe) dans l'URL de redirection ni dans
    # un log - seul "shop" (non secret, déjà connu de Shopify/du
    # navigateur) identifie la boutique côté dashboard Xepay.
    return RedirectResponse(
        url=f"https://app.xepay.finance/dashboard.html?shopify=connected&shop={shop}"
    )
