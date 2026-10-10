from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import WebhookDeliveryLog
from datetime import datetime, timezone
from backend.models import UserDB
from backend.security import decode_token, ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME
from fastapi.responses import JSONResponse
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dispensés de la vérification du cookie d'ACCÈS (access_token) : routes
# pré-session (login, signup, 2FA, OAuth, reset password), /refresh et
# /logout (qui valident eux-mêmes le cookie de REFRESH — /refresh est
# justement appelé quand l'access token est expiré), /webhook (Stripe,
# aucun cookie) et le reste déjà public avant cette migration.
ACCESS_TOKEN_EXEMPT_PREFIXES = [
    "/login",
    "/signup",
    "/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/webhook",
    "/health",
    # Slash final obligatoire : "/pay" (sans slash) matche aussi
    # /payments-summary, /payments/{id} et /payments/{id}/refund via
    # startswith() — trouvé en revue finale. Seule la page publique
    # /pay/{token} doit être exemptée ici.
    "/pay/",
    "/ai",
    "/invites/accept",
    "/reset-password",
    "/refresh",
    "/logout",
]

# Dispensés de la protection CSRF (double-submit cookie) : uniquement les
# routes pré-session, où aucun cookie de session n'existe encore à
# protéger, + /webhook (appel serveur-à-serveur Stripe, jamais de cookie).
# /refresh et /logout ne sont PAS exemptés : le cookie CSRF survit à
# l'expiration de l'access token (même durée de vie que le refresh token),
# rien ne justifie de les dispenser.
CSRF_EXEMPT_PREFIXES = [
    "/login",
    "/signup",
    "/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/webhook",
    "/health",
    "/pay/",
    "/ai",
    "/invites/accept",
    "/reset-password",
]

CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):

        path = request.url.path
        print("PATH:", path)

        if path.startswith("/webhook"):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        access_exempt = any(path.startswith(p) for p in ACCESS_TOKEN_EXEMPT_PREFIXES)

        if not access_exempt:
            token = request.cookies.get(ACCESS_COOKIE_NAME)
            # decode_token() vérifie signature, expiration ET le claim
            # "type" == "access" — même fonction que get_current_user
            # (backend/auth.py), pour ne plus jamais diverger entre les deux
            # validateurs (cf. audit).
            payload = decode_token(token) if token else None

            if not payload or not payload.get("sub"):
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized"}
                )

        if request.method in CSRF_PROTECTED_METHODS:
            csrf_exempt = any(path.startswith(p) for p in CSRF_EXEMPT_PREFIXES)
            if not csrf_exempt:
                csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
                csrf_header = request.headers.get("x-csrf-token")
                if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                    return JSONResponse(
                        status_code=403,
                        content={"error": "CSRF token invalide ou manquant"}
                    )

        response = await call_next(request)

        return response