"""Pont Verto pour l'architecture "Zero-Custody" des retraits UEMOA (voir
payout.py, webhook/verto.py, Profile dans models.py) : un sous-compte +
wallet USD par marchand (créés via API, jamais via le dashboard Verto),
alimenté par un Stripe Payout classique, puis relayé vers le compte
bancaire local UEMOA du marchand via un virement IBAN.

Couverture confirmée (support.verto.co/en/articles/16244165, vérifié
2026-10-31) : les 8 pays UEMOA (Bénin, Burkina Faso, Guinée-Bissau,
Côte d'Ivoire, Mali, Niger, Sénégal, Togo) pour le XOF - mais UNIQUEMENT
par virement bancaire (IBAN), aucun mobile money (pas de Wave/Orange
Money/MTN/Moov chez Verto pour le XOF)."""

import os
import base64
import time
import requests
from dotenv import load_dotenv
load_dotenv()
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization

VERTO_CLIENT_ID = os.getenv("VERTO_CLIENT_ID")
VERTO_API_KEY = os.getenv("VERTO_API_KEY")
# Clé PUBLIQUE RSA émise par Verto (Portal -> Verto API -> Certificates ->
# Generate Public Key) - sert à chiffrer VERTO_API_KEY avant chaque login
# (POST /users/login). Sens inverse de VERTO_WEBHOOK_PRIVATE_KEY_PEM
# ci-dessous (celle-ci, Xepay la génère et donne sa clé PUBLIQUE à Verto).
VERTO_LOGIN_PUBLIC_KEY_PEM = os.getenv("VERTO_LOGIN_PUBLIC_KEY_PEM")
VERTO_AUTH_BASE_URL = os.getenv(
    "VERTO_AUTH_BASE_URL", "https://api-company-sandbox.vertofx.com"
)
# Hôte de LOGIN, distinct de VERTO_AUTH_BASE_URL (sous-comptes, voir
# create_sub_account) - confirmé le 2026-11-07 : ce sont deux hôtes dont
# l'acceptation de nos identifiants diffère réellement. POST
# {VERTO_LOGIN_BASE_URL}/users/login sur api-v3-sandbox renvoie 200 avec
# notre clé actuelle, alors que le même appel sur api-company-sandbox
# (VERTO_AUTH_BASE_URL) renvoie 401 "Invalid API Key". Le jeton obtenu via
# api-v3-sandbox est ensuite accepté par wallet/onboarding/beneficiary
# (200/404-légitime) - seul POST /sub-accounts sur api-company-sandbox
# renvoie 403 "Access Denied" avec ce jeton (accès Atlas probablement pas
# activé sur ce compte sandbox, voir VertoAtlasNotEnabledError - pas un
# problème d'identifiants). Doit être défini APRÈS VERTO_AUTH_BASE_URL
# (sert de valeur par défaut). Legacy api-v3-sandbox annoncé déprécié par
# Verto (sunset 2027-01-30) : le défaut pointe donc déjà vers le nouvel
# hôte, à surcharger via .env tant que api-company-sandbox/users/login ne
# marche pas pour notre compte.
VERTO_LOGIN_BASE_URL = os.getenv("VERTO_LOGIN_BASE_URL", VERTO_AUTH_BASE_URL)
# "apiKey_plain" (sandbox, confirmé via docs.verto.co/docs/authentication-1
# le 2026-10-31 : en sandbox, apiKey part en clair, sans chiffrement RSA)
# ou "certificate" (production - chiffrement RSA via VERTO_LOGIN_PUBLIC_KEY_PEM,
# cf. _encrypt_api_key). Les deux modes coexistent, celui-ci choisit lequel
# utiliser - ne jamais forcer "certificate" en sandbox ni l'inverse en prod.
VERTO_AUTH_MODE = os.getenv("VERTO_AUTH_MODE", "apiKey_plain")
# Clé privée RSA générée par Xepay, dont la clé publique correspondante
# est enregistrée côté Verto - nécessaire pour déchiffrer les en-têtes
# `auth-*` de leurs webhooks (voir verify_webhook_signature). PAS ENCORE
# GÉNÉRÉE/ENREGISTRÉE - placeholder tant que ce n'est pas fait.
VERTO_WEBHOOK_PRIVATE_KEY_PEM = os.getenv("VERTO_WEBHOOK_PRIVATE_KEY_PEM")


