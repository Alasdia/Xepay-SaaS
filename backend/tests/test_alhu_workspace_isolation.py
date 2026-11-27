"""Isolation stricte entre workspaces pour Alhu (demande explicite du
2026-11-27, "sécurité maximale... ne doit jamais donner des informations
sur un autre workspace") - 2 angles distincts :

1. Niveau ROUTE : X-Workspace-Id pointant vers un workspace dont
   l'utilisateur n'est PAS membre doit être refusé (403) par
   get_membership AVANT même d'atteindre Alhu/les outils - jamais une
   requête LLM ne doit être tentée dans ce cas (mocké et vérifié
   explicitement).
2. Niveau OUTIL : get_balance/get_recent_transactions/
   get_buildness_status/get_stripe_connect_status, appelés directement
   avec 2 workspace_id réels distincts (chacun avec ses propres
   données), ne doivent JAMAIS renvoyer les données de l'autre - testé
   sans dépendre du LLM (non déterministe), qui n'intervient pas dans
   le filtrage des requêtes SQL/Stripe, seulement dans leur usage une
   fois renvoyées.

Même conventions que test_verto_routes.py (SQLite mémoire, dependency
overrides, WorkspaceUser réels)."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import (
    BuildnessCompany,
    BuildnessCustomer,
    UserDB,
    Wallet,
    WalletTransaction,
    WorkspaceUser,
)

# Même précaution que test_verto_routes.py : backend/routes/__init__.py
# ouvre une vraie connexion réseau à la base de prod à l'import du
# package - neutralisée le temps du seul import.
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
    from backend.routes.alhu import router as alhu_router
finally:
    _database.engine.connect = _real_engine_connect

from backend.services import alhu_service

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)

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
    app.include_router(alhu_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


class AlhuRouteWorkspaceIsolationTests(unittest.TestCase):
    """Niveau route : get_membership doit refuser AVANT tout appel LLM."""

    def setUp(self):
        self.db = TestingSessionLocal()
        self.user = UserDB(email=f"alhu-route-{id(self)}@example.com", password="x")
        self.other_workspace_owner = UserDB(email=f"alhu-other-{id(self)}@example.com", password="x")
        self.db.add_all([self.user, self.other_workspace_owner])
        self.db.flush()
        # self.user n'est membre QUE de son propre workspace, jamais de
        # celui de other_workspace_owner.
        self.db.add(WorkspaceUser(user_id=self.user.id, workspace_id=self.user.id, role="owner"))
        self.db.add(WorkspaceUser(
            user_id=self.other_workspace_owner.id,
            workspace_id=self.other_workspace_owner.id,
            role="owner",
        ))
        self.db.commit()
        _active_user_id["value"] = self.user.id
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.alhu.stream_alhu_chat")
    def test_foreign_workspace_id_is_rejected_before_reaching_alhu(self, mock_stream):
        """X-Workspace-Id = le workspace d'un AUTRE utilisateur (pas un
        membre) -> 403, et stream_alhu_chat (donc tout appel LLM/outil)
        n'est jamais invoqué."""
        res = self.client.post(
            "/alhu/chat",
            headers={"X-Workspace-Id": self.other_workspace_owner.id},
            json={"messages": [{"role": "user", "content": "Quel est mon solde ?"}]},
        )
        self.assertEqual(res.status_code, 403)
        mock_stream.assert_not_called()

    @patch("backend.routes.alhu.stream_alhu_chat")
    def test_own_workspace_id_is_accepted(self, mock_stream):
        """Son propre workspace (celui dont il est owner) doit, lui,
        être accepté - confirme que le 403 ci-dessus est bien dû à
        l'absence de membership, pas à un défaut générique de la route."""
        mock_stream.return_value = iter([{"type": "done", "reply": "ok"}])
        res = self.client.post(
            "/alhu/chat",
            headers={"X-Workspace-Id": self.user.id},
            json={"messages": [{"role": "user", "content": "Quel est mon solde ?"}]},
        )
        self.assertEqual(res.status_code, 200)
        mock_stream.assert_called_once()
        # 1er argument positionnel de stream_alhu_chat = workspace_id -
        # doit être EXACTEMENT celui du header, jamais substitué.
        self.assertEqual(mock_stream.call_args[0][0], self.user.id)


