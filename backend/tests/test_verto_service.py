import importlib
import os
import time
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

        # Cas "sans surcharge" testé en supprimant explicitement la clé ET
        # en neutralisant load_dotenv() - sinon reload() la réimporte
        # aussitôt depuis le vrai .env de la machine (elle y a été
        # ajoutée depuis, voir conversation du 2026-11-07), rendant
        # impossible de tester l'absence d'override indépendamment du
        # fichier .env réel.
        # Patch sur dotenv.load_dotenv (la source), pas
        # backend.services.verto_service.load_dotenv : reload() ré-exécute
        # `from dotenv import load_dotenv`, qui réécraserait un patch posé
        # sur le nom local importé dans verto_service.
        with patch.dict(os.environ, {}, clear=False), patch("dotenv.load_dotenv"):
            os.environ.pop("VERTO_LOGIN_BASE_URL", None)
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


class TestValidateIbanBic(unittest.TestCase):
    # IBAN/BIC publics d'exemple utilisés tout au long de la conversation
    # du 2026-11-07 (bénéficiaire test-api-1, id 18023 en sandbox).
    VALID_IBAN = "SN08SN0100152000048500003035"
    VALID_BIC = "BICISNDXXXX"

    def test_valid_pair_does_not_raise(self):
        vs.validate_iban_bic(self.VALID_IBAN, self.VALID_BIC)

    def test_iban_wrong_length_raises(self):
        with self.assertRaises(ValueError):
            vs.validate_iban_bic(self.VALID_IBAN[:-1], self.VALID_BIC)

    def test_iban_non_uemoa_country_raises(self):
        non_uemoa_iban = "FR" + self.VALID_IBAN[2:]
        with self.assertRaises(ValueError):
            vs.validate_iban_bic(non_uemoa_iban, self.VALID_BIC)

    def test_bic_wrong_length_raises(self):
        with self.assertRaises(ValueError):
            vs.validate_iban_bic(self.VALID_IBAN, "BICISND")

    def test_bic_8_chars_is_valid_length(self):
        vs.validate_iban_bic(self.VALID_IBAN, "BICISNDX")

    def test_country_mismatch_raises(self):
        mismatched_bic = "BICITGDXXXX"  # TG (Togo) au lieu de SN
        with self.assertRaises(ValueError):
            vs.validate_iban_bic(self.VALID_IBAN, mismatched_bic)


class TestCreateBeneficiaryPayload(unittest.TestCase):
    """Vérifie le payload EXACT envoyé à Verto (voir les champs confirmés
    obligatoires/placés le 2026-11-07 : paymentMode LOCAL, BIC dans
    bankCode, bankAddress minimal, beneficiaryAddress complet)."""

    @patch("backend.services.verto_service._sub_account_headers", return_value={})
    @patch("backend.services.verto_service.requests.post")
    def test_exact_payload_sent_to_verto(self, mock_post, _mock_headers):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 18023, "verificationState": "approved"},
            raise_for_status=lambda: None,
        )

        vs.create_beneficiary(
            company_id="16262",
            currency_id=49,
            company_name="Test Merchant SARL",
            iban="SN08SN0100152000048500003035",
            bic="BICISNDXXXX",
            bank_name="SUNU Bank Senegal",
            bank_country_code="SN",
            beneficiary_address_line1="Adresse non precisee",
            beneficiary_country_code="SN",
            beneficiary_city="Dakar",
            beneficiary_postal_code="11000",
            beneficiary_state_or_province="Dakar",
        )

        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["json"],
            {
                "currencyId": 49,
                "beneficiaryType": "company",
                "paymentMode": "LOCAL",
                "accountNumber": "SN08SN0100152000048500003035",
                "bankCode": "BICISNDXXXX",
                "bankName": "SUNU Bank Senegal",
                "bankAddress": {"countryCode": "SN"},
                "beneficiaryAddress": {
                    "addressLine1": "Adresse non precisee",
                    "countryCode": "SN",
                    "city": "Dakar",
                    "postCode": "11000",
                    "stateOrProvience": "Dakar",
                },
                "companyName": "Test Merchant SARL",
            },
        )


