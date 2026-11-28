"""Centre de notifications (icône cloche, bandeau du haut) - voir
models.Notification pour la distinction explicite avec les toasts
(éphémères, réservés aux actions faites DEPUIS le dashboard Xepay) :
une Notification signale un évènement survenu AILLEURS (ex. un produit/
client/commande créé directement sur la boutique Shopify connectée).

create_notification ne lève JAMAIS (même garantie que
security_log_service.log_security_event) : un échec d'écriture ici ne
doit jamais faire échouer l'action/le webhook qui l'a déclenchée."""

import logging

from sqlalchemy.orm import Session

from backend.models import Notification

logger = logging.getLogger(__name__)


def create_notification(db: Session, workspace_id: str, event_type: str, title: str, description: str | None = None) -> None:
    try:
        db.add(Notification(workspace_id=workspace_id, event_type=event_type, title=title, description=description))
        db.commit()
    except Exception:
        logger.exception("Echec creation notification workspace_id=%s event_type=%s", workspace_id, event_type)
        db.rollback()
