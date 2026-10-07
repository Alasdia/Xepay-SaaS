import stripe
import os
from backend.models import Link, UserDB, Profile
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_checkout_session(
    db,
    mode,
    email,
    user_id,
    amount=None,
    link_id=None,
    plan=None,
    currency="USD",
):
    currency = currency.lower()
    if currency not in ["usd", "eur"]:
        raise Exception("Currency not supported")
    if mode == "payment":
        link = db.query(Link).filter(Link.id == link_id).first()
        if not link:
            raise Exception("Link not found")
        merchant = db.query(UserDB).filter(UserDB.id == link.user_id).first()
        profile = db.query(Profile).filter(
            Profile.user_id == merchant.id
        ).first()
        if not profile or not profile.stripe_account_id:
            raise Exception("Merchant Stripe account not found")
        stripe_account_id = profile.stripe_account_id
        session = stripe.checkout.Session.create(
            mode=mode,
            customer_email=None,
            payment_intent_data={
                "application_fee_amount": int(amount * 0.06 * 100),  
                "transfer_data": {
                    "destination": stripe_account_id
                },
                "on_behalf_of": stripe_account_id
            },
            metadata={
                "user_id": str(user_id),
                "link_id": str(link_id)
            },
            line_items=[{
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {
                        "name": "Paiement Xepay",
                    },
                    "unit_amount": int(amount * 100),
                },
                "quantity": 1,
            }],
            success_url="https://alasdia.com/success.html",
            cancel_url="https://alasdia.com/cancel.html",
        )
        return session.url
    elif mode == "subscription":
        price_map = {
            "pro": "price_1ULaX80I86XW25IrFJBTIif0",
            "business": "price_1ULaZ30I86XW25IrZPncow7U"
        }
        price_id = price_map.get(plan)
        if not price_id:
            raise Exception("Plan invalide")
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            metadata={
                "user_id": str(user_id),
                "plan": plan
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user_id),
                    "plan": plan
                }
            },
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            success_url="https://alasdia.com/success.html",
            cancel_url="https://alasdia.com/cancel.html",
        )
        return session.url

def create_connect_invoice(
    merchant_account: str,
    customer_id: str,
    price_id: str,
    quantity: int = 1,
    collection_method: str = "send_invoice",
    days_until_due: int | None = 7,
    application_fee_amount: int | None = None,
    metadata: dict | None = None,
):
    """
    Crée et finalise une facture dans le compte Stripe Connect du marchand.
    """
    invoice_params = {
        "customer": customer_id,
        "collection_method": collection_method,
        "metadata": metadata or {},
    }
    if collection_method == "send_invoice" and days_until_due is not None:
        invoice_params["days_until_due"] = days_until_due
    if application_fee_amount is not None:
        invoice_params["application_fee_amount"] = application_fee_amount
    invoice = stripe.Invoice.create(
        **invoice_params,
        stripe_account=merchant_account,
    )
    stripe.InvoiceItem.create(
        customer=customer_id,
        invoice=invoice.id,
        pricing={
            "price": price_id,
        },
        quantity=quantity,
        stripe_account=merchant_account,
    )
    invoice = stripe.Invoice.finalize_invoice(
        invoice.id,
        stripe_account=merchant_account,
    )
    return invoice

def create_connect_subscription(
    merchant_account: str,
    customer_id: str,
    price_id: str,
    quantity: int = 1,
    application_fee_percent: float | None = None,
    collection_method: str = "charge_automatically",
    payment_method_id: str | None = None,
    metadata: dict | None = None,
):
    """
    Crée un abonnement dans le compte Stripe Connect du marchand.
    """
    subscription_params = {
        "customer": customer_id,
        "items": [
            {
                "price": price_id,
                "quantity": quantity,
            }
        ],
        "collection_method": collection_method,
        "metadata": metadata or {},
    }
    if payment_method_id:
        subscription_params[
            "default_payment_method"
        ] = payment_method_id
    if application_fee_percent is not None:
        subscription_params[
            "application_fee_percent"
        ] = application_fee_percent
    subscription = stripe.Subscription.create(
        **subscription_params,
        stripe_account=merchant_account,
    )
    return subscription

def create_subscription_setup_session(
    merchant_account: str,
    customer_id: str,
    subscription_id: str,
    price_id: str,
    workspace_id: str,
    user_id: str,
):
    metadata = {
        "subscription_id": str(subscription_id),
        "customer_id": str(customer_id),
        "price_id": str(price_id),
        "workspace_id": str(workspace_id),
        "user_id": str(user_id),
        "xepay_type": "merchant_subscription_payment_method",
    }
    session = stripe.checkout.Session.create(
        mode="setup",
        customer=customer_id,
        metadata=metadata,
        setup_intent_data={
            "metadata": metadata,
        },
        stripe_account=merchant_account,
    )
    return session

def create_connect_customer(
    merchant_account: str,
    name: str,
    email: str,
    phone: str | None = None,
    metadata: dict | None = None,
):
    params = {
        "name": name,
        "email": email,
        "metadata": metadata or {},
    }
    if phone:
        params["phone"] = phone
    return stripe.Customer.create(
        **params,
        stripe_account=merchant_account,
    )

def create_connect_product(
    merchant_account: str,
    name: str,
    description: str | None,
    unit_amount: int,
    currency: str,
    recurring: bool = False,
    interval: str | None = None,
    metadata: dict | None = None,
):
    product = stripe.Product.create(
        name=name,
        description=description,
        metadata=metadata or {},
        stripe_account=merchant_account,
    )
    price_params = {
        "product": product.id,
        "unit_amount": unit_amount,
        "currency": currency.lower(),
        "metadata": metadata or {},
    }
    if recurring:
        price_params["recurring"] = {
            "interval": interval or "month",
        }
    price = stripe.Price.create(
        **price_params,
        stripe_account=merchant_account,
    )
    return product, price