from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, Webhook, WebhookDeliveryLog, Payment
from backend.auth import get_current_user
from pydantic import BaseModel
from typing import List
import httpx
from datetime import datetime, timezone
import secrets
import uuid

secret = secrets.token_hex(32)

router = APIRouter()

class WebhookCreate(BaseModel):
    url: str
    events: List[str]

# GET — lister les webhooks
@router.get("/webhooks-api")
def get_webhooks(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    webhooks = db.query(Webhook).filter(Webhook.user_id == current_user.id).all()
    return [
        {
            "id": w.id,
            "url": w.url,
            "events": w.events.split(","),
            "is_active": w.is_active,
            "last_triggered": w.last_triggered.isoformat() if w.last_triggered else None
        }
        for w in webhooks
    ]

# POST — créer un webhook
@router.post("/webhooks-api")
def create_webhook(
    data: WebhookCreate,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    webhook = Webhook(
        user_id=current_user.id,
        url=data.url,
        events=",".join(data.events),
        is_active=True,
        secret="whsec_" + secrets.token_hex(32)
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return {
        "message": "Webhook créé", 
        "id": webhook.id,
        "secret": webhook.secret
    }

# DELETE — supprimer un webhook
@router.delete("/webhooks-api/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook introuvable")
    db.delete(webhook)
    db.commit()
    return {"message": "Webhook supprimé"}

@router.post("/webhooks-api/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Webhook introuvable"
        )

    # Récupérer un paiement réel de l'utilisateur
    payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == "paid"
    ).order_by(Payment.created_at.desc()).first()

    if not payment:
        raise HTTPException(
            status_code=400,
            detail="Aucun paiement réussi disponible pour effectuer le test"
        )

    now = datetime.now(timezone.utc)

    payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "timestamp": int(now.timestamp()),
        "event": "payment.success",
        "data": {
            "amount": payment.amount_local,
            "currency": payment.currency_local,
            "user_id": str(payment.user_id),
            "link_id": str(payment.link_id)
        }
    }

    status_code = 0
    success = False
    error_message = None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                webhook.url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Xepay-Event": payload["event"]
                }
            )

        status_code = response.status_code
        success = 200 <= status_code < 300

        if not success:
            error_message = f"HTTP {status_code}"

    except httpx.TimeoutException:
        error_message = "Timeout lors de l'envoi du webhook"

    except httpx.RequestError as e:
        error_message = str(e)

    webhook.last_triggered = now

    log = WebhookDeliveryLog(
        user_id=current_user.id,
        webhook_id=webhook.id,
        url=webhook.url,
        event=payload["event"],
        status_code=status_code,
        success=success,
        created_at=now
    )

    db.add(log)
    db.commit()

    return {
        "success": success,
        "status_code": status_code,
        "error": error_message,
        "event_id": payload["id"]
    }