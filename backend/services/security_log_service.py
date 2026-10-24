from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from backend.models import SecurityEvent


def resolve_log_workspace_id(request: Optional[Request], user_id: str) -> str:
    """Workspace actif au moment de l'action : l'en-tête X-Workspace-Id,
    envoyé automatiquement par apiFetch sur chaque requête (voir
    core/apiClient.js), même pour les endpoints qui ne le valident pas
    eux-mêmes. Repli sur user_id (son propre workspace) quand l'en-tête est
    absent - requête serveur-à-serveur, ou request non disponible ici."""
    if request is not None:
        header_value = request.headers.get("X-Workspace-Id")
        if header_value:
            return header_value
    return user_id


def log_security_event(
    db: Session,
    user_id: str,
    event_type: str,
    description: str,
    workspace_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    """Enregistre un événement dans le journal d'activité (Paramètres >
    Équipe et sécurité). workspace_id détermine dans QUEL journal
    d'équipe cet événement apparaît (voir GET /security/events, filtré sur
    workspace_id) - repli sur user_id si non précisé (action sans contexte
    d'équipe identifié). Ne doit jamais faire échouer l'action qu'il
    accompagne : toute erreur ici est seulement loguée, jamais remontée."""
    try:
        db.add(SecurityEvent(
            user_id=user_id,
            workspace_id=workspace_id or user_id,
            event_type=event_type,
            description=description,
            ip=ip,
        ))
        db.commit()
    except Exception as e:
        print("SECURITY EVENT LOG - failed:", repr(e))
        db.rollback()
