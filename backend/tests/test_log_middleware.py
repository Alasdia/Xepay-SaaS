import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.log_middleware import LogMiddleware


def build_app():
    app = FastAPI()
    app.add_middleware(LogMiddleware)

    @app.get("/redoc")
    def redoc():
        return {"ok": True}

    @app.get("/protected")
    def protected():
        return {"ok": True}

    return app


class TestLogMiddlewarePublicPrefixes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(build_app())

    def test_redoc_is_public(self):
        response = self.client.get("/redoc")
        self.assertEqual(response.status_code, 200)

    def test_unlisted_route_requires_auth(self):
        response = self.client.get("/protected")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
