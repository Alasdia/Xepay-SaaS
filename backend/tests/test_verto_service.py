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

    @patch("backend.services.verto_service._headers", return_value={})
    @patch("backend.services.verto_service.requests.post")
    def test_exact_payload_sent_to_verto(self, mock_post, _mock_headers):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 18023, "verificationState": "approved"},
            raise_for_status=lambda: None,
        )

        vs.create_beneficiary(
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


if __name__ == "__main__":
    unittest.main()
