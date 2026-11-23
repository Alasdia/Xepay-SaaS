"""Script de test local du flux webhook Buildness (voir routes/webhook/
doola.py, routes/buildness.py) - vérifie que la base passe bien de
"submitted" à "processing" puis "completed" après deux événements webhook
HMAC valides, et que rejouer le même event_id ne retraite rien une
seconde fois (idempotence, BuildnessWebhookLog.event_id UNIQUE).

Payload/noms d'événements mis à jour le 2026-11-23 après vérification
contre la vraie doc officielle doola (docs.doola.com/api/webhooks) :
eventName (pas eventType), doolaCompanyId sous eventPayload (pas à la
racine), company_formation_submitted/company_ein_issued (pas
company.created/ein.issued, qui n'existent pas chez doola) - voir le
docstring de webhook/doola.py pour le détail des corrections.

Usage (le serveur Xepay doit déjà tourner en local, même
DOOLA_WEBHOOK_SECRET des deux côtés, ET BUILDNESS_ALLOW_MOCK=true côté
serveur pour que company_ein_issued puisse récupérer un EIN du
MockDoolaService sans clé réelle - voir doola_client.py) :

    DOOLA_WEBHOOK_SECRET=test_secret python3 -m backend.scripts.test_doola_webhook

Ce script insère BuildnessCustomer/BuildnessCompany DIRECTEMENT en base (saute
POST /buildness/onboard, qui exige une session authentifiée - simuler tout
un login ici serait hors sujet) puis pilote POST /webhook/doola en HTTP
réel, exactement comme le ferait doola - c'est cette partie qu'on veut
vérifier. Nécessite au moins un utilisateur existant dans la base ciblée
par DATABASE_URL (backend/database.py), réutilisé comme marchand de test.

La mise à jour de BuildnessCompany part en BackgroundTask côté serveur (voir
webhook/doola.py) : elle peut donc arriver un peu APRÈS que ce script ait
reçu la réponse HTTP 200 - _wait_for() retente la lecture en base pendant
quelques secondes plutôt que de vérifier une seule fois immédiatement."""

import hashlib
import hmac
import json
import os
import time
import uuid

import httpx

from backend.database import SessionLocal
from backend.models import BuildnessCompany, BuildnessCustomer, BuildnessWebhookLog, UserDB

BASE_URL = os.getenv("BUILDNESS_TEST_BASE_URL", "http://127.0.0.1:8000")
DOOLA_WEBHOOK_SECRET = os.getenv("DOOLA_WEBHOOK_SECRET", "test_secret")


def _sign(raw_body: bytes) -> str:
    return hmac.new(DOOLA_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()


def _send_webhook(event_id: str, event_name: str, doola_company_id: str, extra_event_payload: dict | None = None) -> httpx.Response:
    # Forme réelle doola (confirmée docs.doola.com/api/webhooks le
    # 2026-11-23) : eventName + doolaCompanyId sous eventPayload, jamais
    # à la racine.
    payload = {
        "eventId": event_id,
        "eventName": event_name,
        "eventPayload": {"doolaCompanyId": doola_company_id, **(extra_event_payload or {})},
        "timestamp": int(time.time() * 1000),
    }
    raw_body = json.dumps(payload).encode("utf-8")
    return httpx.post(
        f"{BASE_URL}/webhook/doola",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Doola-Signature": _sign(raw_body),
        },
        timeout=10,
    )


def _wait_for(predicate, *, timeout=5.0, interval=0.2):
    """Retente `predicate()` jusqu'à True ou expiration - absorbe le délai
    entre la réponse HTTP (envoyée avant la BackgroundTask, voir webhook/
    doola.py) et le commit réel de BuildnessCompany."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def main():
    db = SessionLocal()
    try:
        user = db.query(UserDB).first()
        if not user:
            print("Aucun utilisateur en base - crée un compte via l'UI avant de lancer ce script.")
            return

        doola_company_id = f"mock_co_{uuid.uuid4().hex[:12]}"

        customer = (
            db.query(BuildnessCustomer)
            .filter(BuildnessCustomer.xepay_merchant_id == user.id)
            .first()
        )
        if not customer:
            customer = BuildnessCustomer(
                xepay_merchant_id=user.id,
                doola_customer_id=f"mock_cus_{uuid.uuid4().hex[:12]}",
                email=user.email or "test@example.com",
                first_name="Test",
                last_name="Founder",
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

        company = BuildnessCompany(
            customer_id=customer.id,
            doola_company_id=doola_company_id,
            company_name="Test LLC",
            state="DE",
            status="submitted",
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        print(f"Seed OK - company_id={company.id} doola_company_id={doola_company_id} status={company.status}")

        # 1) company_formation_submitted -> processing
        resp = _send_webhook(str(uuid.uuid4()), "company_formation_submitted", doola_company_id)
        print(f"POST /webhook/doola (company_formation_submitted) -> {resp.status_code} {resp.json()}")
        assert _wait_for(lambda: (db.refresh(company), company.status)[1] == "processing"), (
            f"status toujours {company.status!r} après 5s, attendu 'processing'"
        )
        print(f"OK - status = {company.status}")

        # 2) company_ein_issued -> completed, ein_number renseigné. Le
        # payload webhook ne contient JAMAIS l'EIN chez le vrai doola :
        # le handler va le chercher via get_doola_service().get_company_status()
        # (MockDoolaService ici, voir doola_mock_service.py - nécessite
        # BUILDNESS_ALLOW_MOCK=true côté serveur, sinon ce test échoue).
        ein_event_id = str(uuid.uuid4())
        resp = _send_webhook(ein_event_id, "company_ein_issued", doola_company_id)
        print(f"POST /webhook/doola (company_ein_issued) -> {resp.status_code} {resp.json()}")
        assert _wait_for(lambda: (db.refresh(company), company.status)[1] == "completed"), (
            f"status toujours {company.status!r} après 5s, attendu 'completed'"
        )
        assert company.ein_number == "99-9999999", f"ein_number={company.ein_number!r}"
        print(f"OK - status = {company.status}, ein_number = {company.ein_number}")

        # 3) Idempotence : rejouer EXACTEMENT le même event_id (même
        # payload) ne doit rien retraiter - un seul BuildnessWebhookLog pour
        # cet event_id, company.updated_at inchangé (la 2e livraison ne
        # relance même pas la BackgroundTask, voir webhook/doola.py).
        updated_at_before = company.updated_at
        log_count_before = (
            db.query(BuildnessWebhookLog)
            .filter(BuildnessWebhookLog.event_id == ein_event_id)
            .count()
        )
        resp = _send_webhook(ein_event_id, "company_ein_issued", doola_company_id)
        print(f"POST /webhook/doola (company_ein_issued, REJOUÉ) -> {resp.status_code} {resp.json()}")
        time.sleep(1)  # laisse le temps à une éventuelle (mauvaise) 2e BackgroundTask de s'exécuter
        db.refresh(company)
        log_count_after = (
            db.query(BuildnessWebhookLog)
            .filter(BuildnessWebhookLog.event_id == ein_event_id)
            .count()
        )
        assert log_count_before == log_count_after == 1, (
            f"event_id rejoué journalisé {log_count_after} fois (attendu 1)"
        )
        assert company.updated_at == updated_at_before, "event_id rejoué a été retraité (updated_at a changé)"
        print("OK - événement rejoué : aucun retraitement, aucun doublon de log")

        print("\nTOUS LES TESTS SONT PASSÉS.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
