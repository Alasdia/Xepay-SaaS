from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks, Depends
import stripe
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import SessionLocal
from backend.models import UserDB, Wallet
from backend.models import Payment, WalletTransaction, Link, Profile
from backend.models import Webhook, WebhookDeliveryLog
from backend.auth import get_current_user
from backend.database import get_db
from backend.services.pdf_service import generate_invoice_pdf
from backend.services.email_service import send_payment_email
from backend.services.email_service import (
    send_payment_email,
    send_merchant_notification,
    send_payment_failed_email,
    send_payment_refunded_email
)
from backend.services.webhook_service import send_webhook_event
import traceback
import hmac
import hashlib
import uuid
import json
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
import os

router = APIRouter()

WEBHOOK_SECRET_PAYMENT = os.getenv("WEBHOOK_SECRET_PAYMENT")

# Délai de propagation Stripe observé en prod (confirmé par mesure directe,
# IDs réels) : balance_transaction, application_fee et transfer ne sont pas
# garantis disponibles sur le Charge au moment où checkout.session.completed
# arrive — pas seulement sur Stripe Link (observé aussi sur carte classique),
# et pour application_fee/transfer spécifiquement sur Link, mesuré au-delà de
# 18s dans au moins un cas réel. Un instantané unique sans nouvelle tentative
# perd alors le paiement (ou ses montants de frais) de façon définitive (la
# route a déjà répondu "ok" à Stripe, qui ne retente jamais). SETTLEMENT_
# RETRY_DELAYS_SECONDS absorbe ce délai dans la tâche de fond elle-même
# (thread pool, ne bloque jamais l'event loop) avec un backoff croissant
# jusqu'à ~3 minutes de patience cumulée — pas de nouvelle table, pas de
# cron, pas de nouvelle architecture.
SETTLEMENT_RETRY_DELAYS_SECONDS = [2, 3, 5, 8, 10, 15, 20, 20, 20, 20, 20, 20, 20]
MAX_SETTLEMENT_ATTEMPTS = len(SETTLEMENT_RETRY_DELAYS_SECONDS) + 1


def _fetch_settled_charge_data(charge_id, stripe_account=None):
    """Relit le Charge et sa BalanceTransaction jusqu'à ce que les deux
    soient disponibles (balance_transaction est strictement requis, le
    calcul du montant en dépend) et, si possible, jusqu'à ce que
    application_fee/transfer le soient aussi (sinon le paiement est quand
    même conservé, avec fee_amount/transfer_amount à None en dernier
    recours — jamais perdu pour cette seule raison)."""
    charge_dict = None
    balance_tx = None
    for attempt in range(MAX_SETTLEMENT_ATTEMPTS):
        charge = stripe.Charge.retrieve(charge_id)
        charge_dict = charge.to_dict()
        balance_txs = stripe.BalanceTransaction.list(source=charge_id, limit=1)
        if balance_txs.data:
            balance_tx = balance_txs.data[0]
            if charge_dict.get("application_fee") and charge_dict.get("transfer"):
                break
        if attempt < len(SETTLEMENT_RETRY_DELAYS_SECONDS):
            time.sleep(SETTLEMENT_RETRY_DELAYS_SECONDS[attempt])
    return charge_dict, balance_tx


