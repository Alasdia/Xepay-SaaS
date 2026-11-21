from fastapi import APIRouter
import stripe
from fastapi.responses import RedirectResponse
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.models import Link
from fastapi import Depends
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from fastapi import Header
from backend.database import get_db, SessionLocal
from backend.models import LinkCreate
from backend.models import Link, Payment
from backend.middleware.authorization import require_capability
from backend.models import Link, WorkspaceUser, generate_prefixed_id
from backend.services.stripe_service import create_checkout_session
from backend.routes.webhook.stripe import _emails_by_user_id, _enrich_metadata
from backend.models import Payment
from backend.models import UserDB
from fastapi import HTTPException
from backend.auth import get_current_user
import hashlib
import os
from backend.models import LinkDashboardResponse
from backend.models import FlexibleLinkCheckout

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Domaine du backend tel qu'il est réellement joignable publiquement (route
# /pay/{token} incluse) - jamais en dur, pour pouvoir basculer vers une
# autre instance (ex: AWS pendant une panne Railway) sans recasser les
# liens déjà générés avec l'ancien domaine à chaque changement.
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://api.xepay.finance")

# Durée de validité par défaut d'un lien à usage unique (max_uses=1) quand
# le marchand n'en précise pas (LinkCreate.expires_in_minutes) - un lien
# multi-usage (quota ou illimité) n'expire jamais par défaut, voir
# create_link.
ONE_TIME_LINK_DEFAULT_EXPIRY_MINUTES = 30

router = APIRouter()


def _resolve_link_status(successful_count: int, link: Link, now: datetime) -> str:
    """Statut d'un lien à partir du nombre de paiements réussis déjà
    reçus - un lien épuisé (quota atteint, ou usage unique déjà payé)
    reste "paid"/"exhausted" même après sa date d'expiration, jamais
    rétrogradé en "expired" (la vraie raison pour laquelle il n'est plus
    payable, c'est qu'il a rempli son rôle, pas le temps écoulé)."""
    if link.max_uses is not None and successful_count >= link.max_uses:
        return "paid" if link.max_uses == 1 else "exhausted"
    if link.expires_at and link.expires_at < now:
        return "expired"
    return "pending"

