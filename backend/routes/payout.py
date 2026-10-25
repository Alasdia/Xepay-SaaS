from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from backend.database import get_db
from backend.models import Wallet, Withdrawal, WithdrawRequest, WalletTransaction, WebhookDeliveryLog, Webhook, RefundRequest
from backend.services.webhook_service import send_webhook_event
from backend.middleware.authorization import require_pro_or_business, require_capability
from backend.models import WorkspaceUser
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from sqlalchemy import func, case, and_, or_
from backend.models import Payment, Link, UserDB, Profile, generate_prefixed_id
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

    # Agrégats calculés côté SQL (une seule ligne renvoyée par Postgres, pas
    # un .all() qui rapatrie chaque transaction en mémoire Python) : seul
    # moyen de rester performant quand l'historique d'un wallet atteint des
    # millions/milliards de lignes. fee_total réutilise fee_amount, déjà
    # posé sur chaque dépôt par les webhooks Stripe — aucun appel
    # supplémentaire (ni HTTP, ni Stripe) n'est nécessaire pour l'obtenir.
    # status == "success" est requis ici : un remboursement (webhook
    # charge.refunded, paiement.py) ne crée pas une ligne "sortie" séparée,
    # il repasse directement le statut de CETTE ligne de dépôt à "refunded"
    # (et décrémente wallet.balance en parallèle). Sans ce filtre, le dépôt
    # remboursé restait compté dans unlocked_deposits/locked_amount comme
    # s'il était toujours valide — le remboursement n'était alors jamais
    # déduit du solde affiché ici (déjà correct sur /wallet/breakdown, qui
    # filtre status=="success" depuis le départ).
    is_deposit = and_(WalletTransaction.type == "deposit", WalletTransaction.status == "success")
    is_unlocked = or_(
        WalletTransaction.available_at.is_(None),
        WalletTransaction.available_at <= now,
    )
    is_locked = and_(WalletTransaction.available_at.isnot(None), WalletTransaction.available_at > now)

    agg = db.query(
        func.coalesce(
            func.sum(case((and_(is_deposit, is_unlocked), WalletTransaction.amount))), 0
        ).label("unlocked_deposits"),
        func.coalesce(
            func.sum(case((and_(is_deposit, is_locked), WalletTransaction.amount))), 0
        ).label("locked_amount"),
        func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            WalletTransaction.type == "withdraw",
                            WalletTransaction.status.in_(("pending", "processing", "success")),
                        ),
                        WalletTransaction.amount,
                    )
                )
            ),
            0,
        ).label("withdrawn_total"),
        func.coalesce(
            func.sum(case((is_deposit, WalletTransaction.fee_amount))),
            0,
        ).label("fee_total"),
        func.min(case((and_(is_deposit, is_locked), WalletTransaction.available_at))).label("next_available_at"),
    ).filter(WalletTransaction.user_id == owner_id).one()

    available_amount = agg.unlocked_deposits - agg.withdrawn_total

    # Liste détaillée bornée : à ce volume, afficher *chaque* dépôt encore
    # verrouillé n'a pas de sens pour l'utilisateur et ferait grossir la
    # réponse sans limite. L'index partiel (user_id, available_at) WHERE
    # type='deposit' permet ce tri + LIMIT en O(log n) plutôt qu'un scan.
    locked_rows = (
        db.query(WalletTransaction.amount, WalletTransaction.available_at, WalletTransaction.source)
        .filter(
            WalletTransaction.user_id == owner_id,
            WalletTransaction.type == "deposit",
            WalletTransaction.status == "success",
            WalletTransaction.available_at.isnot(None),
            WalletTransaction.available_at > now,
        )
        .order_by(WalletTransaction.available_at.asc())
        .limit(50)
        .all()
    )

    return {
        "available": available_amount,
        "pending_withdrawal": wallet.pending,
        "locked_amount": agg.locked_amount,
        "next_available_at": agg.next_available_at,
        "locked_items": [
            {"amount": row.amount, "available_at": row.available_at, "source": row.source}
            for row in locked_rows
        ],
        "fee_total": float(agg.fee_total or 0),
    }


