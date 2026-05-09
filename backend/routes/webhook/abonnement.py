from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from backend.database import SessionLocal
from backend.models import Payment, Link, Wallet
from backend.services.wallet_service import create_wallet_transaction
from datetime import datetime, timezone
from sqlalchemy import text
from backend.models import UserDB

router = APIRouter()

STRIPE_WEBHOOK_SECRET_SUBSCRIPTION = os.getenv("STRIPE_WEBHOOK_SECRET_SUBSCRIPTION")
print("🔥 MIDDLEWARE TRIGGERED")

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="stripe-signature")):
    print("🔥 MIDDLEWARE TRIGGERED")
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET_SUBSCRIPTION
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    print("🔥 EVENT:", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        if session.mode != "subscription":
            return {"status": "ignored"}

        subscription_id = session.subscription

        subscription = stripe.Subscription.retrieve(subscription_id)

        user_id = subscription["metadata"]["user_id"]
        plan = subscription["metadata"]["plan"]

        print("USER:", user_id)
        print("PLAN:", plan)

        db = SessionLocal()

        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        if user:
            user.plan = plan
            db.commit()
            print("✅ PLAN UPDATED")

        db.close()

    return {"status": "ok"}

