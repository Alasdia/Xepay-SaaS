from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from backend.database import get_db
from backend.models import Wallet, Withdrawal, WithdrawRequest, WalletTransaction, WebhookDeliveryLog, Webhook
from backend.middleware.authorization import require_owner
from backend.models import WorkspaceUser
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from sqlalchemy import func
from backend.models import Payment, Link, UserDB, Profile
from fastapi import Request
import json
import time
import hmac
import hashlib
import requests
import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
print(stripe.api_key)


router = APIRouter()

@router.get("/wallet/me")
def get_wallet(
    db: Session = Depends(get_db), 
    user=Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        user,
        workspace_id,
        db
    )

    wallet = db.query(Wallet).filter(Wallet.user_id == owner_id).first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")
    
    now = datetime.now(timezone.utc)

    txs = db.query(WalletTransaction).filter(
        WalletTransaction.user_id == owner_id
    ).all()

    deposits = [tx for tx in txs if tx.type == "deposit"]
    withdrawals = [tx for tx in txs if tx.type == "withdraw"]

    unlocked_deposits = sum(
        tx.amount for tx in deposits
        if not tx.available_at or tx.available_at <= now
    )

    locked_amount = sum(
        tx.amount for tx in txs
        if tx.type == "deposit" and tx.available_at and tx.available_at > now
    )

    withdrawn_total = sum(
        tx.amount for tx in withdrawals
        if tx.status in ("pending", "processing", "success")
    )

    available_amount = unlocked_deposits - withdrawn_total

    future_dates = [tx.available_at for tx in txs if tx.available_at and tx.available_at > now]
    next_available_at = min(future_dates) if future_dates else None

    return {
        "available": available_amount,
        "pending_withdrawal": wallet.pending,
        "locked_amount": locked_amount,
        "next_available_at": next_available_at
    }


@router.get("/wallet/history")
def get_wallet_history(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        user,
        workspace_id,
        db
    )
    
    txs = db.query(WalletTransaction)\
        .filter(WalletTransaction.user_id == owner_id)\
        .order_by(WalletTransaction.created_at.desc())\
        .all()

    return {
        "transactions": [
            {
                "amount": tx.amount,
                "direction": tx.direction,
                "type": tx.type,
                "description": tx.description,
                "reference": tx.reference,
                "created_at": tx.created_at.isoformat()
            }
            for tx in txs
        ]
    }
        
@router.post("/withdraw")
def withdraw(
    req: WithdrawRequest, 
    db: Session = Depends(get_db), 
    membership: WorkspaceUser = Depends(require_owner)
):
    owner_id = membership.workspace_id

    print("ROUTE /withdraw appelée")

    from backend.services.wallet_service import create_wallet_transaction

    wallet = db.query(Wallet)\
        .filter(Wallet.user_id == owner_id)\
        .with_for_update()\
        .first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    # 🔥 sécurité
    if req.amount <= 0:
        raise HTTPException(400, "Invalid amount")
    
    now = datetime.now(timezone.utc)

    next_available = db.query(WalletTransaction.available_at)\
        .filter(
            WalletTransaction.user_id == owner_id,
            WalletTransaction.type == "deposit",
            WalletTransaction.status == "success",
            WalletTransaction.available_at > now
        )\
        .order_by(WalletTransaction.available_at.asc())\
        .first()

    print("DEBUG TX:")
    for tx in db.query(WalletTransaction).filter(WalletTransaction.user_id == owner_id).all():
        print(tx.type, tx.status, tx.amount, tx.available_at)

    available_amount = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.user_id == owner_id,
        WalletTransaction.type == "deposit",
        WalletTransaction.status == "success",
        WalletTransaction.available_at <= now
    ).scalar() or 0

    print("AVAILABLE_STRIPE:", available_amount)
    print("AVAILABLE_WALLET:", wallet.available)

    # ✅ check réel Stripe
    if available_amount < req.amount:
        raise HTTPException(
            400,
            detail={
                "message": "Funds not yet available",
                "next_available_at": next_available[0].isoformat() if next_available else None
            }
        )

    print(f"[WITHDRAW BEFORE] owner={owner_id} available={wallet.available} pending={wallet.pending}")

    # 🔒 lock les fonds
    wallet.available -= req.amount
    wallet.pending += req.amount

    print(f"[WITHDRAW AFTER] owner={owner_id} available={wallet.available} pending={wallet.pending}")

    ref = f"wd_{uuid.uuid4()}"

    print(f"[NEW WITHDRAW] owner={owner_id} amount={req.amount} ref={ref}")

    withdrawal = Withdrawal(
        user_id=owner_id,
        wallet_id=wallet.id,
        amount=req.amount,
        status="pending",
        reference=ref
    )
    
    create_wallet_transaction(
        db=db,
        user_id=owner_id,
        wallet_id=wallet.id,
        amount=req.amount,
        type="withdraw",
        direction="out",
        status="pending",
        reference=ref, 
        description="Retrait en attente"
    )


    db.add(withdrawal)
    db.commit()
    db.refresh(withdrawal)

    return {
        "status": "pending",
        "id": withdrawal.id,
        "next_available_at": next_available[0] if next_available else None
    }
    