def process_checkout_session_payment(session_dict, user_id, link_id, reference_key, pi_id, event_type):
    """Traite, après que la réponse HTTP ait déjà été renvoyée à Stripe, la
    part de checkout.session.completed qui dépend du règlement Stripe.
    Exécutée comme tâche de fond (thread pool, pas l'event loop).

    La BalanceTransaction du Charge est retrouvée via
    stripe.BalanceTransaction.list(source=charge.id) plutôt que via le champ
    charge.balance_transaction : ce champ a un délai de propagation non
    borné (observé en prod sur Stripe Link, >30s), alors que la
    BalanceTransaction elle-même existe dès la création du Charge — source=
    la retrouve indépendamment de ce champ. Voir _fetch_settled_charge_data
    pour la tentative bornée qui absorbe ce même type de délai sur
    application_fee/transfer, et sur balance_transaction lui-même si jamais
    observé (constat confirmé aussi sur carte classique)."""
    db = SessionLocal()
    try:
        existing_tx = db.query(WalletTransaction).filter(
            WalletTransaction.reference == reference_key
        ).first()
        if existing_tx:
            return

        intent = stripe.PaymentIntent.retrieve(pi_id) if pi_id else None
        if intent and not intent.latest_charge:
            raise Exception("payment_intent_without_charge_yet")

        balance_tx = None
        available_at = None
        card_brand = card_last4 = card_exp_month = card_exp_year = None
        fee_id = transfer_id = payment_method_id = payment_method_type = None
        fee_amount = transfer_amount = stripe_fee_amount = None
        transfer_destination = transfer_reversed = transfer_created_at = None
        transfer_amount_reversed = None
        amount_usd = None

        if intent and intent.latest_charge:
            charge_dict, balance_tx = _fetch_settled_charge_data(intent.latest_charge)
            payment_method_details = charge_dict.get("payment_method_details", {})
            payment_method_type = payment_method_details.get("type")
            card_info = payment_method_details.get("card", {})
            card_brand = card_info.get("brand")
            card_last4 = card_info.get("last4")
            card_exp_month = card_info.get("exp_month")
            card_exp_year = card_info.get("exp_year")
            fee_id = charge_dict.get("application_fee")
            transfer_id = charge_dict.get("transfer")
            payment_method_id = charge_dict.get("payment_method")
            if fee_id:
                fee_obj = stripe.ApplicationFee.retrieve(fee_id)
                fee_amount = fee_obj.amount / 100
            if transfer_id:
                transfer_obj = stripe.Transfer.retrieve(transfer_id)
                transfer_amount = transfer_obj.amount / 100
                transfer_destination = transfer_obj.destination
                transfer_reversed = transfer_obj.reversed
                transfer_amount_reversed = transfer_obj.amount_reversed / 100
                transfer_created_at = datetime.fromtimestamp(transfer_obj.created, tz=timezone.utc)

            if balance_tx:
                amount_usd = balance_tx.amount / 100
                stripe_fee_amount = balance_tx.fee / 100
                available_on = balance_tx.available_on
                available_at = datetime.fromtimestamp(available_on, tz=timezone.utc)

        if not balance_tx:
            raise Exception("balance_transaction_not_available_yet")

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
            raise Exception("user_or_wallet_not_found")
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
            stripe_session_id=session_dict.get("id"),
            stripe_account_id=profile.stripe_account_id,
            stripe_payment_intent_id=pi_id,
            payment_method_id=payment_method_id,
            payment_method_type=payment_method_type,
            fee_id=fee_id,
            fee_amount=fee_amount,
            stripe_fee_amount=stripe_fee_amount,
            transfer_id=transfer_id,
            transfer_amount=transfer_amount,
            transfer_destination=transfer_destination,
            transfer_reversed=transfer_reversed,
            transfer_amount_reversed=transfer_amount_reversed,
            transfer_created_at=transfer_created_at,
            card_brand=card_brand,
            card_last4=card_last4,
            card_exp_month=card_exp_month,
            card_exp_year=card_exp_year
        )
        db.add(payment)
        db.flush()
        try:
            pdf_path = generate_invoice_pdf(payment, user.email)
            send_payment_email(email_client, pdf_path)
            send_merchant_notification(user.email, payment)
        except Exception as e:
            print(f"⚠️ Erreur génération PDF/Email: {e}")
        print("💰 AVANT CREDIT WALLET")
        print("user_id:", user_id)
        print("wallet_id:", wallet.id)
        print("ancien balance:", wallet.balance)
        print("montant à créditer:", amount_local)
        wallet.balance += amount_local
        print("💰 APRÈS CREDIT WALLET")
        print("nouveau balance:", wallet.balance)
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
            description=tx_description,
            fee_id=fee_id,
            fee_amount=fee_amount,
            transfer_id=transfer_id,
            transfer_amount=transfer_amount,
            payment_method_id=payment_method_id,
            card_brand=card_brand,
            card_last4=card_last4,
            card_exp_month=card_exp_month,
            card_exp_year=card_exp_year
        )
        db.add(tx)
        db.commit()
        send_webhook_event(user_id, "payment.success", {
            "reference": reference_key,
            "amount": amount_local,
            "currency": "XOF",
            "status": "paid",
            "stripe_session_id": session_dict.get("id")
        })
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        print(f"⚠️ Échec différé checkout.session.completed (reference={reference_key}): {e}")
    finally:
        db.close()