class VertoAtlasNotEnabledError(RuntimeError):
    """POST /sub-accounts a renvoyé 403 "Access Denied" alors que le jeton
    est valide (accepté par wallet/onboarding/beneficiary, voir le test du
    2026-11-07) - signe que la fonctionnalité "Atlas for Platforms" n'est
    probablement pas activée sur ce compte Verto, pas un identifiant
    invalide. Permet à l'appelant (routes/verto.py) de distinguer ce cas
    précis d'une vraie panne et d'afficher un message propre au marchand,
    sans exposer le détail brut de Verto."""


# Cache du JWT de session (valide 60 min côté Verto) - un seul process
# Xepay partage une session Verto (le compte parent), pas un jwt par
# requête. Pas thread-safe au sens strict (pas de lock), mais une relogin
# en double en cas de course est sans conséquence (juste un appel réseau
# en plus) - voir _get_token.
_jwt_cache: dict = {"token": None, "expires_at": 0, "company_id": None, "company_settings_id": None}


def _encrypt_api_key(raw_api_key: str) -> str:
    """Mode certificat (production uniquement - voir VERTO_AUTH_MODE) :
    chiffre "API_KEY:timestamp_ms" (pas la clé seule) avec la clé publique
    RSA émise par Verto, padding OAEP/SHA-512."""
    if not VERTO_LOGIN_PUBLIC_KEY_PEM:
        raise RuntimeError("VERTO_LOGIN_PUBLIC_KEY_PEM manquant")
    public_key = serialization.load_pem_public_key(VERTO_LOGIN_PUBLIC_KEY_PEM.encode())
    payload = f"{raw_api_key}:{int(time.time() * 1000)}"
    ciphertext = public_key.encrypt(
        payload.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA512()),
            algorithm=hashes.SHA512(),
            label=None,
        ),
    )
    return base64.b64encode(ciphertext).decode()


def _login() -> dict:
    api_key_field = (
        VERTO_API_KEY if VERTO_AUTH_MODE == "apiKey_plain" else _encrypt_api_key(VERTO_API_KEY)
    )
    resp = requests.post(
        f"{VERTO_LOGIN_BASE_URL}/users/login",
        headers={"Content-Type": "application/json"},
        json={
            "mode": "apiKey",
            "clientId": VERTO_CLIENT_ID,
            "apiKey": api_key_field,
        },
        timeout=20,
    )
    print("VERTO HTTP:", resp.status_code)
    resp.raise_for_status()
    data = resp.json()
    # Confirmé via docs.verto.co/docs/authentication-1 : le champ est
    # "token" (pas "jwt") - on garde un repli sur "jwt" par prudence si la
    # forme diffère réellement entre les deux modes d'auth.
    _jwt_cache["token"] = data.get("token") or data.get("jwt")
    # Renouvelle 5 min avant l'expiration réelle (60 min) pour éviter
    # qu'une requête parte avec un token expiré pendant le trajet réseau.
    _jwt_cache["expires_at"] = time.time() + (60 * 60) - (5 * 60)
    _jwt_cache["company_id"] = data.get("companyId")
    _jwt_cache["company_settings_id"] = data.get("companySettingsId")
    return data


def get_token() -> str:
    """Token Bearer en cache, renouvelé automatiquement à l'expiration."""
    if not _jwt_cache["token"] or time.time() >= _jwt_cache["expires_at"]:
        _login()
    return _jwt_cache["token"]


