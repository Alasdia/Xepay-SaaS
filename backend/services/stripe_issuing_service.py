"""Stripe Issuing pour Connect - compte DÉDIÉ par marchand, distinct du
compte Express (profile.stripe_account_id, paiements/payouts - voir
routes/payout.py, services/stripe_service.py).

Pourquoi deux comptes Stripe Connect par marchand : Issuing n'est pas
compatible avec un compte à dashboard Stripe-hosted (Express). Il faut un
compte "dashboard: none" où Xepay porte la collecte des requirements et
la responsabilité des pertes (voir Account v2, controller/defaults
ci-dessous) - voir docs.stripe.com/issuing/connect. Validé manuellement
en sandbox le 2026-11-06 (voir backend/scripts/issuing_test_flow.py) :
le compte Express historique (ex. acct_1UUb0D20ZDX6kBdN, "Winner") refuse
purement et simplement la capacité `card_issuing`.

Point non-évident qui a pris du temps à isoler (voir script de test pour
le détail complet) : créer le programme Issuing sur le compte connecté
(ensure_issuing_program) demande la capacité `card_issuing_*` en
coulisses, mais Stripe NE L'EXPOSE PAS dans `account.capabilities` (v1)
ni dans `configuration.card_creator` (v2, jamais accessible sur aucune
version d'API testée) - il faut interroger explicitement
`/v1/accounts/{id}/capabilities/{capability}` pour voir son statut et ses
requirements (voir get_issuing_capability_status).

Ce module ne touche jamais la base (pas de db.commit/db.add) - c'est aux
routes appelantes (routes/users.py, routes/issuing.py) de persister les
IDs retournés sur Profile, comme pour services/verto_service.py."""

import os
import requests
import stripe
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

API_BASE = "https://api.stripe.com"
# Flag bêta confirmé fonctionnel le 2026-11-06 pour les comptes v2, les
# programmes Issuing et les capacités - pas de doc publique au-delà de
# l'exemple GB (commercial.stripe.charge_card), ce header a été trouvé
# par essais successifs, voir conversation du 2026-11-06.
ISSUING_STRIPE_VERSION = "2026-10-28.preview; issuing_program_beta=v2"


def _api_key() -> str:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY manquant dans l'environnement")
    return key


def _request(method: str, path: str, account: str | None = None, api_version: str = "v1", **data) -> dict:
    headers = {"Stripe-Version": ISSUING_STRIPE_VERSION}
    if account:
        headers["Stripe-Account"] = account

    url = f"{API_BASE}{path}"
    if api_version == "v2":
        headers["Authorization"] = f"Bearer {_api_key()}"
        resp = requests.request(method, url, headers=headers, json=data, timeout=30)
    else:
        resp = requests.request(
            method, url, headers=headers, auth=(_api_key(), ""), data=data or None, timeout=30
        )

    body = resp.json()
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {resp.status_code} : {body.get('error', body)}")
    return body


def get_default_platform_program() -> dict:
    """Le programme Issuing (banque partenaire + réseau) que Stripe a
    configuré pour la plateforme Xepay (acct_1ULZVC0I86XW25Ir) - un seul
    programme par défaut actuellement (Mastercard / Cross River Bank)."""
    resp = _request("GET", "/v1/issuing/programs")
    for program in resp["data"]:
        if program.get("is_default"):
            return program
    raise RuntimeError(
        "Aucun programme Issuing par défaut sur la plateforme - "
        "Platform Issuing doit être configuré côté Stripe avant intégration."
    )


