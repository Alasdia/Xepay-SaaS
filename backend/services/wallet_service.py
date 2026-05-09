from backend.models import WalletTransaction
from datetime import datetime, timezone
import uuid


def create_wallet_transaction(
    db,
    user_id,
    wallet_id,
    amount,
    type,
    direction,
    status="success",
    description=None,
    related_user_id=None,
    reference=str(uuid.uuid4())
):    
    tx = WalletTransaction(
        user_id=user_id,
        wallet_id=wallet_id,
        amount=amount,
        type=type,
        direction=direction,
        status=status,
        description=description,
        related_user_id=related_user_id,
        reference=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc)
    )

    db.add(tx)

