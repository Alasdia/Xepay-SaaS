from fastapi import HTTPException
from backend.models import WorkspaceUser


def get_workspace_owner_id(
    current_user,
    workspace_id,
    db
):

    # ✅ aucun workspace choisi
    if not workspace_id:
        return current_user.id

    # ✅ vérifier accès workspace
    membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="Workspace access denied"
        )

    # ✅ owner du workspace
    return workspace_id