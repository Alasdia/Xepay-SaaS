from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import ApiLog
from backend.auth import get_current_user
from backend.models import Webhook
from datetime import timezone, datetime
from backend.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/logs")
def get_logs(
    limit: int = 5, 
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    logs = db.query(ApiLog)\
        .filter(ApiLog.user_id == user.id)\
        .order_by(ApiLog.created_at.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "method": log.method,
            "status": log.status_code,
            "path": log.path,
            "time": log.created_at
        }
        for log in logs
    ]

@router.get("/logs/stats")
def logs_stats(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    total = db.query(ApiLog).filter(ApiLog.user_id == user.id).count()

    success = db.query(ApiLog).filter(
        ApiLog.user_id == user.id,
        ApiLog.status_code == 200
    ).count()

    errors = db.query(ApiLog).filter(
        ApiLog.user_id == user.id,
        ApiLog.status_code >= 400
    ).count()

    now = datetime.now(timezone.utc)

    start_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    if now.month == 1:
        start_last_month = datetime(now.year - 1, 12, 1, tzinfo=timezone.utc)
    else:
        start_last_month = datetime(now.year, now.month - 1, 1, tzinfo=timezone.utc)

    calls_this_month = db.query(ApiLog).filter(
        ApiLog.user_id == user.id,
        ApiLog.created_at >= start_month,
        ApiLog.created_at < next_month
    ).count()

    calls_last_month = db.query(ApiLog).filter(
        ApiLog.user_id == user.id,
        ApiLog.created_at >= start_last_month,
        ApiLog.created_at < start_month
    ).count()

    growth = ((calls_this_month - calls_last_month) / calls_last_month * 100) if calls_last_month > 0 else 0

    # ===== WEBHOOKS =====
    total_webhooks = db.query(Webhook).filter(
        Webhook.user_id == user.id
    ).count()

    active_webhooks = db.query(Webhook).filter(
        Webhook.user_id == user.id,
        Webhook.is_active == True
    ).count()

    return {
        "total": total,  
        "calls_this_month": calls_this_month, 
        "errors": errors,
        "success_rate": (success / total * 100) if total > 0 else 0,
        "growth": round(growth, 1),
        "active_webhooks": active_webhooks,
        "total_webhooks": total_webhooks
    }
