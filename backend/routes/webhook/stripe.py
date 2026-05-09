from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile
import stripe  
import os

STRIPE_WEBHOOK_SECRET_CONNECT = os.getenv("STRIPE_WEBHOOK_SECRET_CONNECT")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter()


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        print("⚠️ No Stripe signature → ignored")
        return {"status": "ignored"}

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET_CONNECT
        )
    except ValueError:
        print("❌ Invalid payload")
        return {"status": "invalid_payload"}
    except stripe.error.SignatureVerificationError:
        print("❌ Invalid signature")
        return {"status": "invalid_signature"}

    event_type = event["type"]

    if event_type != "account.updated":
        print(f"⚠️ Ignored event: {event_type}")
        return {"status": "ignored"}

    account = event["data"]["object"]
    stripe_id = account["id"]

    account = stripe.Account.retrieve(stripe_id)

    profile = db.query(Profile).filter(
        Profile.stripe_account_id == stripe_id
    ).first()

    if profile:
        individual = getattr(account, "individual", None)

        first_name = ""
        last_name = ""
        phone = None

        if individual:
            first_name = getattr(individual, "first_name", "") or ""
            last_name = getattr(individual, "last_name", "") or ""
            phone = getattr(individual, "phone", None)

        profile.full_name = f"{first_name} {last_name}".strip()
        
        if phone:
            profile.phone = phone

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"❌ DB error: {e}")
            return {"status": "db_error"}
    return {"ok": True}