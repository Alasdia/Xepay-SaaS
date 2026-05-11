from fastapi import APIRouter
import stripe
from fastapi.responses import RedirectResponse
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from backend.models import Link
from fastapi import Depends
from backend.database import get_db, SessionLocal
from backend.models import LinkCreate
from backend.models import Link, Payment
from backend.models import PaymentResponse
from backend.models import Payment
from backend.services.rates import get_live_rate
from backend.models import UserDB
from fastapi import HTTPException
from backend.auth import get_current_user
from backend.models import LinkResponse
import hashlib
import os
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, extract
from backend.models import LinkDashboardResponse
from backend.models import PayRequest, Wallet
from backend.services.stripe_service import create_checkout_session

router = APIRouter()

print(Link.__table__.columns.keys())

# ✅ CREATE LINK (Stripe style)
@router.post("/links")
def create_link(
    data: LinkCreate, 
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):

    current_month = datetime.now(timezone.utc).month
    current_year = datetime.now(timezone.utc).year

    links_count = db.query(Link).filter(
        Link.user_id == user.id,
        extract("month", Link.created_at) == current_month,
        extract("year", Link.created_at) == current_year
    ).count()

    now = datetime.now(timezone.utc)

    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

    paid_count = (
        db.query(Payment.link_id)
        .join(Link, Payment.link_id == Link.id)
        .filter(Link.user_id == user.id)
        .filter(Payment.status.in_(["paid", "success", "réussi"]))
        .filter(Payment.created_at >= start)
        .filter(Payment.created_at < end)
        .distinct()
        .count()
    )
    
    PLAN_LIMITS = {
        "free": {"paid": 10, "links": 30},
        "pro": {"paid": 100, "links": 200},
        "business": {"paid": float("inf"), "links": float("inf")}
    }

    plan = getattr(user, "plan", "free")
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    PAID_LIMIT = limits["paid"]
    LINK_LIMIT = limits["links"]

    if paid_count >= PAID_LIMIT:
        raise HTTPException(
            status_code=403,
            detail="Limite de paiements atteinte (10/mois)"
        )

    if links_count >= LINK_LIMIT:
        raise HTTPException(
            status_code=403,
            detail="Limite de liens atteinte (30/mois)"
        )
    
    internal_id = str(uuid4())  # DB

    expires_at= datetime.now(timezone.utc) + timedelta(minutes=10)

    import uuid
    import hashlib

    raw_token = str(uuid.uuid4())

    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

    link = Link(
        id=internal_id,
        token=hashed_token,
        user_id=user.id,
        email=user.email,
        name=data.name.strip() if data.name else "Lien de paiement",
        amount=data.amount,
        currency=data.currency,
        url=f"http://127.0.0.1:8000/pay/{raw_token}",
        created_at=datetime.now(timezone.utc),
        active=True,
        expires_at=expires_at,
        source=getattr(data, "source", "dashboard")
    )

    db.add(link)
    db.commit()
    db.refresh(link)

    return link