class TestSubAccountTokenCache(unittest.TestCase):
    """Cache de jetons PAR SOUS-COMPTE (PARTNER_REFERRED, voir le plan du
    2026-11-07) - indépendant du cache du jeton parent (_jwt_cache)."""

    def setUp(self):
        vs._sub_account_jwt_cache.clear()

    @patch("backend.services.verto_service._sub_account_login")
    def test_two_company_ids_have_independent_entries(self, mock_login):
        mock_login.side_effect = lambda company_id: f"token-for-{company_id}"

        token_a = vs.get_sub_account_token("111")
        token_b = vs.get_sub_account_token("222")

        self.assertEqual(token_a, "token-for-111")
        self.assertEqual(token_b, "token-for-222")
        self.assertEqual(mock_login.call_count, 2)

    @patch("backend.services.verto_service._sub_account_login")
    def test_token_reused_before_expiry(self, mock_login):
        mock_login.return_value = "fake-token"
        vs.get_sub_account_token("111")
        vs.get_sub_account_token("111")
        # Un seul login malgré deux appels - le second a réutilisé le cache.
        mock_login.assert_called_once()

    @patch("backend.services.verto_service._sub_account_login")
    def test_token_renewed_once_expired(self, mock_login):
        mock_login.return_value = "fake-token"
        vs.get_sub_account_token("111")
        vs._sub_account_jwt_cache["111"]["expires_at"] = time.time() - 1
        vs.get_sub_account_token("111")
        self.assertEqual(mock_login.call_count, 2)

    def test_login_placeholder_never_leaks_a_token_value(self):
        # _sub_account_login n'est pas encore implémentée (endpoint NON
        # CONFIRMÉ) - vérifie que son message d'erreur ne contient jamais
        # de valeur de jeton (il n'y en a d'ailleurs aucune à ce stade,
        # ce test documente l'intention pour quand elle sera implémentée).
        with self.assertRaises(NotImplementedError) as ctx:
            vs._sub_account_login("111")
        self.assertNotIn("Bearer", str(ctx.exception))


class TestScopedFunctionsUseSubAccountHeaders(unittest.TestCase):
    """Les fonctions scoped à un marchand utilisent _sub_account_headers
    (jeton du BON company_id), jamais _headers (jeton parent) - voir le
    plan PARTNER_REFERRED du 2026-11-07."""

    @patch("backend.services.verto_service._sub_account_headers")
    @patch("backend.services.verto_service._headers")
    @patch("backend.services.verto_service.requests.post")
    def test_create_wallet_uses_sub_account_headers(self, mock_post, mock_headers, mock_sub_headers):
        mock_sub_headers.return_value = {"Authorization": "Bearer sub-token"}
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "w1"}, raise_for_status=lambda: None)

        vs.create_wallet("16262", currency="USD")

        mock_sub_headers.assert_called_once_with("16262")
        mock_headers.assert_not_called()

    @patch("backend.services.verto_service._sub_account_headers")
    @patch("backend.services.verto_service._headers")
    @patch("backend.services.verto_service.requests.get")
    def test_list_payment_purpose_codes_uses_sub_account_headers(self, mock_get, mock_headers, mock_sub_headers):
        mock_sub_headers.return_value = {"Authorization": "Bearer sub-token"}
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"documentTypes": []}, raise_for_status=lambda: None,
        )

        vs.list_payment_purpose_codes(company_id="16262", payment_direction="Outbound", currency="XOF", mode="LOCAL")

        mock_sub_headers.assert_called_once_with("16262")
        mock_headers.assert_not_called()

    @patch("backend.services.verto_service._sub_account_headers")
    @patch("backend.services.verto_service._headers")
    @patch("backend.services.verto_service.requests.post")
    def test_create_payment_request_uses_sub_account_headers(self, mock_post, mock_headers, mock_sub_headers):
        mock_sub_headers.return_value = {"Authorization": "Bearer sub-token"}
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "p1"}, raise_for_status=lambda: None)

        vs.create_payment_request(
            company_id="16262", beneficiary_id=1, purpose_id=1, amount_usd=5,
            wallet_id=1, client_reference="ref", payment_id="pay-1",
        )

        mock_sub_headers.assert_called_once_with("16262")
        mock_headers.assert_not_called()


if __name__ == "__main__":
    unittest.main()
