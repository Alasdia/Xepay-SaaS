from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile, Wallet, WalletTransaction, Withdrawal, UserDB, WorkspaceUser
from backend.middleware.authorization import require_manager
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
                        "refund_management": False,
                        "dispute_management": False,
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

@router.get("/stripe/connect/{account_id}/activity")
def get_connect_activity(
    account_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager)
):
    get_authorized_connect_profile(account_id, db, membership)
    try:
        transfers = stripe.Transfer.list(destination=account_id,limit=100)
        balance_transactions = (
            stripe.BalanceTransaction.list(stripe_account=account_id, limit=100)
        )
        application_fees = [
            fee.to_dict_recursive()
            for fee in stripe.ApplicationFee.list(
                limit=100
            ).auto_paging_iter()
            if fee.account == account_id
        ]
        return {
            "account_id": account_id,
            "transfers": [
                item.to_dict_recursive()
                for item in transfers.data
            ],
            "balance_transactions": [
                item.to_dict_recursive()
                for item in balance_transactions.data
            ],
            "application_fees": application_fees
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=e.user_message or str(e))