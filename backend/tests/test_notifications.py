"""Centre de notifications (icône cloche, bandeau du haut - ajouté le
2026-11-28, demande explicite de l'utilisateur après confirmation que
le bouton existant n'était relié à rien) :

1. Routes dashboard (GET /notifications, GET /notifications/unread-
   count, POST /notifications/{id}/read, POST /notifications/read-all)
   - isolation stricte par workspace (jamais la notification d'un
     autre workspace, même structure que les tests Alhu).
2. Webhooks Shopify products/create, customers/create, et l'extension
   d'orders/create (TOUTE commande, pas seulement celles payées via le
   gateway manuel "Xepay") - créent chacun UN évènement ponctuel,
   jamais une copie synchronisée (voir create_notification,
   notification_service.py).
3. register_product_created_webhook/register_customer_created_webhook
   (shopify_service.py) : idempotents, même principe que
   register_app_uninstalled_webhook déjà testé ailleurs.

Même conventions SQLite mémoire + patch de SessionLocal là où elle est
IMPORTÉE (jamais à son origine) que les autres fichiers de ce dossier."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import Notification, ShopifyShop, UserDB, WorkspaceUser

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
    from backend.routes.notifications import router as notifications_router
    import backend.routes.webhook.shopify as shopify_webhooks
    import backend.services.shopify_service as shopify_service
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


def build_notifications_app():
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


def build_webhook_app():
    app = FastAPI()
    app.include_router(shopify_webhooks.router)
    app.dependency_overrides[get_db] = override_get_db
    return app


class NotificationRoutesTests(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.owner = UserDB(email=f"notif-owner-{suffix}@example.com", password="x")
        self.other_owner = UserDB(email=f"notif-other-{suffix}@example.com", password="x")
        self.db.add_all([self.owner, self.other_owner])
        self.db.flush()
        self.workspace_id = self.owner.id
        self.other_workspace_id = self.other_owner.id
        self.db.add(WorkspaceUser(user_id=self.owner.id, workspace_id=self.workspace_id, role="owner"))
        self.db.add(WorkspaceUser(user_id=self.other_owner.id, workspace_id=self.other_workspace_id, role="owner"))
        self.db.add(Notification(workspace_id=self.workspace_id, event_type="shopify_product_created", title="Nouveau produit", description="T-shirt"))
        self.db.add(Notification(workspace_id=self.other_workspace_id, event_type="shopify_product_created", title="Produit d'un autre workspace", description="X"))
        self.db.commit()
        _active_user_id["value"] = self.owner.id
        self.app = build_notifications_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    def test_list_notifications_scoped_to_own_workspace(self):
        res = self.client.get("/notifications", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["title"], "Nouveau produit")
        self.assertFalse(body[0]["read"])

    def test_cannot_list_another_workspace_notifications(self):
        res = self.client.get("/notifications", headers={"X-Workspace-Id": self.other_workspace_id})
        self.assertEqual(res.status_code, 403)

    def test_unread_count_reflects_real_state(self):
        res = self.client.get("/notifications/unread-count", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(res.json(), {"unread_count": 1})

    def test_mark_read_updates_unread_count(self):
        notif_id = self.db.query(Notification).filter(Notification.workspace_id == self.workspace_id).first().id
        res = self.client.post(f"/notifications/{notif_id}/read", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["read"])
        count_res = self.client.get("/notifications/unread-count", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(count_res.json(), {"unread_count": 0})

    def test_cannot_mark_another_workspace_notification_as_read(self):
        other_notif_id = self.db.query(Notification).filter(Notification.workspace_id == self.other_workspace_id).first().id
        res = self.client.post(f"/notifications/{other_notif_id}/read", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(res.status_code, 404)

    def test_mark_all_read(self):
        self.db.add(Notification(workspace_id=self.workspace_id, event_type="shopify_customer_created", title="Nouveau client"))
        self.db.commit()
        res = self.client.post("/notifications/read-all", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(res.status_code, 200)
        count_res = self.client.get("/notifications/unread-count", headers={"X-Workspace-Id": self.workspace_id})
        self.assertEqual(count_res.json(), {"unread_count": 0})


class ShopifyNotificationWebhookTests(unittest.TestCase):
    def setUp(self):
        session_patcher = patch("backend.routes.webhook.shopify.SessionLocal", TestingSessionLocal)
        session_patcher.start()
        self.addCleanup(session_patcher.stop)

        self.app = build_webhook_app()
        self.client = TestClient(self.app)
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.shop = f"notif-{suffix}.myshopify.com"
        self.owner = UserDB(email=f"notif-webhook-owner-{suffix}@example.com", password="x")
        self.db.add(self.owner)
        self.db.flush()
        self.db.add(ShopifyShop(shop_domain=self.shop, merchant_id=self.owner.id, access_token="shpat_fake"))
        self.db.commit()
        self.headers = {"X-Shopify-Shop-Domain": self.shop, "X-Shopify-Hmac-Sha256": "x"}

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_products_create_webhook_creates_a_notification(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/products-create", headers=self.headers,
            json={"id": 1, "title": "Nouveau T-shirt"},
        )
        self.assertEqual(res.status_code, 200)
        notif = self.db.query(Notification).filter(Notification.workspace_id == self.owner.id).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.event_type, "shopify_product_created")
        self.assertEqual(notif.description, "Nouveau T-shirt")

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_customers_create_webhook_creates_a_notification(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/customers-create", headers=self.headers,
            json={"id": 2, "first_name": "Alice", "last_name": "Dupont", "email": "alice@example.com"},
        )
        self.assertEqual(res.status_code, 200)
        notif = self.db.query(Notification).filter(Notification.workspace_id == self.owner.id).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.description, "Alice Dupont")

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_unrattached_shop_creates_no_notification(self, mock_verify):
        # Boutique jamais rattachée à un marchand (Buildshop pré-
        # transfert, merchant_id NULL) - aucune notification à créer,
        # aucun workspace à notifier.
        self.db.add(ShopifyShop(shop_domain="buildshop-pretransfer.myshopify.com", merchant_id=None, access_token="shpat_fake2"))
        self.db.commit()
        res = self.client.post(
            "/webhook/shopify/products-create",
            headers={"X-Shopify-Shop-Domain": "buildshop-pretransfer.myshopify.com", "X-Shopify-Hmac-Sha256": "x"},
            json={"id": 99, "title": "Produit Buildshop"},
        )
        self.assertEqual(res.status_code, 200)
        # DB SQLite partagée entre méthodes de test (même convention que
        # le reste de ce dossier) - jamais un count() global, qui
        # compterait aussi les notifications d'autres tests déjà
        # exécutés. Cherche spécifiquement celle que CE test aurait pu
        # créer par erreur.
        self.assertIsNone(
            self.db.query(Notification).filter(Notification.description == "Produit Buildshop").first()
        )

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_orders_create_notifies_for_every_order_regardless_of_gateway(self, mock_verify):
        # Commande payée via Shopify Payments (PAS le gateway manuel
        # "Xepay") - aucun lien Xepay généré, mais la notification DOIT
        # quand même être créée (la notification est indépendante de ce
        # filtre métier).
        res = self.client.post(
            "/webhook/shopify/orders-create", headers=self.headers,
            json={
                "id": 3, "name": "#2001", "financial_status": "paid",
                "payment_gateway_names": ["shopify_payments"], "total_price": "49.90", "currency": "EUR",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True, "ignored": True})
        notif = self.db.query(Notification).filter(
            Notification.workspace_id == self.owner.id, Notification.event_type == "shopify_order_created"
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("#2001", notif.title)
        self.assertEqual(notif.description, "49.90 EUR")


class RegisterNotificationWebhooksTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_product_created_webhook_is_idempotent(self):
        with patch.object(shopify_service, "_find_webhook_subscription_id") as mock_find, \
             patch.object(shopify_service, "_admin_graphql") as mock_graphql:
            async def _find(*a, **kw):
                return "existing-id"
            mock_find.side_effect = _find

            await shopify_service.register_product_created_webhook("shop.myshopify.com", "token")
            mock_graphql.assert_not_called()

    async def test_register_customer_created_webhook_creates_when_missing(self):
        with patch.object(shopify_service, "_find_webhook_subscription_id") as mock_find, \
             patch.object(shopify_service, "_admin_graphql") as mock_graphql:
            async def _find(*a, **kw):
                return None

            async def _graphql(*a, **kw):
                return {"webhookSubscriptionCreate": {"webhookSubscription": {"id": "x"}, "userErrors": []}}

            mock_find.side_effect = _find
            mock_graphql.side_effect = _graphql

            await shopify_service.register_customer_created_webhook("shop.myshopify.com", "token")
            mock_graphql.assert_called_once()
            self.assertEqual(mock_graphql.call_args[0][3]["topic"], "CUSTOMERS_CREATE")


if __name__ == "__main__":
    unittest.main()
