from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB
from backend.security import decode_token, jwt, JWTError, SECRET_KEY, ALGORITHM
from fastapi.security import OAuth2PasswordBearer
from jose import JOSEError, ExpiredSignatureError


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
