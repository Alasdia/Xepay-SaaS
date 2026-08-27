from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from datetime import datetime, timezone
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
            # Conversion explicite en dictionnaire
            session = event["data"]["object"].to_dict()

            if session.get("mode") == "subscription":
                subscription_id = session.get("subscription")
                subscription_obj = stripe.Subscription.retrieve(subscription_id)
                subscription = subscription_obj.to_dict()

                invoice_id = subscription.get("latest_invoice")
                invoice_obj = stripe.Invoice.retrieve(invoice_id)
                invoice = invoice_obj.to_dict()

                invoice_pdf = invoice.get("invoice_pdf")
                hosted_invoice_url = invoice.get("hosted_invoice_url")

                # Récupération sécurisée dans metadata
                session_meta = session.get("metadata") or {}
                sub_meta = subscription.get("metadata") or {}

                user_id = session_meta.get("user_id") or sub_meta.get("user_id")
                plan = session_meta.get("plan") or sub_meta.get("plan", "pro")

                print(f"ERREUR: Aucun 'user")

                user = db.query(UserDB).filter(UserDB.id == user_id).first()

                if user:
                    current_period_end = datetime.fromtimestamp(
                        subscription["current_period_end"], 
                        tz=timezone.utc
                    )
                    user.plan = plan
                    user.plan_started_at = datetime.now(timezone.utc)
                    user.plan_expires_at = current_period_end
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
            subscription = event["data"]["object"].to_dict()
            sub_meta = subscription.get("metadata") or {}
            
            user_id = sub_meta.get("user_id")
            user = db.query(UserDB).filter(UserDB.id == user_id).first() if user_id else None

            if user:
                plan = sub_meta.get("plan", user.plan)
                status = subscription.get("status")

                if status == "active":
                    current_period_end = datetime.fromtimestamp(
                        subscription["current_period_end"], 
                        tz=timezone.utc
                    )
                    user.plan = plan
                    user.plan_expires_at = current_period_end
                    db.commit()
                    print(f"✅ ABONNEMENT PROLONGÉ JUSQU'À {current_period_end}")

        # 3. Résiliation
        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"].to_dict()
            sub_meta = subscription.get("metadata") or {}
            user_id = sub_meta.get("user_id")

            user = db.query(UserDB).filter(UserDB.id == user_id).first() if user_id else None

            if user:
                user.plan = "free"
                db.commit()
                print("⚠️ ABONNEMENT RÉSILIÉ -> RETOUR AU PLAN FREE")

        # 4. Échec de paiement de renouvellement
        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"].to_dict()
            customer_email = invoice.get("customer_email")
            print(f"❌ ÉCHEC DE PRÉLÈVEMENT POUR {customer_email}")

    except Exception as e:
        db.rollback()
        print(f"❌ ERREUR WEBHOOK: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne webhook")
    finally:
        db.close()

    return {"status": "ok"}