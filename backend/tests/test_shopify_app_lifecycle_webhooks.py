"""Cycle de vie de l'app Shopify (app/uninstalled) - ajouté le
2026-11-28. AUCUN mirroring de données Shopify (produits/commandes/
clients) : le marchand préfère explicitement tout lire en direct via
l'API, jamais une copie côté Xepay (voir le docstring des fichiers
touchés pour le contexte - un chantier de mirroring complet a été
construit puis explicitement annulé le même jour).

Les 3 webhooks RGPD obligatoires (customers/data_request, customers/
redact, shop/redact) ont été envisagés puis RETIRÉS le 2026-11-28 :
Shopify ne les impose qu'aux apps listées sur l'App Store ("Custom
apps for a single store are not required to implement GDPR
webhooks"), "Xepay Sync" n'y est jamais soumise - et sans aucune
donnée Shopify mirorée, ils n'auraient eu aucune action réelle à
accomplir. Jamais ajoutés pour cette raison (voir le signalement de
l'utilisateur, "je ne vois aucune utilité sur ces 3 webhooks").

1. app/uninstalled : marque ShopifyShop.uninstalled_at SANS jamais
   vider access_token (contrainte explicite du modèle) ; une boutique
   désinstallée ne résout plus jamais comme "connectée".
2. register_app_uninstalled_webhook (shopify_service.py) : idempotent,
   même principe que register_order_webhook déjà existant.

Signature HMAC mockée par défaut (verify_webhook_signature, patchée là
où elle est IMPORTÉE - backend.routes.webhook.shopify - jamais à son
origine), même conventions SQLite mémoire que les autres fichiers de
ce dossier. Le handler ouvre SessionLocal() directement (jamais
Depends(get_db)) - SessionLocal est donc patchée là où elle est
importée pour éviter toute tentative de connexion vers le Postgres
distant de prod pendant les tests."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import ShopifyShop, UserDB

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
    import backend.routes.webhook.shopify as shopify_webhooks
    from backend.routes.shopify import _get_connected_shop
    import backend.services.shopify_service as shopify_service
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
    app.include_router(shopify_webhooks.router)
    app.dependency_overrides[get_db] = override_get_db
    return app


class AppUninstalledTests(unittest.TestCase):
    def setUp(self):
        session_patcher = patch("backend.routes.webhook.shopify.SessionLocal", TestingSessionLocal)
        session_patcher.start()
        self.addCleanup(session_patcher.stop)

        self.app = build_app()
        self.client = TestClient(self.app)
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.shop = f"uninstall-{suffix}.myshopify.com"
        self.owner = UserDB(email=f"uninstall-owner-{suffix}@example.com", password="x")
        self.db.add(self.owner)
        self.db.flush()
        self.db.add(ShopifyShop(shop_domain=self.shop, merchant_id=self.owner.id, access_token="shpat_fake"))
        self.db.commit()
        self.headers = {"X-Shopify-Shop-Domain": self.shop, "X-Shopify-Hmac-Sha256": "x"}

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_app_uninstalled_marks_shop_without_clearing_token(self, mock_verify):
        res = self.client.post("/webhook/shopify/app-uninstalled", headers=self.headers, json={"id": 1})
        self.assertEqual(res.status_code, 200)
        row = self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first()
        self.assertIsNotNone(row.uninstalled_at)
        self.assertEqual(row.access_token, "shpat_fake")

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_uninstalled_shop_no_longer_resolves_as_connected(self, mock_verify):
        self.client.post("/webhook/shopify/app-uninstalled", headers=self.headers, json={"id": 1})
        self.assertIsNone(_get_connected_shop(self.db, self.owner.id))

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_unknown_shop_uninstall_is_a_safe_noop(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/app-uninstalled",
            headers={"X-Shopify-Shop-Domain": "jamais-connue.myshopify.com", "X-Shopify-Hmac-Sha256": "x"},
            json={"id": 1},
        )
        self.assertEqual(res.status_code, 200)

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=False)
    def test_invalid_signature_rejected_before_any_db_write(self, mock_verify):
        res = self.client.post("/webhook/shopify/app-uninstalled", headers=self.headers, json={"id": 1})
        self.assertEqual(res.status_code, 401)
        row = self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first()
        self.assertIsNone(row.uninstalled_at)


class RegisterAppUninstalledWebhookTests(unittest.IsolatedAsyncioTestCase):
    async def test_skips_when_already_registered_with_the_same_url(self):
        with patch.object(shopify_service, "_find_app_uninstalled_webhook_subscription_id") as mock_find, \
             patch.object(shopify_service, "_admin_graphql") as mock_graphql:
            async def _find(*a, **kw):
                return "existing-id"
            mock_find.side_effect = _find

            await shopify_service.register_app_uninstalled_webhook("shop.myshopify.com", "token")
            mock_graphql.assert_not_called()

    async def test_creates_when_missing(self):
        with patch.object(shopify_service, "_find_app_uninstalled_webhook_subscription_id") as mock_find, \
             patch.object(shopify_service, "_admin_graphql") as mock_graphql:
            async def _find(*a, **kw):
                return None

            async def _graphql(*a, **kw):
                return {"webhookSubscriptionCreate": {"webhookSubscription": {"id": "x"}, "userErrors": []}}

            mock_find.side_effect = _find
            mock_graphql.side_effect = _graphql

            await shopify_service.register_app_uninstalled_webhook("shop.myshopify.com", "token")
            mock_graphql.assert_called_once()
            self.assertEqual(mock_graphql.call_args[0][3]["topic"], "APP_UNINSTALLED")


if __name__ == "__main__":
    unittest.main()