WALLET_SOURCE_LABELS = {
    "payment_link": "Liens de paiement",
    "invoice": "Factures",
    "subscription": "Abonnements",
}


@router.get("/wallet/breakdown")
def get_wallet_breakdown(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    """Solde principal décortiqué par source de revenu : chaque sous-solde
    est la somme des dépôts réussis d'une source (`WalletTransaction.source`
    — liens de paiement, factures, abonnements...), et leur somme totale
    reconstitue le solde principal cumulé. Les sorties (retraits, transferts)
    ne sont pas ventilées ici : elles réduisent le solde disponible affiché
    dans la vue "Solde global", pas cette répartition par source de revenu.

    fee_total et next_available_at sont calculés dans cette même requête
    groupée (fee_amount et available_at sont déjà posés sur chaque ligne par
    les webhooks Stripe) : aucun appel réseau ni aggregat Python supplémentaire,
    donc un coût identique quel que soit le volume de transactions déjà
    accumulé."""
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    now = datetime.now(timezone.utc)

    # available_amount/locked_amount par source : même case-based
    # aggregation que /wallet/me (is_unlocked/is_locked), mais groupée par
    # source — pure répartition par date de disponibilité des dépôts de
    # cette source, sans déduire les retraits (jamais liés à une source
    # précise, comme le "total" cumulé ci-dessous ne le fait déjà pas).
    is_unlocked = or_(
        WalletTransaction.available_at.is_(None),
        WalletTransaction.available_at <= now,
    )
    is_locked = and_(WalletTransaction.available_at.isnot(None), WalletTransaction.available_at > now)

    rows = (
        db.query(
            WalletTransaction.source,
            func.sum(WalletTransaction.amount).label("amount"),
            func.coalesce(
                func.sum(case((is_unlocked, WalletTransaction.amount))), 0
            ).label("available_amount"),
            func.coalesce(
                func.sum(case((is_locked, WalletTransaction.amount))), 0
            ).label("locked_amount"),
            func.coalesce(func.sum(WalletTransaction.fee_amount), 0).label("fee_total"),
            func.min(case((is_locked, WalletTransaction.available_at))).label("next_available_at"),
        )
        .filter(
            WalletTransaction.user_id == owner_id,
            WalletTransaction.type == "deposit",
            WalletTransaction.direction == "in",
            WalletTransaction.status == "success",
        )
        .group_by(WalletTransaction.source)
        .all()
    )

    sub_balances = [
        {
            "source": row.source,
            "label": WALLET_SOURCE_LABELS.get(row.source, row.source),
            "amount": float(row.amount or 0),
            "available_amount": float(row.available_amount or 0),
            "locked_amount": float(row.locked_amount or 0),
            "fee_total": float(row.fee_total or 0),
            "next_available_at": row.next_available_at,
        }
        for row in rows
    ]

    return {
        "total": sum(item["amount"] for item in sub_balances),
        "fee_total": sum(item["fee_total"] for item in sub_balances),
        "sub_balances": sub_balances,
    }


@router.get("/wallet/history")
def get_wallet_history(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    ),
    limit: int = 100,
    offset: int = 0
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    txs = db.query(WalletTransaction)\
        .filter(WalletTransaction.user_id == owner_id)\
        .order_by(WalletTransaction.created_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()
    references = [tx.reference for tx in txs]
    withdrawals_by_ref = {
        wd.reference: wd
        for wd in db.query(Withdrawal).filter(Withdrawal.reference.in_(references)).all()
    } if references else {}
    transactions_data = []
    for tx in txs:
        wd = withdrawals_by_ref.get(tx.reference)
        display_status = wd.status if wd else tx.status
        transactions_data.append({
            "id": wd.id if wd else tx.id,
            "withdrawal_id": wd.id if wd else None,
            "amount": tx.amount,
            "direction": tx.direction,
            "type": tx.type,
            "status": display_status,
            "description": tx.description,
            "reference": tx.reference,
            "refund_id": tx.refund_id,
            "source": tx.source,
            "created_at": tx.created_at.isoformat(),
        })
    return {"transactions": transactions_data}

@router.post("/withdraw")
def withdraw(
    req: WithdrawRequest, 
    db: Session = Depends(get_db), 
    membership: WorkspaceUser = Depends(require_capability("withdraw_funds"))
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

    ref = generate_prefixed_id("wd")

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
    id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("withdraw_funds"))
):
    wd = db.query(Withdrawal)\
        .filter(Withdrawal.id == id, Withdrawal.user_id == membership.workspace_id)\
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
    user = db.query(UserDB).filter(UserDB.id == wd.user_id).first()
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(400, "Stripe account not connected")
    account = stripe.Account.retrieve(profile.stripe_account_id)
    if not account["payouts_enabled"]:
        raise HTTPException(400, "Payouts not enabled")
    USD_RATE = 577.325
    usd_amount = wd.amount / USD_RATE
    amount_cents = int(usd_amount * 100)
    if amount_cents <= 0:
        raise HTTPException(400, "Amount too small")
    balance = stripe.Balance.retrieve(
        stripe_account=profile.stripe_account_id
    )
    instant_available = sum(b["amount"] for b in balance["instant_available"])
    if instant_available < amount_cents:
        raise HTTPException(400, "Insufficient Stripe balance")
    wd.status = "processing"
    db.flush()
    try:
        payout = stripe.Payout.create(amount=amount_cents, currency="usd", stripe_account=profile.stripe_account_id, method="instant")
        wd.status = payout.status
        wd.stripe_payout_id = payout.id
        wd.payout_method = payout.method
        if payout.arrival_date:
            wd.payout_arrival_date = datetime.fromtimestamp(payout.arrival_date, tz=timezone.utc)
        wallet.pending -= wd.amount
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first()
        if tx:
            tx.status = payout["status"]
            tx.description = f"Retrait {payout['status']}"
    except Exception as e:
        wd.status = "failed"
        wd.payout_failure_message = getattr(e, "user_message", None) or str(e)
        wallet.pending -= wd.amount
        wallet.available += wd.amount
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first()
        if tx:
            tx.status = "failed"
            tx.description = "Retrait échoué"
    wd.processed_at = datetime.now(timezone.utc)
    db.commit()
    background_tasks.add_task(send_webhook_event, wd.user_id, "withdrawal.done", {
        "withdrawal_id": wd.id,
        "amount": wd.amount,
        "currency": "XOF",
        "status": wd.status,
        "reference": wd.reference,
        "stripe_payout_id": wd.stripe_payout_id
    })
    return {"status": wd.status}

@router.get("/withdrawals")
def get_withdrawals(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("withdraw_funds"))
):
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(
        Profile.user_id == owner_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=400,
            detail="Stripe account not connected"
        )
    try:
        payouts = stripe.Payout.list(
            limit=100,
            stripe_account=profile.stripe_account_id
        )
        return [
            payout.to_dict()
            for payout in payouts.data
        ]
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=502,
            detail=str(e)
        )

