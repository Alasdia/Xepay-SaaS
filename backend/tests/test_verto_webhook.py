import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import UserDB, Profile

import backend.database as _database


class _NullConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return None


_real_engine_connect = _database.engine.connect
_database.engine.connect = lambda *a, **kw: _NullConnection()
try:
    from backend.routes.webhook.verto import router as verto_webhook_router
finally:
    _database.engine.connect = _real_engine_connect

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_app():
    app = FastAPI()
    app.include_router(verto_webhook_router)
    app.dependency_overrides[get_db] = override_get_db
    return app


class TestVertoWebhookFeatureFlag(unittest.TestCase):
    """VERTO_ENABLED=false (défaut) : les événements d'onboarding/retrait
    renvoient {"ok": True} sans toucher à la base ni appeler verto_service
    - voir le plan PARTNER_REFERRED du 2026-11-07. Le bloc Issuing (micro-
    dépôts carte) est une fonctionnalité séparée, jamais concernée."""

    def setUp(self):
        self.db = TestingSessionLocal()
        user = UserDB(email=f"verto-webhook-test-{id(self)}@example.com", password="x")
        self.db.add(user)
        self.db.flush()
        self.company_id = str(id(self))
        profile = Profile(user_id=user.id, verto_company_id=self.company_id, verto_onboarding_status="pending")
        self.db.add(profile)
        self.db.commit()
        self.user_id = user.id
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    @patch("backend.services.verto_service.VERTO_ENABLED", False)
    @patch("backend.services.verto_service.verify_webhook_signature", return_value=True)
    @patch("backend.services.verto_service.create_wallet")
    def test_company_approved_disabled_by_default(self, mock_create_wallet, _mock_sig):
        res = self.client.post(
            "/webhook/verto",
            json={"companyId": self.company_id, "eventType": "company.approved"},
        )
        self.assertEqual(res.status_code, 200)
        mock_create_wallet.assert_not_called()
        profile = self.db.query(Profile).filter(Profile.verto_company_id == self.company_id).first()
        self.assertEqual(profile.verto_onboarding_status, "pending")  # inchangé

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.verify_webhook_signature", return_value=True)
    def test_director_consent_accepted_sets_status(self, _mock_sig):
        res = self.client.post(
            "/webhook/verto",
            json={"companyId": self.company_id, "eventType": "director.consent_accepted"},
        )
        self.assertEqual(res.status_code, 200)
        profile = self.db.query(Profile).filter(Profile.verto_company_id == self.company_id).first()
        self.assertEqual(profile.verto_director_consent_status, "accepted")

    @patch("backend.services.verto_service.VERTO_ENABLED", False)
    @patch("backend.services.verto_service.verify_webhook_signature", return_value=True)
    def test_director_consent_accepted_disabled_by_default(self, _mock_sig):
        res = self.client.post(
            "/webhook/verto",
            json={"companyId": self.company_id, "eventType": "director.consent_accepted"},
        )
        self.assertEqual(res.status_code, 200)
        profile = self.db.query(Profile).filter(Profile.verto_company_id == self.company_id).first()
        self.assertEqual(profile.verto_director_consent_status, "not_sent")  # inchangé


if __name__ == "__main__":
    unittest.main()
