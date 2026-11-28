"""Commande créée DEPUIS le dashboard Xepay pour un client du marchand
(ajouté le 2026-11-28, demande explicite : "le marchand doit comprendre
que cette commande... est payée via un lien xepay") :

1. POST /shopify/draft-orders (routes/shopify.py) - crée la commande
   Shopify (draftOrderCreate, SANS jamais passer par le checkout natif,
   voir services/shopify_service.py::create_draft_order) puis un Link
   Xepay envoyé directement au client.
2. sync_draft_order_paid_with_shopify (services/
   shopify_order_sync_service.py) - appelée une fois ce Link payé,
   complète la commande côté Shopify (draftOrderComplete) ET crée une
   Notification confirmant explicitement au marchand que cette commande
   a été payée via Xepay.

Même conventions SQLite mémoire + patch de SessionLocal là où elle est
IMPORTÉE que les autres fichiers de ce dossier - aucun appel réel à
Shopify (create_draft_order/complete_draft_order mockés)."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import Link, Notification, ShopifyDraftOrderPayment, ShopifyShop, UserDB, WorkspaceUser
from backend.security import encrypt_secret

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
    from backend.services.shopify_order_sync_service import sync_draft_order_paid_with_shopify
finally:
    _database.engine.connect = _real_engine_connect

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


class CreateShopifyDraftOrderRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.owner = UserDB(email=f"draft-owner-{suffix}@example.com", password="x")
        self.db.add(self.owner)
        self.db.flush()
        self.workspace_id = self.owner.id
        self.db.add(WorkspaceUser(user_id=self.owner.id, workspace_id=self.workspace_id, role="owner"))
        self.shop = f"draft-{suffix}.myshopify.com"
        self.db.add(ShopifyShop(shop_domain=self.shop, merchant_id=self.owner.id, access_token=encrypt_secret("shpat_fake")))
        self.db.commit()
        _active_user_id["value"] = self.owner.id
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.shopify.send_shopify_payment_link_email")
    @patch("backend.routes.shopify.create_draft_order")
    def test_creates_link_and_sends_payment_email(self, mock_create_draft_order, mock_email):
        async def _create_draft_order(*args, **kwargs):
            # Vérifie que note/tags signalent bien l'origine Xepay (voir
            # routes/shopify.py::create_shopify_draft_order) - le
            # marchand doit pouvoir le comprendre depuis l'admin Shopify.
            self.assertIn("Xepay", kwargs.get("note") or "")
            self.assertEqual(kwargs.get("tags"), ["Xepay"])
            return {"id": "gid://shopify/DraftOrder/1", "totalPriceSet": {"shopMoney": {"amount": "49.90", "currencyCode": "EUR"}}}

        mock_create_draft_order.side_effect = _create_draft_order

        res = self.client.post(
            "/shopify/draft-orders",
            headers={"X-Workspace-Id": self.workspace_id},
            json={
                "customer_email": "client@example.com",
                "customer_name": "Alice Dupont",
                "line_items": [{"title": "T-shirt", "price": 49.90, "quantity": 1}],
            },
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["draft_order_gid"], "gid://shopify/DraftOrder/1")
        self.assertTrue(body["pay_url"])

        link = self.db.query(Link).filter(Link.id == self.db.query(ShopifyDraftOrderPayment).first().link_id).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.link_metadata["xepay_type"], "shopify_draft_order_payment")
        self.assertEqual(link.link_metadata["shopify_draft_order_gid"], "gid://shopify/DraftOrder/1")
        self.assertEqual(link.amount, 49.90)

        draft_payment = self.db.query(ShopifyDraftOrderPayment).filter(ShopifyDraftOrderPayment.link_id == link.id).first()
        self.assertIsNotNone(draft_payment)
        self.assertEqual(draft_payment.shop_domain, self.shop)
        self.assertEqual(draft_payment.merchant_id, self.workspace_id)
        self.assertIsNone(draft_payment.completed_at)

        mock_email.assert_called_once()

    def test_no_connected_shop_returns_404(self):
        self.db.query(ShopifyShop).delete()
        self.db.commit()
        res = self.client.post(
            "/shopify/draft-orders",
            headers={"X-Workspace-Id": self.workspace_id},
            json={"customer_email": "client@example.com", "line_items": [{"title": "T-shirt", "price": 10, "quantity": 1}]},
        )
        self.assertEqual(res.status_code, 404)

    def test_rejects_empty_line_items(self):
        res = self.client.post(
            "/shopify/draft-orders",
            headers={"X-Workspace-Id": self.workspace_id},
            json={"customer_email": "client@example.com", "line_items": []},
        )
        self.assertEqual(res.status_code, 422)


class SyncDraftOrderPaidWithShopifyTests(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.owner = UserDB(email=f"sync-draft-owner-{suffix}@example.com", password="x")
        self.db.add(self.owner)
        self.db.flush()
        self.shop = f"sync-draft-{suffix}.myshopify.com"
        self.db.add(ShopifyShop(shop_domain=self.shop, merchant_id=self.owner.id, access_token=encrypt_secret("shpat_fake")))
        self.link = Link(id=f"lk_{suffix}", token=f"tok_{suffix}", user_id=self.owner.id, email=self.owner.email, name="Commande Shopify")
        self.db.add(self.link)
        self.db.flush()
        self.draft_payment = ShopifyDraftOrderPayment(
            shop_domain=self.shop, draft_order_gid="gid://shopify/DraftOrder/42",
            link_id=self.link.id, merchant_id=self.owner.id,
        )
        self.db.add(self.draft_payment)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch("backend.services.shopify_order_sync_service.complete_draft_order")
    def test_completes_draft_order_and_creates_notification(self, mock_complete):
        async def _complete(*args, **kwargs):
            return {"id": "gid://shopify/DraftOrder/42", "order": {"id": "gid://shopify/Order/99", "name": "#1099"}}

        mock_complete.side_effect = _complete

        sync_draft_order_paid_with_shopify(self.db, self.link, "xepay-ref-1")

        self.db.refresh(self.draft_payment)
        self.assertIsNotNone(self.draft_payment.completed_at)
        self.assertEqual(self.draft_payment.xepay_reference, "xepay-ref-1")

        notif = self.db.query(Notification).filter(
            Notification.workspace_id == self.owner.id, Notification.event_type == "shopify_draft_order_paid"
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, "Commande Shopify payée via Xepay")

    @patch("backend.services.shopify_order_sync_service.complete_draft_order")
    def test_already_completed_is_a_no_op(self, mock_complete):
        from datetime import datetime, timezone
        self.draft_payment.completed_at = datetime.now(timezone.utc)
        self.db.commit()

        sync_draft_order_paid_with_shopify(self.db, self.link, "xepay-ref-2")
        mock_complete.assert_not_called()

    @patch("backend.services.shopify_order_sync_service.complete_draft_order")
    def test_missing_shop_token_does_not_raise(self, mock_complete):
        self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).delete()
        self.db.commit()

        sync_draft_order_paid_with_shopify(self.db, self.link, "xepay-ref-3")
        mock_complete.assert_not_called()
        self.db.refresh(self.draft_payment)
        self.assertIsNone(self.draft_payment.completed_at)


if __name__ == "__main__":
    unittest.main()
