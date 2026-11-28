"""Mirroring produits/commandes/clients + cycle de vie de l'app Shopify
(ajouté le 2026-11-28, demande explicite de synchronisation complète) :

1. Helpers d'upsert (_upsert_product_mirror/_upsert_order_mirror/
   _upsert_customer_mirror) : idempotents - un 2e appel sur le même id
   met à jour la ligne existante, jamais une seconde ligne.
2. Routes de webhook : signature invalide -> 401 (jamais traité comme
   valide) ; delete/redact suppriment les bonnes lignes, jamais
   d'autres ; app/uninstalled marque uninstalled_at SANS jamais vider
   access_token (contrainte explicite du modèle) ; shop/redact purge
   les 3 mirroirs + la ligne ShopifyShop, mais ne touche JAMAIS
   ShopifyOrderPayment/Link (propres registres financiers Xepay).
3. register_all_mirror_webhooks (shopify_service.py) : idempotent,
   best-effort par topic.

Signature HMAC MOCKÉE par défaut (verify_webhook_signature, patchée là
où elle est IMPORTÉE - backend.routes.webhook.shopify - jamais à son
origine) pour isoler la logique métier du calcul cryptographique, SAUF
un test dédié qui calcule une vraie signature pour prouver que le
branchement HMAC fonctionne réellement de bout en bout. Même
conventions SQLite mémoire que les autres fichiers de ce dossier."""
import base64
import hashlib
import hmac as hmac_module
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, SessionLocal as RealSessionLocal, get_db
from backend.models import (
    Link,
    ShopifyCustomerMirror,
    ShopifyOrderMirror,
    ShopifyOrderPayment,
    ShopifyProductMirror,
    ShopifyShop,
    UserDB,
)

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


class UpsertHelpersTests(unittest.TestCase):
    """Logique pure - pas de route, pas de DB SQLite mémoire partagée
    avec les autres classes (chaque test ouvre/ferme la sienne)."""

    def setUp(self):
        self.db = TestingSessionLocal()
        self.shop = f"shop-{id(self)}.myshopify.com"

    def tearDown(self):
        self.db.close()

    def test_upsert_product_mirror_is_idempotent(self):
        product = {
            "id": 111, "title": "T-shirt", "status": "active", "vendor": "Acme",
            "variants": [{"price": "19.99"}, {"price": "24.99"}],
            "image": {"src": "https://cdn.shopify.com/t.jpg"},
            "created_at": "2026-11-01T10:00:00-05:00", "updated_at": "2026-11-01T10:00:00-05:00",
        }
        shopify_webhooks._upsert_product_mirror(self.db, self.shop, product)
        shopify_webhooks._upsert_product_mirror(self.db, self.shop, {**product, "title": "T-shirt v2"})

        rows = self.db.query(ShopifyProductMirror).filter(
            ShopifyProductMirror.shop_domain == self.shop, ShopifyProductMirror.shopify_product_id == "111"
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "T-shirt v2")
        self.assertEqual(rows[0].price_min, 19.99)
        self.assertEqual(rows[0].price_max, 24.99)
        self.assertEqual(rows[0].image_url, "https://cdn.shopify.com/t.jpg")

    def test_upsert_order_mirror_is_idempotent(self):
        order = {
            "id": 222, "name": "#1001", "financial_status": "pending",
            "fulfillment_status": None, "total_price": "49.90", "currency": "EUR",
            "email": "client@example.com",
        }
        shopify_webhooks._upsert_order_mirror(self.db, self.shop, order)
        shopify_webhooks._upsert_order_mirror(self.db, self.shop, {**order, "financial_status": "paid"})

        rows = self.db.query(ShopifyOrderMirror).filter(
            ShopifyOrderMirror.shop_domain == self.shop, ShopifyOrderMirror.shopify_order_id == "222"
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].financial_status, "paid")
        self.assertEqual(rows[0].total_price, 49.90)
        self.assertEqual(rows[0].customer_email, "client@example.com")

    def test_upsert_customer_mirror_is_idempotent(self):
        customer = {
            "id": 333, "first_name": "Alice", "last_name": "Dupont",
            "email": "alice@example.com", "orders_count": 1, "total_spent": "10.00",
        }
        shopify_webhooks._upsert_customer_mirror(self.db, self.shop, customer)
        shopify_webhooks._upsert_customer_mirror(self.db, self.shop, {**customer, "orders_count": 2, "total_spent": "30.00"})

        rows = self.db.query(ShopifyCustomerMirror).filter(
            ShopifyCustomerMirror.shop_domain == self.shop, ShopifyCustomerMirror.shopify_customer_id == "333"
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].orders_count, 2)
        self.assertEqual(rows[0].total_spent, 30.00)

    def test_upsert_without_id_is_a_safe_noop(self):
        shopify_webhooks._upsert_product_mirror(self.db, self.shop, {"title": "sans id"})
        shopify_webhooks._upsert_order_mirror(self.db, self.shop, {"name": "#sans-id"})
        shopify_webhooks._upsert_customer_mirror(self.db, self.shop, {"email": "sans-id@example.com"})
        self.assertEqual(self.db.query(ShopifyProductMirror).filter(ShopifyProductMirror.shop_domain == self.shop).count(), 0)
        self.assertEqual(self.db.query(ShopifyOrderMirror).filter(ShopifyOrderMirror.shop_domain == self.shop).count(), 0)
        self.assertEqual(self.db.query(ShopifyCustomerMirror).filter(ShopifyCustomerMirror.shop_domain == self.shop).count(), 0)


