from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
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


def _fetch_settled_charge_data(charge_id):
    """Relit le Charge et sa BalanceTransaction jusqu'à ce que les deux
    soient disponibles (balance_transaction est strictement requis, le
    calcul du montant/commission/frais Stripe en dépend tous les trois -
    voir process_checkout_session_payment).

    Ne bloque plus en plus sur application_fee/transfer une fois
    balance_tx trouvée : ces deux-là ne servent plus qu'à des champs
    secondaires (fee_id/fee_amount/transfer_amount, gardés à titre
    indicatif), la commission Xepay venant désormais directement de
    charge.application_fee_amount (toujours disponible immédiatement,
    sans délai de propagation). S'ils sont déjà là, tant mieux ; sinon
    le paiement est créé sans eux plutôt que d'attendre inutilement -
    le handler charge.updated (voir stripe_payment_webhook) corrige de
    toute façon stripe_fee_amount/balance_transaction_net/available_at
    dès que Stripe a fini de régler la balance_transaction, sans
    sondage, dès qu'elle devient disponible."""
    charge_dict = None
    balance_tx = None
    for attempt in range(MAX_SETTLEMENT_ATTEMPTS):
        charge = stripe.Charge.retrieve(charge_id)
        charge_dict = charge.to_dict()
        balance_txs = stripe.BalanceTransaction.list(source=charge_id, limit=1)
        if balance_txs.data:
            balance_tx = balance_txs.data[0]
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
        application_fee_requested = None
        balance_transaction_net = None
        transfer_destination = transfer_reversed = transfer_created_at = None
        transfer_amount_reversed = None
        amount_usd = None

        if intent and intent.latest_charge:
            charge_dict, balance_tx = _fetch_settled_charge_data(intent.latest_charge)
            payment_method_details = charge_dict.get("payment_method_details", {})
            card_info = payment_method_details.get("card", {})
            card_brand = card_info.get("brand")
            card_last4 = card_info.get("last4")
            card_exp_month = card_info.get("exp_month")
            card_exp_year = card_info.get("exp_year")
            # Apple Pay/Google Pay/Link payés par carte arrivent avec
            # payment_method_details.type == "card" (le wallet est un
            # sous-champ, card.wallet.type) — sans ça, payment_method_type
            # vaut toujours "card" et l'UI affiche le logo Visa/Mastercard
            # au lieu du logo du wallet.
            wallet_type = (card_info.get("wallet") or {}).get("type")
            payment_method_type = wallet_type or payment_method_details.get("type")
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
                # Champs Stripe confirmés sur de vrais paiements (EUR et
                # USD) - plus aucune dérivation/hypothèse de taux fixe :
                # - commission Xepay = charge.application_fee_amount, un
                #   champ direct de la charge, dans la même devise que
                #   Payment.amount/currency (contrairement à
                #   ApplicationFee.amount/fee_amount, resté dans la devise
                #   d'origine du lien).
                # - frais Stripe = balance_tx.fee, celle DE LA CHARGE
                #   elle-même (_fetch_settled_charge_data la retrouve par
                #   source=charge_id) - c'est elle qui porte le vrai frais
                #   de traitement carte, jamais celle de l'ApplicationFee.
                # - net marchand = brut - commission Xepay - frais Stripe.
                application_fee_requested = (charge_dict.get("application_fee_amount") or 0) / 100
                stripe_fee_amount = balance_tx.fee / 100
                balance_transaction_net = round(amount_usd - application_fee_requested - stripe_fee_amount, 2)
                available_on = balance_tx.available_on
                available_at = datetime.fromtimestamp(available_on, tz=timezone.utc)

        if not balance_tx:
            raise Exception("balance_transaction_not_available_yet")

        currency = session_dict.get("currency", "USD").upper()
        if currency == "XOF":
            amount_local = amount_usd
            rate_used = 1
            payment_currency = "XOF"
        else:
            row = db.execute(text("""
                SELECT rate FROM exchange_rates
                WHERE from_currency = 'USD' AND to_currency = 'XOF'
            """)).fetchone()
            rate_used = row.rate if row else 600
            total_fee = amount_usd * 0.06
            merchant_amount = amount_usd - total_fee
            amount_local = int(float(merchant_amount) * float(rate_used))
            # Un lien en EUR (ou toute devise non-XOF) est converti par
            # Stripe en USD au règlement : amount_usd est donc déjà en USD,
            # jamais dans la devise d'origine du lien (currency ci-dessus).
            # L'étiquetait avec "currency" (EUR par ex.) faisait mentir
            # Payment.currency sur ce que Payment.amount représente
            # vraiment.
            payment_currency = "USD"
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
            currency=payment_currency,
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
            application_fee_requested=application_fee_requested,
            stripe_fee_amount=stripe_fee_amount,
            balance_transaction_net=balance_transaction_net,
            available_at=available_at,
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
            source="payment_link",
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
            pi_id = object_data.payment_intent
            connected_account_id = event.account

            # Rembourse la part d'Application Fee correspondant au montant
            # déjà remboursé sur ce charge (object_data.amount_refunded est
            # cumulatif, pas seulement ce dernier remboursement). Calculé en
            # comparant à ce que l'ApplicationFee a déjà rendu
            # (fee_obj.amount_refunded) plutôt qu'en se fiant à qui a
            # déclenché ce remboursement : si refund_application_fee=True
            # (paiement par lien) ou POST /payments/{id}/refund (facture/
            # abonnement) l'ont déjà fait, la différence calculée ici tombe
            # à 0 et ce bloc ne fait rien — couvre donc aussi, sans double
            # remboursement, un remboursement fait directement depuis le
            # dashboard Stripe (jamais vu par notre code sinon).
            fee_id = getattr(object_data, "application_fee", None)
            if fee_id:
                try:
                    app_fee_amount = getattr(object_data, "application_fee_amount", None) or 0
                    charge_amount = getattr(object_data, "amount", None) or 0
                    amount_refunded = getattr(object_data, "amount_refunded", None) or 0
                    if app_fee_amount and charge_amount:
                        target_fee_refunded = int(app_fee_amount * amount_refunded / charge_amount)
                        fee_obj = stripe.ApplicationFee.retrieve(fee_id)
                        already_refunded = getattr(fee_obj, "amount_refunded", 0) or 0
                        fee_refund_amount = target_fee_refunded - already_refunded
                        if fee_refund_amount > 0:
                            stripe.ApplicationFee.create_refund(
                                fee_id, amount=fee_refund_amount
                            )
                except stripe.error.StripeError as e:
                    print(
                        f"⚠️ ApplicationFee.create_refund a échoué pour fee_id={fee_id} "
                        f"(charge={charge_id}): {e}"
                    )

            payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == pi_id)
                .first()
            )
            if payment:
                payment.status = (
                    "refunded"
                    if object_data.refunded
                    else "partially_refunded"
                )

            reference = pi_id
            tx = db.query(WalletTransaction).filter(WalletTransaction.reference == reference).first()
            if not tx and connected_account_id:
                # Facture/abonnement (direct charge sur le compte connecté) :
                # WalletTransaction.reference vaut invoice_id, jamais
                # payment_intent_id (voir process_invoice_paid_event dans
                # stripe.py). charge.invoice n'existe plus depuis l'API
                # basil, donc on retrouve la facture via InvoicePayment.list.
                try:
                    invoice_payments = stripe.InvoicePayment.list(
                        payment={"type": "payment_intent", "payment_intent": pi_id},
                        stripe_account=connected_account_id,
                    )
                    if invoice_payments.data:
                        tx = db.query(WalletTransaction).filter(
                            WalletTransaction.reference == invoice_payments.data[0].invoice
                        ).first()
                except stripe.error.StripeError as e:
                    print(f"⚠️ InvoicePayment.list a échoué pour payment_intent={pi_id}: {e}")

            just_refunded = bool(tx and tx.status != "refunded")
            if just_refunded:
                tx.status = "refunded"
                # object_data (le Charge) porte la liste des Refund qui lui
                # sont attachés ; on garde le plus récent (il peut y en
                # avoir plusieurs sur des remboursements partiels successifs).
                refunds_list = getattr(object_data, "refunds", None)
                refunds_data = getattr(refunds_list, "data", None) or []
                if refunds_data:
                    tx.refund_id = max(refunds_data, key=lambda r: r.created).id
                wallet = db.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
                if wallet:
                    wallet.balance -= tx.amount

            # Commit inconditionnel : avant, imbriqué dans le bloc
            # just_refunded ci-dessus, payment.status se perdait
            # silencieusement dès que tx n'était pas trouvé — systématique
            # pour facture/abonnement, reference valant invoice_id et non
            # payment_intent_id. Stripe marquait le paiement remboursé,
            # notre base restait bloquée sur "paid".
            db.commit()

            if just_refunded:
                db.refresh(tx)
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
        elif event_type == "charge.updated":
            # Stripe crée la balance_transaction de façon asynchrone après
            # le succès du paiement (automatic_async) : charge.updated est
            # l'événement dédié qui signale qu'elle est enfin prête - un
            # seul appel direct ici, jamais de sondage (contrairement à
            # _fetch_settled_charge_data, nécessaire uniquement à
            # checkout.session.completed, qui arrive souvent avant que la
            # balance_transaction existe). Corrige/complète un Payment déjà
            # créé plutôt que d'en créer un nouveau - traité en synchrone
            # (un seul appel Stripe rapide, pas besoin de tâche de fond).
            balance_transaction_id = object_data.balance_transaction
            if not balance_transaction_id:
                return {"status": "ignored"}
            pi_id = object_data.get("payment_intent")
            payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == pi_id)
                .first()
            )
            if not payment:
                return {"status": "ignored"}
            try:
                balance_tx = stripe.BalanceTransaction.retrieve(balance_transaction_id)
            except stripe.error.StripeError as e:
                print(f"⚠️ BalanceTransaction.retrieve a échoué pour {balance_transaction_id} (pi={pi_id}): {e}")
                return {"status": "ok"}
            amount_usd = balance_tx.amount / 100
            application_fee_requested = (object_data.get("application_fee_amount") or 0) / 100
            stripe_fee_amount = balance_tx.fee / 100
            payment.application_fee_requested = application_fee_requested
            payment.stripe_fee_amount = stripe_fee_amount
            payment.balance_transaction_net = round(amount_usd - application_fee_requested - stripe_fee_amount, 2)
            payment.available_at = datetime.fromtimestamp(balance_tx.available_on, tz=timezone.utc)
            db.commit()
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
