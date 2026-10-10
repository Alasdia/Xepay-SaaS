import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.log_middleware import LogMiddleware
from backend.security import create_access_token, ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME

VALID_ACCESS_TOKEN = create_access_token({"sub": "csrf-user@example.com"})


def build_app():
    app = FastAPI()
    app.add_middleware(LogMiddleware)

    @app.post("/some-protected-action")
    def protected_action():
        return {"ok": True}

    @app.post("/webhook/stripe")
    def webhook():
        return {"ok": True}

    @app.post("/login")
    def login():
        return {"ok": True}

    @app.post("/refresh")
    def refresh():
        return {"ok": True}

    @app.get("/some-protected-action")
    def protected_get():
        return {"ok": True}

    @app.get("/pay/{token}")
    def public_pay_page(token: str):
        return {"ok": True}

    @app.post("/payments/{payment_id}/refund")
    def refund(payment_id: str):
        return {"ok": True}

    @app.get("/payments-summary")
    def payments_summary():
        return {"ok": True}

    return app


class CsrfProtectionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(build_app())

    def test_post_with_valid_access_cookie_but_no_csrf_is_403(self):
        res = self.client.post(
            "/some-protected-action",
            cookies={ACCESS_COOKIE_NAME: VALID_ACCESS_TOKEN},
        )
        self.assertEqual(res.status_code, 403)

    def test_post_with_matching_csrf_cookie_and_header_succeeds(self):
        res = self.client.post(
            "/some-protected-action",
            cookies={
                ACCESS_COOKIE_NAME: VALID_ACCESS_TOKEN,
                CSRF_COOKIE_NAME: "csrf-abc",
            },
            headers={"X-CSRF-Token": "csrf-abc"},
        )
        self.assertEqual(res.status_code, 200)

    def test_post_with_mismatched_csrf_cookie_and_header_is_403(self):
        res = self.client.post(
            "/some-protected-action",
            cookies={
                ACCESS_COOKIE_NAME: VALID_ACCESS_TOKEN,
                CSRF_COOKIE_NAME: "csrf-abc",
            },
            headers={"X-CSRF-Token": "csrf-DIFFERENT"},
        )
        self.assertEqual(res.status_code, 403)

    def test_get_never_requires_csrf(self):
        res = self.client.get(
            "/some-protected-action",
            cookies={ACCESS_COOKIE_NAME: VALID_ACCESS_TOKEN},
        )
        self.assertEqual(res.status_code, 200)

    def test_stripe_webhook_bypasses_csrf_and_access_check(self):
        res = self.client.post("/webhook/stripe")
        self.assertEqual(res.status_code, 200)

    def test_login_is_exempt_from_csrf_and_access_check(self):
        res = self.client.post("/login")
        self.assertEqual(res.status_code, 200)

    def test_refresh_bypasses_access_check_but_still_requires_csrf(self):
        # Pas de cookie d'accès du tout (c'est justement le cas d'usage de
        # /refresh) : ne doit pas être bloqué par le contrôle d'accès...
        no_csrf = self.client.post("/refresh")
        self.assertEqual(no_csrf.status_code, 403)  # ... mais CSRF s'applique quand même.

        with_csrf = self.client.post(
            "/refresh",
            cookies={CSRF_COOKIE_NAME: "csrf-xyz"},
            headers={"X-CSRF-Token": "csrf-xyz"},
        )
        self.assertEqual(with_csrf.status_code, 200)

    def test_public_pay_page_is_exempt(self):
        # /pay/{token} : page de paiement publique, aucune session —
        # exemptée d'accès ET de CSRF.
        res = self.client.get("/pay/tok_abc123")
        self.assertEqual(res.status_code, 200)

    def test_refund_endpoint_is_not_exempt_from_csrf(self):
        """Régression : /pay (sans slash) matchait aussi /payments/{id}/
        refund via startswith(), exemptant à tort cet endpoint de la
        protection CSRF (trouvé en revue finale). /payments/{id}/refund ne
        doit JAMAIS être exempté, qu'une session existe ou non."""
        no_cookies_at_all = self.client.post("/payments/pay_123/refund")
        self.assertEqual(no_cookies_at_all.status_code, 401)  # bloqué par le contrôle d'accès

        with_access_but_no_csrf = self.client.post(
            "/payments/pay_123/refund",
            cookies={ACCESS_COOKIE_NAME: VALID_ACCESS_TOKEN},
        )
        self.assertEqual(with_access_but_no_csrf.status_code, 403)

        with_everything = self.client.post(
            "/payments/pay_123/refund",
            cookies={
                ACCESS_COOKIE_NAME: VALID_ACCESS_TOKEN,
                CSRF_COOKIE_NAME: "csrf-refund",
            },
            headers={"X-CSRF-Token": "csrf-refund"},
        )
        self.assertEqual(with_everything.status_code, 200)

    def test_payments_summary_is_not_exempt_from_access_check(self):
        """Même régression que ci-dessus côté lecture : /payments-summary
        (GET) ne doit pas être traité comme public."""
        res = self.client.get("/payments-summary")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
