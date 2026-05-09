
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .users import UserDB 
from backend.database import get_db
from backend.models import Wallet
from backend.models import UserDB
from backend.auth import get_current_user
import os
import stripe


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()


@router.get("/wallet")
def get_wallet(user=Depends(get_current_user), db: Session = Depends(get_db)):
    

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()

    return {
        "available": wallet.available,
        "pending": wallet.pending
    }