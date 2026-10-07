from backend.models import WalletTransaction, generate_prefixed_id
from datetime import datetime, timezone

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
    reference=None
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
        reference=reference or generate_prefixed_id("txn"),
        created_at=datetime.now(timezone.utc)
    )

    db.add(tx)

