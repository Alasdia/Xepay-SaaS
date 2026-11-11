"""Recharge le solde Issuing (TEST UNIQUEMENT) d'un compte Connect
EXISTANT, via pull funding - jeton bancaire de test -> source ach_debit ->
micro-dépôts de test -> topup destination_balance=issuing. Voir
docs.stripe.com/issuing/connect/funding, section "Pull funding".

Stripe Support a activé Platform Issuing mais refuse l'API Balance
Transfer (bêta) pour Xepay : impossible de financer le solde Issuing
depuis le solde Paiements du compte connecté. Ce script suit donc le
contournement documenté par Stripe lui-même (micro-dépôts de test, jamais
un vrai virement).

Sécurité : refuse de s'exécuter si la clé n'est pas sk_test_ (jamais codée
en dur, jamais logguée). Le compte cible est un argument OBLIGATOIRE,
jamais une valeur par défaut ni une boucle sur plusieurs comptes - ce
script ne touche jamais un autre compte que celui passé en CLI.

Usage :
    python3 -m backend.scripts.fund_issuing_balance <account_id> <amount_usd>
"""

import os
import sys
import time

import stripe
from dotenv import load_dotenv

load_dotenv()

from backend.services import stripe_issuing_service as svc

# Valeurs de test PUBLIQUES documentées par Stripe (docs.stripe.com/
# connect/testing#bank-accounts et #ach-micro-deposits) - jamais des
# secrets, jamais les coordonnées d'un vrai compte bancaire.
TEST_BANK_ROUTING_NUMBER = "110000000"
TEST_BANK_ACCOUNT_NUMBER = "000123456789"
TEST_MICRODEPOSIT_VALUES = [32, 45]

TOPUP_POLL_INTERVAL_S = 5
TOPUP_POLL_TIMEOUT_S = 90


def _require_test_key() -> None:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY manquant dans l'environnement")
    if not key.startswith("sk_test_"):
        raise RuntimeError(
            "Clé non-test détectée (ce script refuse toute clé qui n'est "
            "pas sk_test_) - abandon avant le moindre appel Stripe. "
            "(la clé elle-même n'est jamais affichée)"
        )
    stripe.api_key = key


def _check_card_issuing_capability(account_id: str) -> None:
    account = stripe.Account.retrieve(account_id).to_dict()
    raw_capabilities = account.get("capabilities") or {}
    print(
        f"GET /v1/accounts/{account_id} -> capabilities.card_issuing = "
        f"{raw_capabilities.get('card_issuing')!r}"
    )

    # Point documenté dans stripe_issuing_service.py : ce champ top-level
    # n'expose PAS fiablement le statut Issuing réel (confirmé en sandbox
    # le 2026-11-06) - la source de vérité est l'endpoint de capacité dédié
    # ci-dessous, utilisé pour la décision d'arrêt.
    platform_program = svc.get_default_platform_program()
    capability_name = platform_program["capability"]
    status = svc.get_issuing_capability_status(account_id, capability_name)
    print(
        f"GET /v1/accounts/{account_id}/capabilities/{capability_name} -> "
        f"status = {status.get('status')!r}"
    )

    if status.get("status") != "active":
        missing = status.get("requirements", {}).get("currently_due") or status.get(
            "requirements", {}
        ).get("past_due", [])
        print(
            "ARRET : Issuing n'est pas actif sur ce compte "
            f"(statut: {status.get('status')!r}). Informations manquantes "
            f"ou en attente : {missing}"
        )
        sys.exit(1)

    print("Issuing est actif sur ce compte - poursuite de la recharge.")


def _print_balance(account_id: str, label: str) -> int:
    amount = svc.get_issuing_balance(account_id)
    print(f"Solde Issuing {label} : {amount / 100:.2f} USD ({amount} cents)")
    return amount


def _wait_for_topup(topup_id: str, account_id: str) -> dict:
    deadline = time.time() + TOPUP_POLL_TIMEOUT_S
    while True:
        topup = stripe.Topup.retrieve(topup_id, stripe_account=account_id).to_dict()
        if topup["status"] == "succeeded":
            return topup
        if topup["status"] == "failed":
            raise RuntimeError(
                f"Topup {topup_id} a échoué : "
                f"{topup.get('failure_message') or topup.get('failure_code')}"
            )
        if time.time() > deadline:
            raise RuntimeError(
                f"Topup {topup_id} toujours en attente après "
                f"{TOPUP_POLL_TIMEOUT_S}s (statut: {topup['status']!r})"
            )
        time.sleep(TOPUP_POLL_INTERVAL_S)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m backend.scripts.fund_issuing_balance <account_id> <amount_usd>")
        sys.exit(1)

    account_id, amount_usd_str = sys.argv[1], sys.argv[2]
    amount_cents = int(round(float(amount_usd_str) * 100))

    _require_test_key()

    print(f"Cible (et UNIQUEMENT ce compte) : {account_id}")
    _check_card_issuing_capability(account_id)

    balance_before = _print_balance(account_id, "AVANT recharge")

    source = svc.create_issuing_bank_source(
        account_id,
        account_number=TEST_BANK_ACCOUNT_NUMBER,
        routing_number=TEST_BANK_ROUTING_NUMBER,
        account_holder_name="Xepay Issuing Test",
    )
    print(f"Source ach_debit créée : {source['id']} (statut initial: {source['status']})")

    svc.verify_issuing_bank_source(account_id, source["id"], TEST_MICRODEPOSIT_VALUES)
    print("Source vérifiée via les micro-dépôts de test Stripe.")

    topup = svc.topup_issuing_balance(account_id, source["id"], amount_cents)
    print(f"Topup créé : {topup['id']} (statut initial: {topup['status']})")

    topup = _wait_for_topup(topup["id"], account_id)
    print(f"Topup {topup['id']} -> statut final : {topup['status']}")

    balance_after = _print_balance(account_id, "APRES recharge")

    print(f"Différence : {(balance_after - balance_before) / 100:.2f} USD")


if __name__ == "__main__":
    try:
        main()
    except (stripe.error.StripeError, RuntimeError) as e:
        print(f"ERREUR Stripe (message exact) : {e}", file=sys.stderr)
        sys.exit(1)
