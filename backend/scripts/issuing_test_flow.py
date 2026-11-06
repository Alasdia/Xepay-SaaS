"""Script de vérification manuelle : rejoue de zéro, sur un NOUVEAU compte
Connect, tout le cycle Stripe Issuing validé manuellement le 2026-11-06 sur
acct_1UYlMN0j0iZXzVin / carte ic_1UYlSd0j0iZXzVinLx4A5Flh :

    compte (dashboard none) -> KYC de test -> programme Issuing -> ToS
    (compte + cardholder) -> cardholder -> carte virtuelle -> financement
    (pull funding ACH test) -> autorisation + capture -> 2 refus simulés.

MODE TEST UNIQUEMENT. Ce script ne doit jamais être pointé sur une clé
"sk_live_...". Les adresses IP / dates d'acceptation des conditions
Issuing utilisées ici sont des valeurs FACTICES fournies par ce script
pour les besoins du test (voir TEST_TOS_IP / TEST_TOS_DATE ci-dessous) -
en production, ces deux valeurs doivent venir d'un vrai geste de
consentement du marchand (IP et horodatage réels capturés au moment où
il accepte les conditions dans l'UI Xepay), jamais être fabriquées par
le backend.

Usage :

    python3 -m backend.scripts.issuing_test_flow

Nécessite STRIPE_SECRET_KEY dans l'environnement (.env), une clé
"sk_test_...". Le script refuse de s'exécuter sur une clé "sk_live_...".
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.stripe.com"
# Flag bêta confirmé fonctionnel le 2026-11-06 pour : création de compte v2,
# programmes Issuing, cardholders, cartes. Les endpoints d'autorisation/
# capture ont aussi été validés avec ce même header (pas testé sans).
ISSUING_STRIPE_VERSION = "2026-10-28.preview; issuing_program_beta=v2"

# --- TEST ONLY --------------------------------------------------------
# Valeurs d'acceptation de conditions (ToS) FACTICES, pour sandbox
# uniquement. Jamais utiliser en production : en prod, l'IP et la date
# doivent venir du navigateur du marchand au moment réel où il accepte
# les conditions Issuing dans l'UI Xepay (pas une valeur du backend).
TEST_TOS_IP = "172.18.80.19"  # valeur d'exemple de la doc Stripe (connect/testing-verification)
# ------------------------------------------------------------------------

# Adresse/identité de test standard Stripe (persona "Jenny Rosen" utilisée
# dans toute la documentation Stripe Issuing/Connect).
TEST_ADDRESS = {
    "line1": "510 Townsend Street",
    "city": "San Francisco",
    "state": "CA",
    "postal_code": "94111",
    "country": "US",
}
# SSN/EIN de test Stripe qui se vérifient automatiquement en sandbox.
TEST_ID_NUMBER = "000000000"
TEST_TAX_ID = "000000000"
# Routing/numéro de compte de test Stripe ("Stripe Test Bank").
TEST_BANK_ROUTING_NUMBER = "110000000"
TEST_BANK_ACCOUNT_NUMBER = "000123456789"
# Les deux montants de micro-dépôt que Stripe accepte pour toute source
# ach_debit de test (voir doc connect/funding).
TEST_MICRODEPOSIT_VALUES = [32, 45]


def _get_api_key() -> str:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY manquant dans l'environnement")
    if key.startswith("sk_live"):
        raise RuntimeError(
            "Clé live détectée (sk_live_...) - ce script est test-only, abandon."
        )
    return key


def _request(method, path, account=None, version=None, api_version="v1", **data):
    """Appel Stripe générique. `data` devient des paires de formulaire pour
    v1 (POST/GET classiques) ou un corps JSON pour v2. La clé n'est jamais
    affichée ni journalisée ici."""
    key = _get_api_key()
    headers = {}
    if version:
        headers["Stripe-Version"] = version
    if account:
        headers["Stripe-Account"] = account

    url = f"{API_BASE}{path}"
    if api_version == "v2":
        headers["Authorization"] = f"Bearer {key}"
        resp = requests.request(method, url, headers=headers, json=data, timeout=30)
    else:
        resp = requests.request(
            method, url, headers=headers, auth=(key, ""), data=data or None, timeout=30
        )

    body = resp.json()
    if resp.status_code >= 400:
        err = body.get("error", body)
        raise RuntimeError(f"{method} {path} -> {resp.status_code} : {err}")
    return body


def list_default_platform_program():
    """Le programme Issuing de la plateforme (banque/réseau) est configuré
    une fois par Stripe pour tout le compte plateforme - on le retrouve
    dynamiquement plutôt que de coder en dur son id, qui est spécifique à
    cet environnement Stripe."""
    resp = _request("GET", "/v1/issuing/programs", version=ISSUING_STRIPE_VERSION)
    for program in resp["data"]:
        if program.get("is_default"):
            return program
    raise RuntimeError("Aucun programme Issuing par défaut trouvé sur la plateforme")


def create_connected_account(suffix: str) -> str:
    body = _request(
        "POST",
        "/v2/core/accounts",
        api_version="v2",
        version="2026-10-28.preview",
        include=["configuration.recipient", "requirements"],
        contact_email=f"issuing-test-{suffix}@example.com",
        display_name=f"Issuing test {suffix}",
        identity={"country": "US", "entity_type": "company"},
        dashboard="none",
        defaults={
            "currency": "usd",
            "responsibilities": {"fees_collector": "application", "losses_collector": "application"},
        },
        configuration={
            "recipient": {"capabilities": {"stripe_balance": {"stripe_transfers": {"requested": True}}}}
        },
    )
    return body["id"]


def fill_kyc_test_data(acct_id: str, suffix: str) -> None:
    now_ts = int(time.time())

    _request(
        "POST",
        f"/v1/accounts/{acct_id}",
        **{
            "business_profile[mcc]": "5734",
            # product_description plutôt que url : Stripe rejette example.com
            # (domaine réservé documentation) comme "Not a valid URL", et un
            # vrai domaine serait nécessaire sinon - product_description
            # évite cette dépendance pour un script de test rejouable.
            "business_profile[product_description]": f"Compte de test Issuing #{suffix}",
            "company[name]": f"Issuing Test Co {suffix}",
            "company[phone]": "8888675309",
            "company[tax_id]": TEST_TAX_ID,
            "company[address][line1]": TEST_ADDRESS["line1"],
            "company[address][city]": TEST_ADDRESS["city"],
            "company[address][state]": TEST_ADDRESS["state"],
            "company[address][postal_code]": TEST_ADDRESS["postal_code"],
            "company[address][country]": TEST_ADDRESS["country"],
            # ToS plateforme générique (Stripe Services Agreement), pas celui
            # d'Issuing - valeur de test, voir avertissement en tête de fichier.
            "tos_acceptance[date]": now_ts,
            "tos_acceptance[ip]": TEST_TOS_IP,
            "external_account[object]": "bank_account",
            "external_account[country]": "US",
            "external_account[currency]": "usd",
            "external_account[account_holder_type]": "company",
            "external_account[routing_number]": TEST_BANK_ROUTING_NUMBER,
            "external_account[account_number]": TEST_BANK_ACCOUNT_NUMBER,
        },
    )

    # Une seule personne, à la fois représentant et propriétaire à 100% -
    # Stripe refuse deux Person identiques (même nom/dob/adresse) sur un
    # même compte, donc on ne crée PAS une seconde personne "owner".
    person = _request(
        "POST",
        f"/v1/accounts/{acct_id}/persons",
        first_name="Jenny",
        last_name="Rosen",
        **{"email": "jenny.rosen@example.com"},
        **{
            "dob[day]": 1,
            "dob[month]": 11,
            "dob[year]": 1981,
            "address[line1]": TEST_ADDRESS["line1"],
            "address[city]": TEST_ADDRESS["city"],
            "address[state]": TEST_ADDRESS["state"],
            "address[postal_code]": TEST_ADDRESS["postal_code"],
            "address[country]": TEST_ADDRESS["country"],
            "id_number": TEST_ID_NUMBER,
            "relationship[representative]": "true",
            "relationship[executive]": "true",
            "relationship[title]": "CEO",
        },
    )
    _request(
        "POST",
        f"/v1/accounts/{acct_id}/persons/{person['id']}",
        **{"relationship[owner]": "true", "relationship[percent_ownership]": "100"},
    )

    _request("POST", f"/v1/accounts/{acct_id}", **{"company[owners_provided]": "true"})


def create_program_on_account(acct_id: str, platform_program_id: str) -> str:
    body = _request(
        "POST",
        "/v1/issuing/programs",
        account=acct_id,
        version=ISSUING_STRIPE_VERSION,
        platform_program=platform_program_id,
        is_default="true",
    )
    return body["id"]


def accept_account_level_issuing_tos(acct_id: str, capability_id: str) -> None:
    """Lit les champs réellement exigés par la capacité Issuing du compte
    (settings.card_issuing.tos_acceptances.<accord>.date/.ip) et les remplit
    avec la valeur de test - plutôt que de coder en dur des noms de banque,
    ce qui casserait si Stripe change de partenaire bancaire."""
    cap = _request(
        "GET",
        f"/v1/accounts/{acct_id}/capabilities/{capability_id}",
        version=ISSUING_STRIPE_VERSION,
    )
    agreements = set()
    for field in cap["requirements"]["currently_due"]:
        # ex: "settings.card_issuing.tos_acceptances.account_holder.date"
        if field.startswith("settings.card_issuing.tos_acceptances."):
            agreements.add(field.split(".")[3])

    if not agreements:
        return

    now_ts = int(time.time())
    data = {}
    for agreement in agreements:
        data[f"settings[card_issuing][tos_acceptances][{agreement}][date]"] = now_ts
        data[f"settings[card_issuing][tos_acceptances][{agreement}][ip]"] = TEST_TOS_IP

    _request("POST", f"/v1/accounts/{acct_id}", version=ISSUING_STRIPE_VERSION, **data)


def wait_for_capability_active(acct_id: str, capability_id: str, timeout_s: int = 90) -> None:
    """Après acceptation des ToS, la capacité passe par un statut 'pending'
    (vérification sandbox simulée) avant 'active' - observé jusqu'à ~25s
    le 2026-11-06, ce timeout laisse une marge confortable."""
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        cap = _request(
            "GET",
            f"/v1/accounts/{acct_id}/capabilities/{capability_id}",
            version=ISSUING_STRIPE_VERSION,
        )
        last_status = cap["status"]
        if last_status == "active":
            return
        time.sleep(3)
    raise RuntimeError(
        f"Capacité {capability_id} toujours '{last_status}' après {timeout_s}s"
    )


def create_cardholder(acct_id: str, suffix: str) -> str:
    cardholder = _request(
        "POST",
        "/v1/issuing/cardholders",
        account=acct_id,
        version=ISSUING_STRIPE_VERSION,
        name="Jenny Rosen",
        **{"email": "jenny.rosen@example.com", "phone_number": "+18888675309"},
        status="active",
        type="individual",
        **{
            "individual[first_name]": "Jenny",
            "individual[last_name]": "Rosen",
            "individual[dob][day]": 1,
            "individual[dob][month]": 11,
            "individual[dob][year]": 1981,
            "billing[address][line1]": TEST_ADDRESS["line1"],
            "billing[address][city]": TEST_ADDRESS["city"],
            "billing[address][state]": TEST_ADDRESS["state"],
            "billing[address][postal_code]": TEST_ADDRESS["postal_code"],
            "billing[address][country]": TEST_ADDRESS["country"],
        },
    )

    # Accepte, pour ce cardholder, tous les accords dont l'url est renseignée
    # (donc applicables à son programme) - même logique que pour le compte :
    # on lit ce que Stripe demande plutôt que de coder en dur "cross_river".
    now_ts = int(time.time())
    data = {}
    for agreement, info in cardholder["individual"]["user_terms_acceptance"].items():
        if info.get("url"):
            data[f"individual[user_terms_acceptance][{agreement}][date]"] = now_ts
            data[f"individual[user_terms_acceptance][{agreement}][ip]"] = TEST_TOS_IP
    if data:
        _request(
            "POST",
            f"/v1/issuing/cardholders/{cardholder['id']}",
            account=acct_id,
            version=ISSUING_STRIPE_VERSION,
            **data,
        )

    return cardholder["id"]


def create_virtual_card(acct_id: str, cardholder_id: str) -> str:
    card = _request(
        "POST",
        "/v1/issuing/cards",
        account=acct_id,
        version=ISSUING_STRIPE_VERSION,
        cardholder=cardholder_id,
        currency="usd",
        type="virtual",
        status="active",
    )
    # On ne journalise jamais le numéro complet / le CVC : la création d'une
    # carte ne les renvoie pas par défaut (il faudrait un expand + une clé
    # restreinte PCI dédiée, jamais demandé ici).
    return card["id"]


def fund_issuing_balance_pull(acct_id: str, amount_cents: int, timeout_s: int = 90) -> None:
    """Financement du solde Issuing du COMPTE CONNECTÉ (pas celui de la
    plateforme) : chaque marchand finance ses propres cartes depuis son
    propre compte bancaire externe. En sandbox US, le test helper direct
    (/test_helpers/issuing/fund_balance) est verrouillé par la bêta privée
    "push funding US" (confirmé par erreur API le 2026-11-06) - on utilise
    donc la méthode pull générale (token -> source ach_debit -> vérif par
    micro-dépôts de test -> topup avec destination_balance=issuing)."""
    token = _request(
        "POST",
        "/v1/tokens",
        account=acct_id,
        **{
            "bank_account[country]": "US",
            "bank_account[currency]": "usd",
            "bank_account[account_holder_name]": "Jenny Rosen",
            "bank_account[account_holder_type]": "individual",
            "bank_account[routing_number]": TEST_BANK_ROUTING_NUMBER,
            "bank_account[account_number]": TEST_BANK_ACCOUNT_NUMBER,
        },
    )
    source = _request(
        "POST",
        "/v1/sources",
        account=acct_id,
        type="ach_debit",
        currency="usd",
        token=token["id"],
        **{
            "owner[address][line1]": TEST_ADDRESS["line1"],
            "owner[address][city]": TEST_ADDRESS["city"],
            "owner[address][state]": "California",
            "owner[address][country]": TEST_ADDRESS["country"],
            "owner[email]": "jenny.rosen@example.com",
            "owner[name]": "Jenny Rosen",
            "owner[phone]": "5554443333",
        },
    )
    _request(
        "POST",
        f"/v1/sources/{source['id']}/verify",
        account=acct_id,
        **{f"values[{i}]": v for i, v in enumerate(TEST_MICRODEPOSIT_VALUES)},
    )
    topup = _request(
        "POST",
        "/v1/topups",
        account=acct_id,
        amount=amount_cents,
        currency="usd",
        description="Issuing test flow - financement sandbox",
        destination_balance="issuing",
        statement_descriptor="XepayTest",
        source=source["id"],
    )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        current = _request("GET", f"/v1/topups/{topup['id']}", account=acct_id)
        if current["status"] == "succeeded":
            return
        if current["status"] == "failed":
            raise RuntimeError(f"Topup échoué : {current.get('failure_message')}")
        time.sleep(5)
    raise RuntimeError(
        f"Topup {topup['id']} toujours en statut 'pending' après {timeout_s}s "
        "(peut nécessiter plus de temps en sandbox)"
    )


def get_issuing_balance(acct_id: str) -> int:
    balance = _request("GET", "/v1/balance", account=acct_id)
    for entry in balance.get("issuing", {}).get("available", []):
        if entry["currency"] == "usd":
            return entry["amount"]
    return 0


def simulate_authorization_and_capture(acct_id: str, card_id: str, amount_cents: int) -> str:
    auth = _request(
        "POST",
        "/v1/test_helpers/issuing/authorizations",
        account=acct_id,
        card=card_id,
        amount=amount_cents,
        authorization_method="online",
        **{
            "merchant_data[category]": "eating_places_restaurants",
            "merchant_data[name]": "Issuing Test Flow Resto",
        },
    )
    if not auth["approved"]:
        raise RuntimeError(f"Autorisation inattendue refusée : {auth}")

    _request(
        "POST",
        f"/v1/test_helpers/issuing/authorizations/{auth['id']}/capture",
        account=acct_id,
    )
    return auth["id"]


def simulate_decline_insufficient_funds(acct_id: str, card_id: str, amount_cents: int) -> str:
    auth = _request(
        "POST",
        "/v1/test_helpers/issuing/authorizations",
        account=acct_id,
        card=card_id,
        amount=amount_cents,
        authorization_method="online",
        **{
            "merchant_data[category]": "eating_places_restaurants",
            "merchant_data[name]": "Issuing Test Flow Resto Trop Cher",
        },
    )
    return auth["request_history"][0]["reason"]


def simulate_decline_blocked_category(acct_id: str, card_id: str) -> str:
    _request(
        "POST",
        f"/v1/issuing/cards/{card_id}",
        account=acct_id,
        **{"spending_controls[blocked_categories][0]": "betting_casino_gambling"},
    )
    auth = _request(
        "POST",
        "/v1/test_helpers/issuing/authorizations",
        account=acct_id,
        card=card_id,
        amount=1000,
        authorization_method="online",
        **{
            "merchant_data[category]": "betting_casino_gambling",
            "merchant_data[name]": "Issuing Test Flow Casino Interdit",
        },
    )
    return auth["request_history"][0]["reason"]


def main():
    suffix = str(int(time.time()))
    print(f"[1/9] Recherche du programme Issuing plateforme par défaut...")
    program = list_default_platform_program()
    print(f"      -> {program['id']} ({program['brand']}, {program['capability']})")

    print("[2/9] Création du compte connecté (dashboard=none)...")
    acct_id = create_connected_account(suffix)
    print(f"      -> {acct_id}")

    print("[3/9] Remplissage KYC de test (business, representative/owner, banque)...")
    fill_kyc_test_data(acct_id, suffix)

    print("[4/9] Création du programme Issuing sur le compte (demande la capacité)...")
    account_program_id = create_program_on_account(acct_id, program["id"])
    print(f"      -> {account_program_id} (capacité associée : {program['capability']})")

    print("[5/9] Acceptation des ToS Issuing niveau compte (valeurs TEST ONLY)...")
    accept_account_level_issuing_tos(acct_id, program["capability"])
    wait_for_capability_active(acct_id, program["capability"])
    print("      -> capacité active")

    print("[6/9] Création du cardholder (+ ToS cardholder, valeurs TEST ONLY)...")
    cardholder_id = create_cardholder(acct_id, suffix)
    print(f"      -> {cardholder_id}")

    print("[7/9] Création de la carte virtuelle...")
    card_id = create_virtual_card(acct_id, cardholder_id)
    print(f"      -> {card_id} (numéro complet et CVC jamais récupérés/journalisés)")

    print("[8/9] Financement du solde Issuing du compte connecté (pull funding, 100 USD)...")
    fund_issuing_balance_pull(acct_id, amount_cents=10_000)
    print(f"      -> solde disponible : {get_issuing_balance(acct_id) / 100:.2f} USD")

    print("[9/9] Simulation : autorisation + capture, puis 2 refus...")
    auth_id = simulate_authorization_and_capture(acct_id, card_id, amount_cents=2_000)
    print(f"      -> autorisée + capturée : {auth_id}")
    print(f"      -> solde restant : {get_issuing_balance(acct_id) / 100:.2f} USD")

    reason_balance = simulate_decline_insufficient_funds(acct_id, card_id, amount_cents=999_999)
    print(f"      -> refus (montant excessif) : {reason_balance}")

    reason_category = simulate_decline_blocked_category(acct_id, card_id)
    print(f"      -> refus (catégorie bloquée) : {reason_category}")

    print("\nTerminé. Rien n'a été supprimé : compte, cardholder et carte restent")
    print(f"consultables dans le Dashboard test sous {acct_id}.")


if __name__ == "__main__":
    main()
