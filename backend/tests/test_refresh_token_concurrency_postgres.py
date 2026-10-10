# Test de concurrence RÉELLE (deux threads, deux connexions PostgreSQL
# distinctes, synchronisés par une barrière) pour la rotation des refresh
# tokens — voir backend/services/refresh_token_service.py et la revue finale
# de la migration cookies.
#
# Pourquoi PostgreSQL et pas SQLite : le verrouillage ligne par ligne réel
# (qui bloque la seconde UPDATE concurrente jusqu'au commit de la première,
# puis la relâche exactement au moment du commit) ne peut être observé
# qu'avec un vrai moteur MVCC. SQLite ne permet pas d'écritures concurrentes
# comparables et n'aurait pas pu révéler la fenêtre de course corrigée
# (revoked_at et replaced_by posés en deux commits séparés dans l'ancienne
# version du service).
#
# Ce test NE TOUCHE JAMAIS la base de production Railway : il se connecte à
# une instance PostgreSQL locale, jetable, dont l'URL est fournie via la
# variable d'environnement TEST_POSTGRES_URL. Si elle est absente, le test
# est explicitement SKIPPÉ (jamais simulé, jamais déclaré "passé" à tort).
#
# Instance locale utilisée pour cette revue (non committée, à reproduire
# pour toute ré-exécution) :
#   initdb -D /tmp/xepay_pgdata -U testuser --auth=trust
#   pg_ctl -D /tmp/xepay_pgdata -l /tmp/xepay_pg.log \
#       -o "-p 55432 -k /tmp/xepay_pgsock" start
#   createdb -h /tmp/xepay_pgsock -p 55432 -U testuser xepay_test
#   export TEST_POSTGRES_URL="postgresql+psycopg2://testuser@/xepay_test?host=/tmp/xepay_pgsock&port=55432"

import os
import threading
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import UserDB, RefreshToken
from backend.security import hash_refresh_token
from backend.services.refresh_token_service import (
    issue_refresh_token,
    rotate_refresh_token,
)

TEST_POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@unittest.skipUnless(
    TEST_POSTGRES_URL,
    "TEST_POSTGRES_URL non défini : test de concurrence PostgreSQL réelle "
    "skippé (jamais simulé sur SQLite — voir docstring du module).",
)
class RefreshTokenRealConcurrencyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(TEST_POSTGRES_URL)
        # Restreint la création aux deux tables nécessaires (users,
        # refresh_tokens) : jamais le schéma complet, jamais une base de
        # production.
        Base.metadata.create_all(
            bind=cls.engine,
            tables=[UserDB.__table__, RefreshToken.__table__],
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine, autocommit=False, autoflush=False)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.db = self.SessionLocal()
        user = UserDB(email=f"concurrency-{id(self)}@example.com", password="x")
        self.db.add(user)
        self.db.commit()
        self.user_id = user.id

    def tearDown(self):
        # Nettoyage explicite (base jetable, mais on reste rigoureux) :
        # jamais de TRUNCATE/DROP global, uniquement les lignes de ce test.
        self.db.query(RefreshToken).filter(RefreshToken.user_id == self.user_id).delete()
        self.db.query(UserDB).filter(UserDB.id == self.user_id).delete()
        self.db.commit()
        self.db.close()

    def test_two_concurrent_rotations_of_the_same_token_both_succeed(self):
        raw_token = issue_refresh_token(self.db, self.user_id)

        barrier = threading.Barrier(2)
        results = [None, None]
        errors = [None, None]

        def worker(index):
            # Connexion/session dédiée à ce thread — jamais partagée, pour
            # une concurrence réelle au niveau de la base, pas seulement du
            # thread Python.
            session = self.SessionLocal()
            try:
                barrier.wait(timeout=5)
                result = rotate_refresh_token(session, raw_token)
                if result is not None:
                    raw, user = result
                    # user.id lu ICI, avant session.close() : l'objet ORM
                    # devient détaché (DetachedInstanceError sur tout accès
                    # d'attribut) une fois sa session fermée.
                    results[index] = (raw, user.id)
            except Exception as exc:  # noqa: BLE001 - on veut voir tout crash
                errors[index] = exc
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertIsNone(errors[0], f"thread 0 a levé: {errors[0]}")
        self.assertIsNone(errors[1], f"thread 1 a levé: {errors[1]}")

        # Les DEUX requêtes concurrentes doivent réussir (course bénigne) —
        # c'est précisément le comportement que l'ancienne version pouvait
        # violer (toute la famille révoquée par erreur).
        self.assertIsNotNone(results[0], "la rotation 0 a échoué (famille tuée à tort ?)")
        self.assertIsNotNone(results[1], "la rotation 1 a échoué (famille tuée à tort ?)")

        raw_a, user_id_a = results[0]
        raw_b, user_id_b = results[1]
        self.assertNotEqual(raw_a, raw_b)
        self.assertEqual(user_id_a, self.user_id)
        self.assertEqual(user_id_b, self.user_id)

        verify_db = self.SessionLocal()
        try:
            original = verify_db.query(RefreshToken).filter(
                RefreshToken.token_hash == hash_refresh_token(raw_token)
            ).first()
            self.assertIsNotNone(original.revoked_at)
            self.assertIsNotNone(original.replaced_by)

            family_rows = verify_db.query(RefreshToken).filter(
                RefreshToken.family_id == original.family_id
            ).all()
            # 1 original révoqué + 2 enfants (A et B), AUCUN autre révoqué.
            self.assertEqual(len(family_rows), 3)
            active = [r for r in family_rows if r.revoked_at is None]
            self.assertEqual(len(active), 2)
        finally:
            verify_db.close()

    def test_rapid_sequential_rotation_chain_never_breaks(self):
        """Non-régression : une chaîne de rotations strictement séquentielles
        (pas de course) continue de fonctionner après le passage à la claim
        atomique."""
        raw = issue_refresh_token(self.db, self.user_id)
        for _ in range(5):
            result = rotate_refresh_token(self.db, raw)
            self.assertIsNotNone(result)
            raw, _ = result


if __name__ == "__main__":
    unittest.main()
