import json
import time
import hmac
import hashlib
import uuid
import requests
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models import Webhook, WebhookDeliveryLog

def send_webhook_event(db: Session, user_id: str, event_type: str, data: dict):
    """
    Envoie un événement webhook à tous les endpoints actifs du marchand
    qui sont abonnés à ce type d'événement.
    """
    webhooks = db.query(Webhook).filter(Webhook.user_id == user_id, Webhook.is_active == True).all()
    for webhook in webhooks:
        if event_type not in webhook.events.split(","):
            continue
        payload = {
            "id": f"evt_{uuid.uuid4().hex}",
            "timestamp": int(time.time()),
            "event": event_type,
            "data": data
        }
        payload_bytes = json.dumps(payload).encode()
        signature = hmac.new(
            webhook.secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        success = False
        final_status_code = None
        for attempt in range(3):
            try:
                response = requests.post(
                    webhook.url,
                    json=payload,
                    headers={
                        "X-Signature": signature,
                        "X-Epay-Event": event_type,
                        "X-Epay-Timestamp": str(payload["timestamp"])
                    },
                    timeout=5
                )
                final_status_code = response.status_code
                if response.status_code == 200:
                    success = True
                    break
            except Exception:
                final_status_code = 0
            time.sleep(2)
        log = WebhookDeliveryLog(
            user_id=user_id,
            webhook_id=webhook.id,
            url=webhook.url,
            event=event_type,
            status_code=final_status_code,
            success=success
        )
        db.add(log)
        webhook.last_triggered = datetime.now(timezone.utc)
        webhook.status = "active" if success else "error"
        webhook.last_status_code = final_status_code
        db.commit()
