import pyotp
import qrcode
import base64
from io import BytesIO
from fastapi import Header, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, TwoFAVerifyRequest, WorkspaceUser, LoginTwoFAVerify
from datetime import datetime, timezone
from backend.security import decode_token, jwt, JWTError, SECRET_KEY, ALGORITHM, create_access_token
from fastapi.security import OAuth2PasswordBearer
from jose import JOSEError, ExpiredSignatureError

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("sub")
    user = db.query(UserDB).filter(UserDB.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.is_deleted:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    return user


@router.post("/2fa/setup")
def setup_2fa(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    secret = pyotp.random_base32()
    current_user.two_factor_secret = secret
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

    totp = pyotp.TOTP(current_user.two_factor_secret)

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
    db: Session = Depends(get_db)
):
    user = db.query(UserDB).filter(UserDB.email == data.email).first()

    if not user or not user.two_factor_secret:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable ou 2FA non configuré")

    totp = pyotp.TOTP(user.two_factor_secret)

    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Code incorrect")

    workspace_user = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.role == "owner"
    ).first()

    if not workspace_user:
        workspace_user = db.query(WorkspaceUser).filter(
            WorkspaceUser.user_id == user.id
        ).first()

    token = create_access_token({"sub": user.email})

    return {
        "access_token": token,
        "workspace_id": workspace_user.workspace_id
    }
