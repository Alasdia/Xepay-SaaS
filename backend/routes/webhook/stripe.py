from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile, Wallet, WalletTransaction, Withdrawal, UserDB, WorkspaceUser, ConnectInvoiceCreateRequest, ConnectSubscriptionCreateRequest, ConnectProductCreateRequest, ConnectCustomerCreateRequest
from backend.middleware.authorization import require_manager
from backend.services.stripe_service import (create_connect_invoice, create_connect_product, create_connect_customer)
from backend.services.email_service import send_account_updated_email, send_payout_success_email, send_payout_failed_email
import stripe  
import os

STRIPE_WEBHOOK_SECRET_CONNECT = os.getenv("STRIPE_WEBHOOK_SECRET_CONNECT")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter()

# Les montants Stripe sont exprimés dans l'unité minimale de la devise.
# XOF est une devise sans sous-unité (partagé entre PaymentIntent et facture).
ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK",
    "JPY", "KMF", "KRW", "PYG", "RWF",
    "UGX", "VND", "VUV", "XAF", "XOF",
    "XPF",
}


def _convert_merchant_amount_to_xof(db, merchant_amount, currency):
    """merchant_amount : Decimal, net de commission, dans `currency`.
    Retourne le montant arrondi (ROUND_DOWN) en XOF."""
    from decimal import Decimal, ROUND_DOWN
    from sqlalchemy import text

    if currency == "XOF":
        return merchant_amount.quantize(Decimal("1"), rounding=ROUND_DOWN)

    rate_row = db.execute(
        text("""
            SELECT rate
            FROM exchange_rates
            WHERE from_currency = :currency
              AND to_currency = 'XOF'
        """),
        {"currency": currency},
    ).fetchone()

    if not rate_row:
        raise ValueError(f"Taux {currency}/XOF introuvable")

    return (merchant_amount * Decimal(str(rate_row.rate))).quantize(
        Decimal("1"),
        rounding=ROUND_DOWN,
    )


