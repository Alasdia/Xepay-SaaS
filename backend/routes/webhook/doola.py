"""Webhook doola (voir services/doola_service.py, routes/bildbus.py,
BildBusWebhookLog/BildBusCompany dans models.py).

AVERTISSEMENT (même mise en garde que webhook/verto.py) : le nom du
header de signature ("X-Doola-Signature"), le schéma HMAC-SHA256 sur le
corps brut, et les noms de champs (eventId/eventType/doolaCompanyId/
einNumber) reprennent tels quels le cahier des charges fourni le
2026-11-21 - NON CONFIRMÉS par une vraie doc/sandbox doola. À valider
contre un vrai événement sandbox avant mise en prod.

DOOLA_WEBHOOK_SECRET n'a PAS de valeur par défaut en dur ici (contrairement
à ce que suggérait le cahier des charges, "test_secret") : un défaut en
dur dans le code finirait immanquablement par partir en prod tel quel.
Positionner DOOLA_WEBHOOK_SECRET=test_secret dans le .env LOCAL suffit
pour le flux de test (voir scripts/test_doola_webhook.py)."""

import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from backend.database import SessionLocal
from backend.models import BildBusCompany, BildBusWebhookLog

router = APIRouter()
logger = logging.getLogger(__name__)

DOOLA_WEBHOOK_SECRET = os.getenv("DOOLA_WEBHOOK_SECRET")


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """hmac.compare_digest (temps constant) plutôt que == : une simple
    égalité de chaînes fuite un timing exploitable pour reconstruire la
    signature attendue octet par octet."""
    if not DOOLA_WEBHOOK_SECRET or not signature_header:
        return False
    expected = hmac.new(DOOLA_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _apply_doola_event(event_type: str, payload: dict) -> None:
    """Tâche de fond (voir BackgroundTasks dans doola_webhook ci-dessous) -
    ouvre sa PROPRE session, jamais celle de la requête : même convention
    que process_checkout_session_payment/stripe_payment_webhook
    (webhook/paiement.py), qui n'utilisent jamais Depends(get_db) pour
    cette raison - une session liée à la requête HTTP ne doit pas être
    réutilisée dans du code qui continue de s'exécuter après la réponse."""
    db = SessionLocal()
    try:
        doola_company_id = payload.get("doolaCompanyId") or (payload.get("data") or {}).get("doolaCompanyId")
        if not doola_company_id:
            logger.warning("Webhook doola %s sans doolaCompanyId, ignoré", event_type)
            return

        company = (
            db.query(BildBusCompany)
            .filter(BildBusCompany.doola_company_id == str(doola_company_id))
            .first()
        )
        if not company:
            logger.warning(
                "Webhook doola %s pour doolaCompanyId=%s inconnu côté Xepay",
                event_type, doola_company_id,
            )
            return

        if event_type == "company.created":
            company.status = "processing"
            company.last_successful_step = "processing"
        elif event_type == "ein.issued":
            company.status = "completed"
            company.last_successful_step = "completed"
            ein_number = payload.get("einNumber") or (payload.get("data") or {}).get("einNumber")
            if ein_number:
                company.ein_number = str(ein_number)
        else:
            logger.info("Webhook doola %s sans transition de statut connue, ignoré", event_type)
            return

        db.commit()
    except Exception:
        logger.exception("Echec traitement webhook doola (event_type=%s)", event_type)
        db.rollback()
    finally:
        db.close()


@router.post("/webhook/doola")
async def doola_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()

    if not _verify_signature(raw_body, request.headers.get("X-Doola-Signature")):
        raise HTTPException(status_code=400, detail="Signature invalide")

    try:
        payload = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=400, detail="JSON invalide")

    event_id = payload.get("eventId") or payload.get("id")
    event_type = payload.get("eventType") or payload.get("type")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="eventId/eventType manquant")

    # event_id UNIQUE (voir models.py) est le vrai filet de sécurité, pas
    # un SELECT préalable : deux livraisons quasi simultanées du même
    # événement passeraient toutes les deux un simple "if not exists"
    # avant qu'aucune n'ait committé. Ici, la seconde échoue sur la
    # contrainte et reçoit la même réponse 200 - jamais traitée deux fois.
    db = SessionLocal()
    try:
        db.add(BildBusWebhookLog(
            event_id=str(event_id),
            event_type=str(event_type),
            payload=payload,
        ))
        db.commit()
    except IntegrityError:
        db.rollback()
        db.close()
        return {"ok": True}
    db.close()

    # BackgroundTasks : la mise à jour de BildBusCompany part en tâche de
    # fond pour répondre 200 à doola sans attendre - demandé explicitement
    # (le cahier des charges), au-delà de ce que Stripe/Verto ont besoin
    # ici (eux ne déportent que l'appel SORTANT vers le webhook du
    # marchand, jamais leur propre écriture locale, qui est déjà rapide).
    background_tasks.add_task(_apply_doola_event, str(event_type), payload)

    return {"ok": True}
