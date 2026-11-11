"""Treasury for platforms (Financial Account) - prototype de test sur
acct_1UYofyP5Gfz5cr66 (voir conversation du 2026-11-11). Objectif actuel :
faire fonctionner tout le circuit en mode TEST ; la production n'est pas
une préoccupation pour l'instant - TREASURY_ENABLED exige donc une clé
sk_test_ en plus de l'interrupteur lui-même (contrairement à VERTO_ENABLED,
qui ne porte aucune condition sur le mode de la clé).

Les ressources Treasury (FinancialAccount, ses Features, les test
helpers ReceivedCredit) n'existent dans le SDK stripe-python installé
qu'en version "service" (StripeClient), jamais en classe statique comme
stripe.Topup/stripe.issuing.Card - confirmé en inspectant le SDK (voir
conversation). D'où l'usage de stripe.StripeClient(...) ici, alors que
stripe_issuing_service.py utilise le style stripe.XXX.create() classique.

Ce module ne fait jamais de db.commit/db.add (même règle que
stripe_issuing_service.py) - c'est aux routes appelantes de persister."""
import os

import stripe

# Même garde que stripe_issuing_service.py : posé explicitement ici
# plutôt que de compter sur un autre module importé plus tôt dans l'app
# pour le faire (cassant pour un script qui importe ce module isolément).
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

TREASURY_ENABLED = os.getenv("TREASURY_ENABLED", "false").lower() == "true"


def is_treasury_available() -> bool:
    """Les deux conditions sont requises : l'interrupteur ET une clé
    sk_test_ - jamais l'une sans l'autre tant que la prod n'est pas
    décidée (voir docstring du module)."""
    key = os.getenv("STRIPE_SECRET_KEY") or ""
    return TREASURY_ENABLED and key.startswith("sk_test_")


def _client() -> "stripe.StripeClient":
    return stripe.StripeClient(api_key=os.getenv("STRIPE_SECRET_KEY"))


def get_treasury_capability_status(account_id: str) -> dict:
    """Statut réel de la capacité treasury du compte - même usage que
    get_issuing_capability_status (stripe_issuing_service.py), mais via
    la méthode SDK dédiée (endpoint stable, pas besoin du header
    issuing_program_beta)."""
    capability = stripe.Account.retrieve_capability(account_id, "treasury")
    return capability.to_dict()


def request_treasury_capability(account_id: str) -> dict:
    """Demande la capacité - ne fait QUE ça, jamais de création de
    compte financier dans le même appel (étapes volontairement
    séparées, comme pour card_issuing/ensure_issuing_program)."""
    capability = stripe.Account.modify_capability(account_id, "treasury", requested=True)
    return capability.to_dict()


def create_financial_account(account_id: str, currency: str = "usd") -> dict:
    """Demande financial_addresses.aba ET card_issuing dans le même
    appel (ajustement du 2026-11-11) - la seule façon d'obtenir des
    coordonnées bancaires est financial_addresses.aba, prérequis
    constaté empiriquement pour même simuler un financement de test."""
    account = _client().v1.treasury.financial_accounts.create(
        params={
            "supported_currencies": [currency],
            "features": {
                "financial_addresses": {"aba": {"requested": True}},
                "card_issuing": {"requested": True},
            },
        },
        options={"stripe_account": account_id},
    )
    return account.to_dict()


def create_account_onboarding_session(account_id: str) -> str:
    """AccountSession pour le composant embarqué Connect "account-
    onboarding" (ConnectJS, stripeConnect.create("account-onboarding")) -
    confirmé dans la doc Stripe : ce composant gère nativement l'étape
    "treasury_and_card_issuing_terms_of_service" (acceptation des
    conditions Treasury/Issuing par LE MARCHAND, avec sa propre date/IP
    réelles - jamais un formulaire maison, jamais rempli par Xepay à sa
    place). Même style d'appel (legacy stripe.AccountSession.create) que
    create_account_session/create_connect_activity_session
    (webhook/stripe.py), pas le style StripeClient des autres fonctions
    de ce module - AccountSession existe en classe statique dans ce SDK."""
    session = stripe.AccountSession.create(
        account=account_id,
        components={"account_onboarding": {"enabled": True}},
    )
    return session.client_secret


def get_financial_account(account_id: str, financial_account_id: str) -> dict:
    """Solde, coordonnées (financial_addresses) et les 3 tableaux de
    features (active/pending/restricted) - tous vivent sur l'objet
    FinancialAccount lui-même, pas sur la sous-ressource /features
    (vérifié dans la doc Stripe, voir conversation).

    financial_addresses[].aba.account_number : CONFIRMÉ en direct le
    2026-11-12 sur fa_1UaglcP5Gfz5cr665qoV9O4G, une fois financial_
    addresses.aba passé actif - sans expand, seul account_number_last4
    est renvoyé ; avec expand=["financial_addresses.aba.account_number"],
    le numéro complet est bien présent en plus du last4 (conforme à
    docs.stripe.com/treasury/connect/legacy/v1/account-management/
    financial-account-features). Une affirmation précédente ici
    ("jamais renvoyé en entier sur le v1") reposait sur un résumé de
    recherche web sans source citable et était fausse - corrigée."""
    account = _client().v1.treasury.financial_accounts.retrieve(
        financial_account_id,
        params={"expand": ["financial_addresses.aba.account_number"]},
        options={"stripe_account": account_id},
    )
    return account.to_dict()


