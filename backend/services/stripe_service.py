import stripe
import os
from decimal import Decimal
from backend.models import Link, UserDB, Profile
from backend.services import commission_service
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
        amount_cents = int(amount * 100)
        # Commission dégressive par volume mensuel du marchand (voir
        # backend/services/commission_service.py) - résolue ICI, avant que
        # ce paiement n'existe en base, pour qu'il ne compte jamais dans son
        # propre volume. Le taux est dupliqué dans la metadata
        # (commission_rate_applied) : c'est la seule trace de "quel taux a
        # réellement été appliqué à CETTE transaction" - indispensable au
        # webhook de règlement (routes/webhook/paiement.py), qui normalise
        # tout en USD via la balance_transaction Stripe et ne peut donc pas
        # relire application_fee_amount directement (il reste dans la
        # devise d'origine du lien) ni se contenter de ré-appeler
        # resolve_commission_rate (le volume du mois aurait pu bouger entre
        # la création de cette session et le règlement du paiement).
        commission_rate = commission_service.resolve_commission_rate(db, merchant.id)
        application_fee_amount = int(Decimal(amount_cents) * commission_rate)
        session = stripe.checkout.Session.create(
            mode=mode,
            customer_email=None,
            payment_intent_data={
                "application_fee_amount": application_fee_amount,
                "transfer_data": {
                    "destination": stripe_account_id
                },
                "on_behalf_of": stripe_account_id,
                  "metadata": {
                    "source": "xepay",
                    "payment_type": "payment_link",
                    "link_id": str(link.id),
                    "merchant_id": str(merchant.id),
                    "user_id": str(user_id),
                    "stripe_account_id": str(stripe_account_id),
                    "commission_rate_applied": str(commission_rate),
                }
            },
            metadata={
                "source": "xepay",
                "payment_type": "payment_link",
                "user_id": str(user_id),
                "link_id": str(link.id),
                "merchant_id": str(merchant.id),
                "stripe_account_id": str(stripe_account_id)
            },
            line_items=[{
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {
                        "name": "Paiement Xepay",
                    },
                    "unit_amount": amount_cents,
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
        # L'abonnement Xepay (facturation SaaS) est désormais porté par la
        # configuration "customer" du MÊME compte v2 que le marchand utilise
        # déjà comme "merchant"/"recipient" (voir account_configuration dans
        # /signup et l'inscription Google, backend/routes/users.py) - un seul
        # objet Stripe par marchand au lieu d'un Customer v1 séparé.
        # customer_account remplace donc customer_email : Stripe n'auto-crée
        # plus de Customer, il facture directement ce compte. stripe_version
        # requis par appel (pas de réglage global) car "customer"/
        # customer_account restent une fonctionnalité preview chez Stripe à
        # ce jour - voir la vérification faite en direct sur l'API le
        # 2026-10-25 (confirmée disponible pour cette plateforme).
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile or not profile.stripe_account_id:
            raise Exception("Merchant Stripe account not found")
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_account=profile.stripe_account_id,
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
            stripe_version="2025-09-30.preview",
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


def create_connect_customer(
    merchant_account: str,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    country: str | None = None,
    metadata: dict | None = None,
):
    params = {"metadata": metadata or {}}
    if name:
        params["name"] = name
    if email:
        params["email"] = email
    if phone:
        params["phone"] = phone
    if country:
        params["address"] = {"country": country}
    return stripe.Customer.create(
        **params,
        stripe_account=merchant_account,
    )

def update_connect_customer(
    merchant_account: str,
    customer_id: str,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    country: str | None = None,
):
    # Meme logique que create_connect_customer : un champ vide/absent n'est
    # pas envoye (donc jamais efface involontairement), seuls les champs
    # effectivement renseignes dans le formulaire sont mis a jour.
    params = {}
    if name:
        params["name"] = name
    if email:
        params["email"] = email
    if phone:
        params["phone"] = phone
    if country:
        params["address"] = {"country": country}
    return stripe.Customer.modify(
        customer_id,
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
    interval_count: int = 1,
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
            "interval_count": interval_count or 1,
        }
    price = stripe.Price.create(
        **price_params,
        stripe_account=merchant_account,
    )
    return product, price