def get_company_settings_id() -> str | None:
    """`companySettingsId` renvoyé par /users/login (serveur legacy
    api-v3-sandbox) - usage exact pas encore déterminé, mis en cache au
    cas où un endpoint wallet/legacy en a besoin."""
    if not _jwt_cache["token"]:
        _login()
    return _jwt_cache["company_settings_id"]


def get_parent_company_id() -> str:
    """ID du compte parent Verto de Xepay (pas celui d'un sous-compte
    marchand) - renvoyé par /users/login."""
    if not _jwt_cache["company_id"]:
        _login()
    return _jwt_cache["company_id"]


# Chaque ressource Verto vit sur un sous-domaine dédié (confirmé un par un
# via leurs specs OpenAPI, pas une convention uniforme /{companyId}/... -
# ne pas supposer qu'un nouvel endpoint partage un domaine déjà utilisé
# sans le vérifier explicitement).
VERTO_ONBOARDING_BASE_URL = os.getenv(
    "VERTO_ONBOARDING_BASE_URL", "https://api-onboarding-sandbox.vertofx.com"
)
VERTO_WALLET_BASE_URL = os.getenv(
    "VERTO_WALLET_BASE_URL", "https://api-wallet-sandbox.vertofx.com"
)
VERTO_BENEFICIARY_BASE_URL = os.getenv(
    "VERTO_BENEFICIARY_BASE_URL", "https://api-beneficiary-sandbox.vertofx.com"
)
VERTO_PAYMENT_BASE_URL = os.getenv(
    "VERTO_PAYMENT_BASE_URL", "https://api-payment-sandbox.vertofx.com"
)
VERTO_EXCHANGE_BASE_URL = os.getenv(
    "VERTO_EXCHANGE_BASE_URL", "https://api-exchange-now-sandbox.vertofx.com"
)
# `currencyId` Verto pour le compte bénéficiaire local UEMOA (XOF) - aucun
# endpoint "list currencies" trouvé dans la doc publique, donc NON
# VÉRIFIÉ, contrairement à purposeId qui lui se résout dynamiquement via
# list_payment_purpose_codes(). A confirmer avec Verto/leur sandbox.
VERTO_XOF_CURRENCY_ID = int(os.getenv("VERTO_XOF_CURRENCY_ID", "0"))


def _headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_sub_account(
    *,
    account_type: str,
    country: str,
    name: str,
    sub_category: str,
    identification_number: str,
    tax_id_or_ein: str | None = None,
    external_id: str | None = None,
) -> dict:
    """Première étape de l'onboarding marchand : crée l'enregistrement du
    sous-compte (statut initial `CREATED`) et renvoie son `id`
    (= company_id), à utiliser ensuite pour submit_onboarding_data,
    create_wallet, etc. `account_type="SUB_CLIENT"` est la valeur
    attendue pour un marchand final de la plateforme (pas un partenaire
    revendeur ni une entité liée à Xepay elle-même)."""
    body = {
        "accountType": account_type,
        "country": country,
        "name": name,
        "subCategory": sub_category,
        "identificationNumber": identification_number,
    }
    if tax_id_or_ein:
        body["taxIdOrEin"] = tax_id_or_ein
    if external_id:
        body["externalId"] = external_id
    resp = requests.post(
        f"{VERTO_AUTH_BASE_URL}/sub-accounts",
        headers=_headers(),
        json=body,
        timeout=20,
    )
    if resp.status_code == 403:
        raise VertoAtlasNotEnabledError(
            "Verto a refusé la création de sous-compte (403 Access Denied) "
            "- probablement l'accès \"Atlas for Platforms\" non activé sur "
            "ce compte sandbox (vérifié le 2026-11-07, le jeton lui-même "
            "est valide). À confirmer avec le support Verto."
        )
    resp.raise_for_status()
    return resp.json()


