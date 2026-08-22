from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from uuid import uuid4
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import os

load_dotenv()

TWO_FACTOR_KEY = os.getenv("TWO_FACTOR_ENCRYPTION_KEY")
fernet = Fernet(TWO_FACTOR_KEY.encode())

SECRET_KEY = os.getenv("SECRET_KEY")
print("SECRET_KEY =", SECRET_KEY)
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =========================
# 🔑 PASSWORD FUNCTIONS
# =========================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def encrypt_secret(secret: str) -> str:
    return fernet.encrypt(secret.encode()).decode()

def decrypt_secret(encrypted_secret: str) -> str:
    return fernet.decrypt(encrypted_secret.encode()).decode()

# =========================
# 🎟️ TOKEN (JWT)
# =========================

def create_access_token(data: dict):
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "iat": now,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "access"
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str):
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None