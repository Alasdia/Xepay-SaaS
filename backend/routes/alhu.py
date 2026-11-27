"""Route Alhu — assistant marchand intégré au dashboard (voir
services/alhu_service.py pour le prompt système, les outils et la
boucle outil/réponse). Gatée par get_membership seul (pas une capacité
précise) : toute donnée consultable via les outils de lecture est déjà
visible par n'importe quel membre du workspace ailleurs dans le
dashboard, même un "lecteur" - aucune raison de restreindre davantage
un assistant qui ne fait QUE lire. Les outils d'écriture (gestion
d'équipe, demande de boutique Shopify) sont, eux, gatés par rôle/
capacité - voir alhu_service._build_tools/_require_owner/
_require_capability, jamais géré au niveau de cette route."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.middleware.authorization import get_membership
from backend.models import AlhuChatRequest, WorkspaceUser
from backend.services.alhu_service import AlhuNotConfiguredError, stream_alhu_chat

router = APIRouter()
logger = logging.getLogger(__name__)


def _ndjson_stream(workspace_id: str, caller_user_id: str, caller_role: str, messages: list[dict]):
    """NDJSON (une ligne JSON par évènement) plutôt que du SSE classique
    (text/event-stream) - demande du 2026-11-27 (streaming) : consommé
    côté client via fetch()+ReadableStream (voir shared/alhuWidget.js),
    jamais EventSource (GET uniquement, incompatible avec le header
    X-CSRF-Token exigé sur ce POST)."""
    try:
        for event in stream_alhu_chat(workspace_id, caller_user_id, caller_role, messages):
            yield json.dumps(event, ensure_ascii=False) + "\n"
    except AlhuNotConfiguredError:
        yield json.dumps({"type": "error", "message": "Alhu n'est pas encore disponible."}) + "\n"
    except Exception:
        logger.exception("Echec stream Alhu pour workspace_id=%s", workspace_id)
        yield json.dumps({"type": "error", "message": "Erreur interne. Réessayez."}) + "\n"


@router.post("/alhu/chat")
def alhu_chat(
    body: AlhuChatRequest,
    membership: WorkspaceUser = Depends(get_membership),
):
    if not body.messages:
        raise HTTPException(400, "Aucun message.")
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    return StreamingResponse(
        _ndjson_stream(membership.workspace_id, membership.user_id, membership.role, messages),
        media_type="application/x-ndjson",
    )