@router.post("/payments/{payment_id}/refund")
def refund_payment(
    payment_id: str,
    req: RefundRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.user_id == owner_id
        )
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Paiement introuvable"
        )
    if payment.status != "paid":
        raise HTTPException(
            status_code=400,
            detail="Ce paiement n'est pas remboursable dans son état actuel"
        )
    if not payment.stripe_payment_intent_id:
        raise HTTPException(
            status_code=400,
            detail="PaymentIntent Stripe introuvable"
        )
    profile = (
        db.query(Profile)
        .filter(Profile.user_id == owner_id)
        .first()
    )
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=400,
            detail="Compte Stripe Connect introuvable"
        )
    # Le paiement par lien est un destination charge : le PaymentIntent vit
    # côté plateforme (pas de stripe_account). Facture/abonnement est un
    # direct charge : il vit sur le compte connecté (stripe_account requis,
    # sinon Stripe répond "no such payment_intent"). payment.link_id n'est
    # posé que pour le paiement par lien (paiement.py) — seul signal fiable
    # pour distinguer les deux ici, Payment n'a pas de colonne "source".
    stripe_kwargs = {} if payment.link_id else {"stripe_account": profile.stripe_account_id}
    try:
        intent = stripe.PaymentIntent.retrieve(
            payment.stripe_payment_intent_id, **stripe_kwargs
        )
        if intent.status != "succeeded":
            raise HTTPException(
                status_code=400,
                detail="Le paiement Stripe n'est pas confirmé"
            )
        charge_id = intent.latest_charge
        if not charge_id:
            raise HTTPException(
                status_code=400,
                detail="Charge Stripe introuvable"
            )
        charge = stripe.Charge.retrieve(charge_id, **stripe_kwargs)
        if charge.refunded:
            raise HTTPException(
                status_code=400,
                detail="Ce paiement est déjà intégralement remboursé"
            )
        refunds = stripe.Refund.list(
            charge=charge_id,
            limit=100,
            **stripe_kwargs,
        )
        refunded_amount = sum(
            refund.amount for refund in refunds.data
            if refund.status != "failed" and refund.status != "canceled"
        )
        remaining = charge.amount - refunded_amount
        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail="Aucun montant restant à rembourser"
            )
        amount = remaining if req.amount is None else req.amount
        if amount > remaining:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Le montant dépasse le montant remboursable",
                    "remaining_amount": remaining,
                    "currency": charge.currency
                }
            )
        refund_params = {
            "payment_intent": payment.stripe_payment_intent_id,
            "amount": amount,
            "reason": req.reason or "requested_by_customer",
        }
        if payment.link_id:
            # reverse_transfer (annule le Transfer vers le compte connecté)
            # et refund_application_fee (récupère la commission Xepay déjà
            # transférée) ne s'appliquent qu'aux destination charges
            # (paiement par lien). Les direct charges (facture/abonnement)
            # n'ont pas de Transfer séparé (voir process_invoice_paid_event)
            # — Stripe rejette l'appel si on les passe quand même, ce qui
            # faisait échouer tout remboursement sur ces deux flux.
            refund_params["reverse_transfer"] = True
            refund_params["refund_application_fee"] = True
        import logging
        from decimal import Decimal

        logger = logging.getLogger(__name__)

        refund = stripe.Refund.create(
            **refund_params,
            idempotency_key=f"xepay-refund-{payment.id}-{uuid.uuid4()}",
            **stripe_kwargs,
        )
        logger.warning(
            "refund_payment : Refund.create a renvoyé id=%s status=%s pour payment_id=%s",
            refund.id, refund.status, payment.id,
        )
        # stripe.Refund.create() n'arrive ici que si Stripe a accepté le
        # remboursement (toute vraie erreur lève stripe.error.StripeError,
        # attrapé plus bas) : seuls "failed"/"canceled" signalent un rejet
        # explicite malgré une réponse sans exception. On ne devine plus la
        # liste exacte des statuts "ok" (vu en prod : se limiter à
        # "succeeded" laissait passer d'autres valeurs sans jamais mettre
        # à jour Payment/WalletTransaction).
        if refund.status not in ("failed", "canceled"):
            charge = stripe.Charge.retrieve(charge_id, **stripe_kwargs)
            logger.warning(
                "refund_payment : charge.refunded=%s (amount_refunded=%s/%s) pour payment_id=%s",
                charge.refunded, getattr(charge, "amount_refunded", None), charge.amount, payment.id,
            )
            if charge.refunded:
                payment.status = "refunded"
            else:
                payment.status = "partially_refunded"

            if not payment.link_id:
                # Direct charge (facture/abonnement) : reverse_transfer/
                # refund_application_fee (qui auraient fait ça tout seuls)
                # ne s'appliquent qu'aux destination charges. Sans ce
                # remboursement explicite, Stripe débite le compte connecté
                # du montant BRUT du remboursement, alors qu'il n'avait reçu
                # net que gross - application_fee à l'encaissement : la
                # commission Xepay n'étant jamais rendue, le compte connecté
                # ressort perdant de ce montant (le "solde négatif" observé).
                # Proportionnel au montant réellement remboursé (amount),
                # comme le fait Stripe lui-même pour refund_application_fee
                # sur un remboursement partiel d'une destination charge.
                fee_id = getattr(charge, "application_fee", None)
                app_fee_amount = getattr(charge, "application_fee_amount", None)
                if fee_id and app_fee_amount and charge.amount:
                    fee_refund_amount = int(app_fee_amount * amount / charge.amount)
                    if fee_refund_amount > 0:
                        try:
                            stripe.ApplicationFee.create_refund(
                                fee_id, amount=fee_refund_amount
                            )
                        except stripe.error.StripeError:
                            logger.exception(
                                "ApplicationFee.create_refund a échoué pour fee_id=%s "
                                "(payment_id=%s, montant=%s) : la commission Xepay n'a "
                                "pas été rendue au compte connecté",
                                fee_id, payment.id, fee_refund_amount,
                            )

            # Répercute sur le wallet : WalletTransaction.reference diffère
            # selon le flux (payment_intent_id pour le paiement par lien,
            # invoice_id pour facture/abonnement — charge.invoice n'existe
            # plus depuis l'API basil, voir process_invoice_paid_event) donc
            # on tente la correspondance directe d'abord, puis on résout
            # l'invoice au besoin. Même simplification que le webhook
            # charge.refunded de paiement.py : un remboursement, complet ou
            # partiel, déduit tout le montant crédité et marque la ligne
            # "refunded" (pas de comptabilité au prorata ici, pour rester
            # cohérent avec ce que fait déjà ce webhook pour le même cas).
            tx = db.query(WalletTransaction).filter(
                WalletTransaction.reference == payment.stripe_payment_intent_id
            ).first()
            if not tx and not payment.link_id:
                try:
                    invoice_payments = stripe.InvoicePayment.list(
                        payment={
                            "type": "payment_intent",
                            "payment_intent": payment.stripe_payment_intent_id,
                        },
                        stripe_account=profile.stripe_account_id,
                    )
                except stripe.error.StripeError:
                    logger.exception(
                        "InvoicePayment.list a échoué pour payment_intent=%s (payment_id=%s)",
                        payment.stripe_payment_intent_id, payment.id,
                    )
                    invoice_payments = None
                if invoice_payments and invoice_payments.data:
                    invoice_id = invoice_payments.data[0].invoice
                    tx = db.query(WalletTransaction).filter(
                        WalletTransaction.reference == invoice_id
                    ).first()
                    if not tx:
                        logger.warning(
                            "Aucune WalletTransaction pour reference=%s "
                            "(résolue depuis payment_intent=%s, payment_id=%s)",
                            invoice_id, payment.stripe_payment_intent_id, payment.id,
                        )
                else:
                    logger.warning(
                        "Aucun InvoicePayment trouvé pour payment_intent=%s (payment_id=%s) "
                        "-> wallet non mis à jour pour ce remboursement",
                        payment.stripe_payment_intent_id, payment.id,
                    )

            if tx and tx.status != "refunded":
                tx.status = "refunded"
                tx.refund_id = refund.id
                tx_wallet = db.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
                if tx_wallet:
                    tx_wallet.balance = Decimal(str(tx_wallet.balance or 0)) - Decimal(str(tx.amount))
            elif not tx:
                logger.warning(
                    "refund_payment : impossible de retrouver la WalletTransaction "
                    "pour payment_id=%s, wallet.balance non ajusté",
                    payment.id,
                )

            logger.warning(
                "refund_payment : avant commit, payment_id=%s payment.status=%s "
                "tx_found=%s tx.status=%s",
                payment.id, payment.status, bool(tx), tx.status if tx else None,
            )
            db.commit()
            db.refresh(payment)
            logger.warning(
                "refund_payment : après commit+refresh, payment_id=%s payment.status=%s",
                payment.id, payment.status,
            )
        else:
            logger.warning(
                "refund_payment : Refund.create a renvoyé status=%s (rejeté), "
                "payment_id=%s inchangé",
                refund.status, payment.id,
            )

        return {
            "payment_id": payment.id,
            "refund_id": refund.id,
            "amount": refund.amount,
            "currency": refund.currency,
            "status": refund.status,
            "payment_status": payment.status,
            "message": "Demande de remboursement transmise à Stripe"
        }
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=502,
            detail=getattr(e, "user_message", None) or str(e)
        )

