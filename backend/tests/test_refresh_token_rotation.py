import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import UserDB, RefreshToken
from backend.security import hash_refresh_token, REFRESH_TOKEN_REUSE_GRACE_SECONDS
from backend.services.refresh_token_service import (
    issue_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
)


class _NaiveUtcDatetime(datetime):
    """SQLite ne restitue jamais de tzinfo sur une colonne DateTime(timezone=True)
    (même raison que backend/tests/test_detail_endpoints.py) : aligné ici sur
    ce que SQLite renvoie réellement, pour la durée de ce module de test
    seulement — ne touche pas au fichier de prod."""

    @classmethod
    def now(cls, tz=None):
        return datetime.now(tz).replace(tzinfo=None) if tz is not None else datetime.now(tz)


import backend.services.refresh_token_service as _rts_module  # noqa: E402
_rts_module.datetime = _NaiveUtcDatetime


class RefreshTokenRotationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        user = UserDB(email=f"user-{id(self)}@example.com", password="x")
        self.db.add(user)
        self.db.commit()
        self.user = user

    def tearDown(self):
        self.db.close()

    def test_issue_then_rotate_succeeds_and_revokes_old(self):
        raw1 = issue_refresh_token(self.db, self.user.id)
        row1 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw1)
        ).first()
        self.assertIsNotNone(row1)
        self.assertIsNone(row1.revoked_at)

        result = rotate_refresh_token(self.db, raw1)
        self.assertIsNotNone(result)
        raw2, user = result
        self.assertEqual(user.id, self.user.id)
        self.assertNotEqual(raw1, raw2)

        self.db.refresh(row1)
        self.assertIsNotNone(row1.revoked_at)

        row2 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw2)
        ).first()
        self.assertIsNotNone(row2)
        self.assertIsNone(row2.revoked_at)
        self.assertEqual(row2.family_id, row1.family_id)

    def test_rotating_an_already_rotated_token_fails(self):
        raw1 = issue_refresh_token(self.db, self.user.id)
        rotate_refresh_token(self.db, raw1)  # consomme raw1 une première fois

        # Un troisième essai, bien après coup (hors fenêtre de grâce
        # simulée en reculant manuellement revoked_at), doit être traité
        # comme une réutilisation malveillante et tuer toute la famille.
        row1 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw1)
        ).first()
        row1.revoked_at = datetime.now(timezone.utc) - timedelta(
            seconds=REFRESH_TOKEN_REUSE_GRACE_SECONDS + 5
        )
        self.db.commit()

        result = rotate_refresh_token(self.db, raw1)
        self.assertIsNone(result)

        # Toute la famille (y compris le jeton enfant légitimement émis par
        # la première rotation) doit être révoquée.
        family_rows = self.db.query(RefreshToken).filter(
            RefreshToken.family_id == row1.family_id
        ).all()
        self.assertTrue(len(family_rows) >= 2)
        for row in family_rows:
            self.assertIsNotNone(row.revoked_at)

    def test_concurrent_rotation_within_grace_window_is_benign(self):
        """Deux requêtes concurrentes présentant le MÊME refresh token
        (cookie pas encore mis à jour côté client) ne doivent pas se
        pénaliser mutuellement : les deux doivent réussir, sans révoquer la
        famille."""
        raw1 = issue_refresh_token(self.db, self.user.id)

        result_a = rotate_refresh_token(self.db, raw1)  # gagne la course
        self.assertIsNotNone(result_a)

        result_b = rotate_refresh_token(self.db, raw1)  # perd la course, mais dans la fenêtre de grâce
        self.assertIsNotNone(result_b)

        raw_a, _ = result_a
        raw_b, _ = result_b
        self.assertNotEqual(raw_a, raw_b)

        row1 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw1)
        ).first()
        family_rows = self.db.query(RefreshToken).filter(
            RefreshToken.family_id == row1.family_id
        ).all()
        # 1 (raw1, révoqué par la rotation) + 2 enfants (A et B), tous deux
        # encore actifs.
        self.assertEqual(len(family_rows), 3)
        still_active = [r for r in family_rows if r.revoked_at is None]
        self.assertEqual(len(still_active), 2)

    def test_unknown_token_returns_none(self):
        self.assertIsNone(rotate_refresh_token(self.db, "this-token-was-never-issued"))

    def test_expired_token_is_rejected(self):
        raw1 = issue_refresh_token(self.db, self.user.id)
        row1 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw1)
        ).first()
        row1.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        self.db.commit()

        self.assertIsNone(rotate_refresh_token(self.db, raw1))

    def test_logout_revokes_whole_family_not_just_latest_token(self):
        raw1 = issue_refresh_token(self.db, self.user.id)
        result = rotate_refresh_token(self.db, raw1)
        raw2, _ = result

        revoke_refresh_token(self.db, raw2)

        row1 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw1)
        ).first()
        row2 = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_refresh_token(raw2)
        ).first()
        self.assertIsNotNone(row1.revoked_at)
        self.assertIsNotNone(row2.revoked_at)

        # Rejouer raw2 juste après le logout (dans la fenêtre de grâce) ne
        # doit PAS réussir : le logout a tué toute la famille, la fenêtre de
        # grâce ne s'applique qu'aux courses de ROTATION, jamais à un
        # logout explicite.
        self.assertIsNone(rotate_refresh_token(self.db, raw2))


if __name__ == "__main__":
    unittest.main()
