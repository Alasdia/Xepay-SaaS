import unittest

from backend.database import engine


class TestEnginePoolPrePing(unittest.TestCase):
    def test_pool_pre_ping_enabled(self):
        # pool_pre_ping=True fait émettre un SELECT 1 avant de réutiliser une
        # connexion du pool, pour éviter qu'une connexion coupée côté proxy
        # Railway (idle) ne remonte en OperationalError sur la première
        # requête après une période creuse.
        self.assertTrue(engine.pool._pre_ping)


if __name__ == "__main__":
    unittest.main()
