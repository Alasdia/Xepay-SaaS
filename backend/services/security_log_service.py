from typing import Optional

from sqlalchemy.orm import Session

from backend.models import SecurityEvent


def log_security_event(
    db: Session,
    user_id: str,
    event_type: str,
    description: str,
    ip: Optional[str] = None,
) -> None:
    """Enregistre un événement dans l'historique de sécurité (Paramètres >
    Équipe et sécurité). Ne doit jamais faire échouer l'action qu'il
    accompagne : toute erreur ici est seulement loguée, jamais remontée."""
    try:
        db.add(SecurityEvent(user_id=user_id, event_type=event_type, description=description, ip=ip))
        db.commit()
    except Exception as e:
        print("SECURITY EVENT LOG - failed:", repr(e))
        db.rollback()
