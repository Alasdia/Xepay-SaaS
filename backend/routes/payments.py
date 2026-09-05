from fastapi import APIRouter
from backend.models import Payment, PaymentUpdate, Withdrawal
from backend.database import engine, get_db
from datetime import datetime, timezone
from sqlalchemy import text
from backend.models import PaymentCreate, PaymentResponse, Payment, Withdrawal, WalletTransaction, PaymentUpdate
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from backend.middleware.authorization import require_member
from backend.models import WorkspaceUser
from datetime import timedelta
from backend.models import Payment, Link
from backend.models import UserDB
from fastapi import Header
import os
from typing import Optional
from sqlalchemy.orm import joinedload

router = APIRouter()

@router.get("/transactions")
def get_transactions(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_member),
    status: Optional[str] = None,
    offset: int = 0,
    limit: int = 10
):
    owner_id = membership.workspace_id

    now = datetime.now(timezone.utc)

    links = db.query(Link).filter(
        Link.user_id == owner_id,
    ).all()

    payments = (
        db.query(Payment)
        .options(joinedload(Payment.link))
        .filter(Payment.user_id == owner_id)
        .all()
    )

    if status and status != "Tous":
        payments = payments.filter(Payment.status == status)
    
    transactions = []

    for p in payments:
        transactions.append({
            "email": p.client_email,
            "amount": p.amount_local,
            "currency": "XOF",
            "status": p.status,
            "date": p.created_at.isoformat() if p.created_at else None
        })

    paid_link_ids = {p.link_id for p in payments}

    for link in links:
        if link.id not in paid_link_ids:
            if link.expires_at and link.expires_at < now:
                link_status = "expired"
            else:
                link_status = "pending"
            
            final_amount = (link.amount or 0) * 0.94 * 577.325
            transactions.append({
                "email": "N/A",
                "amount": final_amount,
                "currency": "XOF",
                "status": link_status,
                "date": link.created_at.isoformat() if link.created_at else None
            })

    transactions.sort(key=lambda x: x["date"], reverse=True)

    if status and status != "Tous":
        transactions = [t for t in transactions if t["status"] == status]
    for t in transactions:
       print(t)
    transactions = transactions[offset:offset + limit]

    return transactions

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_member),
):
    owner_id = membership.workspace_id

    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=30)

    links = db.query(Link).filter(
        Link.user_id == owner_id,
        Link.created_at >= start_period
    ).all()

    payments = (
      db.query(Payment)
      .filter(Payment.user_id == owner_id)
      .all()
    ) 
    
    for p in payments:
        print("PAYMENT:", p.id, "LINK_ID:", p.link_id)
    paid_payments = [p for p in payments if p.status in ["paid", "success", "réussi"]]
    total_received = sum(p.amount_local if p.amount_local not in (None, 0) else p.amount for p in paid_payments)

    pending_withdraw = db.query(Withdrawal).filter(
        Withdrawal.user_id == owner_id,
        Withdrawal.status == "pending"
    ).all()

    pending_withdraw_total = sum(w.amount for w in pending_withdraw)

    for p in paid_payments:
       print("PAYMENT LINK:", p.link_id, type(p.link_id))

    paid_link_ids = {p.link_id for p in paid_payments}
    pending_total = 0
    expired_total = 0

    for link in links:
        if link.id in paid_link_ids:
            continue
        if link.expires_at and link.expires_at < now:
            expired_total += link.amount
            continue

        pending_total += (link.amount or 0) * 0.94 * 577.325

    total_links = len(links)
    paid_links = 0
    pending_links = 0
    expired_links = 0

    for link in links:
        print("LINK:", link.id, type(link.id))
        if link.id in paid_link_ids:
            paid_links += 1
        elif link.expires_at and link.expires_at < now:
            expired_links += 1
        else:
            pending_links += 1

    if total_links > 0:
        success_rate = (paid_links / total_links) * 100
    else:
        success_rate = 0

    success_rate = round(success_rate, 2)
    
    return {
        "total_received": total_received,
        "pending_total": pending_total,
        "pending_withdraw": pending_withdraw_total,
        "success_rate": round(success_rate, 2),
        "paid_links": paid_links,
        "paid_count": paid_links,
        "pending_links": pending_links,
        "failed_links": expired_links,
        "total_links": total_links
    }

@router.get("/activity")
def get_activity(
    type: str = None,
    status: str = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    items = []

    if type in (None, "payment"):
        q = db.query(Payment).filter(Payment.user_id == owner_id)
        if status: q = q.filter(Payment.status == status)
        for p in q.all():
            items.append({
                "type": "payment",
                "label": p.client_email,
                "amount": p.amount_local or p.amount,
                "currency": p.currency_local or p.currency,
                "status": p.status,
                "date": p.created_at,
                "details": {
                    "amount_origin": p.amount,
                    "currency_origin": p.currency,
                    "rate_used": p.rate_used,
                    "stripe_session_id": p.stripe_session_id,
                    "stripe_account_id": p.stripe_account_id,
                    "stripe_payment_intent_id": p.stripe_payment_intent_id,
                    "link_id": p.link_id,
                    "fee_amount": p.fee_amount,
                    "transfer_amount": p.transfer_amount,
                    "payment_method_id": p.payment_method_id,
                    "card_brand": p.card_brand,
                    "card_last4": p.card_last4,
                    "card_exp_month": p.card_exp_month,
                    "card_exp_year": p.card_exp_year
                }
            })
    if type in (None, "withdraw"):
        q = db.query(Withdrawal).filter(Withdrawal.user_id == owner_id)
        if status: q = q.filter(Withdrawal.status == status)
        for w in q.all():
            items.append({
                "type": "withdraw",
                "label": f"Retrait #{w.reference}",
                "amount": w.amount,
                "currency": "XOF",
                "status": w.status,
                "date": w.created_at,
                "details": {
                    "reference": w.reference,
                    "stripe_payout_id": w.stripe_payout_id,
                    "processed_at": w.processed_at.isoformat() if w.processed_at else None
                }
            })
    if type in (None, "transfer"):
        q = db.query(WalletTransaction).filter(
            WalletTransaction.user_id == owner_id,
            WalletTransaction.type == "transfer"
        )
        if status: q = q.filter(WalletTransaction.status == status)
        for t in q.all():
            counterparty = None
            if t.related_user_id:
                other = db.query(UserDB).filter(UserDB.id == t.related_user_id).first()
                counterparty = other.email if other else None

            items.append({
                "type": "transfer",
                "label": (f"Vers {counterparty}" if t.direction == "out" else f"De {counterparty}") if counterparty else "Transfert",
                "amount": t.amount,
                "currency": "XOF",
                "status": t.status,
                "date": t.created_at,
                "details": {
                    "reference": t.reference,
                    "direction": t.direction,
                    "counterparty_email": counterparty,
                    "fee_amount": t.fee_amount,
                    "transfer_id": t.transfer_id,
                    "transfer_amount": t.transfer_amount,
                    "payment_method_id": t.payment_method_id,
                    "card_brand": t.card_brand,
                    "card_last4": t.card_last4,
                    "card_exp_month": t.card_exp_month,
                    "card_exp_year": t.card_exp_year,
                    "description": t.description,
                    "available_at": t.available_at.isoformat() if t.available_at else None
                }
            })

    items.sort(key=lambda x: x["date"], reverse=True)
    paged = items[offset:offset+limit]

    for it in paged:
        it["date"] = it["date"].isoformat() if it["date"] else None

    return paged
