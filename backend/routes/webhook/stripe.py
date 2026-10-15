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
    connected_account_id = event.get("account")

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
        ):
            invoice_id = object_data["id"]

            # Compatibilité avec différentes versions de l'API Stripe.
            subscription_id = object_data.get("subscription")

            if not subscription_id:
                parent = object_data.get("parent")

                if parent:
                    subscription_details = (
                        parent.get("subscription_details")
                        if isinstance(parent, dict)
                        else getattr(parent, "subscription_details", None)
                    )

                    if subscription_details:
                        if isinstance(subscription_details, dict):
                            subscription_id = subscription_details.get(
                                "subscription"
                            )
                        else:
                            subscription_id = getattr(
                                subscription_details,
                                "subscription",
                                None
                            )

            # Si un abonnement est associé, il s'agit d'une
            # facture d'abonnement. Sinon, elle est ponctuelle.
            source_type = (
                "subscription"
                if subscription_id
                else "one_off_invoice"
            )

            profile = None

            if connected_account_id:
                profile = db.query(Profile).filter(
                    Profile.stripe_account_id == connected_account_id
                ).first()

            logger.info(
                "Stripe invoice event: type=%s invoice_id=%s "
                "source=%s subscription_id=%s connected_account=%s",
                event_type,
                invoice_id,
                source_type,
                subscription_id,
                connected_account_id
            )

            if not connected_account_id or not profile:
                logger.warning(
                    "Compte Connect ou profil introuvable pour la facture %s",
                    invoice_id
                )

            # Ici, relier l'événement à ton système de notifications
            # et à ton modèle comptable, avec une vérification
            # d'idempotence fondée sur event.id ou invoice_id.
            #
            # Ne pas créditer le wallet ici sans vérifier si le
            # paiement a déjà été enregistré par un autre webhook.

        # --------------------------------------------------
        # CYCLE DE VIE DES ABONNEMENTS CONNECT
        # --------------------------------------------------
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted"
        ):
            subscription_id = object_data["id"]
            subscription_status = object_data.get("status")

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