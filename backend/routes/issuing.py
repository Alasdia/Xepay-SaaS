import os
import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Profile, WorkspaceUser
from backend.middleware.authorization import require_manager

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()

@router.post("/issuing/create-virtual-card")
def create_virtual_card(
    cardholder_data: dict, 
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager)
):
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(400, "Compte Stripe non connecté")
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
            "stripe_account": profile.stripe_account_id,
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
            stripe_account=profile.stripe_account_id,
        )       
        return {
            "success": True,
            "cardholder_id": cardholder.id,
            "card_id": card.id,
            "currency": card.currency,
            "status": card.status
        }
        
    except stripe.error.StripeError as e:
        print("🔥 STRIPE ISSUING ERROR 🔥")
        print("type:", type(e).__name__)
        print("user_message:", e.user_message)
        print("message:", str(e))
        print("code:", getattr(e, "code", None))
        print("param:", getattr(e, "param", None))
        print("decline_code:", getattr(e, "decline_code", None))
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)}")
