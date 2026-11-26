"""Webhook Stripe DÉDIÉ au paiement de 500 USD (compte plateforme Xepay -
jamais Connect) qu'un marchand doit régler avant de pouvoir déclencher
/buildness/onboard (voir routes/buildness.py, backend/models.py/
BuildnessLlcCredit). Point d'entrée Stripe séparé (sa propre URL, son
propre secret STRIPE_BUILDNESS_WEBHOOK_SECRET) de /webhook/payment
(routes/webhook/paiement.py, qui écoute les paiements CONNECT des
clients des marchands - rien à voir ici)."""

import logging
import os

import stripe
from fastapi import APIRouter, Request, Header, HTTPException

from backend.database import SessionLocal
from backend.models import BuildnessLlcCredit

logger = logging.getLogger(__name__)

STRIPE_BUILDNESS_WEBHOOK_SECRET = os.getenv("STRIPE_BUILDNESS_WEBHOOK_SECRET")

router = APIRouter()


@router.post("/webhook/buildness-payment")
async def buildness_payment_webhook(request: Request, stripe_signature: str = Header(None, alias="stripe-signature")):
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_BUILDNESS_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    # .to_dict() OBLIGATOIRE ici - CORRIGÉ le 2026-11-26 (bug réel trouvé
    # en prod, 500 sur chaque tentative) : event["data"]["object"] est un
    # objet Stripe typé (Session), pas un dict brut - .get(...) dessus
    # lève AttributeError ("'get' is a dict method, but a Session is not
    # a dict"), jamais rattrapée par le try/except plus haut (qui ne
    # couvre que la vérification de signature), donc 500 à chaque appel
    # malgré une signature et des métadonnées parfaitement valides.
    session_obj = event["data"]["object"].to_dict()
    if session_obj.get("payment_status") != "paid":
        # Une session "completed" peut rester impayée pour un mode
        # setup/une carte différée - jamais créer de crédit tant que
        # l'argent n'est pas réellement encaissé.
        return {"status": "ignored"}

    metadata = session_obj.get("metadata") or {}
    workspace_id = metadata.get("workspace_id")
    if not workspace_id or metadata.get("purpose") != "buildness_llc_formation":
        return {"status": "ignored"}

    db = SessionLocal()
    try:
        # Idempotence sur stripe_checkout_session_id (webhooks Stripe
        # peuvent être redélivrés) - jamais un 2e crédit pour la même
        # session déjà traitée.
        existing = (
            db.query(BuildnessLlcCredit)
            .filter(BuildnessLlcCredit.stripe_checkout_session_id == session_obj["id"])
            .first()
        )
        if existing:
            return {"status": "already_processed"}

        db.add(BuildnessLlcCredit(
            workspace_id=workspace_id,
            stripe_checkout_session_id=session_obj["id"],
            status="paid_unused",
        ))
        db.commit()
        logger.info("Crédit LLC Buildness créé pour workspace_id=%s (session=%s)", workspace_id, session_obj["id"])
        return {"status": "ok"}
    finally:
        db.close()