@router.post("/withdraw/{id}/process")
def process_withdraw(
    id: int, 
    db: Session = Depends(get_db)
):
    print("🔥 PROCESS WITHDRAW EXECUTÉ 🔥")

    wd = db.query(Withdrawal)\
        .filter(Withdrawal.id == id)\
        .with_for_update()\
        .first()

    if not wd:
        raise HTTPException(404, "Withdrawal not found")

    if wd.status in ["processing", "success"]:
        return {"error": "already processed"}

    wallet = db.query(Wallet)\
        .filter(Wallet.id == wd.wallet_id)\
        .with_for_update()\
        .first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    # 🔥 récupérer user (merchant)
    user = db.query(UserDB).filter(UserDB.id == wd.user_id).first()

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(400, "Stripe account not connected")
    
    # 🔐 vérifier Stripe account
    account = stripe.Account.retrieve(profile.stripe_account_id)
    print("=== CAPABILITIES ===")
    print(account.capabilities)

    print("=== PAYOUTS ENABLED ===")
    print(account.payouts_enabled)

    print("=== REQUIREMENTS ===")
    print(account.requirements)

    if not account["payouts_enabled"]:
        raise HTTPException(400, "Payouts not enabled")

    USD_RATE = 577.325

    usd_amount = wd.amount / USD_RATE
    amount_cents = int(usd_amount * 100)

    if amount_cents <= 0:
        raise HTTPException(400, "Amount too small")

    # 💰 vérifier balance Stripe
    balance = stripe.Balance.retrieve(
        stripe_account=profile.stripe_account_id
    )
    print("=== STRIPE DEBUG ===")
    print("PENDING:", balance["pending"])
    print("AVAILABLE:", balance["available"])
    print("INSTANT:", balance["instant_available"])

    instant_available = sum(b["amount"] for b in balance["instant_available"])

    print("INSTANT AVAILABLE:", instant_available)

    if instant_available < amount_cents:
        raise HTTPException(400, "Insufficient Stripe balance")

    wd.status = "processing"
    db.flush()
    print("AVANT PAYOUT")

    try:
        payout = stripe.Payout.create(
            amount=amount_cents,
            currency="usd",
            stripe_account=profile.stripe_account_id,
            method="instant"
        )
        print("PAYOUT STATUS:", payout["status"])

        print("APRES PAYOUT")

        wd.status = payout["status"]
        wd.stripe_payout_id = payout["id"]

        wallet.pending -= wd.amount

        tx = db.query(WalletTransaction).filter(
            WalletTransaction.reference == wd.reference
        ).first()

        if tx:
            tx.status = payout["status"]

    except Exception as e:
        print("Stripe error:", str(e))

        wd.status = "failed"
        wallet.pending -= wd.amount
        wallet.available += wd.amount 

        tx = db.query(WalletTransaction).filter(
            WalletTransaction.reference == wd.reference
        ).first()

        if tx:
            tx.status = "failed"

    wd.processed_at = datetime.now(timezone.utc)
    db.commit()

    event_type = "withdrawal.done"
    webhooks = db.query(Webhook).filter(
        Webhook.user_id == wd.user_id,
        Webhook.is_active == True
    ).all()

    for webhook in webhooks:
        if event_type not in webhook.events.split(","):
            continue

        try:
            payload = {
                "id": f"evt_{uuid.uuid4().hex}",
                "timestamp": int(time.time()),
                "event": event_type,
                "data": {
                    "withdrawal_id": wd.id,
                    "amount": wd.amount,
                    "currency": "XOF",
                    "status": wd.status,
                    "reference": wd.reference,
                    "stripe_payout_id": wd.stripe_payout_id
                }
            }

            payload_bytes = json.dumps(payload).encode()
            signature = hmac.new(
                webhook.secret.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()

            success = False
            final_status_code = None
            response = None

            for attempt in range(3):
                try:
                    response = requests.post(
                        webhook.url,
                        json=payload,
                        headers={
                            "X-Signature": signature,
                            "X-Epay-Event": event_type,
                            "X-Epay-Timestamp": str(payload["timestamp"])
                        },
                        timeout=5
                    )
                    final_status_code = response.status_code
                    if response.status_code == 200:
                        success = True
                        break
                except Exception:
                    final_status_code = 0
                time.sleep(2)

            log = WebhookDeliveryLog(
                user_id=wd.user_id,
                webhook_id=webhook.id,
                url=webhook.url,
                event=event_type,
                status_code=final_status_code,
                success=success
            )
            db.add(log)
            
            webhook.last_triggered = datetime.now(timezone.utc)
            webhook.status = "active" if success else "error"
            webhook.last_status_code = final_status_code
            db.commit()

        except Exception as e:
            print("❌ Erreur webhook withdrawal:", e)
            webhook.status = "error"
            webhook.last_triggered = datetime.now(timezone.utc)
            db.commit()

    return {"status": wd.status}

@router.post("/withdrawals/{withdrawal_id}/cancel")
async def cancel_withdrawal(
    withdrawal_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    wd = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    
    if not wd:
        raise HTTPException(status_code=404, detail="Retrait introuvable.")
    
    if wd.status != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Impossible d'annuler ce retrait car son statut est déjà '{wd.status}'."
        )

    try:
        stripe.Payout.cancel(wd.stripe_payout_id)

        wd.status = "canceled"
        
        wallet = db.query(Wallet).filter(Wallet.id == wd.wallet_id).first()
        if wallet:
            wallet.pending -= wd.amount
            wallet.available += wd.amount
            
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first()
        if tx:
            tx.status = "canceled"
            
        db.commit()

        return {"success": True, "message": "Retrait annulé avec succès et fonds recrédités."}

    except stripe.error.StripeError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur Stripe : {e.user_message}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")

