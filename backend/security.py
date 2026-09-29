from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from uuid import uuid4
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import os
import ipaddress
import socket
from urllib.parse import urlparse

load_dotenv()

TWO_FACTOR_KEY = os.getenv("TWO_FACTOR_ENCRYPTION_KEY")
fernet = Fernet(TWO_FACTOR_KEY.encode())

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
PRE_AUTH_TOKEN_EXPIRE_MINUTES = 5

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

# =========================
# 🔐 PRE-AUTH TOKEN (étape 1 -> étape 2 du login 2FA)
# =========================

def create_2fa_pending_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=PRE_AUTH_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "iat": now,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "2fa_pending",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_2fa_pending_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "2fa_pending":
            return None
        return payload
    except JWTError:
        return None

# =========================
# 🌐 WEBHOOK URL SAFETY (anti-SSRF)
# =========================

def assert_public_webhook_url(url: str) -> None:
    """Rejette les URLs de webhook pointant vers localhost, loopback, IP privées,
    link-local ou metadata cloud (IPv4/IPv6), pour empêcher toute SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL de webhook invalide : schéma non autorisé")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL de webhook invalide : hôte manquant")

    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError("URL de webhook invalide : impossible de résoudre l'hôte")

    for _, _, _, _, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("URL de webhook interdite : cible une adresse interne/privée")