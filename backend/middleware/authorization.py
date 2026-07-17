from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, WorkspaceUser
from backend.auth import get_current_user

ROLE_ALIASES = {
    "owner": "owner",
    "admin": "admin",
    "administrateur": "admin",
    "manager": "admin",       
    "agent": "agent",
    "membre": "agent",     
    "lecture": "lecture",
    "lecteur": "lecture",
}

def normalize_role(role: str) -> str:
    return ROLE_ALIASES.get(role.lower().strip(), role.lower().strip())

def get_membership(
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> WorkspaceUser:
    """Vérifie l'appartenance au workspace. Refuse si absente."""
    workspace_id = x_workspace_id or current_user.id

    membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not membership:
        raise HTTPException(403, "Vous n'appartenez pas à ce workspace")

    return membership

def require_role(*allowed_roles: str):
    """Fabrique une dependency qui exige un des rôles listés."""
    allowed = [normalize_role(r) for r in allowed_roles]

    def checker(
        membership: WorkspaceUser = Depends(get_membership)
    ) -> WorkspaceUser:
        if normalize_role(membership.role) not in allowed:
            raise HTTPException(403, "Permission insuffisante")
        return membership

    return checker

require_owner = require_role("owner")
require_admin = require_role("owner", "admin")
require_agent = require_role("owner", "admin", "agent")
require_member = require_role("owner", "admin", "agent", "lecture")
