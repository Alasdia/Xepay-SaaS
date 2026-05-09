from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.auth import get_current_user

from backend.models import UserDB, Wallet
from backend.models import TransferRequest
from backend.services.wallet_service import create_wallet_transaction

import uuid

router = APIRouter()


@router.post("/transfer")
def transfer(
    req: TransferRequest,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user)
):
    from services.wallet_service import create_wallet_transaction
    import uuid

    if req.amount <= 0:
        raise HTTPException(400, "Invalid amount")

    # A = sender (user connecté)
    sender_wallet = db.query(Wallet)\
        .filter(Wallet.user_id == user.id)\
        .first()

    if not sender_wallet:
        raise HTTPException(404, "Sender wallet not found")

    # B = receiver
    receiver = db.query(UserDB)\
        .filter(UserDB.email == req.to_email)\
        .first()

    if not receiver:
        raise HTTPException(404, "Receiver not found")

    receiver_wallet = db.query(Wallet)\
        .filter(Wallet.user_id == receiver.id)\
        .first()

    if not receiver_wallet:
        raise HTTPException(404, "Receiver wallet not found")

    # sécurité
    if sender_wallet.balance < req.amount:
        raise HTTPException(400, "Insufficient balance")
    
    ref_out = str(uuid.uuid4())
    ref_in = str(uuid.uuid4())

    # opérations
    sender_wallet.balance -= req.amount
    receiver_wallet.balance += req.amount

    # transaction A (OUT)
    create_wallet_transaction(
        db=db,
        user_id=user.id,
        wallet_id=sender_wallet.id,
        amount=req.amount,
        type="transfer",
        direction="out",
        status="success",
        reference=ref_out,
        related_user_id=receiver.id,
        description="Transfert envoye"
    )

    # transaction B (IN)
    create_wallet_transaction(
        db=db,
        user_id=receiver.id,
        wallet_id=receiver_wallet.id,
        amount=req.amount,
        type="transfer",
        direction="in",
        status="success",
        reference=ref_in,
        related_user_id=user.id,
        description="Transfert recu"
    )

    db.commit()

    return {"status": "success"}