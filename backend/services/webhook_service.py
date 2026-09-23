import json
import time
import hmac
import hashlib
import uuid
import requests
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models import Webhook, WebhookDeliveryLog

def send_webhook_event(
    db: Session,
    user_id: str,
    event_type: str,
    data: dict
):
    """
    Envoie un événement webhook aux endpoints actifs
    abonnés à cet événement.
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
        raw_body = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False
        ).encode("utf-8")
        signature = hmac.new(
            webhook.secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        success = False
        final_status_code = 0
        for attempt in range(3):
            try:
                response = requests.post(
                    webhook.url,
                    content=raw_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Xepay-Signature": signature,
                        "X-Xepay-Event": event_type,
                        "X-Xepay-Timestamp": str(
                            payload["timestamp"]
                        )
                    },
                    timeout=5
                )
                final_status_code = response.status_code
                if 200 <= response.status_code < 300:
                    success = True
                    break
            except requests.RequestException:
                final_status_code = 0
            if attempt < 2:
                time.sleep(2)
        log = WebhookDeliveryLog(
            user_id=user_id,
            webhook_id=webhook.id,
            url=webhook.url,
            event=event_type,
            status_code=final_status_code,
            success=success,
            created_at=datetime.now(timezone.utc)
        )
        db.add(log)
        webhook.last_triggered = datetime.now(timezone.utc)
        webhook.status = "active" if success else "error"
        webhook.last_status_code = final_status_code
    db.commit()