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


class TestLogMiddlewareNavigateRedirect(unittest.TestCase):
    """Sec-Fetch-Mode: navigate (demande du 2026-11-27, suite d'un 401
    JSON brut reçu en collant /shopify/install directement dans un
    navigateur - route atteinte par navigation top-level, jamais via
    apiFetch/fetch()) : redirige vers la connexion plutôt que de
    renvoyer un JSON illisible comme contenu de page. Un fetch()/XHR
    du SPA (Sec-Fetch-Mode "cors"/"same-origin", jamais "navigate") ou
    un client sans cet en-tête (vieux navigateur, curl) doit garder
    l'ANCIEN comportement JSON, inchangé."""

    def setUp(self):
        self.client = TestClient(build_app())

    def test_navigate_mode_redirects_to_login_instead_of_json(self):
        response = self.client.get(
            "/protected", headers={"sec-fetch-mode": "navigate"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["location"].startswith("https://www.xepay.finance/login.html?next="))

    def test_navigate_mode_next_points_back_to_the_exact_original_url(self):
        response = self.client.get(
            "/protected?shop=connect2-ue6bhfbw.myshopify.com",
            headers={"sec-fetch-mode": "navigate"},
            follow_redirects=False,
        )
        location = response.headers["location"]
        self.assertIn(
            "next=https%3A%2F%2Fapi.xepay.finance%2Fprotected%3Fshop%3Dconnect2-ue6bhfbw.myshopify.com",
            location,
        )

    def test_fetch_style_request_still_gets_json_401(self):
        for mode in ("cors", "same-origin"):
            response = self.client.get("/protected", headers={"sec-fetch-mode": mode})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"error": "Unauthorized"})

    def test_no_sec_fetch_mode_header_still_gets_json_401(self):
        # Vieux navigateur / client non-navigateur (curl, Postman) - pas
        # d'en-tête du tout, jamais confondu avec "navigate" : repli sur
        # l'ancien comportement, jamais une redirection pour un client
        # qu'on ne peut pas identifier avec certitude.
        response = self.client.get("/protected")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Unauthorized"})


if __name__ == "__main__":
    unittest.main()
