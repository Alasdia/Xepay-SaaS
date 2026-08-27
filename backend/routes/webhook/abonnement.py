from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from datetime import timedelta, datetime, timezone
from backend.database import SessionLocal
from backend.models import UserDB
from backend.services.email_service import send_subscription_email

router = APIRouter()

STRIPE_WEBHOOK_SECRET_SUBSCRIPTION = os.getenv("STRIPE_WEBHOOK_SECRET_SUBSCRIPTION")

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="stripe-signature")):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET_SUBSCRIPTION
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event["type"]
    print("🔥 EVENT SUBSCRIPTION:", event_type)

    db = SessionLocal()

    try:
        # 1. Premier achat via Stripe Checkout
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]

            if session.mode == "subscription":
                subscription_id = session.subscription
                subscription = stripe.Subscription.retrieve(subscription_id)

                invoice_id = subscription["latest_invoice"]
                invoice = stripe.Invoice.retrieve(invoice_id)
                invoice_pdf = invoice["invoice_pdf"]
                hosted_invoice_url = invoice["hosted_invoice_url"]

                user_id = subscription["metadata"].get("user_id")
                plan = subscription["metadata"].get("plan", "pro")

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
                    print("✅ PREMIER ACHAT ACTIVÉ")

        # 2. Renouvellement ou changement de plan automatique
        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            user_id = subscription["metadata"].get("user_id")

            user = db.query(UserDB).filter(UserDB.id == user_id).first()

            if user:
                plan = subscription["metadata"].get("plan", user.plan)
                status = subscription["status"]

                if status == "active":
                    current_period_end = datetime.fromtimestamp(
                        subscription["current_period_end"], 
                        tz=timezone.utc
                    )
                    user.plan = plan
                    user.plan_expires_at = current_period_end
                    db.commit()
                    print(f"✅ ABONNEMENT PROLONGÉ JUSQU'À {current_period_end}")

        # 3. Résiliation (Ex: Fin de période ou annulation immédiate)
        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            user_id = subscription["metadata"].get("user_id")

            user = db.query(UserDB).filter(UserDB.id == user_id).first()

            if user:
                user.plan = "free"
                db.commit()
                print("⚠️ ABONNEMENT RÉSILIÉ -> RETOUR AU PLAN FREE")

        # 4. Échec de paiement de renouvellement (carte expirée, solde insuffisant)
        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            customer_email = invoice.get("customer_email")
            print(f"❌ ÉCHEC DE PRÉLÈVEMENT POUR {customer_email}")

    except Exception as e:
        db.rollback()
        print(f"❌ ERREUR WEBHOOK: {e}")
        db.close()
        raise HTTPException(status_code=500, detail="Erreur interne webhook")

    db.close()
    return {"status": "ok"}
