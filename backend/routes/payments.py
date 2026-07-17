from fastapi import APIRouter
from backend.models import Payment, PaymentUpdate, Withdrawal
from backend.database import engine, get_db
from datetime import datetime, timezone
from sqlalchemy import text
from backend.models import PaymentCreate, PaymentResponse
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

    # 🔹 récupérer liens
    links = db.query(Link).filter(
        Link.user_id == owner_id,
    ).all()

    # 🔹 récupérer paiements
    payments = (
        db.query(Payment)
        .options(joinedload(Payment.link))
        .filter(Payment.user_id == owner_id)
        .all()
    )
    print("STATUS DEMANDÉ:", status)

    if status and status != "Tous":
        payments = payments.filter(Payment.status == status)
    print("STATUS FILTER:", status)
    print("PAYMENTS COUNT:", len(payments))
    
    transactions = []

    # =========================
    # 🔹 1. Paiements (PAID)
    # =========================
    print("PAYMENTS AVANT LOOP:", payments)
    for p in payments:
        print("PAYMENT STATUS DB:", p.status)
        print(p.client_email)
        transactions.append({
            "email": p.client_email,
            "amount": p.amount_local,
            "currency": "XOF",
            "status": p.status,
            "date": p.created_at.isoformat() if p.created_at else None
        })
        print("PAID TRANSACTIONS:", transactions)

    # =========================
    # 🔹 2. Liens non payés
    # =========================
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

    # =========================
    # 🔹 3. TRI (IMPORTANT UX)
    # =========================
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

    # 🔹 Récupération des données
    links = db.query(Link).filter(
        Link.user_id == owner_id,
        Link.created_at >= start_period
    ).all()

    payments = (
      db.query(Payment)
      .filter(Payment.user_id == owner_id)
      .all()
    ) 
    
    print("LINKS COUNT:", len(links))
    print("PAYMENTS COUNT:", len(payments))
    for p in payments:
        print("PAYMENT:", p.id, "LINK_ID:", p.link_id)
    # 🔹 Paiements validés uniquement
    paid_payments = [p for p in payments if p.status in ["paid", "success", "réussi"]]

    # 🔹 Total reçu
    total_received = sum(p.amount_local if p.amount_local not in (None, 0) else p.amount for p in paid_payments)

    pending_withdraw = db.query(Withdrawal).filter(
        Withdrawal.user_id == owner_id,
        Withdrawal.status == "pending"
    ).all()

    pending_withdraw_total = sum(w.amount for w in pending_withdraw)

    for p in paid_payments:
       print("PAYMENT LINK:", p.link_id, type(p.link_id))

    # 🔹 IDs des liens déjà payés
    paid_link_ids = {p.link_id for p in paid_payments}

    # 🔹 En attente (liens non payés et non expirés)
    pending_total = 0
    expired_total = 0

    for link in links:

        if link.id in paid_link_ids:
            continue

        if link.expires_at and link.expires_at < now:
            expired_total += link.amount
            continue

        # PENDING
        pending_total += (link.amount or 0) * 0.94 * 577.325
    # 🔹 Taux de réussite (basé sur liens)
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

    # ✅ formule propre
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

