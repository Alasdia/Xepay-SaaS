import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import UserDB, WorkspaceUser, Profile

# Même précaution que test_detail_endpoints.py : backend/routes/__init__.py
# ouvre une vraie connexion réseau à la base de prod à l'import du package -
# neutralisée le temps du seul import.
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
    from backend.routes.verto import router as verto_router
finally:
    _database.engine.connect = _real_engine_connect

from backend.services import verto_service as vs

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
    app.include_router(verto_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


class TestVertoRoutesFeatureFlag(unittest.TestCase):
    """VERTO_ENABLED=false par défaut (voir le plan PARTNER_REFERRED du
    2026-11-07) : create_verto_sub_account, submit_verto_kyb_data,
    resend_director_consent et register_beneficiary doivent refuser avant
    tout appel réseau Verto. get_verto_status, lui, n'est volontairement
    PAS protégé (lecture DB pure, voir la décision explicite du
    2026-11-07 - sinon ça casserait l'affichage déjà fonctionnel de la
    vue Retraits)."""

    def setUp(self):
        self.db = TestingSessionLocal()
        user = UserDB(email=f"verto-route-test-{id(self)}@example.com", password="x")
        self.db.add(user)
        self.db.flush()
        self.db.add(WorkspaceUser(user_id=user.id, workspace_id=user.id, role="owner"))
        self.db.commit()
        self.user_id = user.id
        _active_user_id["value"] = user.id
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    def test_status_works_without_flag(self):
        res = self.client.get("/verto/status", headers={"X-Workspace-Id": self.user_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "not_started")

    @patch("backend.services.verto_service.VERTO_ENABLED", False)
    @patch("backend.services.verto_service.create_sub_account")
    def test_sub_account_creation_disabled_by_default(self, mock_create_sub_account):
        res = self.client.post(
            "/verto/onboarding/sub-account",
            headers={"X-Workspace-Id": self.user_id},
            json={
                "country": "Senegal", "company_name": "Test", "sub_category": "Financial Services",
                "identification_number": "X",
            },
        )
        self.assertEqual(res.status_code, 503)
        mock_create_sub_account.assert_not_called()

    @patch("backend.services.verto_service.VERTO_ENABLED", False)
    @patch("backend.services.verto_service.submit_onboarding_data")
    def test_kyb_data_disabled_by_default(self, mock_submit):
        profile = Profile(user_id=self.user_id, verto_company_id=str(id(self)), verto_onboarding_status="sub_account_created")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post(
            "/verto/onboarding/kyb-data",
            headers={"X-Workspace-Id": self.user_id},
            json={"kyc_payload": {}},
        )
        self.assertEqual(res.status_code, 503)
        mock_submit.assert_not_called()

    @patch("backend.services.verto_service.VERTO_ENABLED", False)
    @patch("backend.services.verto_service.send_director_consent_email")
    def test_resend_consent_disabled_by_default(self, mock_send):
        profile = Profile(user_id=self.user_id, verto_company_id=str(id(self)))
        self.db.add(profile)
        self.db.commit()

        res = self.client.post("/verto/resend-director-consent", headers={"X-Workspace-Id": self.user_id})
        self.assertEqual(res.status_code, 503)
        mock_send.assert_not_called()

    @patch("backend.services.verto_service.VERTO_ENABLED", False)
    @patch("backend.services.verto_service.create_beneficiary")
    def test_beneficiary_disabled_by_default(self, mock_create_beneficiary):
        profile = Profile(
            user_id=self.user_id, verto_company_id=str(id(self)), verto_onboarding_status="approved",
        )
        self.db.add(profile)
        self.db.commit()

        res = self.client.post(
            "/verto/beneficiary",
            headers={"X-Workspace-Id": self.user_id},
            json={
                "iban": "SN08SN0100152000048500003035", "bic": "BICISNDXXXX",
                "bank_name": "SUNU Bank Senegal", "bank_country_code": "SN",
                "beneficiary_address_line1": "x", "beneficiary_country_code": "SN",
                "beneficiary_city": "Dakar", "beneficiary_postal_code": "11000",
                "beneficiary_state_or_province": "Dakar",
            },
        )
        self.assertEqual(res.status_code, 503)
        mock_create_beneficiary.assert_not_called()


class TestDirectorConsentFlow(unittest.TestCase):
    """VERTO_ENABLED=true (monkeypatché) pour isoler la logique de
    consentement elle-même des autres gardes."""

    def setUp(self):
        self.db = TestingSessionLocal()
        user = UserDB(email=f"verto-consent-test-{id(self)}@example.com", password="x")
        self.db.add(user)
        self.db.flush()
        self.db.add(WorkspaceUser(user_id=user.id, workspace_id=user.id, role="owner"))
        self.db.commit()
        self.user_id = user.id
        _active_user_id["value"] = user.id
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.send_director_consent_email")
    @patch("backend.services.verto_service.submit_onboarding_data")
    def test_consent_email_success_sets_sent(self, _mock_submit, mock_consent):
        company_id = str(id(self))
        profile = Profile(user_id=self.user_id, verto_company_id=company_id, verto_onboarding_status="sub_account_created")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post(
            "/verto/onboarding/kyb-data",
            headers={"X-Workspace-Id": self.user_id},
            json={"kyc_payload": {}},
        )
        self.assertEqual(res.status_code, 200)
        mock_consent.assert_called_once_with(company_id)
        profile = self.db.query(Profile).filter(Profile.user_id == self.user_id).first()
        self.assertEqual(profile.verto_onboarding_status, "kyb_submitted")
        self.assertEqual(profile.verto_director_consent_status, "sent")

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.send_director_consent_email", side_effect=NotImplementedError("endpoint non confirmé"))
    @patch("backend.services.verto_service.submit_onboarding_data")
    def test_consent_email_failure_does_not_fail_kyb_submission(self, _mock_submit, _mock_consent):
        profile = Profile(user_id=self.user_id, verto_company_id=str(id(self)), verto_onboarding_status="sub_account_created")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post(
            "/verto/onboarding/kyb-data",
            headers={"X-Workspace-Id": self.user_id},
            json={"kyc_payload": {}},
        )
        self.assertEqual(res.status_code, 200)
        profile = self.db.query(Profile).filter(Profile.user_id == self.user_id).first()
        self.assertEqual(profile.verto_onboarding_status, "kyb_submitted")
        self.assertEqual(profile.verto_director_consent_status, "not_sent")

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    def test_kyb_data_requires_existing_sub_account(self):
        res = self.client.post(
            "/verto/onboarding/kyb-data",
            headers={"X-Workspace-Id": self.user_id},
            json={"kyc_payload": {}},
        )
        self.assertEqual(res.status_code, 400)

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.submit_onboarding_data")
    def test_kyb_data_rejected_after_approval(self, mock_submit):
        profile = Profile(user_id=self.user_id, verto_company_id=str(id(self)), verto_onboarding_status="approved")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post(
            "/verto/onboarding/kyb-data",
            headers={"X-Workspace-Id": self.user_id},
            json={"kyc_payload": {}},
        )
        self.assertEqual(res.status_code, 400)
        mock_submit.assert_not_called()


class TestSubAccountCreationCorrectifAudit(unittest.TestCase):
    """Correctif du bug identifié dans l'audit du 2026-11-07 : avant ce
    découpage, un échec de submit_onboarding_data après un
    create_sub_account réussi ne persistait RIEN, et chaque nouvelle
    tentative créait un sous-compte Verto supplémentaire. Ici,
    create_verto_sub_account persiste verto_company_id dès son propre
    succès, SANS dépendre de l'étape KYB - donc une tentative ultérieure
    doit être bloquée (400), jamais recréer de sous-compte."""

    def setUp(self):
        self.db = TestingSessionLocal()
        user = UserDB(email=f"verto-audit-fix-test-{id(self)}@example.com", password="x")
        self.db.add(user)
        self.db.flush()
        self.db.add(WorkspaceUser(user_id=user.id, workspace_id=user.id, role="owner"))
        self.db.commit()
        self.user_id = user.id
        _active_user_id["value"] = user.id
        self.app = build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    def test_company_id_persisted_immediately_after_creation(self):
        company_id = str(id(self))
        with patch("backend.services.verto_service.create_sub_account", return_value={"id": company_id}):
            res = self.client.post(
                "/verto/onboarding/sub-account",
                headers={"X-Workspace-Id": self.user_id},
                json={
                    "country": "Senegal", "company_name": "Test", "sub_category": "Financial Services",
                    "identification_number": "X",
                },
            )
        self.assertEqual(res.status_code, 200)
        profile = self.db.query(Profile).filter(Profile.user_id == self.user_id).first()
        self.assertEqual(profile.verto_company_id, company_id)
        self.assertEqual(profile.verto_onboarding_status, "sub_account_created")

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.create_sub_account")
    def test_second_attempt_does_not_create_duplicate_sub_account(self, mock_create):
        profile = Profile(user_id=self.user_id, verto_company_id=str(id(self)), verto_onboarding_status="sub_account_created")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post(
            "/verto/onboarding/sub-account",
            headers={"X-Workspace-Id": self.user_id},
            json={
                "country": "Senegal", "company_name": "Test", "sub_category": "Financial Services",
                "identification_number": "X",
            },
        )
        self.assertEqual(res.status_code, 400)
        mock_create.assert_not_called()

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.send_director_consent_email")
    def test_resend_consent_success(self, mock_send):
        company_id = str(id(self))
        profile = Profile(user_id=self.user_id, verto_company_id=company_id, verto_director_consent_status="not_sent")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post("/verto/resend-director-consent", headers={"X-Workspace-Id": self.user_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["director_consent_status"], "sent")
        mock_send.assert_called_once_with(company_id)

    @patch("backend.services.verto_service.VERTO_ENABLED", True)
    @patch("backend.services.verto_service.send_director_consent_email", side_effect=NotImplementedError)
    def test_resend_consent_failure_returns_502(self, _mock_send):
        profile = Profile(user_id=self.user_id, verto_company_id=str(id(self)), verto_director_consent_status="not_sent")
        self.db.add(profile)
        self.db.commit()

        res = self.client.post("/verto/resend-director-consent", headers={"X-Workspace-Id": self.user_id})
        self.assertEqual(res.status_code, 502)
        profile = self.db.query(Profile).filter(Profile.user_id == self.user_id).first()
        self.assertEqual(profile.verto_director_consent_status, "not_sent")


if __name__ == "__main__":
    unittest.main()
