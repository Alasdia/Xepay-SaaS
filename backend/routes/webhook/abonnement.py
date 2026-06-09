from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from datetime import timedelta
from backend.database import SessionLocal
from backend.models import Payment, Link, Wallet
from backend.services.wallet_service import create_wallet_transaction
from backend.services.email_service import send_subscription_email
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

        invoice_id = subscription["latest_invoice"]
        invoice = stripe.Invoice.retrieve(invoice_id)
        invoice_pdf = invoice["invoice_pdf"]
        hosted_invoice_url = invoice["hosted_invoice_url"]

        user_id = subscription["metadata"]["user_id"]
        plan = subscription["metadata"]["plan"]

        print("USER:", user_id)
        print("PLAN:", plan)

        db = SessionLocal()

        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        if user:
            now = datetime.now(timezone.utc)

            user.plan = plan
            user.plan_started_at = now
            user.plan_expires_at = now + timedelta(days=30)

            db.commit()

            send_subscription_email(
                user.email,
                plan,
                invoice_pdf,
                hosted_invoice_url
            )
            print("✅ PLAN UPDATED")

        db.close()

    return {"status": "ok"}

