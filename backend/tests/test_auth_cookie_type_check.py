import unittest

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.auth import get_current_user
from backend.models import UserDB
from backend.security import (
    create_access_token,
    create_2fa_pending_token,
    ACCESS_COOKIE_NAME,
)

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

    @app.get("/protected")
    def protected(current_user: UserDB = Depends(get_current_user)):
        return {"email": current_user.email}

    app.dependency_overrides[get_db] = override_get_db
    return app


class GetCurrentUserCookieTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db = TestingSessionLocal()
        cls.user = UserDB(email="cookie-user@example.com", password="x")
        db.add(cls.user)
        db.commit()
        db.refresh(cls.user)
        db.close()
        cls.client = TestClient(build_app())

    def test_no_cookie_is_401(self):
        res = self.client.get("/protected")
        self.assertEqual(res.status_code, 401)

    def test_valid_access_token_cookie_authenticates(self):
        token = create_access_token({"sub": self.user.email})
        res = self.client.get("/protected", cookies={ACCESS_COOKIE_NAME: token})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], self.user.email)

    def test_2fa_pending_token_in_access_cookie_is_rejected(self):
        """Confusion de type (cf. audit) : un jeton 'type=2fa_pending' ne
        doit jamais être accepté comme un access token, même signé
        correctement et non expiré."""
        pending_token = create_2fa_pending_token(self.user.email)
        res = self.client.get("/protected", cookies={ACCESS_COOKIE_NAME: pending_token})
        self.assertEqual(res.status_code, 401)

    def test_garbage_cookie_value_is_401(self):
        res = self.client.get("/protected", cookies={ACCESS_COOKIE_NAME: "not-a-jwt"})
        self.assertEqual(res.status_code, 401)

    def test_unknown_user_is_401(self):
        token = create_access_token({"sub": "ghost@example.com"})
        res = self.client.get("/protected", cookies={ACCESS_COOKIE_NAME: token})
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