def process_invoice_paid_event(
    invoice_data: dict,
    connected_account_id: str,
    db: Session,
):
    """Crédite le wallet du marchand à la facturation d'une Facture Connect
    ou au règlement d'un cycle d'abonnement Connect (les abonnements Stripe
    se règlent eux aussi via une Invoice, portant `subscription` non nul :
    voir create_merchant_subscription/create_connect_invoice dans
    stripe_service.py, qui posent déjà application_fee_percent/
    application_fee_amount sur ce flux). Schéma défensif classique
    (idempotence par référence, lock du wallet) partagé avec
    process_checkout_session_payment (paiement par lien, paiement.py).

    Depuis l'API Stripe 2025-03-31.basil, l'Invoice du webhook n'a plus
    payment_intent, charge, application_fee_amount ni subscription à plat
    (retirés au profit de invoice.payments/invoice.parent — voir le
    changelog "add-support-for-multiple-partial-payments-on-invoices"). Lire
    ces champs sur invoice_data renvoyait donc toujours None/0, en silence
    (fee toujours à 0, available_at toujours None, abonnements classés
    "invoice"). Plutôt que de deviner/recalculer depuis un payload dont la
    forme a changé sous nos pieds, cette fonction relit l'objet PaymentIntent
    réel qui a réglé la facture (2 à 3 appels Stripe, détaillés plus bas) et
    lit directement dessus tout ce qui peut l'être : montant, devise, frais,
    moyen de paiement, carte, description, date de création, date de
    disponibilité des fonds (avec repli sur BalanceTransaction.list si
    l'expand ne suffit pas — constaté peu fiable sur ce flux, contrairement
    au paiement par lien). Si ce PaymentIntent ne peut pas être retrouvé,
    on lève plutôt que de créditer avec des valeurs devinées : l'exception
    remonte jusqu'au handler webhook, qui répond 500 à Stripe, qui retentera
    la livraison (l'idempotence par référence empêche tout double crédit)."""
    import logging
    from decimal import Decimal
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)

    invoice_id = invoice_data["id"]

    # Seules les factures effectivement payées créditent le wallet.
    if invoice_data.get("status") != "paid":
        return {
            "status": "ignored",
            "invoice_id": invoice_id,
        }

    if not connected_account_id:
        raise ValueError("Compte Connect absent de l'événement facture")

    # Idempotence : ne jamais créditer deux fois la même facture.
    existing = db.query(WalletTransaction).filter(
        WalletTransaction.reference == invoice_id
    ).first()

    if existing:
        return {
            "status": "already_processed",
            "invoice_id": invoice_id,
        }

    profile = db.query(Profile).filter(
        Profile.stripe_account_id == connected_account_id
    ).first()

    if not profile:
        raise ValueError(
            f"Profil introuvable : {connected_account_id}"
        )

    merchant_id = profile.user_id

    wallet = db.query(Wallet).filter(
        Wallet.user_id == merchant_id
    ).with_for_update().first()

    if not wallet:
        raise ValueError(
            f"Portefeuille introuvable : {merchant_id}"
        )

    # Un abonnement Connect se règle via une Invoice portant `subscription` —
    # c'est le seul signal fiable qui distingue un sous-solde "Abonnements"
    # d'un sous-solde "Factures" (customer.subscription.* ne porte, lui,
    # aucune garantie de paiement réussi). Depuis l'API Stripe
    # 2025-03-31.basil, invoice.subscription est retiré au profit de
    # invoice.parent.subscription_details.subscription (avec
    # invoice.parent.type == "subscription_details") — exactement la même
    # vague de retrait que payment_intent/charge. Lire l'ancien champ seul
    # classait donc TOUTE facture d'abonnement comme "invoice" (jamais
    # "subscription"), silencieusement, sur cette clé API (pinnée sur une
    # version postérieure à basil). On garde l'ancien champ en repli, au cas
    # où l'API version du compte changerait.
    parent = invoice_data.get("parent") or {}
    if parent.get("type") == "subscription_details":
        subscription_id = (parent.get("subscription_details") or {}).get("subscription")
    else:
        subscription_id = invoice_data.get("subscription")
    source = "subscription" if subscription_id else "invoice"

    # Retrouve le PaymentIntent qui a réglé cette facture : invoice.payments
    # supporte plusieurs paiements (partiels) par facture, donc on cherche
    # l'entrée réellement payée. expand=["payments.data.payment.payment_intent"]
    # est à la limite Stripe de 4 niveaux d'expand ; aller jusqu'à
    # latest_charge.balance_transaction dans la même requête dépasserait
    # cette limite, d'où le second appel sur le PaymentIntent lui-même.
    inv = stripe.Invoice.retrieve(
        invoice_id,
        expand=["payments.data.payment.payment_intent"],
        stripe_account=connected_account_id,
    )
    payment_intent_ref = None
    for entry in (inv.payments.data if inv.payments else []):
        if entry.status == "paid" and entry.payment.type == "payment_intent":
            payment_intent_ref = entry.payment.payment_intent
            break
    if not payment_intent_ref:
        raise ValueError(
            f"Aucun PaymentIntent réglé trouvé pour la facture {invoice_id}"
        )

    intent = stripe.PaymentIntent.retrieve(
        payment_intent_ref.id,
        expand=["latest_charge.balance_transaction"],
        stripe_account=connected_account_id,
    )

    # Montant et devise directement depuis le PaymentIntent réglé : déjà
    # dans la devise de facturation du marchand (XOF pour ce projet), donc
    # _convert_merchant_amount_to_xof ne fait qu'arrondir (pas de taux de
    # change appliqué) — mais reste générique si une facture est un jour
    # libellée dans une autre devise.
    currency = intent.currency.upper()
    divisor = (
        Decimal("1")
        if currency in ZERO_DECIMAL_CURRENCIES
        else Decimal("100")
    )
    gross_amount = Decimal(intent.amount_received or intent.amount or 0) / divisor
    fee_amount = Decimal(intent.application_fee_amount or 0) / divisor

    # Montant crédité au marchand après la commission Xepay.
    merchant_amount = gross_amount - fee_amount

    if merchant_amount < 0:
        raise ValueError(
            f"Commission supérieure à la facture : {invoice_id}"
        )

    amount_local = _convert_merchant_amount_to_xof(db, merchant_amount, currency)

    latest_charge = intent.latest_charge
    payment_method_details = (
        latest_charge.get("payment_method_details", {}) if latest_charge else {}
    ) or {}
    card_info = payment_method_details.get("card", {}) or {}

    # expand=["latest_charge.balance_transaction"] n'est pas honoré de façon
    # fiable sur ce flux (constaté : balance_transaction revient comme un ID
    # brut "txn_..." plutôt qu'expandé en objet, contrairement au paiement
    # par lien). Même filet de sécurité que process_checkout_session_payment
    # (paiement.py) : BalanceTransaction.list(source=charge_id) retrouve
    # l'objet complet indépendamment de ce que l'expand a renvoyé.
    balance_tx = (
        getattr(latest_charge, "balance_transaction", None) if latest_charge else None
    )
    if latest_charge and (not balance_tx or isinstance(balance_tx, str)):
        balance_txs = stripe.BalanceTransaction.list(
            source=latest_charge.id,
            limit=1,
            stripe_account=connected_account_id,
        )
        balance_tx = balance_txs.data[0] if balance_txs.data else None
    available_at = (
        datetime.fromtimestamp(balance_tx.available_on, tz=timezone.utc)
        if balance_tx and not isinstance(balance_tx, str) else None
    )

    created_at = datetime.fromtimestamp(intent.created, tz=timezone.utc)

    stripe_description = (
        latest_charge.get("description") if latest_charge else None
    )

    # status reste notre vocabulaire domaine ("success"/"pending"/"failed"),
    # pas le statut brut Stripe ("succeeded", "processing"...) : les agrégats
    # SQL de payout.py (solde disponible, breakdown) filtrent littéralement
    # sur status == "success". Mais il est dérivé du vrai intent.status
    # plutôt qu'écrit en dur — un paiement qui ne serait pas "succeeded" ici
    # (cas limite : l'InvoicePayment était "paid" mais le PaymentIntent a
    # depuis été contesté/annulé) ne doit pas compter comme crédité.
    if intent.status == "succeeded":
        status = "success"
    elif intent.status == "processing":
        status = "pending"
    else:
        status = "failed"

    if status != "success":
        # La facture/l'entrée de paiement est "paid" côté Stripe, mais le
        # PaymentIntent qui l'a réglée ne l'est plus (contesté/annulé entre
        # temps) : ne pas créditer le wallet sur la base d'une incohérence.
        raise ValueError(
            f"PaymentIntent {intent.id} non succeeded ({intent.status}) "
            f"pour la facture {invoice_id}"
        )

    tx = WalletTransaction(
        user_id=merchant_id,
        wallet_id=wallet.id,
        source=source,
        type="deposit",
        direction="in",
        amount=amount_local,
        status=status,
        reference=invoice_id,
        fee_id=latest_charge.get("application_fee") if latest_charge else None,
        fee_amount=fee_amount,
        transfer_id=latest_charge.get("transfer") if latest_charge else None,
        payment_method_id=intent.payment_method,
        card_brand=card_info.get("brand"),
        card_last4=card_info.get("last4"),
        card_exp_month=card_info.get("exp_month"),
        card_exp_year=card_info.get("exp_year"),
        available_at=available_at,
        created_at=created_at,
        description=stripe_description or (
            f"Paiement {'abonnement' if source == 'subscription' else 'facture'} "
            f"Stripe {invoice_id}"
        ),
    )

    try:
        db.add(tx)
        db.flush()

        wallet.balance = (
            Decimal(str(wallet.balance or 0)) + amount_local
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    logger.info(
        "Facture Connect traitée : id=%s marchand=%s source=%s montant_XOF=%s",
        invoice_id,
        merchant_id,
        source,
        amount_local,
    )

    return {
        "status": "processed",
        "invoice_id": invoice_id,
        "merchant_id": merchant_id,
        "source": source,
        "currency": currency,
        "gross_amount": str(gross_amount),
        "application_fee_amount": str(fee_amount),
        "credited_amount_xof": str(amount_local),
    }

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    import logging

    logger = logging.getLogger(__name__) 

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Signature manquante")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET_CONNECT
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload invalide")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Signature invalide")

    event_type = event["type"]
    object_data = event["data"]["object"]

    # Identifiant du compte Connect à l'origine de l'événement.
    connected_account_id = event.account

    try:
        # --------------------------------------------------
        # MISE À JOUR DU COMPTE CONNECT
        # --------------------------------------------------
        if event_type == "account.updated":
            stripe_id = object_data["id"]
            account = stripe.Account.retrieve(stripe_id)

            profile = db.query(Profile).filter(
                Profile.stripe_account_id == stripe_id
            ).first()

            if profile:
                individual = getattr(account, "individual", None)

                first_name = getattr(individual, "first_name", "") or ""
                last_name = getattr(individual, "last_name", "") or ""
                phone = getattr(individual, "phone", None)

                profile.full_name = f"{first_name} {last_name}".strip()

                if phone:
                    profile.phone = phone

                db.commit()

                user = db.query(UserDB).filter(
                    UserDB.id == profile.user_id
                ).first()

                if user and user.email:
                    send_account_updated_email(user.email)

        # --------------------------------------------------
        # RETRAITS CONNECT
        # --------------------------------------------------
        elif event_type in (
            "payout.paid",
            "payout.failed",
            "payout.canceled"
        ):
            payout_id = object_data["id"]

            wd = db.query(Withdrawal).filter(
                Withdrawal.stripe_payout_id == payout_id
            ).first()

            if wd and wd.status not in ("success", "failed"):
                wallet = db.query(Wallet).filter(
                    Wallet.id == wd.wallet_id
                ).first()

                tx = db.query(WalletTransaction).filter(
                    WalletTransaction.reference == wd.reference
                ).first()

                if event_type == "payout.paid":
                    wd.status = "success"

                    if tx:
                        tx.status = "success"
                        tx.description = "Retrait réussi"

                else:
                    wd.status = "failed"
                    wd.payout_failure_message = object_data.get(
                        "failure_message"
                    )

                    if wallet:
                        wallet.pending -= wd.amount
                        wallet.available += wd.amount

                    if tx:
                        tx.status = "failed"
                        tx.description = "Retrait échoué"

                db.commit()

                merchant = db.query(UserDB).filter(
                    UserDB.id == wd.user_id
                ).first()

                if merchant and merchant.email:
                    if event_type == "payout.paid":
                        send_payout_success_email(
                            merchant.email, wd.amount
                        )
                    else:
                        send_payout_failed_email(
                            merchant.email, wd.amount
                        )
        # --------------------------------------------------
        # FACTURES CONNECT
        # --------------------------------------------------
        elif event_type in (
            "invoice.paid",
            "invoice.payment_failed",
            "invoice.finalized",
            "invoice.voided",
        ):
            invoice_data = (
                object_data.to_dict()
                if hasattr(object_data, "to_dict")
                else dict(object_data)
            )

            if event_type == "invoice.paid":
                result = process_invoice_paid_event(
                    invoice_data=invoice_data,
                    connected_account_id=connected_account_id,
                    db=db,
                )

                logger.info(
                    "Traitement facture/abonnement Connect : %s",
                    result,
                )
            else:
                logger.info(
                    "Événement facture Connect : type=%s invoice_id=%s",
                    event_type,
                    invoice_data.get("id"),
                )
        # --------------------------------------------------
        # CYCLE DE VIE DES ABONNEMENTS CONNECT
        # --------------------------------------------------
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted"
        ):
            subscription_id = object_data["id"]
            subscription_status = object_data.status

            profile = None

            if connected_account_id:
                profile = db.query(Profile).filter(
                    Profile.stripe_account_id == connected_account_id
                ).first()

            logger.info(
                "Stripe subscription event: type=%s "
                "subscription_id=%s status=%s connected_account=%s",
                event_type,
                subscription_id,
                subscription_status,
                connected_account_id
            )

            if not connected_account_id or not profile:
                logger.warning(
                    "Compte Connect ou profil introuvable "
                    "pour l'abonnement %s",
                    subscription_id
                )

            # Relier ici l'événement à la notification d'abonnement
            # de Xepay. Un abonnement créé ou modifié ne signifie
            # pas nécessairement qu'un paiement a réussi.

        else:
            return {"status": "ignored", "event_type": event_type}

        return {"ok": True, "event_type": event_type}

    except Exception:
        db.rollback()
        logger.exception(
            "Erreur lors du traitement du webhook Stripe %s",
            event_type
        )
        raise HTTPException(
            status_code=500,
            detail="Erreur de traitement du webhook"
        )