class AlhuToolWorkspaceIsolationTests(unittest.TestCase):
    """Niveau outil : 2 workspaces réels avec des données DIFFÉRENTES -
    chaque outil appelé avec le workspace_id A ne doit JAMAIS renvoyer
    une donnée appartenant à B, et réciproquement."""

    def setUp(self):
        self.db = TestingSessionLocal()

        user_a = UserDB(email=f"alhu-a-{id(self)}@example.com", password="x")
        user_b = UserDB(email=f"alhu-b-{id(self)}@example.com", password="x")
        self.db.add_all([user_a, user_b])
        self.db.flush()
        self.workspace_a = user_a.id
        self.workspace_b = user_b.id

        self.db.add(Wallet(user_id=self.workspace_a, balance=1000, available=900, pending=100))
        self.db.add(Wallet(user_id=self.workspace_b, balance=50, available=40, pending=10))

        self.db.add(WalletTransaction(
            user_id=self.workspace_a, wallet_id="wa-a", type="payment", direction="in",
            amount=900, status="success", reference=f"ref-a-1-{id(self)}", description="Paiement A",
        ))
        self.db.add(WalletTransaction(
            user_id=self.workspace_b, wallet_id="wa-b", type="payment", direction="in",
            amount=40, status="success", reference=f"ref-b-1-{id(self)}", description="Paiement B",
        ))

        customer_a = BuildnessCustomer(
            xepay_merchant_id=self.workspace_a, doola_customer_id=f"doola-cus-a-{id(self)}",
            email="a@example.com", first_name="A", last_name="Founder",
        )
        customer_b = BuildnessCustomer(
            xepay_merchant_id=self.workspace_b, doola_customer_id=f"doola-cus-b-{id(self)}",
            email="b@example.com", first_name="B", last_name="Founder",
        )
        self.db.add_all([customer_a, customer_b])
        self.db.flush()
        self.db.add(BuildnessCompany(
            customer_id=customer_a.id, company_name="Wave A LLC", state="WY",
            status="completed", ein_number="11-1111111",
        ))
        self.db.add(BuildnessCompany(
            customer_id=customer_b.id, company_name="Wave B LLC", state="DE",
            status="not_started",
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_get_balance_never_crosses_workspace(self):
        self.assertEqual(alhu_service._get_balance(self.db, self.workspace_a), {"available": 900, "pending": 100})
        self.assertEqual(alhu_service._get_balance(self.db, self.workspace_b), {"available": 40, "pending": 10})

    def test_get_recent_transactions_never_crosses_workspace(self):
        result_a = alhu_service._get_recent_transactions(self.db, self.workspace_a, limit=10)
        result_b = alhu_service._get_recent_transactions(self.db, self.workspace_b, limit=10)
        self.assertEqual(len(result_a["transactions"]), 1)
        self.assertEqual(result_a["transactions"][0]["description"], "Paiement A")
        self.assertEqual(len(result_b["transactions"]), 1)
        self.assertEqual(result_b["transactions"][0]["description"], "Paiement B")

    def test_get_buildness_status_never_crosses_workspace(self):
        result_a = alhu_service._get_buildness_status(self.db, self.workspace_a)
        result_b = alhu_service._get_buildness_status(self.db, self.workspace_b)
        self.assertEqual(result_a["company_name"], "Wave A LLC")
        self.assertEqual(result_a["status"], "completed")
        self.assertEqual(result_b["company_name"], "Wave B LLC")
        self.assertEqual(result_b["status"], "not_started")

    def test_unknown_workspace_id_never_falls_back_to_someone_elses_data(self):
        """Un workspace_id qui n'existe nulle part (jamais le cas en
        pratique, get_membership l'aurait déjà refusé plus haut) ne doit
        renvoyer AUCUNE donnée plutôt que, par erreur, celle d'un autre."""
        result = alhu_service._get_balance(self.db, "workspace-inexistant")
        self.assertEqual(result, {"available": 0, "pending": 0})


if __name__ == "__main__":
    unittest.main()
