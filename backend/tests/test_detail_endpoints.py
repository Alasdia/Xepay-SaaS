import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import UserDB, WorkspaceUser, Payment, Withdrawal, Link

# backend/routes/__init__.py ouvre une vraie connexion réseau à la base de
# prod (engine.connect()) au moment même de l'import du package — avant même
# que ce test n'ait pu brancher sa propre session de test. Neutralisé le
# temps du seul import, sans toucher au fichier de prod.
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
    from backend.routes.payments import router as payments_router
    from backend.routes.payout import router as payout_router
    import backend.routes.lien as _lien_module
finally:
    _database.engine.connect = _real_engine_connect

lien_router = _lien_module.router


class _NaiveUtcDatetime(datetime):
    """SQLite ne restitue jamais de tzinfo sur une colonne DateTime(timezone=True)
    (contrairement à Postgres en prod, où backend/routes/lien.py compare
    link.expires_at à un datetime.now(timezone.utc) tz-aware sans problème).
    Aligné ici sur ce que SQLite renvoie réellement, pour la durée des tests
    seulement — ne touche pas au fichier de prod."""

    @classmethod
    def now(cls, tz=None):
        return datetime.now(tz).replace(tzinfo=None) if tz is not None else datetime.now(tz)


_lien_module.datetime = _NaiveUtcDatetime

# Base SQLite en mémoire partagée (StaticPool) pour que toutes les sessions
# de test voient les mêmes données, indépendamment de la vraie base Postgres
# utilisée par l'app en production.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)

# Utilisateur "connecté" courant pour la requête en cours — modifié par
# chaque test via as_user() avant chaque appel API.
_active_user_id = {"value": None}


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    db = TestingSessionLocal()
    user = db.query(UserDB).filter(UserDB.id == _active_user_id["value"]).first()
    db.close()
    return user


