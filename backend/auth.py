import pyotp
import qrcode
import base64
from io import BytesIO
from fastapi import Header, HTTPException, Depends, APIRouter, Request, Response
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, TwoFAVerifyRequest, WorkspaceUser, LoginTwoFAVerify
from datetime import datetime, timezone
from backend.security import (
    decode_token, create_access_token,
    encrypt_secret, decrypt_secret, decode_2fa_pending_token,
    generate_csrf_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME,
    CSRF_COOKIE_DOMAIN,
)
from backend.services.refresh_token_service import (
    issue_refresh_token, rotate_refresh_token, revoke_refresh_token,
)
from backend.services.email_service import send_login_alert_email
from backend.services.rate_limit import allow_attempt, reset as reset_rate_limit
router = APIRouter()


# Cookies de session posés par /login, /auth/2fa/verify-login,
# /auth/google/callback, /auth/google/exchange et /refresh — jamais de
# jeton exposé dans un corps JSON "sensible côté stockage" ni dans une URL.
#
# access_token / refresh_token restent host-only (pas de Domain) : HttpOnly,
# jamais lus en JS, ils n'ont besoin que d'être ENVOYÉS vers api.alasdia.com
# (ce qui fonctionne déjà sans Domain, l'envoi suit le host ciblé par la
# requête, pas l'origine de la page) — host-only est la portée la plus
# restrictive possible, ne pas l'élargir.
#
# csrf_token DOIT en revanche porter Domain="alasdia.com" : non-HttpOnly par
# construction (pattern double-submit cookie), il doit être lisible via
# document.cookie par le JS de la SPA, qui tourne sur alasdia.com/
# www.alasdia.com — un host DIFFÉRENT d'api.alasdia.com. Un cookie est
# ENVOYÉ en fonction du host ciblé par la requête (host-only suffisait pour
# ça), mais il n'est LU en JS que sur les hosts couverts par son attribut
# Domain — sans cette ligne, document.cookie ne retourne jamais csrf_token
# sur les pages de la SPA, et aucune requête mutative ne peut jamais poser
# un X-CSRF-Token correct (trouvé en revue finale). Domain="alasdia.com"
# couvre alasdia.com, www.alasdia.com ET api.alasdia.com (sous-domaine) :
# aucune des trois cookies n'est donc envoyée à un host hors de ce domaine.
def set_session_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME, value=access_token,
        httponly=True, secure=True, samesite="lax", path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME, value=refresh_token,
        httponly=True, secure=True, samesite="lax", path="/",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME, value=csrf_token,
        httponly=False, secure=True, samesite="lax", path="/",
        domain=CSRF_COOKIE_DOMAIN,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
    # Le Domain doit être identique à celui posé par set_cookie ci-dessus,
    # sinon le navigateur ne reconnaît pas la même cookie et ne la supprime
    # pas (il en créerait même une seconde, host-only, avec Max-Age=0 —
    # inoffensif mais n'efface pas l'originale à Domain=alasdia.com).
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", domain=CSRF_COOKIE_DOMAIN)


def issue_new_session(db: Session, response: Response, user: UserDB) -> None:
    """Point d'entrée unique pour démarrer une session (login classique,
    2FA, Google) : émet l'access token (JWT) + un nouveau refresh token
    (nouvelle famille, DB) + un jeton CSRF, et les pose en cookies."""
    access_token = create_access_token({"sub": user.email})
    refresh_token = issue_refresh_token(db, user.id)
    csrf_token = generate_csrf_token()
    set_session_cookies(response, access_token, refresh_token, csrf_token)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")

    # decode_token() (backend/security.py) vérifie signature, expiration ET
    # le claim "type" == "access" — seule implémentation de décodage JWT
    # côté access token, partagée avec LogMiddleware (voir audit : les deux
    # validateurs étaient auparavant dupliqués et divergents).
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")

    email = payload.get("sub")
    user = db.query(UserDB).filter(UserDB.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.is_deleted:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    return user


@router.post("/refresh")
def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="Aucune session à renouveler")

    result = rotate_refresh_token(db, raw_refresh)
    if result is None:
        # Jeton invalide/expiré/réutilisé hors fenêtre de grâce : on efface
        # les cookies existants pour forcer une reconnexion propre côté SPA.
        clear_session_cookies(response)
        raise HTTPException(status_code=401, detail="Session expirée, veuillez vous reconnecter")

    new_refresh_token, user = result
    access_token = create_access_token({"sub": user.email})
    csrf_token = generate_csrf_token()
    set_session_cookies(response, access_token, new_refresh_token, csrf_token)
    return {"ok": True}


@router.post("/logout")
def logout_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        revoke_refresh_token(db, raw_refresh)
    clear_session_cookies(response)
    return {"ok": True}


@router.post("/2fa/setup")
def setup_2fa(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    secret = pyotp.random_base32()
    current_user.two_factor_secret = encrypt_secret(secret)
    db.commit()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name="Xepay")

    img = qrcode.make(uri)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return {
        "secret": secret,
        "qr_code_base64": f"data:image/png;base64,{qr_base64}"
    }


@router.post("/2fa/verify")
def verify_2fa(
    data: TwoFAVerifyRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="Aucun secret 2FA en attente")

    decrypted = decrypt_secret(current_user.two_factor_secret)
    totp = pyotp.TOTP(decrypted)

    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Code incorrect")

    current_user.two_factor_enabled = True
    db.commit()

    return {"message": "2FA activée avec succès"}


@router.post("/2fa/disable")
def disable_2fa(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Le 2FA est déjà désactivé")

    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    db.commit()

    return {"message": "2FA désactivée avec succès"}


@router.post("/auth/2fa/verify-login")
def verify_login_2fa(
    data: LoginTwoFAVerify,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    normalized_email = data.email.strip().lower()
    email_ip_key = f"2fa-login:{normalized_email}:{ip}"
    ip_key = f"2fa-login:ip:{ip}"
    email_key = f"2fa-login:email:{normalized_email}"

    if not allow_attempt(email_ip_key) or not allow_attempt(ip_key) or not allow_attempt(email_key):
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez plus tard.")

    pending = decode_2fa_pending_token(data.pre_auth_token)
    if not pending or pending.get("sub") != data.email:
        raise HTTPException(status_code=401, detail="Session de connexion invalide ou expirée, veuillez vous reconnecter")

    user = db.query(UserDB).filter(UserDB.email == data.email).first()

    if not user or not user.two_factor_secret:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable ou 2FA non configuré")

    decrypted = decrypt_secret(user.two_factor_secret)
    totp = pyotp.TOTP(decrypted)

    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Code incorrect")

    reset_rate_limit(email_ip_key)
    reset_rate_limit(ip_key)
    reset_rate_limit(email_key)

    workspace_user = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.role == "owner"
    ).first()

    if not workspace_user:
        workspace_user = db.query(WorkspaceUser).filter(
            WorkspaceUser.user_id == user.id
        ).first()

    issue_new_session(db, response, user)

    if user.alert_login:
        device = request.headers.get("user-agent", "Appareil inconnu")
        send_login_alert_email(
            email=user.email,
            device=device,
            ip=ip
        )

    return {
        "workspace_id": workspace_user.workspace_id,
        "account_id": user.account_id
    }