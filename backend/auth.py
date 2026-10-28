import pyotp
import qrcode
import base64
import requests
from io import BytesIO
from fastapi import Header, HTTPException, Depends, APIRouter, Request, Response
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, TwoFAVerifyRequest, WorkspaceUser, LoginTwoFAVerify, RefreshToken
from datetime import datetime, timezone
from backend.security import (
    decode_token, create_access_token,
    encrypt_secret, decrypt_secret, decode_2fa_pending_token,
    generate_csrf_token, hash_refresh_token,
    generate_backup_code, hash_backup_code,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME,
    CSRF_COOKIE_DOMAIN,
)
from backend.services.refresh_token_service import (
    issue_refresh_token, rotate_refresh_token, revoke_refresh_token,
)
from backend.services.email_service import send_login_alert_email, is_notification_enabled
from backend.services.rate_limit import allow_attempt, reset as reset_rate_limit
from backend.services.security_log_service import log_security_event, resolve_log_workspace_id
router = APIRouter()


# Cookies de session posés par /login, /auth/2fa/verify-login,
# /auth/google/callback, /auth/google/exchange et /refresh — jamais de
# jeton exposé dans un corps JSON "sensible côté stockage" ni dans une URL.
#
# access_token / refresh_token restent host-only (pas de Domain) : HttpOnly,
# jamais lus en JS, ils n'ont besoin que d'être ENVOYÉS vers api.xepay.finance
# (ce qui fonctionne déjà sans Domain, l'envoi suit le host ciblé par la
# requête, pas l'origine de la page) — host-only est la portée la plus
# restrictive possible, ne pas l'élargir.
#
# csrf_token DOIT en revanche porter Domain="xepay.finance" : non-HttpOnly par
# construction (pattern double-submit cookie), il doit être lisible via
# document.cookie par le JS de la SPA, qui tourne sur xepay.finance/
# www.xepay.finance/app.xepay.finance — un host DIFFÉRENT d'api.xepay.finance.
# Un cookie est ENVOYÉ en fonction du host ciblé par la requête (host-only
# suffisait pour ça), mais il n'est LU en JS que sur les hosts couverts par
# son attribut Domain — sans cette ligne, document.cookie ne retourne jamais
# csrf_token sur les pages de la SPA, et aucune requête mutative ne peut
# jamais poser un X-CSRF-Token correct (trouvé en revue finale).
# Domain="xepay.finance" couvre xepay.finance, www.xepay.finance,
# app.xepay.finance ET api.xepay.finance (sous-domaine) : aucune des trois
# cookies n'est donc envoyée à un host hors de ce domaine.
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
    # inoffensif mais n'efface pas l'originale à Domain=xepay.finance).
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", domain=CSRF_COOKIE_DOMAIN)


def session_device_ip(request: Request | None) -> tuple[str | None, str | None]:
    """User-agent brut + IP de la requête de connexion - affichés tels quels
    dans "Sessions actives" (Paramètres), pas de parsing device/OS ici."""
    if request is None:
        return None, None
    device = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return device, ip


def issue_new_session(db: Session, response: Response, user: UserDB, request: Request | None = None) -> None:
    """Point d'entrée unique pour démarrer une session (login classique,
    2FA, Google) : émet l'access token (JWT) + un nouveau refresh token
    (nouvelle famille, DB) + un jeton CSRF, et les pose en cookies."""
    access_token = create_access_token({"sub": user.email})
    device, ip = session_device_ip(request)
    refresh_token = issue_refresh_token(db, user.id, device=device, ip=ip)
    csrf_token = generate_csrf_token()
    set_session_cookies(response, access_token, refresh_token, csrf_token)
    log_security_event(db, user.id, "login", "Connexion réussie", workspace_id=resolve_log_workspace_id(request, user.id), ip=ip)


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

    device, ip = session_device_ip(request)
    result = rotate_refresh_token(db, raw_refresh, device=device, ip=ip)
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
        user_id = revoke_refresh_token(db, raw_refresh)
        if user_id:
            log_security_event(db, user_id, "logout", "Déconnexion", workspace_id=resolve_log_workspace_id(request, user_id))
    clear_session_cookies(response)
    return {"ok": True}


# IP -> "Pays (Région)" via un service public gratuit, pas de clé requise -
# meilleur effort uniquement : court timeout, jamais bloquant pour l'affichage
# des sessions, "Lieu inconnu" sur tout échec (IP locale/privée, service
# indisponible, etc.). Pas de cache : volume attendu très faible (ouverture
# de la page Paramètres), pas la peine d'ajouter un store supplémentaire.
def _lookup_ip_location(ip: str | None) -> str:
    if not ip or ip in ("127.0.0.1", "localhost", "::1") or ip.startswith("192.168.") or ip.startswith("10."):
        return "Local"
    try:
        res = requests.get(
            f"https://ip-api.com/json/{ip}",
            params={"fields": "status,country,regionName"},
            timeout=2,
        )
        data = res.json()
        if data.get("status") != "success":
            return "Lieu inconnu"
        country = data.get("country")
        region = data.get("regionName")
        if country and region:
            return f"{country} ({region})"
        return country or "Lieu inconnu"
    except Exception:
        return "Lieu inconnu"


