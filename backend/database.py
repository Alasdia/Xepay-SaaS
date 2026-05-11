from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool


DATABASE_URL = "postgresql://epay_user:JB2004%4025@localhost/epay_db"

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20
)

print("✅ ENGINE CONFIG LOADED")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    from backend.models import UserDB, Payment, Link
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

    
   