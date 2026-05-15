from fastapi import APIRouter, Request, Header, HTTPException
import stripe
from sqlalchemy import text
from backend.database import SessionLocal
from backend.models import UserDB, Wallet
from backend.models import Payment, WalletTransaction, Link, Profile
from backend.models import Webhook, WebhookDeliveryLog
import traceback
import hmac
import hashlib
import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
import time
import os

router = APIRouter()

WEBHOOK_SECRET_PAYMENT = os.getenv("WEBHOOK_SECRET_PAYMENT") 

@router.post("/webhook/payment")
async def stripe_payment_webhook(request: Request, stripe_signature: str = Header(None, alias="stripe-signature")):
    print("🔥 FICHIER PAIEMENT CHARGÉ")
    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            WEBHOOK_SECRET_PAYMENT  # ⚠️ nouveau secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    print("🔥 PAYMENT EVENT:", event["type"])
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        if session.mode != "payment":
            return {"status": "ignored"}

        event_type = "payment.success"

        metadata = session.get("metadata") if isinstance(session, dict) else session["metadata"]

        user_id = metadata["user_id"]
        link_id = metadata["link_id"]

        if not user_id or not link_id:
            print("❌ METADATA MANQUANTE")
            return {"status": "ignored"}
        
        db = SessionLocal()

        # 🔥 montant réel après frais (Stripe + ta commission incluse)
        intent = stripe.PaymentIntent.retrieve(session.payment_intent)

        if not intent.latest_charge:
            return {"status": "waiting"}

        charge = stripe.Charge.retrieve(intent.latest_charge)
        
        balance_tx = None
        available_at = None

        for _ in range(5):
            charge = stripe.Charge.retrieve(intent.latest_charge)

            if charge.balance_transaction:
                balance_tx = stripe.BalanceTransaction.retrieve(charge.balance_transaction)
                amount_usd = balance_tx.amount / 100
                stripe_fee = balance_tx.fee / 100
                net_usd = balance_tx.net / 100 

                print("=== STRIPE DEBUG ===")
                print("AMOUNT USD:", amount_usd)
                print("STRIPE FEE:", stripe_fee)
                print("NET USD:", net_usd)

                available_on = balance_tx.available_on
                available_at = datetime.fromtimestamp(available_on, tz=timezone.utc)
                break

            time.sleep(1)

        if not balance_tx:
            return {"status": "waiting"}

        if not available_at:
            raise Exception("available_at not found")

        if not balance_tx:
            print("❌ balance_transaction pas prêt")
            return {"status": "waiting"}

        currency = session["currency"].upper()
        print(currency)

        row = None

        
        if currency == "XOF":
           amount_local = amount_usd
           rate_used = 1
        else:
            row = db.execute(text("""
                SELECT rate FROM exchange_rates
                WHERE from_currency = 'USD' AND to_currency = 'XOF'
            """)).fetchone()

            rate_used = row.rate if row else 600

            total_fee = amount_usd * 0.06
            commission = total_fee - stripe_fee

            # montant net marchand
            merchant_amount = amount_usd - total_fee
        
            print("=== BUSINESS DEBUG ===")
            print("TOTAL FEE (6%):", total_fee)
            print("COMMISSION:", commission)
            print("MERCHANT AMOUNT:", merchant_amount)

            amount_local = int(float(merchant_amount) * float(rate_used)) 

            print("=== CONVERSION ===")
            print("RATE:", rate_used)
            print("FINAL XOF:", amount_local)

            user = db.query(UserDB).filter(UserDB.id == user_id).first()

            if not user:
                return {"status": "error", "reason": "user_not_found"}

            if not user.wallet:
                return {"status": "error", "reason": "wallet_not_found"}
        
            
            # override propre
            amount_local = int(amount_local)

            
            print("RAW:", amount_local)
            print("WALLET RESIDUAL:", user.wallet.residual_xof)

        
        email_client = session.customer_details.email if session.customer_details else None

        existing_tx = db.query(WalletTransaction).filter(
            WalletTransaction.reference == f"pay_{session.id}"
        ).first()

        if existing_tx:
            print("⚠️ EVENT DEJA TRAITE")
            db.close()
            return {"status": "ignored"}
        
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        if user:
            if not user.wallet:
                print("❌ WALLET NOT FOUND")
                db.close()
                return {"status": "error"}
                

            now = datetime.now(timezone.utc)

            start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

            if now.month == 12:
                end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

            paid_count = (
              db.query(Payment.link_id)
                .join(Link, Payment.link_id == Link.id)
                .filter(Link.user_id == user.id)
                .filter(Payment.status.in_(["paid", "success", "réussi"]))
                .filter(Payment.created_at >= start)
                .filter(Payment.created_at < end)
                .distinct()
                .count()
            )

            PLAN_LIMITS = {
                "free": {"paid": 10, "links": 30},
                "pro": {"paid": 100, "links": 200},
                "business": {"paid": float("inf"), "links": float("inf")}
            }

            plan = getattr(user, "plan", "free")
            limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
            PAID_LIMIT = limits["paid"]

            if paid_count >= PAID_LIMIT:
                print("❌ PAYMENT BLOCKED: LIMIT REACHED")
                return {"status": "limit_reached"}
            
            
            user_id = session.metadata["user_id"]

            user = db.query(UserDB).filter(UserDB.id == user_id).first()

            profile = db.query(Profile).filter(
                Profile.user_id == user.id
            ).first()

            if not profile or not profile.stripe_account_id:
                raise Exception("Stripe account not found")
            
            if not user:
                db.close()
                return {"error": "user not found"}
            
            wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()

            if not wallet:
                wallet = Wallet(user_id=user.id, balance=0)
                db.add(wallet)
                db.flush()

            stripe_account_id = profile.stripe_account_id

            payment = Payment(
                user_id=user_id,
                client_email=email_client,
                amount=amount_usd,
                currency=currency,
                amount_local=amount_local,
                currency_local="XOF",
                rate_used=rate_used,
                status="paid",
                link_id=link_id,
                stripe_session_id=session.id,
                stripe_account_id=stripe_account_id
            )

            db.add(payment)
            db.flush()

            now = datetime.now(timezone.utc)

            wallet.balance += amount_local 
            wallet.available += amount_local

            stripe_available_on = balance_tx["available_on"]

            available_at = datetime.fromtimestamp(
                stripe_available_on,
                tz=timezone.utc
            )

            tx = WalletTransaction(
                user_id=user_id,
                wallet_id=wallet.id,
                type="deposit",
                direction="in",
                amount=amount_local,
                status="success",
                available_at = available_at,
                reference=f"pay_{session['id']}",
                description=f"Paiement reçu via le lien {link_id} par le client {email_client}"
            )
            db.add(tx)

            db.commit()
            print("✅ WALLET CREDITED:", amount_local)

            webhooks = db.query(Webhook).filter(
                Webhook.user_id == user_id,
                Webhook.is_active == True
            ).all()

            import requests
            print("🚀 LOOP WEBHOOK")
            for webhook in webhooks:
                print("SECRET:", webhook.secret)

                # 🔥 filtre des events
                print("EVENT TYPE:", event_type)
                print("WEBHOOK EVENTS:", webhook.events)
                if event_type not in webhook.events.split(","):
                    continue

                try:
                    payload = {
                        "id": f"evt_{uuid.uuid4().hex}",
                        "timestamp": int(time.time()),
                        "event": event_type,
                        "data": {
                            "amount": amount_local,
                            "currency": "XOF",
                            "user_id": user_id,
                            "link_id": link_id
                        }
                    }

                    payload_bytes = json.dumps(payload).encode()

                    signature = hmac.new(
                        webhook.secret.encode(),
                        payload_bytes,
                        hashlib.sha256
                    ).hexdigest()

                    print("SIGNATURE:", signature)
                    print("🔥 AVANT REQUEST")

                    max_retries = 3

                    response = None 
                    success = False  
                    final_status_code = None

                    for attempt in range(max_retries):
                        try:
                            print(f"🚀 Tentative {attempt + 1}")

                            response = requests.post(
                                webhook.url,
                                json=payload,
                                headers={
                                    "X-Signature": signature,
                                    "X-Epay-Event": event_type,
                                    "X-Epay-Timestamp": str(payload["timestamp"])
                                },
                                timeout=5
                            )
                            
                            print("SIGNATURE SENT:", signature)

                            print(f"STATUS: {response.status_code}")

                            final_status_code = response.status_code

                            if response.status_code == 200:
                                print("✅ Webhook envoyé avec succès")
                                success = True
                                break
                            else:
                                print("❌ Échec, retry...")

                        except Exception as e:
                            final_status_code = 0

                        time.sleep(2) 

                    log = WebhookDeliveryLog(
                        user_id=user_id,
                        webhook_id=webhook.id,
                        url=webhook.url,
                        event=event_type,
                        status_code=final_status_code,
                        success=success
                    )

                    db.add(log)
                    db.commit()


                    if response:
                        print(f"STATUS: {response.status_code}")
                        print(f"BODY: {response.text}")
                    else:
                        print("❌ Aucune réponse reçue")

                    webhook.last_triggered = datetime.now(timezone.utc)

                    if success:
                        webhook.status = "active"
                        webhook.last_status_code = 200
                    else:
                        webhook.status = "error"
                        webhook.last_status_code = response.status_code if response else None

                    db.commit()

                except Exception as e:
                    print("❌ erreur webhook:", e)
                    webhook.status = "error"
                    print("UPDATE EXECUTED")
                    webhook.last_triggered = datetime.now(timezone.utc)
                    db.commit()

            db.close()

            return {"status": "ok"}