def create_issuing_account(contact_email: str, display_name: str) -> str:
    """Crée le compte Connect dédié Issuing (dashboard: none). Xepay porte
    les frais et les pertes (losses_collector/fees_collector: application),
    comme c'est déjà le cas pour les paiements du compte Express - voir
    controller.losses sur les comptes existants (confirmé le 2026-11-05)."""
    body = _request(
        "POST",
        "/v2/core/accounts",
        api_version="v2",
        include=["configuration.recipient"],
        contact_email=contact_email,
        display_name=display_name,
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


def ensure_issuing_program(account_id: str) -> dict:
    """Idempotent : renvoie le programme déjà présent sur le compte s'il y
    en a un, sinon en crée un à partir du programme plateforme par défaut.
    Appelable plusieurs fois sans effet de bord (même logique que le
    `if not profile.stripe_account_id` de /onboarding)."""
    existing = _request("GET", "/v1/issuing/programs", account=account_id)
    for program in existing["data"]:
        if program.get("is_default"):
            return program

    platform_program = get_default_platform_program()
    return _request(
        "POST",
        "/v1/issuing/programs",
        account=account_id,
        platform_program=platform_program["id"],
        is_default="true",
    )


def get_issuing_capability_status(account_id: str, capability: str) -> dict:
    """Statut réel de la capacité Issuing du compte : 'active' seulement
    une fois le KYC ET les ToS Issuing acceptés par le marchand (via le
    lien d'onboarding hébergé Stripe, jamais fabriqués côté backend - voir
    create_onboarding_link). Les clés utiles : status, requirements.
    currently_due/past_due (ce qu'il reste à fournir)."""
    return _request("GET", f"/v1/accounts/{account_id}/capabilities/{capability}")


def create_onboarding_link(account_id: str, refresh_url: str, return_url: str) -> str:
    """Lien d'onboarding hébergé Stripe (même mécanisme que /onboarding
    pour le compte Express) : collecte le KYC ET fait accepter au marchand
    les conditions Issuing lui-même - Xepay ne doit jamais soumettre de ToS
    (ip/date) à la place du marchand (seul cas légitime : les valeurs de
    test du script backend/scripts/issuing_test_flow.py, jamais en prod)."""
    account_link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return account_link.url


def create_issuing_bank_source(
    account_id: str, account_number: str, routing_number: str, account_holder_name: str
) -> dict:
    """Crée la source ach_debit qui alimentera le solde Issuing, à partir
    des coordonnées DÉJÀ connues du wallet USD Verto du marchand
    (verto_usd_account_number/verto_usd_bank_code sur Profile) - jamais
    saisies manuellement, jamais un compte bancaire US générique. Source
    créée en statut 'pending' : la vérification par micro-dépôts se fait
    ensuite via le webhook Verto (voir routes/webhook/verto.py), jamais
    par le marchand lui-même (son wallet Verto n'expose pas de relevé)."""
    token = stripe.Token.create(
        bank_account={
            "country": "US",
            "currency": "usd",
            "account_holder_name": account_holder_name,
            "account_holder_type": "company",
            "routing_number": routing_number,
            "account_number": account_number,
        },
        stripe_account=account_id,
    )
    source = stripe.Source.create(
        type="ach_debit",
        currency="usd",
        token=token.id,
        owner={"name": account_holder_name},
        stripe_account=account_id,
    )
    return source.to_dict()


def verify_issuing_bank_source(account_id: str, source_id: str, amounts: list[int]) -> dict:
    """amounts : les deux micro-dépôts, en CENTS (ex: [32, 45]) - lus
    automatiquement depuis les webhooks Verto, jamais saisis par le
    marchand."""
    source = stripe.Source.verify(source_id, values=amounts, stripe_account=account_id)
    return source.to_dict()


def topup_issuing_balance(account_id: str, source_id: str, amount_cents: int) -> dict:
    """Prélève amount_cents depuis la source ach_debit déjà vérifiée
    (wallet Verto du marchand) et l'ajoute au solde Issuing de ce compte -
    jamais le solde de la plateforme (voir conversation du 2026-11-06,
    règle "zéro custody")."""
    topup = stripe.Topup.create(
        amount=amount_cents,
        currency="usd",
        destination_balance="issuing",
        source=source_id,
        stripe_account=account_id,
    )
    return topup.to_dict()
