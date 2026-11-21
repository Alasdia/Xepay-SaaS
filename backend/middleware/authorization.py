from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, WorkspaceUser
from backend.auth import get_current_user
from backend.services import permission_service


def normalize_role(role: str) -> str:
    """Uniformise la casse uniquement, ne change pas le rôle."""
    return role.lower().strip()


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

require_owner   = require_role("owner")
require_admin   = require_role("owner", "admin")
require_manager = require_role("owner", "admin", "manager")
require_membre  = require_role("owner", "admin", "manager", "membre")
require_member  = require_role("owner", "admin", "manager", "membre", "lecteur")


def require_capability(capability_key: str):
    """Fabrique une dependency qui exige le rôle minimal CONFIGURÉ pour
    cette capacité dans le workspace actif (voir
    backend/services/permission_service.py) - par défaut, exactement ce
    que require_owner/require_admin/require_manager imposaient déjà
    (CAPABILITY_DEFAULTS reflète le comportement d'origine), mais le owner
    du workspace peut l'avoir redéfini pour SON workspace (jamais pour les
    autres, voir GET/PUT /workspace/permissions dans routes/users.py)."""
    def checker(
        membership: WorkspaceUser = Depends(get_membership),
        db: Session = Depends(get_db),
    ) -> WorkspaceUser:
        min_role = permission_service.get_effective_min_role(db, membership.workspace_id, capability_key)
        if not permission_service.role_satisfies(membership.role, min_role):
            raise HTTPException(403, "Permission insuffisante")
        return membership

    return checker