def _active_sessions_query(db: Session, user_id: str):
    now = datetime.now(timezone.utc)
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at >= now,
        )
        .order_by(RefreshToken.created_at.desc())
    )


@router.get("/sessions")
def list_sessions(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    current_hash = hash_refresh_token(raw_refresh) if raw_refresh else None

    sessions = _active_sessions_query(db, current_user.id).all()
    return [
        {
            "id": s.id,
            "device": s.device or "Appareil inconnu",
            "ip": s.ip or "—",
            "location": _lookup_ip_location(s.ip),
            "created_at": s.created_at,
            "is_current": s.token_hash == current_hash,
        }
        for s in sessions
    ]


@router.post("/sessions/{session_id}/revoke")
def revoke_one_session(
    session_id: str,
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session_row = db.query(RefreshToken).filter(
        RefreshToken.id == session_id,
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    ).first()
    if not session_row:
        raise HTTPException(status_code=404, detail="Session introuvable")
    # Révoque toute la famille de ce jeton (même logique que le logout
    # classique, voir revoke_refresh_token) - pas seulement cette ligne.
    now = datetime.now(timezone.utc)
    db.query(RefreshToken).filter(
        RefreshToken.family_id == session_row.family_id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now})
    db.commit()
    log_security_event(db, current_user.id, "session_revoked", "Session déconnectée manuellement", workspace_id=resolve_log_workspace_id(request, current_user.id))
    return {"ok": True}


@router.post("/sessions/revoke-others")
def revoke_other_sessions(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    current_hash = hash_refresh_token(raw_refresh) if raw_refresh else None
    current_row = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == current_hash).first()
        if current_hash else None
    )
    current_family = current_row.family_id if current_row else None

    now = datetime.now(timezone.utc)
    q = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    )
    if current_family:
        q = q.filter(RefreshToken.family_id != current_family)
    q.update({"revoked_at": now})
    db.commit()
    log_security_event(db, current_user.id, "sessions_revoked_others", "Déconnexion de toutes les autres sessions", workspace_id=resolve_log_workspace_id(request, current_user.id))
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
    request: Request,
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
    log_security_event(db, current_user.id, "2fa_enabled", "Authentification à deux facteurs activée", workspace_id=resolve_log_workspace_id(request, current_user.id))

    return {"message": "2FA activée avec succès"}


@router.post("/2fa/disable")
def disable_2fa(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Le 2FA est déjà désactivé")

    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    # Un code de sauvegarde n'a de sens que tant que la 2FA est active -
    # réactiver la 2FA plus tard exige d'en régénérer un.
    current_user.two_factor_backup_code_hash = None
    current_user.two_factor_backup_code_generated_at = None
    db.commit()
    log_security_event(db, current_user.id, "2fa_disabled", "Authentification à deux facteurs désactivée", workspace_id=resolve_log_workspace_id(request, current_user.id))

    return {"message": "2FA désactivée avec succès"}


@router.post("/2fa/backup-code/generate")
def generate_backup_code_endpoint(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authentification > Authentification à deux facteurs > "Générer un
    code de sauvegarde". Remplace (invalide) un éventuel code précédent -
    affiché en clair une seule fois ici, jamais stocké tel quel (seul le
    hash l'est)."""
    if not current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Activez d'abord la 2FA avant de générer un code de sauvegarde")

    raw_code = generate_backup_code()
    current_user.two_factor_backup_code_hash = hash_backup_code(raw_code)
    current_user.two_factor_backup_code_generated_at = datetime.now(timezone.utc)
    db.commit()
    log_security_event(db, current_user.id, "backup_code_generated", "Code de sauvegarde 2FA régénéré", workspace_id=resolve_log_workspace_id(request, current_user.id))

    return {
        "backup_code": raw_code,
        "generated_at": current_user.two_factor_backup_code_generated_at,
    }


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

    code_valid = totp.verify(data.code, valid_window=1)
    if not code_valid and user.two_factor_backup_code_hash:
        code_valid = hash_backup_code(data.code) == user.two_factor_backup_code_hash

    if not code_valid:
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

    issue_new_session(db, response, user, request=request)

    if is_notification_enabled(user, "compte.new_device_login", legacy_flag=user.alert_login):
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