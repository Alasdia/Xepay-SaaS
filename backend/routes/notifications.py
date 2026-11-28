"""Centre de notifications (icône cloche, bandeau du haut - voir
models.Notification, services/notification_service.py) - gatée par
get_membership seul (pas une capacité précise), même raisonnement que
routes/alhu.py : un évènement produit/client/commande visible ici
(titre/description figés au moment de l'évènement, jamais une donnée
sensible) n'a aucune raison d'être restreint davantage pour un membre
quelconque du workspace, même un "lecteur"."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.middleware.authorization import get_membership
from backend.models import Notification, WorkspaceUser

router = APIRouter()

# Dernières notifications seulement (même principe que COMMERCE_PAGE_SIZE,
# services/shopify_service.py) - un centre de notifications reste une
# consultation ponctuelle, jamais un export illimité.
NOTIFICATIONS_PAGE_SIZE = 30


def _serialize(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "event_type": notification.event_type,
        "title": notification.title,
        "description": notification.description,
        "created_at": notification.created_at,
        "read": notification.read_at is not None,
    }


@router.get("/notifications")
def list_notifications(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(get_membership),
):
    rows = (
        db.query(Notification)
        .filter(Notification.workspace_id == membership.workspace_id)
        .order_by(Notification.created_at.desc())
        .limit(NOTIFICATIONS_PAGE_SIZE)
        .all()
    )
    return [_serialize(n) for n in rows]


@router.get("/notifications/unread-count")
def get_unread_notifications_count(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(get_membership),
):
    count = (
        db.query(Notification)
        .filter(Notification.workspace_id == membership.workspace_id, Notification.read_at.is_(None))
        .count()
    )
    return {"unread_count": count}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(get_membership),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.workspace_id == membership.workspace_id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    if not notification.read_at:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
    return _serialize(notification)


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(get_membership),
):
    db.query(Notification).filter(
        Notification.workspace_id == membership.workspace_id, Notification.read_at.is_(None)
    ).update({"read_at": datetime.now(timezone.utc)})
    db.commit()
    return {"ok": True}
