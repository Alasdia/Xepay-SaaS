from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext


# 🔐 CONFIG
SECRET_KEY = "super-secret-key-change-this"  # ⚠️ change en prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 🔒 Hashing (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =========================
# 🔑 PASSWORD FUNCTIONS
# =========================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# =========================
# 🎟️ TOKEN (JWT)
# =========================

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(hours=24)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None