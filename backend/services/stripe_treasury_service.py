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

    financial_addresses[].aba.account_number : À CONFIRMER, ne rien
    supposer dans un sens ou l'autre (voir conversation du 2026-11-12 -
    une affirmation précédente ici, "jamais renvoyé en entier sur le
    v1", reposait sur un résumé de recherche web sans source citable et
    s'est révélée contredite par une page Stripe lue directement par
    l'utilisateur : docs.stripe.com/treasury/connect/legacy/v1/
    account-management/financial-account-features montre un exemple
    GET avec expand[]=financial_addresses.aba.account_number qui
    renvoie bien le numéro complet). Cet appel-ci ne passe PAS ce
    paramètre expand (comportement actuel inchangé, affichage last4
    côté UI) - à tester avec et sans dès que financial_addresses.aba
    sera actif sur un compte financier de test, avant de conclure."""
    account = _client().v1.treasury.financial_accounts.retrieve(
        financial_account_id,
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
            "description": "Xepay test Treasury",
        },
        options=options,
    )
    return received_credit.to_dict()