def submit_onboarding_data(company_id: str, kyc_payload: dict) -> dict:
    """Soumet les données KYC entreprise du marchand (collectées côté UI
    Xepay : dirigeants/UBO 25%+, documents, adresse) - un seul POST,
    aucun login Verto requis côté marchand. Le sous-compte passe en
    statut CREATED -> REVIEW -> APPROVED/REJECTED, notifié par webhook
    (voir webhook/verto.py)."""
    resp = requests.post(
        f"{VERTO_ONBOARDING_BASE_URL}/companies/{company_id}/onboarding-data",
        headers=_headers(),
        json=kyc_payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def create_wallet(company_id: str, currency: str = "USD") -> dict:
    """Crée le solde USD du sous-compte - uniquement possible une fois le
    sous-compte APPROVED (toute activité opérationnelle reste bloquée
    avant ça, cf. doc onboarding)."""
    resp = requests.post(
        f"{VERTO_WALLET_BASE_URL}/{company_id}/wallets",
        headers=_headers(),
        json={"currency": currency, "type": "standard"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def get_usd_funding_details(company_id: str, wallet_id: str) -> dict:
    """Coordonnées bancaires receveuses réelles du wallet (accountNumber,
    bankCode, bankName) - autoCreate=true les génère à la volée si elles
    n'existent pas encore. C'est CE résultat qui est affiché dans l'UI
    Xepay pour que le marchand les colle dans son Dashboard Stripe
    Express (voir routes/payout.py pour pourquoi Xepay ne peut pas le
    faire à sa place). Lève si fundsType != "SEGERATED" n'est pas
    vérifié par l'appelant - cette fonction renvoie la donnée brute,
    la vérification est à faire côté appelant."""
    resp = requests.get(
        f"{VERTO_WALLET_BASE_URL}/{company_id}/wallets/{wallet_id}/fundingMethods",
        headers=_headers(),
        params={"autoCreate": "true"},
        timeout=20,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"Aucune méthode de financement renvoyée pour le wallet {wallet_id}")
    return items[0]


def verify_webhook_signature(headers: dict, company_id: str) -> bool:
    """Vérifie un webhook Verto : contrairement à Stripe/Flutterwave (HMAC
    sur le payload), Verto chiffre un jeton (RSA-OAEP/SHA-512) dans un ou
    plusieurs en-têtes `auth-*` - il faut tenter le déchiffrement avec la
    clé privée Xepay, puis vérifier que le jeton déchiffré contient
    base64(company_id) + "||" + <jour UTC du mois>. Avoir plusieurs
    certificats actifs côté Verto fait qu'une partie des en-têtes ne se
    déchiffre pas - c'est normal, il suffit qu'UN seul réussisse."""
    if not VERTO_WEBHOOK_PRIVATE_KEY_PEM:
        return False
    private_key = serialization.load_pem_private_key(
        VERTO_WEBHOOK_PRIVATE_KEY_PEM.encode(), password=None
    )
    expected_prefix = base64.b64encode(company_id.encode()).decode()
    today_utc_day = time.gmtime().tm_mday
    for key, value in headers.items():
        if not key.lower().startswith("auth-"):
            continue
        try:
            decrypted = private_key.decrypt(
                base64.b64decode(value),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA512()),
                    algorithm=hashes.SHA512(),
                    label=None,
                ),
            ).decode()
        except Exception:
            continue
        prefix, _, day_str = decrypted.partition("||")
        if prefix != expected_prefix:
            continue
        try:
            day = int(day_str)
        except ValueError:
            continue
        if abs(day - today_utc_day) <= 1:
            return True
    return False


UEMOA_COUNTRY_CODES = {"BJ", "BF", "CI", "GW", "ML", "NE", "SN", "TG"}


def validate_iban_bic(iban: str, bic: str) -> None:
    """Garde-fou de FORME avant tout appel réseau Verto (évite un aller-
    retour API pour une faute de frappe évidente) - ne remplace pas la
    validation de Verto elle-même (compte réel inconnu ici, checksum
    complet). Longueur IBAN (28, confirmé par le message d'erreur Verto
    "country code followed by 26 characters" le 2026-11-07) et BIC (8 ou
    11, format SWIFT standard), plus cohérence pays IBAN/BIC (positions
    4:6 du BIC = code pays ISO, doit correspondre aux 2 premiers
    caractères de l'IBAN). Lève ValueError, jamais un HTTPException
    directement - ce module ne connaît pas FastAPI (voir en-tête du
    fichier), c'est aux routes appelantes de convertir."""
    iban = (iban or "").strip().upper()
    bic = (bic or "").strip().upper()
    if len(iban) != 28:
        raise ValueError("IBAN invalide : 28 caractères attendus pour un pays UEMOA.")
    iban_country = iban[:2]
    if iban_country not in UEMOA_COUNTRY_CODES:
        raise ValueError(f"IBAN invalide : le pays '{iban_country}' n'est pas un pays UEMOA.")
    if len(bic) not in (8, 11):
        raise ValueError("BIC invalide : 8 ou 11 caractères attendus.")
    bic_country = bic[4:6]
    if bic_country != iban_country:
        raise ValueError(
            f"Le pays du BIC ('{bic_country}') ne correspond pas à celui de l'IBAN ('{iban_country}')."
        )


def create_beneficiary(
    *,
    currency_id: int,
    company_name: str,
    iban: str,
    bic: str,
    bank_name: str,
    bank_country_code: str,
    beneficiary_address_line1: str,
    beneficiary_country_code: str,
    beneficiary_city: str,
    beneficiary_postal_code: str,
    beneficiary_state_or_province: str,
) -> dict:
    """Enregistre le compte bancaire local UEMOA du marchand - une seule
    fois (le resultat, `accounts.id`, est réutilisé à chaque virement).
    `verificationState` peut revenir "pending" : il faut attendre son
    passage à "approved" avant de pouvoir l'utiliser dans un virement
    (voir create_payment_request).

    Confirmé par API le 2026-11-07 (création réussie du bénéficiaire test
    "test-api-1", id 18023, verificationState "approved") :
    - paymentMode="LOCAL" (virement domestique XOF/UEMOA, pas SWIFT).
    - Le BIC va dans `bankCode` - PAS `nationalId` (qui ne satisfait pas
      l'exigence "Bank code is required", contrairement à ce que
      suggérait la doc générale sur les marchés sans code bancaire
      local).
    - `bankAddress` : `countryCode` seul suffit, jamais besoin de
      ville/code postal/région côté banque.
    - `beneficiaryAddress` : countryCode + addressLine1 +
      stateOrProvience + city + postCode sont TOUS obligatoires en
      pratique, même en LOCAL - contrairement à la doc publique qui les
      réserve à INTERNATIONAL (vérifié un par un, chaque champ manquant
      déclenche une erreur 400 dédiée).
    - `bankName` reste obligatoire (son omission déclenche "body must
      have required property 'bankName'") - jamais rendu facultatif,
      contrairement à l'intention initiale.

    N'appelle PAS validate_iban_bic() ici - c'est à l'appelant (routes/
    verto.py) de le faire avant, pour renvoyer un 400 propre plutôt
    qu'une erreur Verto brute sur un format déjà invalide côté client."""
    resp = requests.post(
        f"{VERTO_BENEFICIARY_BASE_URL}/recipients",
        headers=_headers(),
        json={
            "currencyId": currency_id,
            "beneficiaryType": "company",
            "paymentMode": "LOCAL",
            "accountNumber": iban,
            "bankCode": bic,
            "bankName": bank_name,
            "bankAddress": {"countryCode": bank_country_code},
            "beneficiaryAddress": {
                "addressLine1": beneficiary_address_line1,
                "countryCode": beneficiary_country_code,
                "city": beneficiary_city,
                "postCode": beneficiary_postal_code,
                "stateOrProvience": beneficiary_state_or_province,
            },
            "companyName": company_name,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def create_payment_request(
    *,
    beneficiary_id: int,
    purpose_id: int,
    amount_usd: float,
    wallet_id: int,
    client_reference: str,
    payment_id: str,
) -> dict:
    """Deuxième jambe : débite le wallet USD Verto du marchand et envoie
    vers son compte bancaire local UEMOA (beneficiary_id, déjà créé via
    create_beneficiary et "approved") - déclenché par Xepay sur réception
    du webhook "Wallet Credit" (voir webhook/verto.py), jamais automatique
    côté Verto. `payment_id` : UUID généré par l'appelant, pour
    l'idempotence (voir uuid.uuid4()).

    `purpose_id` : code de motif de paiement Verto - voir
    list_payment_purpose_codes() pour le résoudre dynamiquement plutôt
    que de le figer en config."""
    resp = requests.post(
        f"{VERTO_PAYMENT_BASE_URL}/payment-requests",
        headers=_headers(),
        json={
            "beneficiaryId": beneficiary_id,
            "purposeId": purpose_id,
            "amount": amount_usd,
            "walletId": wallet_id,
            "clientReference": client_reference,
            "paymentId": payment_id,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def list_payment_purpose_codes(
    *, payment_direction: str, currency: str, mode: str
) -> list[dict]:
    """Résout dynamiquement le `purposeId` à utiliser pour create_payment_request
    (remplace l'ancienne config statique VERTO_PAYOUT_PURPOSE_ID - cet
    endpoint existe réellement, pas besoin de deviner/configurer en dur).
    `payment_direction` : "Inbound" | "Outbound" | "Cards" (pour un
    retrait marchand : "Outbound"). `mode` : "LOCAL" | "GLOBAL"."""
    resp = requests.get(
        f"{VERTO_PAYMENT_BASE_URL}/payments/purpose-codes",
        headers=_headers(),
        params={
            "purpose": "true",
            "paymentDirection": payment_direction,
            "currency": currency,
            "type": mode,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("documentTypes", [])


def get_fx_quote(
    *, amount: float, amount_currency: str, currency_from: str, currency_to: str
) -> dict:
    """Verrouille un taux de change (vfx_token, de courte durée - voir
    `expiry` dans la réponse) avant de l'utiliser dans create_fx_trade.
    Nécessaire si le wallet source (USD) et la devise du bénéficiaire
    (XOF) diffèrent et que create_payment_request ne gère pas la
    conversion dans le même appel (NON CONFIRMÉ - à vérifier en sandbox :
    il est possible que create_payment_request fasse déjà la conversion
    automatiquement, rendant cet appel inutile pour notre cas d'usage)."""
    resp = requests.post(
        f"{VERTO_EXCHANGE_BASE_URL}/fx/quote",
        headers=_headers(),
        json={
            "amount": amount,
            "amountCurrency": amount_currency,
            "currencyFrom": currency_from,
            "currencyTo": currency_to,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def create_fx_trade_payout(
    *,
    vfx_token: str,
    target_account_id: int,
    purpose_id: int,
    source_wallet_id: int,
    source_amount: float,
    payment_id: str,
    custom_payment_reference: str,
) -> dict:
    """Convertit ET paie en un seul appel (paymentType=convertWalletPayout)
    - alternative à create_payment_request si celui-ci ne gère pas la
    conversion USD->XOF automatiquement (voir get_fx_quote). NON TESTÉ."""
    resp = requests.post(
        f"{VERTO_EXCHANGE_BASE_URL}/fx/payments",
        headers=_headers(),
        json={
            "paymentType": "convertWalletPayout",
            "targetAccountId": target_account_id,
            "vfxToken": vfx_token,
            "purposeId": purpose_id,
            "sourceWalletId": source_wallet_id,
            "sourceAmount": source_amount,
            "paymentId": payment_id,
            "customPaymentReference": custom_payment_reference,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()
