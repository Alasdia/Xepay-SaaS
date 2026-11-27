"""Route Alhu — assistant marchand en LECTURE SEULE (voir
services/alhu_service.py pour le prompt système, les outils et la
boucle outil/réponse). Gatée par get_membership seul (pas une capacité
précise) : toute donnée consultable via les outils est déjà visible
par n'importe quel membre du workspace ailleurs dans le dashboard,
même un "lecteur" - aucune raison de restreindre davantage un
assistant qui ne fait QUE lire."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.middleware.authorization import get_membership
from backend.models import AlhuChatRequest, WorkspaceUser
from backend.services.alhu_service import AlhuNotConfiguredError, run_alhu_chat

router = APIRouter()


@router.post("/alhu/chat")
def alhu_chat(
    body: AlhuChatRequest,
    membership: WorkspaceUser = Depends(get_membership),
    db: Session = Depends(get_db),
):
    if not body.messages:
        raise HTTPException(400, "Aucun message.")
    try:
        reply = run_alhu_chat(
            db,
            membership.workspace_id,
            [{"role": m.role, "content": m.content} for m in body.messages],
        )
    except AlhuNotConfiguredError:
        raise HTTPException(503, "Alhu n'est pas encore disponible.")
    return {"reply": reply}
