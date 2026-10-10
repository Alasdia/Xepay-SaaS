import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import router as auth_router
from backend.models import UserDB, RefreshToken
from backend.security import hash_refresh_token
from backend.services.refresh_token_service import issue_refresh_token

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = override_get_db
    return app


class RefreshLogoutEndpointTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(build_app())

    def setUp(self):
        self.db = TestingSessionLocal()
        self.user = UserDB(email=f"refresh-ep-{id(self)}@example.com", password="x")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.raw_refresh = issue_refresh_token(self.db, self.user.id)

    def tearDown(self):
        self.db.close()

    def test_refresh_with_valid_cookie_rotates_and_sets_new_cookies(self):
        res = self.client.post(
            "/refresh",
            cookies={"refresh_token": self.raw_refresh},
        )
        self.assertEqual(res.status_code, 200)

        set_cookie_headers = res.headers.get_list("set-cookie")
        names = [h.split("=")[0] for h in set_cookie_headers]
        self.assertIn("access_token", names)
        self.assertIn("refresh_token", names)
        self.assertIn("csrf_token", names)

        old_row = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(self.raw_refresh)
        ).first()
        self.assertIsNotNone(old_row.revoked_at)

    def test_refresh_without_cookie_is_401(self):
        res = self.client.post("/refresh")
        self.assertEqual(res.status_code, 401)

    def test_refresh_with_garbage_cookie_is_401(self):
        res = self.client.post("/refresh", cookies={"refresh_token": "garbage"})
        self.assertEqual(res.status_code, 401)

    def test_logout_revokes_token_and_clears_cookies(self):
        res = self.client.post(
            "/logout",
            cookies={"refresh_token": self.raw_refresh},
        )
        self.assertEqual(res.status_code, 200)

        row = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(self.raw_refresh)
        ).first()
        self.assertIsNotNone(row.revoked_at)

        # Le jeton révoqué par logout ne doit plus pouvoir être rafraîchi.
        res2 = self.client.post("/refresh", cookies={"refresh_token": self.raw_refresh})
        self.assertEqual(res2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