def build_app():
    app = FastAPI()
    app.include_router(payments_router)
    app.include_router(payout_router)
    app.include_router(lien_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


def seed():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    owner = UserDB(email="owner@example.com", password="x", plan="business")
    attacker = UserDB(email="attacker@example.com", password="x", plan="business")
    free_owner = UserDB(email="free-owner@example.com", password="x", plan="free")
    db.add_all([owner, attacker, free_owner])
    db.flush()

    # Appartenance workspace : chacun est propriétaire de son propre workspace
    # (convention existante : workspace_id == id du propriétaire).
    db.add(WorkspaceUser(user_id=owner.id, workspace_id=owner.id, role="owner"))
    db.add(WorkspaceUser(user_id=free_owner.id, workspace_id=free_owner.id, role="owner"))
    db.flush()

    payment = Payment(
        user_id=owner.id, client_email="client@example.com",
        amount=100, currency="USD", amount_local=57000, currency_local="XOF",
        status="paid", created_at=now,
    )
    withdrawal = Withdrawal(
        user_id=owner.id, wallet_id="wa_test_owner", amount=5000,
        reference="ref-owner-1", status="pending",
    )
    link = Link(
        user_id=owner.id, token="tok-owner-1", amount=1000, currency="XOF",
        name="Lien test", url="https://api.alasdia.com/pay/tok-owner-1",
        source="links", created_at=now, expires_at=now + timedelta(minutes=10),
        active=True, deleted=False, archived=False,
    )

    free_payment = Payment(
        user_id=free_owner.id, client_email="client2@example.com",
        amount=100, currency="USD", amount_local=57000, currency_local="XOF",
        status="paid", created_at=now,
    )
    free_withdrawal = Withdrawal(
        user_id=free_owner.id, wallet_id="wa_test_free", amount=1000,
        reference="ref-free-1", status="pending",
    )
    free_link = Link(
        user_id=free_owner.id, token="tok-free-1", amount=2000, currency="XOF",
        name="Lien free", url="https://api.alasdia.com/pay/tok-free-1",
        source="links", created_at=now, expires_at=now + timedelta(minutes=10),
        active=True, deleted=False, archived=False,
    )

    db.add_all([payment, withdrawal, link, free_payment, free_withdrawal, free_link])
    db.commit()

    ids = {
        "owner_id": owner.id,
        "attacker_id": attacker.id,
        "free_owner_id": free_owner.id,
        "payment_id": payment.id,
        "withdrawal_id": withdrawal.id,
        "link_id": link.id,
        "free_payment_id": free_payment.id,
        "free_withdrawal_id": free_withdrawal.id,
        "free_link_id": free_link.id,
    }
    db.close()
    return ids


class TestDetailEndpointsAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = seed()
        cls.client = TestClient(build_app())

    def as_user(self, user_id):
        _active_user_id["value"] = user_id

    # --- Paiement ---

    def test_payment_detail_owner_can_access(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get(f"/payments/{self.ids['payment_id']}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["payment_id"], self.ids["payment_id"])

    def test_payment_detail_owner_with_explicit_workspace_header(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get(
            f"/payments/{self.ids['payment_id']}",
            headers={"X-Workspace-Id": self.ids["owner_id"]},
        )
        self.assertEqual(res.status_code, 200)

    def test_payment_detail_idor_blocked_without_workspace_header(self):
        # L'attaquant n'envoie pas de header workspace : owner_id retombe sur
        # son propre id, qui ne possède pas ce paiement -> 404, pas 200/403.
        self.as_user(self.ids["attacker_id"])
        res = self.client.get(f"/payments/{self.ids['payment_id']}")
        self.assertEqual(res.status_code, 404)

    def test_payment_detail_blocked_with_foreign_workspace_header(self):
        # L'attaquant tente d'usurper le workspace de la victime explicitement.
        self.as_user(self.ids["attacker_id"])
        res = self.client.get(
            f"/payments/{self.ids['payment_id']}",
            headers={"X-Workspace-Id": self.ids["owner_id"]},
        )
        self.assertEqual(res.status_code, 403)

    def test_payment_detail_requires_pro_or_business(self):
        self.as_user(self.ids["free_owner_id"])
        res = self.client.get(f"/payments/{self.ids['free_payment_id']}")
        self.assertEqual(res.status_code, 403)

    def test_payment_detail_not_found(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get("/payments/py_does_not_exist")
        self.assertEqual(res.status_code, 404)

    # --- Retrait ---

    def test_withdrawal_detail_owner_can_access(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get(f"/withdrawals/{self.ids['withdrawal_id']}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["withdrawal_id"], self.ids["withdrawal_id"])

    def test_withdrawal_detail_idor_blocked_without_workspace_header(self):
        self.as_user(self.ids["attacker_id"])
        res = self.client.get(f"/withdrawals/{self.ids['withdrawal_id']}")
        self.assertEqual(res.status_code, 404)

    def test_withdrawal_detail_blocked_with_foreign_workspace_header(self):
        self.as_user(self.ids["attacker_id"])
        res = self.client.get(
            f"/withdrawals/{self.ids['withdrawal_id']}",
            headers={"X-Workspace-Id": self.ids["owner_id"]},
        )
        self.assertEqual(res.status_code, 403)

    def test_withdrawal_detail_requires_pro_or_business(self):
        self.as_user(self.ids["free_owner_id"])
        res = self.client.get(f"/withdrawals/{self.ids['free_withdrawal_id']}")
        self.assertEqual(res.status_code, 403)

    def test_withdrawal_detail_not_found(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get("/withdrawals/wd_does_not_exist")
        self.assertEqual(res.status_code, 404)

    # --- Lien ---

    def test_link_detail_owner_can_access(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get(f"/links/{self.ids['link_id']}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], self.ids["link_id"])

    def test_link_detail_idor_blocked_without_workspace_header(self):
        self.as_user(self.ids["attacker_id"])
        res = self.client.get(f"/links/{self.ids['link_id']}")
        self.assertEqual(res.status_code, 404)

    def test_link_detail_blocked_with_foreign_workspace_header(self):
        self.as_user(self.ids["attacker_id"])
        res = self.client.get(
            f"/links/{self.ids['link_id']}",
            headers={"X-Workspace-Id": self.ids["owner_id"]},
        )
        self.assertEqual(res.status_code, 403)

    def test_link_detail_no_plan_restriction(self):
        # Contrairement aux paiements/retraits, le détail d'un lien suit le
        # même accès que GET /links : aucun gating de plan.
        self.as_user(self.ids["free_owner_id"])
        res = self.client.get(f"/links/{self.ids['free_link_id']}")
        self.assertEqual(res.status_code, 200)

    def test_link_detail_not_found(self):
        self.as_user(self.ids["owner_id"])
        res = self.client.get("/links/lk_does_not_exist")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
