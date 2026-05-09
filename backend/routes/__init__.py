from backend.routes.users import router as users_router
from backend.routes.payments import router as payments_router
from backend.database import engine
from sqlalchemy import text


with engine.connect() as conn:

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS wallets (
            id SERIAL PRIMARY KEY,
            user_email TEXT NOT NULL UNIQUE,
            balance NUMERIC(12,2) NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """))