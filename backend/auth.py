from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, TwoFASetupRequest, TwoFAVerifyRequest
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from backend.security import decode_token, jwt, JWTError, SECRET_KEY, ALGORITHM
from fastapi.security import OAuth2PasswordBearer
from jose import JOSEError, ExpiredSignatureError
import random
from backend.models import UserDB, TwoFASetupRequest, TwoFAVerifyRequest, WorkspaceUser, LoginTwoFAVerify
from backend.security import decode_token, jwt, JWTError, SECRET_KEY, ALGORITHM, create_access_token
from backend.services.sms_service import send_2fa_sms
from pydantic import BaseModel

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    print("TOKEN:", token)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print("DECODE OK:", payload)

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
    data: TwoFASetupRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    code = str(random.randint(100000, 999999))

    current_user.two_factor_phone = data.phone
    current_user.two_factor_code = code
    current_user.two_factor_code_expires_at = (
        datetime.utcnow() + timedelta(minutes=5)
    )
    db.commit()

    send_2fa_sms(data.phone, code)

    return {
        "message": "Code de vérification envoyé"
    }

@router.post("/2fa/verify")
def verify_2fa(
    data: TwoFAVerifyRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    if not current_user.two_factor_code:
        raise HTTPException(
            status_code=400,
            detail="Aucun code à vérifier"
        )
    
    if current_user.two_factor_code != data.code:
        raise HTTPException(
            status_code=400,
            detail="Code incorrect"
        )
    
    if not current_user.two_factor_code_expires_at:
        raise HTTPException(
            status_code=400,
            detail="Aucun code de vérification en attente"
        )

    if current_user.two_factor_code_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Code expiré"
        )
    
    current_user.two_factor_enabled = True
    current_user.two_factor_code = None
    current_user.two_factor_code_expires_at = None

    db.commit()

    return {
        "message": "2FA activée avec succès"
    }

@router.post("/2fa/disable")
def disable_2fa(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=400,
            detail="Le 2FA est déjà désactivé"
        )

    current_user.two_factor_enabled = False
    current_user.two_factor_phone = None
    current_user.two_factor_code = None
    current_user.two_factor_code_expires_at = None

    db.commit()

    return {
        "message": "2FA désactivée avec succès"
    }

@router.post("/auth/2fa/verify-login")
def verify_login_2fa(
    data: LoginTwoFAVerify,
    db: Session = Depends(get_db)
):
    user = db.query(UserDB).filter(UserDB.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if not user.two_factor_code:
        raise HTTPException(status_code=400, detail="Aucun code à vérifier")

    if user.two_factor_code != data.code:
        raise HTTPException(status_code=400, detail="Code incorrect")

    if not user.two_factor_code_expires_at:
        raise HTTPException(status_code=400, detail="Aucun code de vérification en attente")

    if user.two_factor_code_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Code expiré")

    user.two_factor_code = None
    user.two_factor_code_expires_at = None
    db.commit()

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