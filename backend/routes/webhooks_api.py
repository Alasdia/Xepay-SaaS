from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, Webhook
from backend.auth import get_current_user
from pydantic import BaseModel
from typing import List
import httpx
from datetime import datetime
import secrets

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
        secret=secrets.token_hex(32)
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
    webhook_id: int,
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

# POST — tester un webhook
@router.post("/webhooks-api/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print("🚀 TEST WEBHOOK START")

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        print("❌ Webhook introuvable")
        raise HTTPException(status_code=404, detail="Webhook introuvable")
    
    print("🔗 URL:", webhook.url)
    print("📦 EVENTS:", webhook.events)
    print("🟢 ACTIVE:", webhook.is_active)
    
    try:
        async with httpx.AsyncClient() as client:
            print("📡 Envoi de la requête...")
            response = await client.post(
                webhook.url,
                json={
                    "event": "test",
                    "message": "Ceci est un test ePay"
                },
                timeout=10
            )

        print("✅ STATUS:", response.status_code)
        print("📩 BODY:", response.text)

        webhook.last_triggered = datetime.utcnow()
        db.commit()
        print("💾 DB updated")

        return {"message": "Test envoyé !"}

    except Exception as e:
        print("🔥 ERREUR WEBHOOK:", str(e))
        return {"error": str(e)}