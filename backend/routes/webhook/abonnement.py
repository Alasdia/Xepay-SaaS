from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from datetime import datetime, timezone, timedelta
from backend.database import SessionLocal
from backend.models import UserDB
from backend.services.email_service import ( 
    send_subscription_email,
    send_subscription_updated_email,
    send_subscription_canceled_email,
    send_payment_failed_subscription_email
)

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
        if event_type == "checkout.session.completed":
            session = event["data"]["object"].to_dict()

            if session.get("mode") == "subscription":
                subscription_id = session.get("subscription")

                if not subscription_id:
                    print("❌ ERREUR: Aucun subscription_id dans la session Checkout")
                    return {"status": "error", "message": "Missing subscription ID"}

                subscription_obj = stripe.Subscription.retrieve(subscription_id)
                subscription = subscription_obj.to_dict()

                invoice_id = subscription.get("latest_invoice")
                invoice_pdf = None
                hosted_invoice_url = None
                if invoice_id:
                    invoice_obj = stripe.Invoice.retrieve(invoice_id)
                    invoice = invoice_obj.to_dict()
                    invoice_pdf = invoice.get("invoice_pdf")
                    hosted_invoice_url = invoice.get("hosted_invoice_url")

                session_meta = session.get("metadata") or {}
                sub_meta = subscription.get("metadata") or {}

                user_id = session_meta.get("user_id") or sub_meta.get("user_id")
                plan = session_meta.get("plan") or sub_meta.get("plan", "pro")

                if not user_id:
                    print("❌ ERREUR: user_id introuvable dans les metadata")
                    return {"status": "error", "message": "Missing user_id"}

                user = db.query(UserDB).filter(UserDB.id == user_id).first()

                if user:
                    period_end_timestamp = subscription.get("current_period_end")
                    if period_end_timestamp:
                        current_period_end = datetime.fromtimestamp(
                            period_end_timestamp, 
                            tz=timezone.utc
                        )
                    else:
                        current_period_end = datetime.now(timezone.utc) + timedelta(days=30)

                    user.plan = plan
                    user.plan_started_at = datetime.now(timezone.utc)
                    user.plan_expires_at = current_period_end
                    user.stripe_customer_id = session.get("customer")
                    user.stripe_subscription_id = subscription_id
                    user.subscription_status = subscription.get("status", "active")
                    user.cancel_at_period_end = subscription.get("cancel_at_period_end", False)
                    db.commit()

                    if user.email:
                        send_subscription_email(
                            user.email,
                            plan,
                            invoice_pdf,
                            hosted_invoice_url
                        )
                    print(f"✅ PREMIER ACHAT ACTIVÉ POUR {user_id}")

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"].to_dict()
            sub_meta = subscription.get("metadata") or {}
            
            user_id = sub_meta.get("user_id")
            stripe_sub_id = subscription.get("id")
            customer_id = subscription.get("customer")

            user = None
            if user_id:
                user = db.query(UserDB).filter(UserDB.id == user_id).first()
            if not user and stripe_sub_id:
                user = db.query(UserDB).filter(UserDB.stripe_subscription_id == stripe_sub_id).first()

            if user:
                plan = sub_meta.get("plan", user.plan)
                status = subscription.get("status")

                user.plan = plan
                user.subscription_status = status
                user.cancel_at_period_end = subscription.get("cancel_at_period_end", False)

                if subscription.get("status") == "active":
                    raw_period_end = subscription.get("current_period_end")
                    if raw_period_end:
                        current_period_end = datetime.fromtimestamp(
                            raw_period_end,
                            tz=timezone.utc
                        )
                        user.plan_expires_at = current_period_end
                        print(f"✅ ABONNEMENT PROLONGÉ JUSQU'À {current_period_end}")

                db.commit()
                if user and user.email:
                    send_subscription_updated_email(user.email, plan, status)

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"].to_dict()
            sub_meta = subscription.get("metadata") or {}
            user_id = sub_meta.get("user_id")

            user = db.query(UserDB).filter(UserDB.id == user_id).first() if user_id else None

            if user:
                user.plan = "free"
                user.subscription_status = "canceled"
                user.stripe_subscription_id = None
                db.commit()
                print("⚠️ ABONNEMENT RÉSILIÉ -> RETOUR AU PLAN FREE")
                if user and user.email:
                    send_subscription_canceled_email(user.email, plan, status)
                
        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"].to_dict()
            customer_id = invoice.get("customer")
            customer_email = invoice.get("customer_email")

            user = db.query(UserDB).filter(UserDB.stripe_customer_id == customer_id).first() if customer_id else None
    
            if user:
                user.subscription_status = "past_due"
                db.commit()
                print(f"❌ ÉCHEC DE PRÉLÈVEMENT POUR {customer_email} -> Statut passé à past_due")
                target_email = customer_email or user.email
                if target_email:
                    send_payment_failed_subscription_email(target_email)
                
    except Exception as e:
        db.rollback()
        print(f"❌ ERREUR WEBHOOK: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne webhook")
    finally:
        db.close()

    return {"status": "ok"}