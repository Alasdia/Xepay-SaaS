from fastapi import HTTPException
from backend.models import WorkspaceUser


def get_workspace_owner_id(
    current_user,
    workspace_id,
    db
):
    print("========== WORKSPACE DEBUG ==========")
    print("CURRENT USER ID:", current_user.id)
    print("WORKSPACE ID:", workspace_id)

    memberships = db.query(WorkspaceUser).all()
    for m in memberships:
        print(
            "MEMBERSHIP:",
            m.user_id,
            m.workspace_id,
            m.role
        )

    if not workspace_id:
        return current_user.id

    membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="Workspace access denied"
        )

    return workspace_id