@router.post("/links")
def create_link(
    data: LinkCreate,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    membership: WorkspaceUser = Depends(require_capability("create_payment_links"))

):
    if data.amount is not None and (data.min_amount is not None or data.max_amount is not None):
        raise HTTPException(status_code=400, detail="Un lien à montant fixe ne peut pas avoir de bornes min/max")
    if data.amount is None and data.min_amount is not None and data.max_amount is not None and data.min_amount > data.max_amount:
        raise HTTPException(status_code=400, detail="Le montant minimum doit être inférieur ou égal au montant maximum")
    if data.max_uses is not None and data.max_uses < 1:
        raise HTTPException(status_code=400, detail="max_uses doit être supérieur ou égal à 1")

    owner_id = membership.workspace_id
    internal_id = generate_prefixed_id("lk")
    if data.expires_in_minutes is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=data.expires_in_minutes)
    elif data.max_uses == 1:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ONE_TIME_LINK_DEFAULT_EXPIRY_MINUTES)
    else:
        expires_at = None
    raw_token = generate_prefixed_id("pl")
    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
    link = Link(
        id=internal_id,
        token=hashed_token,
        user_id=owner_id,
        email=user.email,
        name=data.name.strip() if data.name else "Lien de paiement",
        amount=data.amount,
        currency=data.currency,
        url=f"{PUBLIC_API_URL}/pay/{raw_token}",
        created_at=datetime.now(timezone.utc),
        active=True,
        expires_at=expires_at,
        source=getattr(data, "source", "dashboard"),
        max_uses=data.max_uses,
        min_amount=data.min_amount,
        max_amount=data.max_amount,
        link_metadata={
            "user_id": membership.user_id,
            "workspace_id": membership.workspace_id,
            "xepay_type": "payment_link",
        },
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.get("/links/dashboard")
def get_dashboard_links(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    now = datetime.now(timezone.utc)
    links = (
        db.query(Link)
        .filter(Link.user_id == owner_id)
        .filter(Link.source == "dashboard")
        .filter(Link.archived == False)
        .filter(Link.deleted == False)
        .order_by(Link.created_at.desc())
        .limit(10)
        .all()
    )
    start_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    paid_links_count = db.query(Payment)\
        .join(Link, Payment.link_id == Link.id)\
        .filter(Link.user_id == owner_id)\
        .filter(Payment.status == "paid")\
        .filter(Payment.created_at >= start_month)\
        .count()
    link_ids = [link.id for link in links]
    successful_counts = {}
    if link_ids:
        for p in (
            db.query(Payment)
            .filter(Payment.link_id.in_(link_ids), Payment.status == "paid")
            .all()
        ):
            successful_counts[p.link_id] = successful_counts.get(p.link_id, 0) + 1
    result = []
    for link in links:
        status = _resolve_link_status(successful_counts.get(link.id, 0), link, now)
        result.append({
            "id": link.id,
            "url": link.url,
            "status": status
        })
    return {"links": result, "paid_this_month": paid_links_count}

@router.get("/links", response_model=list[LinkDashboardResponse])
def get_links(
    limit: int = 10,
    offset: int = 0,
    # Filtres optionnels - utilisés par la vue "Liens de paiement", qui a
    # une sous-vue par combinaison usage x montant plutôt qu'une liste
    # unique mélangeant les 6 types (voir spa/views/liens.js). Absents,
    # le comportement est inchangé (tous les liens du workspace).
    usage: str = None,
    amount_mode: str = None,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    query = (
        db.query(Link)
        .filter(Link.user_id == owner_id)
        .filter(Link.source == "links")
        .filter(Link.deleted == False)
        .filter(Link.archived == False)
    )
    if usage == "unique":
        query = query.filter(Link.max_uses == 1)
    elif usage == "quota":
        query = query.filter(Link.max_uses.isnot(None), Link.max_uses > 1)
    elif usage == "unlimited":
        query = query.filter(Link.max_uses.is_(None))
    if amount_mode == "fixed":
        query = query.filter(Link.amount.isnot(None))
    elif amount_mode == "flexible":
        query = query.filter(Link.amount.is_(None))
    links = (
        query
        .order_by(Link.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    link_ids = [link.id for link in links]
    # Paiements réussis par lien, du plus récent au plus ancien - un lien
    # multi-usage peut en avoir plusieurs, le premier de chaque liste sert
    # à afficher le montant/devise réellement payés le plus récemment.
    successful_payments_by_link = {}
    if link_ids:
        for p in (
            db.query(Payment)
            .filter(Payment.link_id.in_(link_ids), Payment.status == "paid")
            .order_by(Payment.created_at.desc())
            .all()
        ):
            successful_payments_by_link.setdefault(p.link_id, []).append(p)
    emails_by_id = _emails_by_user_id(db, [link.link_metadata for link in links])
    result = []
    now = datetime.now(timezone.utc)
    for link in links:
        payments = successful_payments_by_link.get(link.id, [])
        successful_count = len(payments)
        status = _resolve_link_status(successful_count, link, now)
        last_payment = payments[0] if payments else None
        if last_payment:
            # amount/currency (jamais amount_local/currency_local) : le montant
            # brut réellement payé par le client, dans sa devise d'origine —
            # amount_local/currency_local sont le montant déjà net de la
            # commission Xepay et déjà converti en XOF pour le crédit wallet
            # (voir routes/webhook/paiement.py), pas ce qu'affiche ce champ
            # pour un lien pending/expired (link.amount/link.currency, bruts
            # aussi) : les utiliser ici produisait une incohérence de devise
            # et un montant ~6% trop bas selon le statut du lien.
            amount = last_payment.amount
            currency = last_payment.currency
            # Même devise que `amount` ci-dessus (USD, voir
            # process_checkout_session_payment) - toujours renseigné pour
            # un paiement par lien depuis l'introduction de la commission
            # dégressive (backend/services/commission_service.py), jamais
            # une estimation recalculée ici.
            fee_amount = last_payment.application_fee_requested
        else:
            # Lien pas encore payé : amount vaut None pour un lien à
            # montant flexible (voir LinkDashboardResponse), le frontend
            # affiche alors min_amount/max_amount à la place.
            amount = link.amount
            currency = link.currency
            fee_amount = None
        is_active = link.expires_at is None or link.expires_at > now
        result.append(LinkDashboardResponse(
            id=link.id,
            name=link.name,
            amount=amount,
            currency=currency,
            status=status,
            active=is_active,
            archived=link.archived,
            url=link.url,
            expires_at=link.expires_at,
            created_at=link.created_at,
            metadata=_enrich_metadata(link.link_metadata, emails_by_id),
            fee_amount=fee_amount,
            max_uses=link.max_uses,
            min_amount=link.min_amount,
            max_amount=link.max_amount,
            successful_payments_count=successful_count,
        ))
    return result

@router.get("/pay/{token}")
def get_payment(token: str):
    db = SessionLocal()
    hashed = hashlib.sha256(token.encode()).hexdigest()
    link = db.query(Link).filter(Link.token == hashed).first()
    if not link or link.deleted:
        return {"error": "invalid"}
    now = datetime.now(timezone.utc)
    successful_count = db.query(Payment).filter(Payment.link_id == link.id, Payment.status == "paid").count()
    if link.max_uses is not None and successful_count >= link.max_uses:
        return {"error": "already_paid" if link.max_uses == 1 else "exhausted"}
    if link.expires_at and link.expires_at < now:
        return {"error": "expired"}
    user = db.query(UserDB).filter(UserDB.id == link.user_id).first()
    if not user:
        return {"error": "user not found"}
    if link.amount is not None:
        url = create_checkout_session(db=db, mode="payment", email=user.email, user_id=user.id, amount=link.amount, link_id=link.id, currency=link.currency,)
        return RedirectResponse(url, status_code=303)
    # Montant flexible : le montant n'est pas connu tant que le client ne
    # l'a pas saisi - redirige vers la page publique dédiée plutôt que de
    # créer une session Stripe à l'aveugle (voir /pay/{token}/info et
    # POST /pay/{token}/checkout ci-dessous).
    return RedirectResponse(f"https://app.xepay.finance/pay-flexible.html?token={token}", status_code=303)


@router.get("/pay/{token}/info")
def get_payment_info(token: str, db: Session = Depends(get_db)):
    """Infos publiques nécessaires à pay-flexible.html pour afficher le
    formulaire de saisie du montant d'un lien à montant flexible."""
    hashed = hashlib.sha256(token.encode()).hexdigest()
    link = db.query(Link).filter(Link.token == hashed).first()
    if not link or link.deleted:
        return {"error": "invalid"}
    if link.amount is not None:
        return {"error": "not_flexible"}
    now = datetime.now(timezone.utc)
    successful_count = db.query(Payment).filter(Payment.link_id == link.id, Payment.status == "paid").count()
    if link.max_uses is not None and successful_count >= link.max_uses:
        return {"error": "already_paid" if link.max_uses == 1 else "exhausted"}
    if link.expires_at and link.expires_at < now:
        return {"error": "expired"}
    return {
        "name": link.name,
        "currency": link.currency,
        "min_amount": link.min_amount,
        "max_amount": link.max_amount,
    }


@router.post("/pay/{token}/checkout")
def create_flexible_checkout(token: str, data: FlexibleLinkCheckout, db: Session = Depends(get_db)):
    """Crée la session Stripe d'un lien à montant flexible, une fois le
    montant choisi par le client sur pay-flexible.html. Revalide tout
    (validité du lien, bornes min/max) côté serveur - jamais confiance
    dans ce qu'envoie ce frontend public, y compris le montant lui-même."""
    hashed = hashlib.sha256(token.encode()).hexdigest()
    link = db.query(Link).filter(Link.token == hashed).first()
    if not link or link.deleted:
        return {"error": "invalid"}
    if link.amount is not None:
        return {"error": "not_flexible"}
    now = datetime.now(timezone.utc)
    successful_count = db.query(Payment).filter(Payment.link_id == link.id, Payment.status == "paid").count()
    if link.max_uses is not None and successful_count >= link.max_uses:
        return {"error": "already_paid" if link.max_uses == 1 else "exhausted"}
    if link.expires_at and link.expires_at < now:
        return {"error": "expired"}
    amount = data.amount
    if amount is None or amount <= 0:
        return {"error": "invalid_amount"}
    if link.min_amount is not None and amount < link.min_amount:
        return {"error": "amount_too_low"}
    if link.max_amount is not None and amount > link.max_amount:
        return {"error": "amount_too_high"}
    user = db.query(UserDB).filter(UserDB.id == link.user_id).first()
    if not user:
        return {"error": "user not found"}
    url = create_checkout_session(db=db, mode="payment", email=user.email, user_id=user.id, amount=amount, link_id=link.id, currency=link.currency)
    return {"url": url}

@router.post("/create-checkout-session")
def create_checkout(
    data: dict,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plan = data.get("plan")
    amount = data.get("amount")
    if plan and amount:
        return {"error": "Choisir soit plan soit amount"}
    if not plan and not amount:
        return {"error": "Données manquantes"}
    mode = "subscription" if plan else "payment"
    url = create_checkout_session(db=db, mode=mode, email=user.email, user_id=user.id, amount=amount, plan=plan)
    return {"url": url}

@router.delete("/links/{id}")
def delete_link(
    id: str, 
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    link = db.query(Link).filter(Link.id == id,  Link.user_id == owner_id).first()
    if not link:
        return {"error": "not_found"}
    link.deleted = True
    db.commit()
    return {"success": True}

@router.post("/archive/{id}")
def archive_link(
    id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    lien = db.query(Link).filter(Link.id == id, Link.user_id == owner_id).first()
    if not lien:
        return {"error": "not_found"}
    payment = db.query(Payment).filter(Payment.link_id == lien.id, Payment.status == "paid").first()
    if not payment:
        raise HTTPException(status_code=400, detail="Lien non payé")
    lien.archived = True
    db.commit()
    return {"success": True}

@router.get("/links/{link_id}", response_model=LinkDashboardResponse)
def get_link_detail(
    link_id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(user, workspace_id, db)
    link = db.query(Link).filter(Link.id == link_id, Link.user_id == owner_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Lien introuvable")

    payments = (
        db.query(Payment)
        .filter(Payment.link_id == link.id, Payment.status == "paid")
        .order_by(Payment.created_at.desc())
        .all()
    )
    successful_count = len(payments)
    now = datetime.now(timezone.utc)
    status = _resolve_link_status(successful_count, link, now)
    last_payment = payments[0] if payments else None
    if last_payment:
        # Voir get_links ci-dessus : amount/currency (montant brut, devise
        # d'origine), jamais amount_local/currency_local (net XOF).
        amount = last_payment.amount
        currency = last_payment.currency
    else:
        amount = link.amount
        currency = link.currency
    is_active = link.expires_at is None or link.expires_at > now
    emails_by_id = _emails_by_user_id(db, [link.link_metadata])

    return LinkDashboardResponse(
        id=link.id,
        name=link.name,
        amount=amount,
        currency=currency,
        status=status,
        active=is_active,
        archived=link.archived,
        url=link.url,
        expires_at=link.expires_at,
        created_at=link.created_at,
        metadata=_enrich_metadata(link.link_metadata, emails_by_id),
        max_uses=link.max_uses,
        min_amount=link.min_amount,
        max_amount=link.max_amount,
        successful_payments_count=successful_count,
    )