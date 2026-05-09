from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB
from backend.auth import get_current_user
import secrets
from typing import Optional
from passlib.context import CryptContext



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


router = APIRouter()

@router.get("/api-keys")
def get_api_keys(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.api_key_public:
        public_key = "pk_live_" + secrets.token_hex(12)
        raw_secret = "sk_live_" + secrets.token_hex(16)

        hashed_secret = pwd_context.hash(raw_secret)

        current_user.api_key_public = public_key
        current_user.api_key_secret_hash = hashed_secret

        db.commit()

        return {
            "public_key": public_key,
            "secret_key": raw_secret
        }
    
    return {
        "public_key": current_user.api_key_public,
        "secret_key": None  
    }

@router.post("/api-keys/regenerate")
def regenerate_keys(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    public_key = "pk_live_" + secrets.token_hex(12)
    raw_secret = "sk_live_" + secrets.token_hex(16)

    hashed_secret = pwd_context.hash(raw_secret)

    current_user.api_key_public = public_key
    current_user.api_key_secret_hash = hashed_secret

    db.commit()

    return {
        "public_key": public_key,
        "secret_key": raw_secret
    }
