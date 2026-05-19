from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import ApiLog
from datetime import datetime, timezone
from jose import jwt
from backend.models import UserDB 
from backend.security import SECRET_KEY, ALGORITHM
from fastapi.responses import JSONResponse
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        
        public_prefixes = [
            "/login",
            "/signup",
            "/auth",
            "/docs",
            "/openapi.json",
            "/webhook",
            "/pay",
            "/ai",
            "/invite/accept",
        ]
        print("PATH:", request.url.path)

        if request.url.path.startswith("/webhook"):
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in public_prefixes):
            return await call_next(request)
        
        if request.method == "OPTIONS":
            return await call_next(request)

        auth = request.headers.get("authorization")
        user_id = None

        if auth:
            try:
                token = auth.split(" ")[1]
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

                email = payload.get("sub")

                if email:
                    user_id = email

            except Exception:
                pass

        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )

        response = await call_next(request)
        return response