@router.post("/stripe/account-session")
def create_account_session(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager)
):
    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(status_code=404, detail="Compte Stripe introuvable")
    try:
        session = stripe.AccountSession.create(
            account=profile.stripe_account_id,
            components={
                "account_management": {
                    "enabled": True
                }
            }
        )
        return {
            "client_secret": session.client_secret
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=e.user_message or str(e))
    

def get_authorized_connect_profile(
    account_id: str,
    db: Session,
    membership: WorkspaceUser
):
    profile = db.query(Profile).filter(Profile.stripe_account_id == account_id,Profile.user_id == membership.workspace_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Compte Connect introuvable ou non autorisé")
    return profile

@router.post("/stripe/connect/{account_id}/account-session")
def create_connect_activity_session(
    account_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager)
):
    get_authorized_connect_profile(account_id, db, membership)
    try:
        session = stripe.AccountSession.create(
            account=account_id,
            components={
                "payments": {
                    "enabled": True,
                    "features": {
                        "refund_management": True,
                        "dispute_management": True,
                        # Notre flux de paiement (backend/services/stripe_service.py)
                        # ne définit jamais capture_method="manual" : toutes les
                        # charges sont capturées automatiquement par Stripe, il
                        # n'existe donc aucune charge "non capturée" à traiter
                        # dans notre flux — ne pas activer une action qui ne
                        # correspond à aucun état réel chez nous.
                        "capture_payments": False
                    }
                },
                "payment_details": {
                    "enabled": True,
                    "features": {
                        "capture_payments": False
                    }
                },
                "payouts": {
                    "enabled": True,
                    "features": {
                        "standard_payouts": False,
                        "instant_payouts": False
                    }
                }
            }
        )
        return {
            "account_id": account_id,
            "client_secret": session.client_secret
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=e.user_message or str(e))

