from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from uuid import uuid4
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import os
import ipaddress
import socket
import secrets
import hashlib
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
REFRESH_TOKEN_EXPIRE_DAYS = 14
# Fenêtre de tolérance pendant laquelle la réutilisation d'un refresh token
# déjà tourné (rotation) est traitée comme une course bénigne entre requêtes
# concurrentes (cf. audit) plutôt que comme une tentative de vol — au-delà,
# toute la famille de jetons est révoquée.
REFRESH_TOKEN_REUSE_GRACE_SECONDS = 10

# Noms des cookies de session posés par /login, /auth/2fa/verify-login,
# /auth/google/callback, /auth/google/exchange et /refresh.
ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"

# Domain explicite pour le seul cookie non-HttpOnly (csrf_token) : il doit
# être lisible via document.cookie par le JS de la SPA, servie depuis
# alasdia.com/www.alasdia.com — un host différent d'api.alasdia.com où ce
# cookie est posé. "alasdia.com" couvre ses propres sous-domaines
# (alasdia.com, www.alasdia.com, api.alasdia.com), même convention que les
# URLs de redirection déjà en dur ailleurs dans ce fichier/routes/users.py.
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN", "alasdia.com")

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
# 🔁 REFRESH TOKEN (opaque, révocable en base — voir models.RefreshToken et
# services/refresh_token_service.py)
# =========================

def generate_refresh_token() -> str:
    """Valeur brute envoyée au client (cookie HttpOnly) — jamais stockée
    telle quelle en base, seul son hash l'est (cf. hash_refresh_token)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 simple (pas bcrypt) : le token a déjà ~384 bits d'entropie
    (secrets.token_urlsafe), un hash lent par itération n'apporte rien ici
    et empêcherait une recherche par égalité en base à chaque /refresh."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)

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