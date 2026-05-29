from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from backend.database import get_db
from backend.models import Wallet, Withdrawal, WithdrawRequest, WalletTransaction
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from sqlalchemy import func
from backend.models import Payment, Link, UserDB, Profile
from fastapi import Request
import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
print(stripe.api_key)


router = APIRouter()

print("🔥 FICHIER CHARGÉ 🔥")

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

    for tx in txs:
        print({
            "status": tx.status,
            "available_at": tx.available_at,
            "amount": tx.amount
        })

    next_available = db.query(WalletTransaction.available_at)\
        .filter(
            WalletTransaction.user_id == owner_id,
            WalletTransaction.type == "deposit",
            WalletTransaction.available_at != None
        )\
        .order_by(WalletTransaction.available_at.desc())\
        .first()
    
    print("NEXT:", next_available)

    return {
        "available": wallet.available,
        "pending": wallet.pending,
        "next_available_at": next_available[0] if next_available else None
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
                "reference": f"TX-{tx.id}",
                "created_at": tx.created_at.isoformat()
            }
            for tx in txs
        ]
    }
        
@router.post("/withdraw")
def withdraw(
    req: WithdrawRequest, 
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
def process_withdraw(id: int, db: Session = Depends(get_db)):
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

        wd.status = "pending"
        wd.stripe_payout_id = payout["id"]

        tx = db.query(WalletTransaction).filter(
            WalletTransaction.reference == wd.reference
        ).first()

        if tx:
            tx.status = "success"

    except Exception as e:
        print("Stripe error:", str(e))

        wd.status = "failed"
        wallet.pending -= wd.amount
        wallet.available += wd.amount  # rollback

        tx = db.query(WalletTransaction).filter(
            WalletTransaction.reference == wd.reference
        ).first()

        if tx:
            tx.status = "failed"

    wd.processed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": wd.status}