@router.get("/links/dashboard")
def get_dashboard_links(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    links = (
        db.query(Link)
        .filter(Link.user_id == user.id)
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
        .filter(Link.user_id == user.id)\
        .filter(Payment.status == "paid")\
        .filter(Payment.created_at >= start_month)\
        .count()
   
    result = []
    for link in links:
        print("SOURCE:", link.source)
        payment = db.query(Payment).filter(Payment.link_id == link.id).first()
        if payment:
            status = payment.status
        elif link.expires_at and link.expires_at < now:
            status = "expired"
        else:
            status = "pending"
        
        result.append({
            "id": link.id,
            "url": link.url,
            "status": status
        })
    return {
        "links": result,
        "paid_this_month": paid_links_count
    }  

# ✅ GET LINKS (dashboard)
@router.get("/links", response_model=list[LinkDashboardResponse])
def get_links(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):  
    print("USER ID:", user.id)

    links = (
        db.query(Link)
        .filter(Link.user_id == user.id)
        .filter(Link.source == "links")
        .filter(Link.deleted == False)
        .filter(Link.archived == False) 
        .order_by(Link.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []

    now = datetime.now(timezone.utc)

    for link in links:
        payment = (
            db.query(Payment)
            .filter(Payment.link_id == link.id)
            .first()
        ) 

        if payment:
            amount = payment.amount_local
            currency = payment.currency_local
            status = "paid"

        elif link.expires_at < now:
            amount = link.amount
            currency = link.currency
            status = "expired"

        else:
            amount = link.amount
            currency = link.currency
            status = "pending"

        is_active = link.expires_at > now

        result.append(LinkDashboardResponse(
            id=link.id,
            name=link.name,
            amount=amount,
            currency=currency,
            status=status,
            active=is_active,
            archived=link.archived,
            url=link.url,
            expires_at=link.expires_at
        ))

    return result

# ✅ GET PAYMENT PAGE (Stripe style)




stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.get("/pay/{token}")
def get_payment(token: str):
    from backend.services.stripe_service import create_checkout_session
    db = SessionLocal()

    hashed = hashlib.sha256(token.encode()).hexdigest()
    link = db.query(Link).filter(Link.token == hashed).first()

    if not link:
        return {"error": "invalid"}
    
    user = db.query(UserDB).filter(UserDB.id == link.user_id).first()

    if not user:
        return {"error": "user not found"}
    
    now = datetime.now(timezone.utc)

    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

    paid_count = (
      db.query(Payment)
        .join(Link, Payment.link_id == Link.id)
        .filter(Link.user_id == user.id)
        .filter(Payment.status.in_(["paid", "success"]))
        .filter(Payment.created_at >= start)
        .filter(Payment.created_at < end)
        .distinct()
        .count()
    )

    PLAN_LIMITS = {
        "free": {"paid": 10},
        "pro": {"paid": 100},
        "business": {"paid": float("inf")}
    }

    plan = getattr(user, "plan", "free")
    PAID_LIMIT = PLAN_LIMITS[plan]["paid"]

    if paid_count >= PAID_LIMIT:
        return RedirectResponse("/static/limit.html", status_code=303)

    url = create_checkout_session(
        db=db,
        mode="payment",
        email=user.email,
        user_id=user.id,
        amount=link.amount,
        link_id=link.id,
        currency=link.currency,
    )
    return RedirectResponse(url, status_code=303)


@router.post("/create-checkout-session")
def create_checkout(
    data: dict,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    print("🔥 CREATE CHECKOUT HIT")

    plan = data.get("plan")
    amount = data.get("amount")

    if plan and amount:
        return {"error": "Choisir soit plan soit amount"}

    if not plan and not amount:
        return {"error": "Données manquantes"}

    # 🔁 déterminer le mode automatiquement
    mode = "subscription" if plan else "payment"

    url = create_checkout_session(
        db=db,
        mode=mode,
        email=user.email,
        user_id=user.id,
        amount=amount,
        plan=plan
    )

    return {"url": url}


# ✅ DELETE
@router.delete("/links/{id}")
def delete_link(
    id: str, 
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):
    link = db.query(Link).filter(
        Link.id == id, 
        Link.user_id == user.id
    ).first()

    if not link:
        return {"error": "not_found"}

    link.deleted = True
    db.commit()

    return {"success": True}

@router.post("/archive/{id}")
def archive_link(
    id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):
    lien = db.query(Link).filter(
        Link.id == id,
        Link.user_id == user.id
    ).first()

    if not lien:
        return {"error": "not_found"}

    # 🔥 vérifier paiement
    payment = db.query(Payment).filter(
        Payment.link_id == lien.id,
        Payment.status == "paid"
    ).first()

    if not payment:
        raise HTTPException(
            status_code=400,
            detail="Lien non payé"
        )

    lien.archived = True
    db.commit()

    return {"success": True}