"""Vérification live (mode test) des fonctions Treasury de la phase 2 -
contre le compte et le compte financier DÉJÀ existants (créés avant ce
chantier), jamais de création d'un second compte financier ici. Lecture
+ deux actions volontaires (activer card_issuing, financer de test) sur
des objets déjà en bac à sable - voir conversation du 2026-11-11.

Usage :
    python3 -m backend.scripts.test_treasury_phase2 <account_id> <financial_account_id>
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# TREASURY_ENABLED est lu une seule fois à l'import de
# stripe_treasury_service - on le force donc AVANT cet import, pour ce
# process de test uniquement (jamais persisté dans .env par ce script).
os.environ["TREASURY_ENABLED"] = "true"

import stripe  # noqa: E402

from backend.services import stripe_treasury_service as svc  # noqa: E402


def _print_balance(label: str, financial_account: dict) -> None:
    cash = (financial_account.get("balance") or {}).get("cash") or {}
    print(f"Solde Treasury {label} : {cash}")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m backend.scripts.test_treasury_phase2 <account_id> <financial_account_id>")
        sys.exit(1)
    account_id, fa_id = sys.argv[1], sys.argv[2]

    if not svc.is_treasury_available():
        print("is_treasury_available() = False - clé non-test ou TREASURY_ENABLED coupé, abandon.")
        sys.exit(1)
    print("is_treasury_available() = True")

    print(f"\n--- Capacité treasury sur {account_id} ---")
    capability = svc.get_treasury_capability_status(account_id)
    print(f"status       : {capability.get('status')}")
    print(f"requirements : {capability.get('requirements')}")

    print(f"\n--- Compte financier {fa_id} (avant) ---")
    fa = svc.get_financial_account(account_id, fa_id)
    print(f"status             : {fa.get('status')}")
    print(f"active_features    : {fa.get('active_features')}")
    print(f"pending_features   : {fa.get('pending_features')}")
    print(f"restricted_features: {fa.get('restricted_features')}")
    print(f"financial_addresses: {fa.get('financial_addresses')}")
    _print_balance("AVANT", fa)

    print("\n--- Features (sous-ressource dédiée) ---")
    features = svc.get_financial_account_features(account_id, fa_id)
    print(features)

    print("\n--- Activation de card_issuing ---")
    updated_features = svc.update_financial_account_features(
        account_id, fa_id, {"card_issuing": {"requested": True}}
    )
    print(updated_features.get("card_issuing"))

    fa = svc.get_financial_account(account_id, fa_id)
    print(f"active_features (apres)    : {fa.get('active_features')}")
    print(f"pending_features (apres)   : {fa.get('pending_features')}")
    print(f"restricted_features (apres): {fa.get('restricted_features')}")

    print("\n--- Financement de test (50.00 USD) ---")
    import uuid
    received_credit = svc.simulate_received_credit(
        account_id, fa_id, amount_cents=5000, idempotency_key=f"test-phase2-{uuid.uuid4()}"
    )
    print(f"id={received_credit['id']} statut={received_credit.get('status')}")

    fa = svc.get_financial_account(account_id, fa_id)
    _print_balance("APRES", fa)


if __name__ == "__main__":
    try:
        main()
    except (stripe.error.StripeError, RuntimeError) as e:
        print(f"ERREUR Stripe (message exact) : {e}", file=sys.stderr)
        sys.exit(1)
