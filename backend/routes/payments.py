from fastapi import APIRouter
from backend.models import Payment, PaymentUpdate, Withdrawal
from backend.database import engine, get_db
from datetime import datetime, timezone
from sqlalchemy import text
from backend.models import PaymentCreate, PaymentResponse
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.models import Payment, Link
from backend.models import UserDB
from fastapi import Header, HTTPException
import os
from typing import Optional
from sqlalchemy.orm import joinedload



router = APIRouter()



@router.get("/payments")
def get_payments(
    status: str = None,
    email_search: str = None,
    currency: str = None,
    user = Depends(get_current_user)
):
    print("USER:", user)

    query = """
    SELECT p.* 
    FROM payments p
    JOIN links l ON p.link_id = l.id
    WHERE l.user_id = :user_id
    """

    params = {"user_id": user.id}

    # 🔎 filtre recherche email
    if email_search:
        query += " AND p.email ILIKE :email_search"
        params["email_search"] = f"%{email_search}%"

    # 🎯 filtre status
    if status:
        query += " AND p.status = :status"
        params["status"] = status

    # 💱 filtre devise
    if currency:
        query += " AND p.currency = :currency"
        params["currency"] = currency

    with engine.connect() as conn:
        result = conn.execute(text(query), params).fetchall()

    return [dict(row._mapping) for row in result]


@router.post("/create-payment")
def create_payment(payment: PaymentCreate):
    try:
        with engine.begin() as conn:
            status_map = {
                "réussi": "success",
                "payé": "success",
                "success": "success",

                "en attente": "pending",
                "pending": "pending",

                "échoué": "failed",
                "failed": "failed"
            }
            status_clean = status_map.get(payment.status.lower(), "pending")
            result = conn.execute(
                text("""
                    INSERT INTO payments (email, amount, status, created_at) 
                    VALUES (:email, :amount, :status, :created_at)
                    RETURNING id
                """),
                {
                    "email": payment.email,
                    "amount": payment.amount,
                    "status": status_clean,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )
            new_id = result.scalar()

        return {"success": True, "id": new_id}
    except Exception as e:
        print("CREATE ERROR:", e)
        return {"success": False, "error": str(e)}



@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: int):
    try:
        print("DB utilisée :", engine.url)

        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM payments WHERE id = :id"), 
                {"id": payment_id}
            )

            if result.rowcount == 0:
                return {
                    "success": False,
                    "message": "Payment not found"
                }
            
        return {"success": True}
        
    except Exception as e:
        print("Erreur suppression :", e)
        return {
            "success": False, 
            "error": str(e)
        }



    
@router.put("/payments/{payment_id}")
def update_payment(payment_id: int, payment: PaymentUpdate):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE payments
                SET email = :email,
                    amount = :amount,
                    status = :status
                WHERE id = :id
            """),
            {
                "id": payment_id,
                "email": payment.email,
                "amount": payment.amount,
                "status": payment.status
            }
        )

        if result.rowcount == 0:
            return {"success": False, "message": "Payment not found"}

    return {"success": True}


@router.get("/test-wallet")
def test_wallet():
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM wallets")
            ).mappings().all()

        return {"data": result}

    except Exception as e:
        return {"error": str(e)}
    
@router.get("/transactions")
def get_transactions(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: int = Header(..., alias="X-Workspace-Id"),
    status: Optional[str] = None,
    offset: int = 0,
    limit: int = 10
):
    print("CURRENT USER:", user.id)
    now = datetime.now(timezone.utc)

    # 🔹 récupérer liens
    links = db.query(Link).filter(
        Link.user_id == user.id,
        Link.workspace_id == workspace_id
    ).all()

    # 🔹 récupérer paiements
    payments = (
        db.query(Payment)
        .options(joinedload(Payment.link))
        .filter(Payment.user_id == user.id,Payment.workspace_id == workspace_id)
        .all()
    )
    print("STATUS DEMANDÉ:", status)

    if status and status != "Tous":
        payments = [p for p in payments if p.status == status]
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

    print("FINAL TRANSACTIONS:", len(transactions))
    for t in transactions:
       print(t)
    
    return transactions



@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)

    start_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # 🔹 Récupération des données
    links = db.query(Link).filter(
        Link.user_id == user.id,
        Link.created_at >= start_month
    ).all()

    payments = (
      db.query(Payment)
      .filter(Payment.user_id == user.id)
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
        Withdrawal.user_id == user.id,
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

