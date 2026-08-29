from fastapi import APIRouter, Request, Header, HTTPException
import stripe
from sqlalchemy import text
from backend.database import SessionLocal
from backend.models import UserDB, Wallet
from backend.models import Payment, WalletTransaction, Link, Profile
from backend.models import Webhook, WebhookDeliveryLog
from backend.services.pdf_service import generate_invoice_pdf
from backend.services.email_service import send_payment_email
from backend.services.email_service import (
    send_payment_email,
    send_merchant_notification,
    send_payment_failed_email,
    send_payment_refunded_email
)
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
            WEBHOOK_SECRET_PAYMENT  
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event["type"]
    object_data = event["data"]["object"]
    print("🔥 PAYMENT EVENT:", event_type)

    db = SessionLocal()

    try:
        if event_type in ["payment_intent.payment_failed", "payment_intent.canceled"]:
            pi_id = object_data["id"]
            reference = f"pi_{pi_id}"

            tx = db.query(WalletTransaction).filter(WalletTransaction.reference == reference).first()
            if tx and tx.status != "failed":
                tx.status = "failed"
                db.commit()
                print(f"❌ Transaction {reference} marquée comme échouée/annulée.")
                if tx:
                    user = db.query(UserDB).filter(UserDB.id == tx.user_id).first()
                    if user and user.email:
                        send_payment_failed_email(user.email)
            return {"status": "ok"}

        elif event_type == "charge.refunded":
            charge_id = object_data["id"]
            pi_id = object_data.get("payment_intent")
            reference = f"pi_{pi_id}" if pi_id else f"ch_{charge_id}"

            tx = db.query(WalletTransaction).filter(WalletTransaction.reference == reference).first()
            if tx and tx.status != "refunded":
                tx.status = "refunded"
                
                wallet = db.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
                if wallet:
                    wallet.balance -= tx.amount

                db.commit()
                print(f"🔄 Transaction {reference} remboursée et solde mis à jour.")
                if tx:
                    user = db.query(UserDB).filter(UserDB.id == tx.user_id).first()
                    if user and user.email:
                        send_payment_refunded_email(user.email, tx.amount)
            return {"status": "ok"}

        if event_type == "checkout.session.completed":
            session = object_data

            if session.mode != "payment":
                return {"status": "ignored"}

            session_dict = session.to_dict() if hasattr(session, "to_dict") else dict(session)
            metadata = session_dict.get("metadata", {})
            
            user_id = metadata.get("user_id")
            link_id = metadata.get("link_id")

            if not user_id or not link_id:
                print("❌ METADATA MANQUANTE")
                return {"status": "ignored"}
            
            pi_id = session_dict.get("payment_intent")
            reference_key = pi_id if pi_id else session_dict.get('id')

            existing_tx = db.query(WalletTransaction).filter(
                WalletTransaction.reference == reference_key
            ).first()

            if existing_tx:
                print("⚠️ EVENT DEJA TRAITE")
                return {"status": "ignored"}

            intent = stripe.PaymentIntent.retrieve(pi_id) if pi_id else None
            if intent and not intent.latest_charge:
                return {"status": "waiting"}

            balance_tx = None
            available_at = None

            if intent and intent.latest_charge:
                for _ in range(5):
                    charge = stripe.Charge.retrieve(intent.latest_charge)
                    if charge.balance_transaction:
                        balance_tx = stripe.BalanceTransaction.retrieve(charge.balance_transaction)
                        amount_usd = balance_tx.amount / 100
                        stripe_fee = balance_tx.fee / 100
                        available_on = balance_tx.available_on
                        available_at = datetime.fromtimestamp(available_on, tz=timezone.utc)
                        break
                    time.sleep(1)

            if not balance_tx:
                return {"status": "waiting"}

            currency = session_dict.get("currency", "USD").upper()

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
                merchant_amount = amount_usd - total_fee
                amount_local = int(float(merchant_amount) * float(rate_used))

            customer_details = session_dict.get("customer_details")
            email_client = customer_details.get("email") if customer_details else None

            user = db.query(UserDB).filter(UserDB.id == user_id).first()
            if not user or not user.wallet:
                return {"status": "error", "reason": "user_or_wallet_not_found"}

            wallet = user.wallet
            profile = db.query(Profile).filter(Profile.user_id == user.id).first()
            if not profile or not profile.stripe_account_id:
                raise Exception("Stripe account not found")

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
                stripe_account_id=profile.stripe_account_id
            )
            db.add(payment)
            db.flush()

            try:
                pdf_path = generate_invoice_pdf(payment, user.email)
                send_payment_email(email_client, pdf_path)
                send_merchant_notification(user.email, payment)
            except Exception as e:
                print(f"⚠️ Erreur génération PDF/Email: {e}")

            wallet.balance += amount_local 

            stripe_event_id = session_dict.get("id") 
            stripe_status = session_dict.get("payment_status") or session_dict.get("status")
            
            if event_type == "checkout.session.completed":
                tx_status = "success"
                tx_type = "deposit"
                tx_direction = "in"
                tx_description = f"Paiement Stripe réussi (Session: {stripe_event_id})"
            elif event_type in ["payment_intent.payment_failed", "payment_intent.canceled"]:
                tx_status = "failed"
                tx_type = "deposit"
                tx_direction = "in"
                tx_description = f"Échec du paiement Stripe (Statut: {stripe_status})"
            elif event_type == "charge.refunded":
                tx_status = "refunded"
                tx_type = "refund"
                tx_direction = "out"
                tx_description = f"Remboursement de la charge Stripe {stripe_event_id}"
            else:
                tx_status = "pending"
                tx_type = "deposit"
                tx_direction = "in"
                tx_description = f"Événement Stripe brut: {event_type} - Statut: {stripe_status}"

            tx = WalletTransaction(
                user_id=user_id,
                wallet_id=wallet.id,
                type=tx_type,
                direction=tx_direction,
                amount=amount_local,
                status=tx_status, 
                available_at=available_at,
                reference=reference_key, 
                description=tx_description 
            )
            db.add(tx)
            db.commit()
            print("✅ WALLET CREDITED:", amount_local)

            return {"status": "ok"}

    except Exception as e:
        db.rollback()
        print(f"❌ Erreur critique webhook payment: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