@router.post("/webhook/payment")
async def stripe_payment_webhook(request: Request, background_tasks: BackgroundTasks, stripe_signature: str = Header(None, alias="stripe-signature")):
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
    db = SessionLocal()
    try:
        if event_type in ["payment_intent.payment_failed", "payment_intent.canceled"]:
            pi_id = object_data["id"]
            reference = f"pi_{pi_id}"
            tx = db.query(WalletTransaction).filter(WalletTransaction.reference == reference).first()
            if tx and tx.status != "failed":
                tx.status = "failed"
                db.commit()
                if tx:
                    user = db.query(UserDB).filter(UserDB.id == tx.user_id).first()
                    if user and user.email:
                        send_payment_failed_email(user.email)
                    if user:
                        background_tasks.add_task(send_webhook_event, user.id, "payment.failed", {
                            "reference": reference,
                            "amount": tx.amount,
                            "status": "failed"
                        })
            return {"status": "ok"}
        elif event_type == "charge.refunded":
            charge_id = object_data["id"]
            pi_id = object_data.get("payment_intent")
            reference = pi_id
            tx = db.query(WalletTransaction).filter(WalletTransaction.reference == reference).first()
            if tx and tx.status != "refunded":
                tx.status = "refunded"
                wallet = db.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
                if wallet:
                    wallet.balance -= tx.amount
                db.commit()
                user = db.query(UserDB).filter(UserDB.id == tx.user_id).first()
                if user and user.email:
                    send_payment_refunded_email(user.email, tx.amount)
                if user:
                    background_tasks.add_task(send_webhook_event, user.id, "refund.issued", {
                        "reference": reference,
                        "amount": tx.amount,
                        "status": "refunded"
                    })    
            return {"status": "ok"}
        if event_type == "checkout.session.completed":
            print("STRIPE EVENT:", event_type)
            print("STRIPE EVENT ID:", event["id"])
            session = object_data
            if session.mode != "payment":
                return {"status": "ignored"}
            session_dict = session.to_dict() if hasattr(session, "to_dict") else dict(session)
            metadata = session_dict.get("metadata", {})
            user_id = metadata.get("user_id")
            link_id = metadata.get("link_id")
            if not user_id or not link_id:
                return {"status": "ignored"}
            pi_id = session_dict.get("payment_intent")
            reference_key = pi_id if pi_id else session_dict.get('id')
            existing_tx = db.query(WalletTransaction).filter(
                WalletTransaction.reference == reference_key
            ).first()
            if existing_tx:
                return {"status": "ignored"}
            # La disponibilité de charge.balance_transaction chez Stripe peut
            # arriver après cet événement (course observée en prod, ~2s) :
            # toute la suite dépendante en est différée en tâche de fond
            # (process_checkout_session_payment) pour ne plus bloquer l'event
            # loop pendant l'attente, et on répond déjà "ok" à Stripe.
            background_tasks.add_task(
                process_checkout_session_payment,
                session_dict, user_id, link_id, reference_key, pi_id, event_type
            )
            return {"status": "ok"}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/payments")
def get_stripe_payments(
    limit: int = 100,
    starting_after: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(
        Profile.user_id == current_user.id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe Connect introuvable"
        )
    params = {"limit": min(max(limit, 1), 100)}
    if starting_after:
        params["starting_after"] = starting_after
    try:
        result = stripe.Charge.list(
            **params,
            stripe_account=profile.stripe_account_id,
        )
        return {
            "data": [
                charge.to_dict()
                for charge in result.data
            ],
            "has_more": result.has_more,
            "next_cursor": (
                result.data[-1].id if result.data else None
            ),
        }
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Impossible de récupérer les paiements Stripe"
        ) from exc

@router.get("/payment-balance-transactions")
def get_payment_balance_transactions(
    limit: int = 100,
    starting_after: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(
        Profile.user_id == current_user.id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe Connect introuvable"
        )
    params = {"limit": min(max(limit, 1), 100)}
    if starting_after:
        params["starting_after"] = starting_after
    try:
        result = stripe.PaymentIntent.list(
            **params,
            stripe_account=profile.stripe_account_id,
        )
        data = []
        for intent in result.data:
            if intent.latest_charge:
                _, balance_tx = _fetch_settled_charge_data(
                    intent.latest_charge,
                    stripe_account=profile.stripe_account_id,
                )
                if balance_tx:
                    data.append(balance_tx.to_dict())
        return {
            "data": data,
            "has_more": result.has_more,
            "next_cursor": (
                result.data[-1].id
                if result.data
                else None
            ),
        }
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc