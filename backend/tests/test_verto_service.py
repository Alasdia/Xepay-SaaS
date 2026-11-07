import importlib
import os
import unittest
from unittest.mock import MagicMock, patch

from backend.services import verto_service as vs


class TestVertoLogin(unittest.TestCase):
    def setUp(self):
        vs._jwt_cache.update(
            {"token": None, "expires_at": 0, "company_id": None, "company_settings_id": None}
        )

    @patch("backend.services.verto_service.requests.post")
    def test_login_uses_configured_host(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"token": "fake-token", "companyId": "16262"},
        )
        vs._login()
        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.startswith(vs.VERTO_LOGIN_BASE_URL))
        self.assertIn("/users/login", called_url)


class TestVertoLoginBaseUrlOverride(unittest.TestCase):
    """VERTO_LOGIN_BASE_URL doit rester surchargeable via l'environnement
    (voir le commentaire dans verto_service.py : nécessaire tant que
    api-company-sandbox/users/login ne reconnaît pas notre clé)."""

    def tearDown(self):
        # Reconstruit le module avec l'environnement réel, quoi qu'il arrive
        # (même si une assertion échoue), pour ne jamais laisser les autres
        # tests de ce fichier avec une valeur surchargée en mémoire.
        importlib.reload(vs)

    def test_env_override(self):
        with patch.dict(os.environ, {"VERTO_LOGIN_BASE_URL": "https://api-v3-sandbox.vertofx.com"}):
            importlib.reload(vs)
            self.assertEqual(vs.VERTO_LOGIN_BASE_URL, "https://api-v3-sandbox.vertofx.com")

        importlib.reload(vs)
        self.assertEqual(vs.VERTO_LOGIN_BASE_URL, vs.VERTO_AUTH_BASE_URL)


class TestCreateSubAccount(unittest.TestCase):
    @patch("backend.services.verto_service._headers", return_value={})
    @patch("backend.services.verto_service.requests.post")
    def test_403_raises_atlas_not_enabled(self, mock_post, _mock_headers):
        mock_post.return_value = MagicMock(
            status_code=403,
            json=lambda: {"message": "Access Denied: You are not allowed to perform this action."},
        )
        with self.assertRaises(vs.VertoAtlasNotEnabledError):
            vs.create_sub_account(
                account_type="SUB_CLIENT",
                country="Cote D'Ivoire",
                name="Test Merchant SARL",
                sub_category="Financial Services",
                identification_number="TEST-0001",
            )

    @patch("backend.services.verto_service._headers", return_value={})
    @patch("backend.services.verto_service.requests.post")
    def test_success_returns_body(self, mock_post, _mock_headers):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "999", "status": "CREATED"},
            raise_for_status=lambda: None,
        )
        result = vs.create_sub_account(
            account_type="SUB_CLIENT",
            country="Cote D'Ivoire",
            name="Test Merchant SARL",
            sub_category="Financial Services",
            identification_number="TEST-0001",
        )
        self.assertEqual(result["id"], "999")


if __name__ == "__main__":
    unittest.main()
