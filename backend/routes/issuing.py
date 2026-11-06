import os
import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Profile, WorkspaceUser
from backend.middleware.authorization import require_capability
from backend.services import stripe_issuing_service

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()


def _get_active_issuing_account(profile: Profile) -> str:
    """Compte Issuing DÉDIÉ (dashboard: none, voir stripe_issuing_service) -
    distinct de profile.stripe_account_id (Express, paiements/payouts) :
    Issuing n'est pas compatible avec un compte Express, confirmé en
    sandbox le 2026-11-05. Créé via POST /onboarding/issuing. Lève une
    HTTPException actionnable (pas l'erreur Stripe brute) si le compte
    n'est pas encore configuré ou pas encore actif."""
    if not profile or not profile.stripe_issuing_account_id or not profile.stripe_issuing_program_id:
        raise HTTPException(400, "Compte Stripe Issuing non configuré - voir /onboarding/issuing")

    try:
        platform_program = stripe_issuing_service.get_default_platform_program()
        capability = stripe_issuing_service.get_issuing_capability_status(
            profile.stripe_issuing_account_id, platform_program["capability"]
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Erreur Stripe Issuing (vérification du compte) : {e}")

    if capability.get("status") != "active":
        # Erreur Stripe brute ici ("missing requirements to be activated")
        # n'est pas actionnable pour le marchand - on renvoie plutôt ce
        # qu'il reste à fournir (rempli via le même lien d'onboarding que
        # /onboarding/issuing).
        missing = capability.get("requirements", {}).get("currently_due") or capability.get(
            "requirements", {}
        ).get("past_due", [])
        raise HTTPException(
            400,
            "Le compte Stripe Issuing n'est pas encore actif "
            f"(statut: {capability.get('status')}) - complétez l'onboarding "
            f"via /onboarding/issuing. Informations manquantes : {missing}",
        )

    return profile.stripe_issuing_account_id


@router.get("/issuing/cards")
def list_virtual_cards(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Cartes + cardholders du compte Issuing du marchand, et le solde
    Issuing disponible (sert de fonds aux cartes) - voir vue Commerce
    "Émission de carte" (section 1)."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    account_id = _get_active_issuing_account(profile)

    try:
        cards = stripe.issuing.Card.list(
            limit=50, expand=["data.cardholder"], stripe_account=account_id
        )
        balance = stripe.Balance.retrieve(stripe_account=account_id)
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)}")

    issuing_balance = next(
        (b.amount for b in balance.issuing.available if b.currency == "usd"), 0
    ) if getattr(balance, "issuing", None) else 0

    return {
        "balance_available": issuing_balance,
        "cards": [
            {
                "id": card.id,
                "brand": card.brand,
                "last4": card.last4,
                "exp_month": card.exp_month,
                "exp_year": card.exp_year,
                "currency": card.currency,
                "status": card.status,
                "type": card.type,
                "cardholder_name": card.cardholder.name if card.cardholder else None,
                "cardholder_email": card.cardholder.email if card.cardholder else None,
                "spending_limits": card.spending_controls.spending_limits if card.spending_controls else [],
            }
            for card in cards.data
        ],
    }


@router.get("/issuing/transactions")
def list_issuing_transactions(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Transactions Issuing (dépenses sur les cartes) du compte du
    marchand - alimente le tableau et le graphe de dépenses de la vue
    Commerce "Émission de carte" (sections 2 et 3)."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    account_id = _get_active_issuing_account(profile)

    try:
        transactions = stripe.issuing.Transaction.list(
            limit=100, expand=["data.card"], stripe_account=account_id
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)}")

    return {
        "transactions": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "currency": tx.currency,
                "type": tx.type,
                "created": tx.created,
                "merchant_name": tx.merchant_data.name if tx.merchant_data else None,
                "merchant_category": tx.merchant_data.category if tx.merchant_data else None,
                "card_last4": tx.card.last4 if tx.card else None,
            }
            for tx in transactions.data
        ],
    }


@router.post("/issuing/create-virtual-card")
def create_virtual_card(
    cardholder_data: dict,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    issuing_account_id = _get_active_issuing_account(profile)

    name = cardholder_data.get("name")
    if not name or not name.strip():
        raise HTTPException(400, "Le nom du porteur ou de la LLC est obligatoire.")
    holder_type = cardholder_data.get("type", "individual")
    card_currency = cardholder_data.get("currency", "usd").lower()
    try:
        cardholder_params = {
            "type": holder_type,
            "name": name.strip(),
            "email": cardholder_data.get("email"),
            "billing": {
                "address": {
                    "line1": cardholder_data.get("address_line1"),
                    "line2": cardholder_data.get("address_line2"),
                    "city": cardholder_data.get("city"),
                    "state": cardholder_data.get("state"),
                    "postal_code": cardholder_data.get("postal_code"),
                    "country": cardholder_data.get("country", "US"),
                }
            },
            "stripe_account": issuing_account_id,
        }
        if holder_type == "individual":
            cardholder_params["phone_number"] = cardholder_data.get("phone_number")
        cardholder = stripe.issuing.Cardholder.create(**cardholder_params)
        card = stripe.issuing.Card.create(
            cardholder=cardholder.id,
            currency=card_currency,
            type="virtual",
            spending_controls={
                "spending_limits": [{
                    "amount": int(cardholder_data.get("limit_amount", 50000)),
                    "interval": "per_authorization"
                }]
            },
            stripe_account=issuing_account_id,
        )
        return {
            "success": True,
            "cardholder_id": cardholder.id,
            "card_id": card.id,
            "currency": card.currency,
            "status": card.status
        }
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)}")