class WebhookRouteTests(unittest.TestCase):
    """Signature HMAC mockée (passe toujours) - isole la logique métier
    de chaque route, testée via de vraies requêtes HTTP (TestClient)."""

    def setUp(self):
        # Les handlers de ce fichier ouvrent SessionLocal() directement
        # (jamais Depends(get_db), même pattern que le handler
        # orders/create pré-existant) - app.dependency_overrides[get_db]
        # n'a donc AUCUN effet sur eux. Patché ici où SessionLocal est
        # IMPORTÉ (backend.routes.webhook.shopify), jamais à son origine
        # (backend.database) - sans ça, chaque appel ouvre une VRAIE
        # connexion vers le Postgres distant de prod et reste bloqué
        # indéfiniment (trouvé en débogant un hang de 120s+ sur ce
        # fichier de test).
        session_patcher = patch("backend.routes.webhook.shopify.SessionLocal", TestingSessionLocal)
        session_patcher.start()
        self.addCleanup(session_patcher.stop)

        self.app = build_app()
        self.client = TestClient(self.app)
        self.shop = f"route-{id(self)}.myshopify.com"
        self.headers = {"X-Shopify-Shop-Domain": self.shop, "X-Shopify-Hmac-Sha256": "whatever"}
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_invalid_shop_domain_header_rejected(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/products-create",
            headers={"X-Shopify-Shop-Domain": "not-a-shop", "X-Shopify-Hmac-Sha256": "x"},
            json={"id": 1, "title": "x"},
        )
        self.assertEqual(res.status_code, 400)

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=False)
    def test_invalid_signature_rejected_before_any_db_write(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/products-create", headers=self.headers, json={"id": 999, "title": "x"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(
            self.db.query(ShopifyProductMirror).filter(ShopifyProductMirror.shop_domain == self.shop).count(), 0
        )

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_products_create_route_upserts(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/products-create", headers=self.headers,
            json={"id": 1, "title": "Produit A", "status": "active", "variants": [{"price": "9.99"}]},
        )
        self.assertEqual(res.status_code, 200)
        row = self.db.query(ShopifyProductMirror).filter(
            ShopifyProductMirror.shop_domain == self.shop, ShopifyProductMirror.shopify_product_id == "1"
        ).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.title, "Produit A")

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_products_delete_route_removes_row(self, mock_verify):
        shopify_webhooks._upsert_product_mirror(self.db, self.shop, {"id": 2, "title": "À supprimer"})
        res = self.client.post("/webhook/shopify/products-delete", headers=self.headers, json={"id": 2})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            self.db.query(ShopifyProductMirror).filter(
                ShopifyProductMirror.shop_domain == self.shop, ShopifyProductMirror.shopify_product_id == "2"
            ).count(),
            0,
        )

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_customers_delete_route_removes_row(self, mock_verify):
        shopify_webhooks._upsert_customer_mirror(self.db, self.shop, {"id": 3, "email": "a@example.com"})
        res = self.client.post("/webhook/shopify/customers-delete", headers=self.headers, json={"id": 3})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            self.db.query(ShopifyCustomerMirror).filter(
                ShopifyCustomerMirror.shop_domain == self.shop, ShopifyCustomerMirror.shopify_customer_id == "3"
            ).count(),
            0,
        )

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_orders_update_route_upserts(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/orders-update", headers=self.headers,
            json={"id": 4, "name": "#2001", "financial_status": "paid", "fulfillment_status": "fulfilled"},
        )
        self.assertEqual(res.status_code, 200)
        row = self.db.query(ShopifyOrderMirror).filter(
            ShopifyOrderMirror.shop_domain == self.shop, ShopifyOrderMirror.shopify_order_id == "4"
        ).first()
        self.assertEqual(row.fulfillment_status, "fulfilled")


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
        # Contrainte explicite du modèle : access_token ne doit JAMAIS
        # être vidé, même après désinstallation.
        self.assertEqual(row.access_token, "shpat_fake")

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_uninstalled_shop_no_longer_resolves_as_connected(self, mock_verify):
        self.client.post("/webhook/shopify/app-uninstalled", headers=self.headers, json={"id": 1})
        resolved = _get_connected_shop(self.db, self.owner.id)
        self.assertIsNone(resolved)

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_unknown_shop_uninstall_is_a_safe_noop(self, mock_verify):
        res = self.client.post(
            "/webhook/shopify/app-uninstalled",
            headers={"X-Shopify-Shop-Domain": "jamais-connue.myshopify.com", "X-Shopify-Hmac-Sha256": "x"},
            json={"id": 1},
        )
        self.assertEqual(res.status_code, 200)


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
        shopify_webhooks._upsert_product_mirror(self.db, self.shop, {"id": 10, "title": "P"})
        shopify_webhooks._upsert_order_mirror(self.db, self.shop, {"id": 11, "name": "#1"})
        shopify_webhooks._upsert_customer_mirror(self.db, self.shop, {"id": 12, "email": "c@example.com"})

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
    def test_customers_redact_deletes_customer_mirror_only(self, mock_verify, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "{}"
        res = self.client.post(
            "/webhook/shopify/customers-redact", headers=self.headers,
            json={"customer": {"id": 12, "email": "c@example.com"}},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            self.db.query(ShopifyCustomerMirror).filter(ShopifyCustomerMirror.shop_domain == self.shop).count(), 0
        )
        # Produits/commandes jamais touchés par une redaction CLIENT.
        self.assertEqual(
            self.db.query(ShopifyProductMirror).filter(ShopifyProductMirror.shop_domain == self.shop).count(), 1
        )

    @patch("backend.services.email_service.requests.post")
    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_shop_redact_purges_all_mirrors_and_shop_row_but_keeps_xepay_financial_records(self, mock_verify, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "{}"
        res = self.client.post("/webhook/shopify/shop-redact", headers=self.headers, json={"shop_id": 1})
        self.assertEqual(res.status_code, 200)

        self.assertEqual(self.db.query(ShopifyProductMirror).filter(ShopifyProductMirror.shop_domain == self.shop).count(), 0)
        self.assertEqual(self.db.query(ShopifyOrderMirror).filter(ShopifyOrderMirror.shop_domain == self.shop).count(), 0)
        self.assertEqual(self.db.query(ShopifyCustomerMirror).filter(ShopifyCustomerMirror.shop_domain == self.shop).count(), 0)
        self.assertIsNone(self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first())

        # ShopifyOrderPayment/Link = propres registres financiers Xepay,
        # jamais purgés par une redaction Shopify.
        self.assertEqual(
            self.db.query(ShopifyOrderPayment).filter(ShopifyOrderPayment.shop_domain == self.shop).count(), 1
        )
        self.assertIsNotNone(self.db.query(Link).filter(Link.user_id == self.owner.id).first())

    @patch("backend.routes.webhook.shopify.verify_webhook_signature", return_value=True)
    def test_shop_redact_deletion_commits_even_if_email_notification_fails(self, mock_verify):
        # L'email est best-effort (try/except dans la route) - une
        # panne du fournisseur d'email ne doit JAMAIS empêcher la
        # suppression RGPD de committer.
        with patch(
            "backend.routes.webhook.shopify.send_shopify_gdpr_request_internal_email",
            side_effect=RuntimeError("Resend indisponible"),
        ):
            res = self.client.post("/webhook/shopify/shop-redact", headers=self.headers, json={"shop_id": 1})
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(self.db.query(ShopifyShop).filter(ShopifyShop.shop_domain == self.shop).first())


class RegisterAllMirrorWebhooksTests(unittest.IsolatedAsyncioTestCase):
    async def test_skips_topics_already_registered_with_the_same_url(self):
        # TOUS les topics déjà enregistrés avec la BONNE URL - plus
        # rien à créer, _admin_graphql ne doit jamais être appelé.
        already_registered = [
            {"topic": topic, "endpoint": {"callbackUrl": url}}
            for topic, url in shopify_service.SHOPIFY_MIRROR_WEBHOOK_TOPICS.items()
        ]
        with patch.object(shopify_service, "_list_webhook_subscriptions") as mock_list, \
             patch.object(shopify_service, "_admin_graphql") as mock_graphql:
            async def _list(*a, **kw):
                return already_registered
            mock_list.side_effect = _list

            result = await shopify_service.register_all_mirror_webhooks("shop.myshopify.com", "token")
            self.assertEqual(result["created"], [])
            self.assertEqual(result["failed"], [])
            mock_graphql.assert_not_called()

    async def test_creates_missing_topics_and_is_resilient_to_one_failure(self):
        with patch.object(shopify_service, "_list_webhook_subscriptions") as mock_list, \
             patch.object(shopify_service, "_admin_graphql") as mock_graphql:
            async def _list(*a, **kw):
                return []

            async def _graphql(shop, token, query, variables=None):
                if variables["topic"] == "APP_UNINSTALLED":
                    raise shopify_service.ShopifyAPIError(500, "panne")
                return {"webhookSubscriptionCreate": {"webhookSubscription": {"id": "x"}, "userErrors": []}}

            mock_list.side_effect = _list
            mock_graphql.side_effect = _graphql

            result = await shopify_service.register_all_mirror_webhooks("shop.myshopify.com", "token")
            self.assertIn("APP_UNINSTALLED", [f["topic"] for f in result["failed"]])
            self.assertIn("PRODUCTS_CREATE", result["created"])
            # Toutes les AUTRES créations ont bien été tentées malgré
            # l'échec d'APP_UNINSTALLED.
            self.assertEqual(len(result["created"]), len(shopify_service.SHOPIFY_MIRROR_WEBHOOK_TOPICS) - 1)


class RealHmacSanityTest(unittest.TestCase):
    """Un seul test calcule une VRAIE signature HMAC (jamais mockée) -
    prouve que verify_webhook_signature/le branchement de la route
    fonctionnent réellement ensemble, pas seulement en mock."""

    def test_real_valid_signature_is_accepted_and_invalid_one_rejected(self):
        secret = shopify_service.SHOPIFY_CLIENT_SECRET
        if not secret:
            self.skipTest("SHOPIFY_CLIENT_SECRET non configuré dans cet environnement")

        session_patcher = patch("backend.routes.webhook.shopify.SessionLocal", TestingSessionLocal)
        session_patcher.start()
        self.addCleanup(session_patcher.stop)

        app = build_app()
        client = TestClient(app)
        body = json.dumps({"id": 55, "title": "Produit réel"}).encode()
        real_signature = base64.b64encode(
            hmac_module.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        res_ok = client.post(
            "/webhook/shopify/products-create",
            headers={
                "X-Shopify-Shop-Domain": "real-hmac-test.myshopify.com",
                "X-Shopify-Hmac-Sha256": real_signature,
                "Content-Type": "application/json",
            },
            content=body,
        )
        self.assertEqual(res_ok.status_code, 200)

        res_bad = client.post(
            "/webhook/shopify/products-create",
            headers={
                "X-Shopify-Shop-Domain": "real-hmac-test.myshopify.com",
                "X-Shopify-Hmac-Sha256": "signature-falsifiee",
                "Content-Type": "application/json",
            },
            content=body,
        )
        self.assertEqual(res_bad.status_code, 401)


if __name__ == "__main__":
    unittest.main()
