import stripe
import os
from backend.models import Link, UserDB, Profile

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

        print("DESTINATION:", stripe_account_id)

        account = stripe.Account.retrieve(stripe_account_id)
        print("CAPABILITIES:", account.capabilities)

        print("ACCOUNT ID DEBUG:", stripe_account_id)
        
        print("FINAL AMOUNT BEFORE STRIPE:", amount)

        print("FINAL CURRENCY BEFORE STRIPE:", currency)
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode=mode,
            customer_email=None,

            payment_intent_data={
                "application_fee_amount": int(amount * 0.06 * 100),  
                "transfer_data": {
                    "destination": stripe_account_id
                }
            },
            metadata={
                "user_id": str(user_id),
                "link_id": str(link_id)
            },

            line_items=[{
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {
                        "name": "Paiement ePay",
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
            "pro": "price_1TLmI121oAuf4OUmX8OjO02a",
            "business": "price_1TLmIp21oAuf4OUmQCGqycNy"
        }

        price_id = price_map.get(plan)

        if not price_id:
            raise Exception("Plan invalide")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=email,

            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],

            subscription_data={
                "metadata": {
                    "user_id": str(user_id),
                    "plan": plan
                }
            },

            success_url="https://alasdia.com/html/success.html",
            cancel_url="https://alasdia.com/html/cancel.html",
        )

        return session.url