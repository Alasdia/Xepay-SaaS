from fastapi import APIRouter, HTTPException
from backend.models import Payment, PaymentUpdate, Withdrawal
from backend.database import engine, get_db
from datetime import datetime, timezone
from sqlalchemy import text
from backend.models import PaymentCreate, PaymentResponse, Payment, Withdrawal, PaymentUpdate
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from backend.middleware.authorization import require_member, require_pro_or_business
from backend.models import WorkspaceUser
from datetime import timedelta
from backend.models import Payment, Link
from fastapi import Header
import os
from typing import Optional
from sqlalchemy.orm import joinedload

router = APIRouter()

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
    min_amount: float = None,
    max_amount: float = None,
    currency: str = None,
    payment_method: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    user=Depends(require_pro_or_business),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    items = []

    if type in (None, "payment"):
        q = db.query(Payment).filter(Payment.user_id == owner_id)
        if status:
            # Liste de statuts séparés par des virgules (ex: KPI "Remboursés"
            # = refunded,partially_refunded) : comportement à un seul statut
            # inchangé (toujours une égalité exacte).
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            q = q.filter(
                Payment.status.in_(statuses) if len(statuses) > 1
                else Payment.status == status
            )
        # Filtres propres à la page Paiements (Montant/Devise/Moyen de
        # paiement/Date), jamais envoyés par les vues Retraits/Transferts.
        if min_amount is not None: q = q.filter(Payment.amount >= min_amount)
        if max_amount is not None: q = q.filter(Payment.amount <= max_amount)
        if currency: q = q.filter(Payment.currency == currency.upper())
        if payment_method:
            like = f"%{payment_method}%"
            q = q.filter(
                Payment.card_brand.ilike(like) | Payment.payment_method_type.ilike(like)
            )
        if start_date:
            q = q.filter(Payment.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            q = q.filter(Payment.created_at <= datetime.fromisoformat(end_date) + timedelta(days=1))
        payments_list = q.all()
        # Resout link_id -> URL publique complete du lien (pas reconstructible
        # depuis l'ID seul : Link.token est un hash, Link.url est stocke tel
        # quel a la creation) pour l'afficher dans les metadata du detail.
        link_ids = {p.link_id for p in payments_list if p.link_id}
        link_urls_by_id = (
            dict(db.query(Link.id, Link.url).filter(Link.id.in_(link_ids)).all())
            if link_ids else {}
        )
        for p in payments_list:
            # application_fee_requested = ApplicationFee.balance_transaction.
            # amount (montant réellement réglé sur le solde plateforme,
            # rempli par l'event application_fee.created - voir routes/
            # webhook/paiement.py), toujours dans la même devise que
            # Payment.amount/currency ; fee_amount (ApplicationFee.amount)
            # ne l'est PAS (devise d'origine du lien, ex: EUR alors que
            # Payment.currency vaut "USD"). On privilégie donc
            # application_fee_requested, avec repli sur fee_amount pour les
            # paiements de factures/abonnements (qui ne renseignent pas ce
            # nouveau champ) et les paiements de liens antérieurs à ce fix.
            #
            # C'est la commission GLOBALE (StripeFee + part Xepay réelle),
            # pas la part Xepay seule - confirmé par Stripe ("The
            # application fee amount minus the Stripe fees remains in your
            # platform account's balance"). La part Xepay réelle =
            # commission_xepay - p.stripe_fee_amount (non exposée comme
            # champ séparé, calculable à l'affichage si besoin).
            commission_xepay = (
                p.application_fee_requested
                if p.application_fee_requested is not None
                else p.fee_amount
            )
            # Valeur stockée telle quelle (voir routes/webhook/paiement.py :
            # brut - commission_xepay, càd exactement ce que Stripe règle
            # réellement au compte connecté - stripe_fee_amount n'est PAS
            # soustrait en plus puisqu'il est déjà inclus dans
            # commission_xepay ci-dessus).
            amount_net_merchant = p.balance_transaction_net
            # stripe_account_id retire : deja affiche tel quel dans le detail
            # (p.stripe_account_id ci-dessous), redondant dans les metadata.
            # link_id remplace par l'URL complete du lien quand elle est
            # connue (plus utile a l'affichage que l'ID interne).
            metadata = dict(p.stripe_metadata) if p.stripe_metadata else None
            if metadata:
                metadata.pop("stripe_account_id", None)
                if metadata.get("link_id") in link_urls_by_id:
                    metadata["link_id"] = link_urls_by_id[metadata["link_id"]]
            items.append({
                "type": "payment",
                "payment_id": p.id,
                "label": p.client_email,
                "amount": p.amount_local or p.amount,
                "currency": p.currency_local or p.currency,
                "status": p.status,
                "date": p.created_at,
                "client_email": p.client_email,
                "amount_gross": p.amount,
                "currency_gross": p.currency,
                "commission_xepay": commission_xepay,
                "stripe_fee": p.stripe_fee_amount,
                "amount_net_merchant": amount_net_merchant,
                "payment_method_type": p.payment_method_type,
                "source": p.source,
                "details": {
                    "amount_origin": p.amount,
                    "currency_origin": p.currency,
                    "rate_used": p.rate_used,
                    "stripe_session_id": p.stripe_session_id,
                    "stripe_account_id": p.stripe_account_id,
                    "stripe_payment_intent_id": p.stripe_payment_intent_id,
                    "link_id": p.link_id,
                    "fee_amount": p.fee_amount,
                    "available_at": p.available_at.isoformat() if p.available_at else None,
                    "transfer_amount": p.transfer_amount,
                    "payment_method_id": p.payment_method_id,
                    "payment_method_type": p.payment_method_type,
                    "card_brand": p.card_brand,
                    "card_last4": p.card_last4,
                    "card_exp_month": p.card_exp_month,
                    "card_exp_year": p.card_exp_year,
                    "metadata": metadata
                }
            })
    if type in (None, "withdraw"):
        q = db.query(Withdrawal).filter(Withdrawal.user_id == owner_id)
        if status: q = q.filter(Withdrawal.status == status)
        for w in q.all():
            items.append({
                "type": "withdraw",
                "withdrawal_id": w.id,
                "label": f"Retrait #{w.reference}",
                "amount": w.amount,
                "currency": "XOF",
                "status": w.status,
                "date": w.created_at,
                "reference": w.reference,
                "payout_method": w.payout_method,
                "payout_arrival_date": w.payout_arrival_date.isoformat() if w.payout_arrival_date else None,
                "payout_failure_message": w.payout_failure_message,
                "details": {
                    "reference": w.reference,
                    "stripe_payout_id": w.stripe_payout_id,
                    "payout_method": w.payout_method,
                    "payout_arrival_date": w.payout_arrival_date.isoformat() if w.payout_arrival_date else None,
                    "payout_failure_message": w.payout_failure_message,
                    "processed_at": w.processed_at.isoformat() if w.processed_at else None
                }
            })
    items.sort(key=lambda x: x["date"], reverse=True)
    paged = items[offset:offset+limit]

    for it in paged:
        it["date"] = it["date"].isoformat() if it["date"] else None

    return paged

@router.get("/payments-summary")
def get_payments_summary(
    db: Session = Depends(get_db),
    user=Depends(require_pro_or_business),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    """Résumé Xepay (Commission Xepay / Frais Stripe / Net marchand) affiché
    au-dessus du composant Stripe ConnectPayments natif, qui ne connaît rien
    de cette décomposition propre à Xepay. Calculé à partir des `Payment`
    déjà stockés en base — aucun appel Stripe, même formule que /activity."""
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    payments = db.query(Payment).filter(Payment.user_id == owner_id).all()

    # application_fee_requested en priorité (même devise que p.amount),
    # repli sur fee_amount (factures/abonnements, ou liens antérieurs à ce
    # fix) — voir le commentaire équivalent dans /activity ci-dessus.
    def commission_for(p):
        return p.application_fee_requested if p.application_fee_requested is not None else p.fee_amount

    commission_xepay = sum(
        commission_for(p)
        for p in payments
        if commission_for(p) is not None
    )
    stripe_fee = sum(p.stripe_fee_amount for p in payments if p.stripe_fee_amount is not None)

    # commission_xepay ci-dessus est la commission GLOBALE (StripeFee + part
    # Xepay réelle, voir le commentaire équivalent dans /activity) - net
    # marchand = brut - cette commission globale, jamais - stripe_fee en
    # plus. Valeur stockée telle quelle (balance_transaction_net), jamais
    # redérivée ici.
    amount_net_merchant = sum(
        p.balance_transaction_net
        for p in payments
        if p.balance_transaction_net is not None
    )

    return {
        "commission_xepay": commission_xepay,
        "stripe_fee": stripe_fee,
        "amount_net_merchant": amount_net_merchant,
        "currency": payments[0].currency if payments else "USD"
    }

@router.get("/payments/{payment_id}")
def get_payment_detail(
    payment_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_pro_or_business),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)

    p = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == owner_id
    ).first()

    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")

    return {
        "type": "payment",
        "payment_id": p.id,
        "label": p.client_email,
        "amount": p.amount_local or p.amount,
        "currency": p.currency_local or p.currency,
        "status": p.status,
        "date": p.created_at.isoformat() if p.created_at else None,
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
            "transfer_destination": p.transfer_destination,
            "transfer_reversed": p.transfer_reversed,
            "transfer_amount_reversed": p.transfer_amount_reversed,
            "payment_method_id": p.payment_method_id,
            "payment_method_type": p.payment_method_type,
            "card_brand": p.card_brand,
            "card_last4": p.card_last4,
            "card_exp_month": p.card_exp_month,
            "card_exp_year": p.card_exp_year
        }
    }
