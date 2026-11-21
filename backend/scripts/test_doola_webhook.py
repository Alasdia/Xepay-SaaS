"""Script de test local du flux webhook BildBus (voir routes/webhook/
doola.py, routes/bildbus.py) - vérifie que la base passe bien de
"submitted" à "processing" puis "completed" après deux événements webhook
HMAC valides, et que rejouer le même event_id ne retraite rien une
seconde fois (idempotence, BildBusWebhookLog.event_id UNIQUE).

Usage (le serveur Xepay doit déjà tourner en local, même
DOOLA_WEBHOOK_SECRET des deux côtés) :

    DOOLA_WEBHOOK_SECRET=test_secret python3 -m backend.scripts.test_doola_webhook

Ce script insère BildBusCustomer/BildBusCompany DIRECTEMENT en base (saute
POST /bildbus/onboard, qui exige une session authentifiée - simuler tout
un login ici serait hors sujet) puis pilote POST /webhook/doola en HTTP
réel, exactement comme le ferait doola - c'est cette partie qu'on veut
vérifier. Nécessite au moins un utilisateur existant dans la base ciblée
par DATABASE_URL (backend/database.py), réutilisé comme marchand de test.

La mise à jour de BildBusCompany part en BackgroundTask côté serveur (voir
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
from backend.models import BildBusCompany, BildBusCustomer, BildBusWebhookLog, UserDB

BASE_URL = os.getenv("BILDBUS_TEST_BASE_URL", "http://127.0.0.1:8000")
DOOLA_WEBHOOK_SECRET = os.getenv("DOOLA_WEBHOOK_SECRET", "test_secret")


def _sign(raw_body: bytes) -> str:
    return hmac.new(DOOLA_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()


def _send_webhook(event_id: str, event_type: str, doola_company_id: str, extra: dict | None = None) -> httpx.Response:
    payload = {
        "eventId": event_id,
        "eventType": event_type,
        "doolaCompanyId": doola_company_id,
        **(extra or {}),
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
    doola.py) et le commit réel de BildBusCompany."""
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
            db.query(BildBusCustomer)
            .filter(BildBusCustomer.xepay_merchant_id == user.id)
            .first()
        )
        if not customer:
            customer = BildBusCustomer(
                xepay_merchant_id=user.id,
                doola_customer_id=f"mock_cus_{uuid.uuid4().hex[:12]}",
                email=user.email or "test@example.com",
                first_name="Test",
                last_name="Founder",
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

        company = BildBusCompany(
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

        # 1) company.created -> processing
        resp = _send_webhook(str(uuid.uuid4()), "company.created", doola_company_id)
        print(f"POST /webhook/doola (company.created) -> {resp.status_code} {resp.json()}")
        assert _wait_for(lambda: (db.refresh(company), company.status)[1] == "processing"), (
            f"status toujours {company.status!r} après 5s, attendu 'processing'"
        )
        print(f"OK - status = {company.status}")

        # 2) ein.issued -> completed, ein_number renseigné
        ein_event_id = str(uuid.uuid4())
        resp = _send_webhook(ein_event_id, "ein.issued", doola_company_id, {"einNumber": "12-3456789"})
        print(f"POST /webhook/doola (ein.issued) -> {resp.status_code} {resp.json()}")
        assert _wait_for(lambda: (db.refresh(company), company.status)[1] == "completed"), (
            f"status toujours {company.status!r} après 5s, attendu 'completed'"
        )
        assert company.ein_number == "12-3456789", f"ein_number={company.ein_number!r}"
        print(f"OK - status = {company.status}, ein_number = {company.ein_number}")

        # 3) Idempotence : rejouer EXACTEMENT le même event_id (même
        # payload) ne doit rien retraiter - un seul BildBusWebhookLog pour
        # cet event_id, company.updated_at inchangé (la 2e livraison ne
        # relance même pas la BackgroundTask, voir webhook/doola.py).
        updated_at_before = company.updated_at
        log_count_before = (
            db.query(BildBusWebhookLog)
            .filter(BildBusWebhookLog.event_id == ein_event_id)
            .count()
        )
        resp = _send_webhook(ein_event_id, "ein.issued", doola_company_id, {"einNumber": "12-3456789"})
        print(f"POST /webhook/doola (ein.issued, REJOUÉ) -> {resp.status_code} {resp.json()}")
        time.sleep(1)  # laisse le temps à une éventuelle (mauvaise) 2e BackgroundTask de s'exécuter
        db.refresh(company)
        log_count_after = (
            db.query(BildBusWebhookLog)
            .filter(BildBusWebhookLog.event_id == ein_event_id)
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
