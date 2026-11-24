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

import hashlib
import hmac
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOPIFY_REDIRECT_URI = os.getenv("SHOPIFY_REDIRECT_URI", "https://api.xepay.finance/auth/shopify/callback")
SHOPIFY_TIMEOUT_SECONDS = 10

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


def is_valid_shop_domain(shop: str) -> bool:
    return bool(_SHOP_DOMAIN_RE.match(shop or ""))


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
