"""Webhook doola (voir services/doola_service.py, routes/buildness.py,
BuildnessWebhookLog/BuildnessCompany dans models.py).

VÉRIFIÉ le 2026-11-23 contre la vraie documentation officielle
(docs.doola.com/api/webhooks) :
- Header de signature "X-Doola-Signature" : CONFIRMÉ.
- HMAC-SHA256 hex digest sur le corps brut SEUL (pas de timestamp signé,
  pas de préfixe "sha256=") : CONFIRMÉ, _verify_signature ci-dessous
  était déjà correct.
- eventId au niveau racine : CONFIRMÉ.

CORRIGÉ suite à cette vérification (le cahier des charges du 2026-11-21
avait deviné des noms de champs/événements qui n'existent pas chez
doola) :
- Le type d'événement est "eventName", jamais "eventType" - gardé en
  repli pour tolérer un futur changement doola, mais eventName est
  désormais lu en premier.
- doolaCompanyId vit dans un sous-objet "eventPayload", jamais à la
  racine ni sous "data".
- Les noms d'événements réels sont "company_formation_submitted"/
  "company_formation_submitted_to_state"/"company_formation_completed"/
  "company_formation_failed"/"company_ein_issued" (underscore, pas
  "company.created"/"ein.issued" qui n'existent pas chez doola).
- Le payload webhook ne contient JAMAIS l'EIN (confirmé explicitement
  par la doc) - company_ein_issued déclenche désormais un GET /v1/
  partner/companies/{id} pour récupérer le champ "ein" réel, au lieu de
  lire un champ "einNumber" inexistant dans le payload.

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
from backend.models import BuildnessCompany, BuildnessWebhookLog
from backend.services.doola_client import get_doola_service, DoolaNotConfiguredError
from backend.services.doola_service import DoolaAPIError

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


# Événements réels doola (confirmés docs.doola.com/api/webhooks le
# 2026-11-23) qui font avancer le statut local vers "processing" - la
# formation est soumise/en cours de traitement par l'État, mais ni LLC
# formée ni EIN émis (voir le docstring de BuildnessCompany, models.py :
# "completed" exige les deux).
_PROCESSING_EVENTS = {
    "company_formation_submitted",
    "company_formation_submitted_to_state",
    "company_formation_completed",
}


async def _apply_doola_event(event_type: str, payload: dict) -> None:
    """Tâche de fond (voir BackgroundTasks dans doola_webhook ci-dessous) -
    ouvre sa PROPRE session, jamais celle de la requête : même convention
    que process_checkout_session_payment/stripe_payment_webhook
    (webhook/paiement.py), qui n'utilisent jamais Depends(get_db) pour
    cette raison - une session liée à la requête HTTP ne doit pas être
    réutilisée dans du code qui continue de s'exécuter après la réponse.
    async (pas juste sync) : company_ein_issued a besoin d'un appel
    réseau sortant vers doola pour récupérer l'EIN (voir ci-dessous) -
    BackgroundTasks de Starlette exécute un callable async nativement,
    sans event loop dédié à gérer ici."""
    db = SessionLocal()
    try:
        event_payload = payload.get("eventPayload") or {}
        doola_company_id = (
            event_payload.get("doolaCompanyId")
            or payload.get("doolaCompanyId")
            or (payload.get("data") or {}).get("doolaCompanyId")
        )
        if not doola_company_id:
            logger.warning("Webhook doola %s sans doolaCompanyId, ignoré", event_type)
            return

        company = (
            db.query(BuildnessCompany)
            .filter(BuildnessCompany.doola_company_id == str(doola_company_id))
            .first()
        )
        if not company:
            logger.warning(
                "Webhook doola %s pour doolaCompanyId=%s inconnu côté Xepay",
                event_type, doola_company_id,
            )
            return

        if event_type in _PROCESSING_EVENTS:
            company.status = "processing"
            company.last_successful_step = "processing"
        elif event_type == "company_formation_failed":
            company.status = "failed"
        elif event_type == "company_ein_issued":
            # Le payload webhook ne contient JAMAIS l'EIN (confirmé par la
            # doc officielle) - seul un GET /v1/partner/companies/{id}
            # après cet événement renvoie le champ "ein" réel.
            try:
                doola = get_doola_service()
                status_data = await doola.get_company_status(str(doola_company_id))
            except (DoolaNotConfiguredError, DoolaAPIError):
                logger.exception(
                    "Echec récupération EIN doola pour doolaCompanyId=%s après company_ein_issued",
                    doola_company_id,
                )
                return
            ein = status_data.get("ein")
            company.status = "completed"
            company.last_successful_step = "completed"
            if ein:
                company.ein_number = str(ein)
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
    # eventName : nom réel du champ chez doola (voir docstring en tête de
    # fichier) - eventType/type gardés en repli uniquement par robustesse.
    event_type = payload.get("eventName") or payload.get("eventType") or payload.get("type")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="eventId/eventName manquant")

    # event_id UNIQUE (voir models.py) est le vrai filet de sécurité, pas
    # un SELECT préalable : deux livraisons quasi simultanées du même
    # événement passeraient toutes les deux un simple "if not exists"
    # avant qu'aucune n'ait committé. Ici, la seconde échoue sur la
    # contrainte et reçoit la même réponse 200 - jamais traitée deux fois.
    db = SessionLocal()
    try:
        db.add(BuildnessWebhookLog(
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

    # BackgroundTasks : la mise à jour de BuildnessCompany part en tâche de
    # fond pour répondre 200 à doola sans attendre - demandé explicitement
    # (le cahier des charges), au-delà de ce que Stripe/Verto ont besoin
    # ici (eux ne déportent que l'appel SORTANT vers le webhook du
    # marchand, jamais leur propre écriture locale, qui est déjà rapide).
    background_tasks.add_task(_apply_doola_event, str(event_type), payload)

    return {"ok": True}