def get_financial_account_features(account_id: str, financial_account_id: str) -> dict:
    features = _client().v1.treasury.financial_accounts.features.retrieve(
        financial_account_id,
        options={"stripe_account": account_id},
    )
    return features.to_dict()


def update_financial_account_features(account_id: str, financial_account_id: str, requested: dict) -> dict:
    """requested : dict déjà à la forme attendue par Stripe, ex.
    {"card_issuing": {"requested": True}} - jamais construit en dur ici,
    l'appelant décide précisément quelles fonctions demander (voir
    routes/treasury.py, qui ne demande que ce qui sert ce prototype)."""
    features = _client().v1.treasury.financial_accounts.features.update(
        financial_account_id,
        params=requested,
        options={"stripe_account": account_id},
    )
    return features.to_dict()


def simulate_received_credit(
    account_id: str,
    financial_account_id: str,
    amount_cents: int,
    currency: str = "usd",
    network: str = "ach",
    idempotency_key: str | None = None,
) -> dict:
    """Test uniquement - POST /v1/test_helpers/treasury/received_credits
    (documenté comme réservé au mode test : impossible de créer un
    ReceivedCredit initié par un tiers en mode live via cet endpoint).
    L'appelant doit avoir déjà vérifié is_treasury_available()."""
    options = {"stripe_account": account_id}
    if idempotency_key:
        options["idempotency_key"] = idempotency_key
    received_credit = _client().v1.test_helpers.treasury.received_credits.create(
        params={
            "amount": amount_cents,
            "currency": currency,
            "financial_account": financial_account_id,
            "network": network,
            # 10 caractères max pour le réseau ACH - confirmé en direct le
            # 2026-11-12 ("Description must be at most 10 characters long
            # for ACH transfers."), jamais documenté à l'avance, une
            # chaîne plus longue ("Xepay test Treasury") faisait échouer
            # CHAQUE financement de test.
            "description": "XepayTest",
        },
        options=options,
    )
    return received_credit.to_dict()


def list_cardholders(account_id: str) -> list[dict]:
    """Cardholders DÉJÀ existants sur ce compte Issuing (créés via le
    flux classique /issuing/create-virtual-card, routes/issuing.py) -
    jamais recréés ici : une carte financée par le compte financier
    (Phase 3) réutilise un cardholder existant, elle n'en crée jamais un
    nouveau (évite de dupliquer toute la logique de conformité/ToS déjà
    en place dans create_virtual_card). stripe.issuing.Card/Cardholder
    sont des classes statiques du SDK (pas StripeClient ici, contrairement
    au reste de ce module - mêmes ressources que stripe_issuing_service.py)."""
    cardholders = stripe.issuing.Cardholder.list(limit=50, stripe_account=account_id)
    return [
        {"id": c.id, "name": c.name, "email": c.email, "status": c.status}
        for c in cardholders.data
    ]


def create_card_funded_by_financial_account(
    account_id: str,
    financial_account_id: str,
    cardholder_id: str,
    currency: str,
    limit_amount_cents: int,
) -> dict:
    """Carte financée par le compte financier (financial_account=), par
    opposition au solde Issuing classique (create_virtual_card,
    routes/issuing.py - jamais modifiée pour cette fonctionnalité). Les
    deux types de cartes coexistent sur le même compte Connect : c'est le
    paramètre financial_account à la création qui fixe, pour toujours,
    quel solde une carte donnée utilise - rien ne les fait changer de
    solde après coup (voir docs.stripe.com/treasury/account-management/
    issuing-cards, confirmé dans la conversation)."""
    card = stripe.issuing.Card.create(
        cardholder=cardholder_id,
        financial_account=financial_account_id,
        currency=currency,
        type="virtual",
        spending_controls={
            "spending_limits": [{"amount": limit_amount_cents, "interval": "per_authorization"}]
        },
        stripe_account=account_id,
    )
    return card.to_dict()


def list_transactions(account_id: str, financial_account_id: str, limit: int = 20) -> list[dict]:
    """Historique des mouvements du compte financier (financement,
    OutboundTransfer, OutboundPayment, ...) - toujours relu en direct
    depuis Stripe (treasury.Transaction), jamais mis en cache côté
    Xepay, même règle que get_financial_account."""
    transactions = _client().v1.treasury.transactions.list(
        params={"financial_account": financial_account_id, "limit": limit},
        options={"stripe_account": account_id},
    )
    return [t.to_dict() for t in transactions.data]
