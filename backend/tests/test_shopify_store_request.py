"""Demande de boutique Shopify "prête à l'emploi" (Buildshop) - ajouté
le 2026-11-27, 2 points d'entrée pour la MÊME action (enregistrer la
demande + alerter un humain côté Xepay, JAMAIS assigner/transférer une
boutique automatiquement - impossible via l'API Shopify, voir
services/buildshop_service.py) :

1. Route dashboard : POST /shopify/store-request (routes/shopify.py),
   gatée par la capacité de workspace "manage_shopify_integration"
   (owner par défaut, personnalisable).
2. Outil Alhu : request_shopify_store (alhu_service.py), proposé au
   modèle UNIQUEMENT si l'appelant satisfait cette même capacité
   (_build_tools), et re-vérifié indépendamment à l'exécution
   (_require_capability) même si cette offre était contournée.

Email réel JAMAIS envoyé (requests.post mocké) - mêmes conventions que
test_alhu_workspace_isolation.py/test_buildshop_provisioning.py
(SQLite mémoire, dependency overrides, WorkspaceUser réels, mocks
patchés là où ils sont IMPORTÉS, pas à leur origine)."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import ShopifyStoreRequest, UserDB, WorkspacePermissionOverride, WorkspaceUser

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
    from backend.routes.shopify import router as shopify_router
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
    app.include_router(shopify_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


class ShopifyStoreRequestRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.owner = UserDB(email=f"store-req-owner-{suffix}@example.com", password="x")
        self.member = UserDB(email=f"store-req-member-{suffix}@example.com", password="x")
        self.db.add_all([self.owner, self.member])
        self.db.flush()
        self.workspace_id = self.owner.id
        self.db.add(WorkspaceUser(user_id=self.owner.id, workspace_id=self.workspace_id, role="owner"))
        self.db.add(WorkspaceUser(user_id=self.member.id, workspace_id=self.workspace_id, role="membre"))
        self.db.commit()
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.shopify.send_shopify_store_request_internal_email")
    def test_owner_can_create_request_and_email_is_sent(self, mock_email):
        _active_user_id["value"] = self.owner.id
        res = self.client.post(
            "/shopify/store-request",
            headers={"X-Workspace-Id": self.workspace_id},
            json={"note": "Pour ma nouvelle gamme de produits"},
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["status"], "pending")
        mock_email.assert_called_once_with(
            self.workspace_id, self.owner.email, self.owner.email, "Pour ma nouvelle gamme de produits"
        )

        row = self.db.query(ShopifyStoreRequest).filter(ShopifyStoreRequest.id == body["id"]).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.workspace_id, self.workspace_id)

    @patch("backend.routes.shopify.send_shopify_store_request_internal_email")
    def test_non_owner_cannot_create_request_by_default(self, mock_email):
        _active_user_id["value"] = self.member.id
        res = self.client.post(
            "/shopify/store-request",
            headers={"X-Workspace-Id": self.workspace_id},
            json={"note": None},
        )
        self.assertEqual(res.status_code, 403)
        mock_email.assert_not_called()
        self.assertEqual(
            self.db.query(ShopifyStoreRequest).filter(ShopifyStoreRequest.workspace_id == self.workspace_id).count(),
            0,
        )

    @patch("backend.routes.shopify.send_shopify_store_request_internal_email")
    def test_list_requests_scoped_to_workspace(self, mock_email):
        _active_user_id["value"] = self.owner.id
        self.client.post("/shopify/store-request", headers={"X-Workspace-Id": self.workspace_id}, json={})
        res = self.client.get("/shopify/store-requests", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

    @patch("backend.routes.shopify.send_shopify_store_request_internal_email")
    def test_overridden_capability_lets_member_request_and_email_shows_both_emails(self, mock_email):
        # Le propriétaire a personnalisé manage_shopify_integration pour
        # "membre" sur CE workspace - le membre peut alors soumettre la
        # demande lui-même, et l'email doit distinguer qui l'a demandé
        # (requester_email) de qui est réellement propriétaire
        # (owner_email), jamais les confondre.
        self.db.add(WorkspacePermissionOverride(
            workspace_id=self.workspace_id, capability_key="manage_shopify_integration", min_role="membre",
        ))
        self.db.commit()

        _active_user_id["value"] = self.member.id
        res = self.client.post(
            "/shopify/store-request",
            headers={"X-Workspace-Id": self.workspace_id},
            json={"note": "demande par un membre"},
        )
        self.assertEqual(res.status_code, 201)
        mock_email.assert_called_once_with(
            self.workspace_id, self.owner.email, self.member.email, "demande par un membre"
        )


class AlhuRequestShopifyStoreTests(unittest.TestCase):
    """Même action, déclenchée via l'outil Alhu plutôt que la route
    dashboard - _require_capability (générique, respecte les
    surcharges) plutôt que _require_owner (réservé à la gestion
    d'équipe, jamais personnalisable)."""

    def setUp(self):
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.owner = UserDB(email=f"alhu-store-owner-{suffix}@example.com", password="x")
        self.member = UserDB(email=f"alhu-store-member-{suffix}@example.com", password="x")
        self.db.add_all([self.owner, self.member])
        self.db.flush()
        self.workspace_id = self.owner.id
        self.db.add(WorkspaceUser(user_id=self.owner.id, workspace_id=self.workspace_id, role="owner"))
        self.db.add(WorkspaceUser(user_id=self.member.id, workspace_id=self.workspace_id, role="membre"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch("backend.services.alhu_service.send_shopify_store_request_internal_email")
    def test_owner_can_request_store_via_alhu(self, mock_email):
        result = alhu_service._request_shopify_store(self.db, self.workspace_id, self.owner.id, "besoin rapide")
        self.assertTrue(result["success"])
        mock_email.assert_called_once_with(self.workspace_id, self.owner.email, self.owner.email, "besoin rapide")
        self.assertEqual(
            self.db.query(ShopifyStoreRequest).filter(ShopifyStoreRequest.workspace_id == self.workspace_id).count(),
            1,
        )

    @patch("backend.services.alhu_service.send_shopify_store_request_internal_email")
    def test_non_owner_blocked_by_default_via_alhu(self, mock_email):
        result = alhu_service._request_shopify_store(self.db, self.workspace_id, self.member.id, None)
        self.assertIn("error", result)
        mock_email.assert_not_called()
        self.assertEqual(
            self.db.query(ShopifyStoreRequest).filter(ShopifyStoreRequest.workspace_id == self.workspace_id).count(),
            0,
        )

    def test_note_is_truncated_defensively(self):
        with patch("backend.services.alhu_service.send_shopify_store_request_internal_email"):
            long_note = "x" * 5000
            result = alhu_service._request_shopify_store(self.db, self.workspace_id, self.owner.id, long_note)
            row = self.db.query(ShopifyStoreRequest).filter(ShopifyStoreRequest.id == result["id"]).first()
            self.assertEqual(len(row.note), 1000)

    def test_require_capability_rejects_non_member(self):
        outsider = UserDB(email=f"outsider-{id(self)}@example.com", password="x")
        self.db.add(outsider)
        self.db.commit()
        error = alhu_service._require_capability(self.db, self.workspace_id, outsider.id, "manage_shopify_integration")
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
