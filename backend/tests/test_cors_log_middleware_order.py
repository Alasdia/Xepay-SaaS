import pathlib
import unittest

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.middleware.log_middleware import LogMiddleware

ALLOWED_ORIGIN = "https://www.alasdia.com"


def build_app():
    app = FastAPI()
    # Même ordre que backend/main.py : LogMiddleware ajoutée avant
    # CORSMiddleware. Starlette empile les middlewares dans l'ordre inverse
    # de add_middleware() (le dernier ajouté devient le plus externe), donc
    # CORSMiddleware (ajoutée en dernier) enveloppe LogMiddleware et peut
    # ajouter ses headers même sur les réponses que LogMiddleware renvoie
    # directement (401), sans jamais appeler call_next().
    app.add_middleware(LogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/protected")
    def protected():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/some-protected-action")
    def protected_action():
        return {"ok": True}

    return app


class TestCorsWrapsLogMiddleware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(build_app())

    def test_401_from_log_middleware_carries_cors_header(self):
        res = self.client.get("/protected", headers={"Origin": ALLOWED_ORIGIN})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)

    def test_public_route_also_carries_cors_header(self):
        res = self.client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)

    def test_preflight_options_handled_by_cors(self):
        res = self.client.options(
            "/protected",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)

    def test_401_from_cookie_based_check_carries_cors_header(self):
        # Migration cookies de session (voir audit) : plus de header
        # Authorization, mais le même principe doit tenir pour le cookie
        # d'accès manquant/invalide.
        res = self.client.get(
            "/protected",
            headers={"Origin": ALLOWED_ORIGIN},
            cookies={"access_token": "not-a-valid-jwt"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)

    def test_403_from_csrf_check_carries_cors_header(self):
        # Même raisonnement que le 401 ci-dessus, pour le 403 renvoyé
        # directement par la protection CSRF (double-submit cookie) : sans
        # header CORS, le SPA ne pourrait pas distinguer ce 403 applicatif
        # d'une erreur CORS et réagir en conséquence.
        from backend.security import create_access_token
        token = create_access_token({"sub": "csrf-order-test@example.com"})
        res = self.client.post(
            "/some-protected-action",
            headers={"Origin": ALLOWED_ORIGIN},
            cookies={"access_token": token},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)


class TestMainPyMiddlewareOrder(unittest.TestCase):
    """Garde-fou textuel : backend/main.py doit ajouter LogMiddleware avant
    CORSMiddleware, sans quoi le bug (401 masqué derrière une erreur CORS)
    reviendrait silencieusement si l'ordre est inversé."""

    def test_log_middleware_added_before_cors_in_main(self):
        main_source = pathlib.Path("backend/main.py").read_text()
        log_mw_idx = main_source.index("app.add_middleware(LogMiddleware)")
        cors_idx = main_source.index("CORSMiddleware,")
        self.assertLess(log_mw_idx, cors_idx)


if __name__ == "__main__":
    unittest.main()
