from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models import UserDB
from backend.database import get_db
from backend.auth import get_current_user

router = APIRouter()


@router.get("/{account_id}/dashboard")
def dashboard(
    account_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    account = db.query(UserDB).filter(
        UserDB.account_id == account_id
    ).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Compte introuvable"
        )

    if account.id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Accès refusé"
        )

    return {
        "message": "Bienvenue dans le dashboard",
        "account_id": account.account_id
    }