"""Provisioning Buildshop (demande du 2026-11-27, suite de la discussion
d'architecture Shopify) - 2 angles, même esprit que
test_alhu_workspace_isolation.py :

1. GARDE-FOU CRITIQUE (_require_buildshop_shop) : une boutique DÉJÀ
   rattachée à un marchand réel (ShopifyShop.merchant_id non NULL) doit
   être refusée (409) AVANT tout appel Shopify - jamais une action
   Buildshop ne doit pouvoir s'exécuter sur la boutique d'un marchand
   en production. Testé au niveau route (mocks Shopify jamais appelés)
   ET au niveau fonction.
2. GATE INTERNE (_require_buildshop_internal_key) : sans clé configurée
   -> 503 ; mauvaise clé -> 401 ; bonne clé -> passe.

Shopify n'est JAMAIS vraiment appelé (pas de sandbox Partner pilotable
depuis cet environnement, même limite documentée en tête de
shopify_service.py) - mocké au niveau des fonctions buildshop_service
importées PAR LE MODULE ROUTE (backend.routes.shopify.provision_theme,
PAS backend.services.buildshop_service.provision_theme - même piège
déjà rencontré et corrigé pour Alhu : patcher l'origine ne change rien
à la référence déjà liée par l'import `from ... import` du module
appelant)."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import ShopifyShop
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
    import backend.routes.shopify as shopify_routes
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
    app.include_router(shopify_routes.router)
    app.dependency_overrides[get_db] = override_get_db
    return app


class BuildshopInternalKeyGateTests(unittest.TestCase):
    def setUp(self):
        self.app = build_app()
        self.client = TestClient(self.app)
        self._original_key = shopify_routes.BUILDSHOP_INTERNAL_API_KEY

    def tearDown(self):
        shopify_routes.BUILDSHOP_INTERNAL_API_KEY = self._original_key

    def test_missing_server_key_returns_503(self):
        shopify_routes.BUILDSHOP_INTERNAL_API_KEY = None
        res = self.client.get("/buildshop/readiness", params={"shop_domain": "whatever.myshopify.com"})
        self.assertEqual(res.status_code, 503)

    def test_wrong_key_returns_401(self):
        shopify_routes.BUILDSHOP_INTERNAL_API_KEY = "correct-key"
        res = self.client.get(
            "/buildshop/readiness",
            params={"shop_domain": "whatever.myshopify.com"},
            headers={"X-Buildshop-Internal-Key": "wrong-key"},
        )
        self.assertEqual(res.status_code, 401)

    def test_missing_header_returns_401(self):
        shopify_routes.BUILDSHOP_INTERNAL_API_KEY = "correct-key"
        res = self.client.get("/buildshop/readiness", params={"shop_domain": "whatever.myshopify.com"})
        self.assertEqual(res.status_code, 401)

    def test_correct_key_passes_gate(self):
        shopify_routes.BUILDSHOP_INTERNAL_API_KEY = "correct-key"
        # Clé correcte mais boutique inexistante -> doit atteindre la
        # logique métier (404), pas rester bloqué à 401/503 : prouve que
        # la gate elle-même a bien laissé passer.
        res = self.client.get(
            "/buildshop/readiness",
            params={"shop_domain": "inexistante.myshopify.com"},
            headers={"X-Buildshop-Internal-Key": "correct-key"},
        )
        self.assertEqual(res.status_code, 404)


class BuildshopMerchantGuardTests(unittest.TestCase):
    """Le garde-fou le plus critique du module entier : une boutique
    déjà rattachée à un marchand ne doit JAMAIS être touchée par
    Buildshop."""

    def setUp(self):
        self.app = build_app()
        self.client = TestClient(self.app)
        self.headers = {"X-Buildshop-Internal-Key": "test-key"}
        shopify_routes.BUILDSHOP_INTERNAL_API_KEY = "test-key"

        self.db = TestingSessionLocal()
        suffix = id(self)
        self.pre_transfer_domain = f"buildshop-{suffix}.myshopify.com"
        self.merchant_domain = f"merchant-{suffix}.myshopify.com"
        self.db.add(ShopifyShop(
            shop_domain=self.pre_transfer_domain,
            merchant_id=None,
            access_token=encrypt_secret("shpat_pre_transfer_token"),
        ))
        self.db.add(ShopifyShop(
            shop_domain=self.merchant_domain,
            merchant_id=f"usr_{suffix}",
            access_token=encrypt_secret("shpat_merchant_token"),
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch("backend.routes.shopify.provision_webhook")
    @patch("backend.routes.shopify.provision_catalog")
    @patch("backend.routes.shopify.provision_theme")
    def test_provision_rejects_merchant_attached_shop(self, mock_theme, mock_catalog, mock_webhook):
        res = self.client.post(
            "/buildshop/provision",
            json={"shop_domain": self.merchant_domain},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 409)
        mock_theme.assert_not_called()
        mock_catalog.assert_not_called()
        mock_webhook.assert_not_called()

    @patch("backend.routes.shopify.get_buildshop_readiness")
    def test_readiness_rejects_merchant_attached_shop(self, mock_readiness):
        res = self.client.get(
            "/buildshop/readiness",
            params={"shop_domain": self.merchant_domain},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 409)
        mock_readiness.assert_not_called()

    @patch("backend.routes.shopify.provision_webhook")
    @patch("backend.routes.shopify.provision_catalog")
    @patch("backend.routes.shopify.provision_theme")
    def test_provision_accepts_pre_transfer_shop_and_calls_all_three_steps(self, mock_theme, mock_catalog, mock_webhook):
        async def _theme(*a, **kw):
            return {"status": "created", "theme": {"id": "gid://shopify/OnlineStoreTheme/1"}}

        async def _catalog(*a, **kw):
            return {"created": [], "skipped_existing": []}

        async def _webhook(*a, **kw):
            return {"status": "already_registered"}

        mock_theme.side_effect = _theme
        mock_catalog.side_effect = _catalog
        mock_webhook.side_effect = _webhook

        res = self.client.post(
            "/buildshop/provision",
            json={"shop_domain": self.pre_transfer_domain},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        mock_theme.assert_called_once()
        mock_catalog.assert_called_once()
        mock_webhook.assert_called_once()
        # 1er argument positionnel = shop_domain, 2e = le token DÉCHIFFRÉ
        # (jamais le token chiffré tel que stocké en base) - voir
        # routes/shopify.py::buildshop_provision.
        self.assertEqual(mock_theme.call_args[0][0], self.pre_transfer_domain)
        self.assertEqual(mock_theme.call_args[0][1], "shpat_pre_transfer_token")

    def test_provision_rejects_unknown_shop(self):
        res = self.client.post(
            "/buildshop/provision",
            json={"shop_domain": "jamais-installee.myshopify.com"},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 404)

    def test_provision_rejects_invalid_domain(self):
        res = self.client.post(
            "/buildshop/provision",
            json={"shop_domain": "https://not-a-domain.com"},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 400)


class BuildshopServiceIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    """Logique pure de services/buildshop_service.py (jamais de FastAPI/
    DB ici) - prouve l'idempotence de chaque étape : un retry après
    échec partiel ne doit jamais dupliquer un thème/produit/webhook déjà
    présent. Mocks posés sur backend.services.buildshop_service (où ces
    fonctions sont IMPORTÉES et donc effectivement appelées), jamais sur
    backend.services.shopify_service (leur origine) - même piège que
    plus haut dans ce fichier."""

    async def test_provision_theme_skips_when_already_exists(self):
        import backend.services.buildshop_service as buildshop_service
        with patch.object(buildshop_service, "BUILDSHOP_THEME_ZIP_URL", "https://example.com/theme.zip"), \
             patch.object(buildshop_service, "BUILDSHOP_THEME_NAME", "Xepay Buildshop"), \
             patch("backend.services.buildshop_service.list_themes") as mock_list, \
             patch("backend.services.buildshop_service.create_theme_from_url") as mock_create:
            async def _list(*a, **kw):
                return [{"name": "Xepay Buildshop", "processing": False, "processingFailed": False}]
            mock_list.side_effect = _list

            result = await buildshop_service.provision_theme("shop.myshopify.com", "token")
            self.assertEqual(result["status"], "already_exists")
            mock_create.assert_not_called()

    async def test_provision_theme_creates_when_missing(self):
        import backend.services.buildshop_service as buildshop_service
        with patch.object(buildshop_service, "BUILDSHOP_THEME_ZIP_URL", "https://example.com/theme.zip"), \
             patch("backend.services.buildshop_service.list_themes") as mock_list, \
             patch("backend.services.buildshop_service.create_theme_from_url") as mock_create:
            async def _list(*a, **kw):
                return []

            async def _create(*a, **kw):
                return {"id": "gid://shopify/OnlineStoreTheme/1", "processing": True}

            mock_list.side_effect = _list
            mock_create.side_effect = _create

            result = await buildshop_service.provision_theme("shop.myshopify.com", "token")
            self.assertEqual(result["status"], "created")
            mock_create.assert_called_once()

    async def test_provision_theme_skipped_without_zip_url(self):
        import backend.services.buildshop_service as buildshop_service
        with patch.object(buildshop_service, "BUILDSHOP_THEME_ZIP_URL", None), \
             patch("backend.services.buildshop_service.create_theme_from_url") as mock_create:
            result = await buildshop_service.provision_theme("shop.myshopify.com", "token")
            self.assertEqual(result["status"], "skipped")
            mock_create.assert_not_called()

    async def test_provision_catalog_skips_existing_titles_only(self):
        import backend.services.buildshop_service as buildshop_service
        with patch("backend.services.buildshop_service.find_products_by_title") as mock_find, \
             patch("backend.services.buildshop_service.create_product") as mock_create:
            async def _find(shop, token, title):
                return [{"id": "gid://shopify/Product/1"}] if title == "Déjà là" else []

            async def _create(*a, **kw):
                return {"id": "gid://shopify/Product/2", "title": kw.get("title")}

            mock_find.side_effect = _find
            mock_create.side_effect = _create

            result = await buildshop_service.provision_catalog(
                "shop.myshopify.com", "token",
                catalog=[{"title": "Déjà là"}, {"title": "Nouveau produit"}],
            )
            self.assertEqual(len(result["skipped_existing"]), 1)
            self.assertEqual(result["skipped_existing"][0]["title"], "Déjà là")
            self.assertEqual(len(result["created"]), 1)
            mock_create.assert_called_once()

    async def test_provision_webhook_skips_when_already_registered(self):
        import backend.services.buildshop_service as buildshop_service
        with patch("backend.services.buildshop_service.is_order_webhook_registered") as mock_check, \
             patch("backend.services.buildshop_service.register_order_webhook") as mock_register:
            async def _check(*a, **kw):
                return True
            mock_check.side_effect = _check

            result = await buildshop_service.provision_webhook("shop.myshopify.com", "token")
            self.assertEqual(result["status"], "already_registered")
            mock_register.assert_not_called()

    async def test_readiness_survives_one_failing_check(self):
        """Un check Shopify en échec (ex. thème) ne doit jamais faire
        disparaître les 2 AUTRES - chacun reste rapporté, le défaillant
        en "error" plutôt que de faire tout planter."""
        import backend.services.buildshop_service as buildshop_service
        from backend.services.shopify_service import ShopifyAPIError
        with patch.object(buildshop_service, "BUILDSHOP_THEME_ZIP_URL", "https://example.com/theme.zip"), \
             patch("backend.services.buildshop_service.list_themes") as mock_themes, \
             patch("backend.services.buildshop_service.list_products") as mock_products, \
             patch("backend.services.buildshop_service.is_order_webhook_registered") as mock_webhook:
            async def _themes_fail(*a, **kw):
                raise ShopifyAPIError(502, "panne Shopify")

            async def _products(*a, **kw):
                return [{"id": "1"}, {"id": "2"}, {"id": "3"}]

            async def _webhook(*a, **kw):
                return True

            mock_themes.side_effect = _themes_fail
            mock_products.side_effect = _products
            mock_webhook.side_effect = _webhook

            checks = await buildshop_service.get_buildshop_readiness("shop.myshopify.com", "token")
            by_key = {c["key"]: c for c in checks}
            self.assertEqual(by_key["theme"]["status"], "error")
            self.assertEqual(by_key["catalog"]["status"], "ok")
            self.assertEqual(by_key["orders_webhook"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
