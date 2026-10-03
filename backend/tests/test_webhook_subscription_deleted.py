import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import UserDB

# backend/routes/__init__.py ouvre une vraie connexion réseau à la base de
# prod (engine.connect()) au moment même de l'import du package — neutralisé
# le temps du seul import, sans toucher au fichier de prod (même technique
# que backend/tests/test_detail_endpoints.py).
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
    import backend.routes.webhook.abonnement as abonnement_module
finally:
    _database.engine.connect = _real_engine_connect

# La route utilise SessionLocal() directement (pas Depends(get_db)) : on
# remplace la référence que le module a importée pour pointer vers une base
# SQLite de test isolée, sans toucher au fichier de prod.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)
abonnement_module.SessionLocal = TestingSessionLocal


class FakeStripeObject:
    """Stand-in minimal pour un objet Stripe : seule to_dict() est utilisée
    par le handler testé."""

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


def build_app():
    app = FastAPI()
    app.include_router(abonnement_module.router)
    return app


class TestSubscriptionDeletedWebhook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(build_app())

    def setUp(self):
        db = TestingSessionLocal()
        user = UserDB(
            email="sub-user@example.com",
            password="x",
            plan="pro",
            subscription_status="active",
            stripe_subscription_id="sub_123",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        self.user_id = user.id
        db.close()

    def _fake_event(self):
        return {
            "type": "customer.subscription.deleted",
            "data": {
                "object": FakeStripeObject({"metadata": {"user_id": self.user_id}}),
            },
        }

    @patch("backend.routes.webhook.abonnement.send_subscription_canceled_email")
    @patch("stripe.Webhook.construct_event")
    def test_subscription_deleted_resets_plan_without_crashing(self, mock_construct_event, mock_send_email):
        # Avant correctif : send_subscription_canceled_email(email, plan, status)
        # levait un NameError (plan/status jamais définis dans cette branche),
        # intercepté par le except générique -> 500 renvoyé à Stripe et email
        # jamais envoyé. Ce test vérifie que ça ne se reproduit plus.
        mock_construct_event.return_value = self._fake_event()

        res = self.client.post(
            "/webhook",
            data=b"{}",
            headers={"stripe-signature": "fake"},
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})
        mock_send_email.assert_called_once_with("sub-user@example.com")

        db = TestingSessionLocal()
        refreshed = db.query(UserDB).filter(UserDB.id == self.user_id).first()
        self.assertEqual(refreshed.plan, "free")
        self.assertEqual(refreshed.subscription_status, "canceled")
        self.assertIsNone(refreshed.stripe_subscription_id)
        db.close()


if __name__ == "__main__":
    unittest.main()