@router.post("/stripe/connect/invoices")
def create_merchant_invoice(
    data: ConnectInvoiceCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    price = stripe.Price.retrieve(
        data.price_id,
        stripe_account=profile.stripe_account_id,
    )

    amount = price.unit_amount * data.quantity
    application_fee_amount = int(amount * 0.01)

    try:
        invoice = create_connect_invoice(
            merchant_account=profile.stripe_account_id,
            customer_id=data.customer_id,
            price_id=data.price_id,
            quantity=data.quantity,
            collection_method=data.collection_method,
            days_until_due=data.days_until_due,
            application_fee_amount=application_fee_amount,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_invoice",
            },
        )

        return {
            "id": invoice.id,
            "object": invoice.object,
            "status": invoice.status,
            "customer": invoice.customer,
            "currency": invoice.currency,
            "amount_due": invoice.amount_due,
            "amount_paid": invoice.amount_paid,
            "collection_method": invoice.collection_method,
            "hosted_invoice_url": invoice.hosted_invoice_url,
            "invoice_pdf": invoice.invoice_pdf,
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/invoices")
def list_merchant_invoices(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        invoices = stripe.Invoice.list(
            limit=100,
            stripe_account=profile.stripe_account_id,
        )
        return {
            "object": "list",
            "data": [
                invoice.to_dict()
                for invoice in invoices.auto_paging_iter()
            ],
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/subscriptions")
def create_merchant_subscription(
    data: ConnectSubscriptionCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        metadata = {
            "user_id": str(membership.user_id),
            "workspace_id": str(membership.workspace_id),
            "customer_id": str(data.customer_id),
            "price_id": str(data.price_id),
            "quantity": str(data.quantity),
            "xepay_type": "merchant_subscription",
        }
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=data.customer_id,
            line_items=[
                {
                    "price": data.price_id,
                    "quantity": data.quantity,
                }
            ],
            metadata=metadata,
            subscription_data={
                "application_fee_percent": 1.0,
                "metadata": metadata,
            },
            success_url="https://alasdia.com/signup",
            cancel_url="https://alasdia.com/signup",
            stripe_account=profile.stripe_account_id,
        )
        return {
            "id": session.id,
            "url": session.url,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/subscriptions")
def list_merchant_subscriptions(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        # status="all" : par défaut, Stripe exclut les abonnements annulés
        # de la liste — nécessaire ici pour que les KPI "Annulés"/"Tout" de
        # la sous-vue Abonnements comptent des valeurs réelles.
        subscriptions = stripe.Subscription.list(
            limit=100,
            status="all",
            stripe_account=profile.stripe_account_id,
        )
        return {
            "object": "list",
            "data": [
                subscription.to_dict()
                for subscription in subscriptions.auto_paging_iter()
            ],
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/customers")
def create_merchant_customer(
    data: ConnectCustomerCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        customer = create_connect_customer(
            merchant_account=profile.stripe_account_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_customer",
            },
        )
        return {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/customers")
def list_merchant_customers(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )

    stripe_account = profile.stripe_account_id

    try:
        customers = stripe.Customer.list(
            limit=100,
            stripe_account=stripe_account,
        )

        result = []

        for customer in customers.data:

            # ==========================================
            # MOYEN DE PAIEMENT PRINCIPAL
            # ==========================================

            default_payment_method = (
                customer.invoice_settings.default_payment_method
            )

            payment_method_data = None

            if default_payment_method:

                payment_method_id = (
                    default_payment_method.id
                    if hasattr(default_payment_method, "id")
                    else default_payment_method
                )

                payment_method = stripe.PaymentMethod.retrieve(
                    payment_method_id,
                    stripe_account=stripe_account,
                )

                payment_method_data = {
                    "id": payment_method.id,
                    "type": payment_method.type,
                }

                if payment_method.type == "card" and payment_method.card:
                    payment_method_data["card"] = {
                        "brand": payment_method.card.brand,
                        "last4": payment_method.card.last4,
                        "exp_month": payment_method.card.exp_month,
                        "exp_year": payment_method.card.exp_year,
                    }

            # ==========================================
            # PAIEMENTS DU CLIENT
            # ==========================================

            charges = stripe.Charge.list(
                customer=customer.id,
                limit=100,
                stripe_account=stripe_account,
            )

            total_spent = 0
            payments_count = 0
            refunds_total = 0
            disputes_total = 0
            last_payment_at = None

            for charge in charges.data:

                # Paiement réussi
                if charge.paid and not charge.refunded:
                    total_spent += charge.amount
                    payments_count += 1

                # Si le paiement a été partiellement remboursé,
                # on conserve le montant réellement encaissé.
                elif charge.paid:
                    total_spent += (
                        charge.amount - charge.amount_refunded
                    )

                    payments_count += 1

                # Remboursements
                refunds_total += charge.amount_refunded or 0

                # Litiges
                if charge.disputed:
                    disputes_total += charge.amount

                # Dernier paiement réussi
                if charge.paid:
                    if (
                        last_payment_at is None
                        or charge.created > last_payment_at
                    ):
                        last_payment_at = charge.created

            # ==========================================
            # PAYS
            # ==========================================

            country = None

            if customer.address:
                country = customer.address.country
            # ==========================================
            # CLIENT ENRICHI
            # ==========================================
            result.append({
                "id": customer.id,
                "object": customer.object,

                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,

                "created": customer.created,
                "currency": customer.currency,
                "description": customer.description,
                "delinquent": customer.delinquent,
                # Positif = le client doit ce montant sur sa prochaine
                # facture ("solde restant") ; négatif = crédit. Utilisé par
                # le KPI "Soldes restants" de la sous-vue Clients.
                "balance": customer.balance,

                "address": customer.address,
                "shipping": customer.shipping,

                "country": country,

                "invoice_prefix": customer.invoice_prefix,
                "invoice_settings": customer.invoice_settings,

                "metadata": customer.metadata,
                "tax_exempt": customer.tax_exempt,
                "preferred_locales": customer.preferred_locales,

                "default_payment_method": payment_method_data,
                "total_spent": total_spent,
                "payments_count": payments_count,
                "refunds_total": refunds_total,
                "disputes_total": disputes_total,
                "last_payment_at": last_payment_at,
            })

        return {
            "object": "list",
            "data": result,
            "has_more": customers.has_more,
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/products")
def list_merchant_products(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    stripe_account = profile.stripe_account_id
    try:
        products = stripe.Product.list(
            limit=100,
            stripe_account=stripe_account,
        )
        result = []
        for product in products.auto_paging_iter():
            prices = stripe.Price.list(
                product=product.id,
                limit=100,
                stripe_account=stripe_account,
            )
            product_data = product.to_dict()
            product_data["prices"] = [
                price.to_dict()
                for price in prices.auto_paging_iter()
            ]
            result.append(product_data)
        return {
            "object": "list",
            "data": result,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/products")
def create_merchant_product(
    data: ConnectProductCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        product, price = create_connect_product(
            merchant_account=profile.stripe_account_id,
            name=data.name,
            description=data.description,
            unit_amount=data.unit_amount,
            currency=data.currency,
            recurring=data.recurring,
            interval=data.interval,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_product",
            },
        )
        return {
            "product": {
                "id": product.id,
                "name": product.name,
            },
            "price": {
                "id": price.id,
                "unit_amount": price.unit_amount,
                "currency": price.currency,
                "recurring": price.recurring,
            },
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/payment-methods")
def list_merchant_payment_methods(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        configurations = stripe.PaymentMethodConfiguration.list(
            limit=100,
            stripe_account=profile.stripe_account_id,
        )
        return {
            "object": configurations.object,
            "data": [
                configuration.to_dict()
                for configuration in configurations.auto_paging_iter()
            ],
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/risk")
def list_merchant_risk(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        disputes = stripe.Dispute.list(
            limit=100,
            stripe_account=profile.stripe_account_id,
        )
        result = [
            dispute.to_dict()
            for dispute in disputes.auto_paging_iter()
        ]
        return {
            "object": "list",
            "data": result,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )