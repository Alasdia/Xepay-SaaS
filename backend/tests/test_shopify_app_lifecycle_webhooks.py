"""Cycle de vie de l'app Shopify (app/uninstalled) + RGPD obligatoire
(customers/data_request, customers/redact, shop/redact) - ajouté le
2026-11-28. AUCUN mirroring de données Shopify (produits/commandes/
clients) : le marchand préfère explicitement tout lire en direct via
l'API, jamais une copie côté Xepay (voir le docstring des fichiers
touchés pour le contexte - un chantier de mirroring complet a été
construit puis explicitement annulé le même jour).

1. app/uninstalled : marque ShopifyShop.uninstalled_at SANS jamais
   vider access_token (contrainte explicite du modèle) ; une boutique
   désinstallée ne résout plus jamais comme "connectée".
2. shop/redact : supprime la ligne ShopifyShop (connexion propre à
   Xepay) mais ne touche JAMAIS ShopifyOrderPayment/Link (propres
   registres financiers Xepay, pas une donnée Shopify).
3. customers/redact, customers/data_request : purement informatifs
   (rien à supprimer localement, aucune donnée client Shopify
   mirrorée) - la notification email ne doit jamais empêcher le reste
   de committer en cas de panne.
4. register_app_uninstalled_webhook (shopify_service.py) : idempotent,
   même principe que register_order_webhook déjà existant.

Signature HMAC mockée par défaut (verify_webhook_signature, patchée là
où elle est IMPORTÉE - backend.routes.webhook.shopify - jamais à son
origine), même conventions SQLite mémoire que les autres fichiers de
ce dossier. Les handlers de ce fichier ouvrent SessionLocal()
directement (jamais Depends(get_db)) - SessionLocal est donc patchée
là où elle est importée pour éviter toute tentative de connexion vers
le Postgres distant de prod pendant les tests (trouvé en débogant un
hang sur le chantier de mirroring annulé)."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Link, ShopifyOrderPayment, ShopifyShop, UserDB

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


class GdprTests(unittest.TestCase):
    def setUp(self):
        session_patcher = patch("backend.routes.webhook.shopify.SessionLocal", TestingSessionLocal)
        session_patcher.start()
        self.addCleanup(session_patcher.stop)

        self.app = build_app()
        self.client = TestClient(self.app)
        self.db = TestingSessionLocal()
        suffix = id(self)
        self.shop = f"gdpr-{suffix}.myshopify.com"
        self.owner = UserDB(email=f"gdpr-owner-{suffix}@example.com", password="x")
        self.db.add(self.owner)
        self.db.flush()
        self.db.add(ShopifyShop(shop_domain=self.shop, merchant_id=self.owner.id, access_token="shpat_fake"))

        link = Link(id=f"lk_{suffix}", token=f"tok_{suffix}", user_id=self.owner.id, name="Lien Xepay", source="shopify")
        self.db.add(link)
        self.db.flush()
        self.db.add(ShopifyOrderPayment(
            shop_domain=self.shop, shopify_order_id="11", shopify_order_gid="gid://shopify/Order/11",
            link_id=link.id, merchant_id=self.owner.id,
        ))
        self.db.commit()
        self.headers = {"X-Shopify-Shop-Domain": self.shop, "X-Shopify-Hmac-Sha256": "x"}

    def tearDown(self):
        self.db.close()

    @patch("backend.services.email_service.requests.post")
    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_customers_redact_is_informational_only(self, mock_verify, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "{}"
        res = self.client.post(
            "/webhook/shopify/customers-redact", headers=self.headers,
            json={"customer": {"id": 12, "email": "c@example.com"}},
        )
        self.assertEqual(res.status_code, 200)
        # La boutique reste connectée - customers/redact ne touche rien
        # localement (aucune donnée client Shopify mirrorée).
        self.assertIsNotNone(self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first())

    @patch("backend.services.email_service.requests.post")
    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_shop_redact_removes_shop_row_but_keeps_xepay_financial_records(self, mock_verify, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "{}"
        res = self.client.post("/webhook/shopify/shop-redact", headers=self.headers, json={"shop_id": 1})
        self.assertEqual(res.status_code, 200)

        self.assertIsNone(self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first())
        # ShopifyOrderPayment/Link = propres registres financiers Xepay,
        # jamais purgés par une redaction Shopify.
        self.assertEqual(
            self.db.query(ShopifyOrderPayment).filter(ShopifyOrderPayment.shop_domain == self.shop).count(), 1
        )
        self.assertIsNotNone(self.db.query(Link).filter(Link.user_id == self.owner.id).first())

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_shop_redact_deletion_commits_even_if_email_notification_fails(self, mock_verify):
        with patch(
            "backend.routes.webhook.shopify.send_shopify_gdpr_request_internal_email",
            side_effect=RuntimeError("Resend indisponible"),
        ):
            res = self.client.post("/webhook/shopify/shop-redact", headers=self.headers, json={"shop_id": 1})
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first())

    @patch("backend.services.email_service.requests.post")
    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_customers_data_request_never_errors(self, mock_verify, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "{}"
        res = self.client.post(
            "/webhook/shopify/customers-data-request", headers=self.headers,
            json={"customer": {"id": 12, "email": "c@example.com"}},
        )
        self.assertEqual(res.status_code, 200)


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
