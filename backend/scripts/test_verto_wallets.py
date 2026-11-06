"""Script de vérification manuelle : login Verto (sandbox, serveur legacy
api-v3-sandbox - voir VERTO_AUTH_MODE="apiKey_plain") + liste des wallets
du compte parent Xepay sur le serveur wallet "nouveau système" (le token
legacy est accepté là-bas, confirmé en sandbox le 2026-10-31). Usage :

    python3 -m backend.scripts.test_verto_wallets

Nécessite VERTO_CLIENT_ID, VERTO_API_KEY dans l'environnement (.env) -
voir backend/services/verto_service.py. VERTO_LOGIN_PUBLIC_KEY_PEM n'est
utile qu'en mode "certificate" (production)."""

import requests

from backend.services import verto_service


def main():
    company_id = verto_service.get_parent_company_id()
    print(f"Connecté - company_id (compte parent) = {company_id}")

    resp = requests.get(
        f"{verto_service.VERTO_WALLET_BASE_URL}/{company_id}/wallets",
        headers=verto_service._headers(),
        # Requis par ce serveur (confirmé en sandbox) - sans ces deux
        # paramètres, 400 "must have required property 'limit'/'skip'".
        params={"limit": 20, "skip": 0},
        timeout=20,
    )
    resp.raise_for_status()
    wallets = resp.json()
    print(f"{wallets['totalCount']} wallet(s) :")
    for w in wallets["items"]:
        print(f"  - {w['currency']} (id={w['id']}) : solde {w['availableBalance']}")


if __name__ == "__main__":
    main()
