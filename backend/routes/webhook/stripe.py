from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile, Wallet, WalletTransaction, Withdrawal, UserDB, WorkspaceUser, ConnectInvoiceCreateRequest, ConnectSubscriptionCreateRequest, ConnectProductCreateRequest, ConnectCustomerCreateRequest, SetupIntentCreateRequest
from backend.middleware.authorization import require_manager
from backend.services.stripe_service import (create_connect_invoice, create_connect_subscription, create_connect_product, create_connect_customer)
from backend.services.email_service import send_account_updated_email, send_payout_success_email, send_payout_failed_email
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
        return {"status": "ignored"}
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET_CONNECT
        )
    except ValueError:
        return {"status": "invalid_payload"}
    except stripe.error.SignatureVerificationError:
        return {"status": "invalid_signature"}
    event_type = event["type"]
    object_data = event["data"]["object"]
    if event_type == "account.updated":
        stripe_id = object_data["id"]
        account = stripe.Account.retrieve(stripe_id)
        profile = db.query(Profile).filter(Profile.stripe_account_id == stripe_id).first()
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
                user = db.query(UserDB).filter(UserDB.id == profile.user_id).first()
                if user and user.email:
                    send_account_updated_email(user.email)
            except Exception as e:
                db.rollback()
                return {"status": "db_error"}
    elif event_type in ["payout.paid", "payout.failed", "payout.canceled"]:
        payout_id = object_data["id"]
        wd = db.query(Withdrawal).filter(Withdrawal.stripe_payout_id == payout_id).first()
        if wd and wd.status not in ["success", "failed"]:
            wallet = db.query(Wallet).filter(Wallet.id == wd.wallet_id).first()
            tx = db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first()
            if event_type == "payout.paid":
                wd.status = "success"
                if tx:
                    tx.status = "success"
                    tx.description = "Retrait réussi"
            elif event_type in ["payout.failed", "payout.canceled"]:
                wd.status = "failed"
                wd.payout_failure_message = object_data.get("failure_message")
                if wallet:
                    wallet.pending -= wd.amount
                    wallet.available += wd.amount
                if tx:
                    tx.status = "failed"    
                    tx.description = "Retrait échoué"                            
            db.commit()
            merchant = db.query(UserDB).filter(UserDB.id == wd.user_id).first()
            if merchant and merchant.email:
                if event_type == "payout.paid":
                    send_payout_success_email(merchant.email, wd.amount)
                elif event_type in ["payout.failed", "payout.canceled"]:
                    send_payout_failed_email(merchant.email, wd.amount)     
    else:
        return {"status": "ignored"}
    return {"ok": True}

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
                    "enabled": True
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

@router.post("/stripe/connect/setup-intent")
def create_setup_intent(
    data: SetupIntentCreateRequest,
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
        setup_intent = stripe.SetupIntent.create(
            customer=data.customer_id,
            usage="off_session",
            stripe_account=profile.stripe_account_id,
        )
        return {
            "client_secret": setup_intent.client_secret,
            "id": setup_intent.id,
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
        subscription = create_connect_subscription(
            merchant_account=profile.stripe_account_id,
            customer_id=data.customer_id,
            price_id=data.price_id,
            quantity=data.quantity,
            collection_method=data.collection_method,
            payment_method_id=data.payment_method_id,
            application_fee_percent=1.0,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_subscription",
            },
        )
        return {
            "id": subscription.id,
            "object": subscription.object,
            "status": subscription.status,
            "customer": subscription.customer,
            "collection_method": subscription.collection_method,
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
        subscriptions = stripe.Subscription.list(
            limit=100,
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