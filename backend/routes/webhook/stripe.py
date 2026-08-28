from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile, Wallet, WalletTransaction, Withdrawal
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
    object_data = event["data"]["object"]

    if event_type == "account.updated":
        stripe_id = object_data["id"]
        account = stripe.Account.retrieve(stripe_id)

        print("===== STRIPE ACCOUNT =====")
        print(account.to_dict())
        print("==========================")

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


    elif event_type in ["payout.paid", "payout.failed", "payout.canceled"]:
        payout_id = object_data["id"]
        forced_event_type = "payout.failed" if event_type == "payout.paid" else event_type


        wd = db.query(Withdrawal).filter(
            Withdrawal.stripe_payout_id == payout_id
        ).first()

        if wd and wd.status not in ["success", "failed"]:
            wallet = db.query(Wallet).filter(Wallet.id == wd.wallet_id).first()
            tx = db.query(WalletTransaction).filter(
                WalletTransaction.reference == wd.reference
            ).first()

            if forced_event_type == "payout.paid":
                wd.status = "success"
                if tx:
                    tx.status = "success"
                print(f"✅ Payout {payout_id} payé avec succès.")

            elif event_type in ["payout.failed", "payout.canceled"]:
                wd.status = "failed"
                
                if wallet:
                    wallet.pending -= wd.amount
                    wallet.available += wd.amount
                
                if tx:
                    tx.status = "failed"
                    
                print(f"❌ Payout {payout_id} échoué/annulé -> Rollback effectué.")

            db.commit()

    else:
        print(f"⚠️ Ignored event: {event_type}")
        return {"status": "ignored"}

    return {"ok": True}