@router.get("/withdrawals/{withdrawal_id}")
def get_withdrawal_detail(
    withdrawal_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_pro_or_business),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)

    w = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id,
        Withdrawal.user_id == owner_id
    ).first()

    if not w:
        raise HTTPException(status_code=404, detail="Retrait introuvable")

    return {
        "type": "withdraw",
        "withdrawal_id": w.id,
        "label": f"Retrait #{w.reference}",
        "amount": w.amount,
        "currency": "XOF",
        "status": w.status,
        "date": w.created_at.isoformat() if w.created_at else None,
        "details": {
            "reference": w.reference,
            "stripe_payout_id": w.stripe_payout_id,
            "payout_method": w.payout_method,
            "payout_arrival_date": w.payout_arrival_date.isoformat() if w.payout_arrival_date else None,
            "payout_failure_message": w.payout_failure_message,
            "processed_at": w.processed_at.isoformat() if w.processed_at else None
        }
    }

@router.post("/withdrawals/{withdrawal_id}/cancel")
def cancel_withdrawal(
    withdrawal_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: str = Header(None, alias="X-Workspace-Id")
):
    owner_id = get_workspace_owner_id(current_user, workspace_id, db)
    wd = (db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id, Withdrawal.user_id == owner_id).first())
    if not wd:
        raise HTTPException(status_code=404, detail="Retrait introuvable.")
    if wd.status != "pending":
        raise HTTPException(status_code=400, detail=f"Impossible d'annuler ce retrait car son statut est déjà '{wd.status}'.")
    if not wd.stripe_payout_id:
        wd.status = "canceled"
        wd.processed_at = datetime.now(timezone.utc)
        wallet = (db.query(Wallet).filter(Wallet.id == wd.wallet_id).first())
        if not wallet:
            raise HTTPException(status_code=500, detail="Wallet introuvable.")
        wallet.pending -= wd.amount
        wallet.available += wd.amount
        if wallet.pending < 0:
            wallet.pending = 0
        tx = (db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first())
        if tx:
            tx.status = "canceled"
            tx.description = "Retrait annulé"
        db.commit()
        return {"success": True, "message": "Retrait annulé et fonds recrédités."}
    try:
        payout = stripe.Payout.retrieve(
            wd.stripe_payout_id
        )
        if payout.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Ce retrait ne peut plus être annulé. "
                    f"Statut Stripe : {payout.status}"
                )
            )
        stripe.Payout.cancel(
            wd.stripe_payout_id
        )
        wd.status = "canceled"
        wd.processed_at = datetime.now(timezone.utc)
        wallet = (
            db.query(Wallet)
            .filter(Wallet.id == wd.wallet_id)
            .first()
        )
        if not wallet:
            raise HTTPException(status_code=500, detail="Wallet introuvable.")
        wallet.pending -= wd.amount
        wallet.available += wd.amount
        if wallet.pending < 0:
            wallet.pending = 0
        tx = (db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first())
        if tx:
            tx.status = "canceled"
            tx.description = "Retrait annulé"
        db.commit()
        return {"success": True, "message": "Retrait annulé avec succès et fonds recrédités."}
    except stripe.error.StripeError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erreur Stripe : {e.user_message or str(e)}")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")