from datetime import datetime, timezone
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserDB, WorkspaceUser
from backend.auth import get_current_user
from backend.services.workspace_service import get_workspace_owner_id


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


def require_plan(*allowed_plans: str):
    """Fabrique une dependency qui exige que le plan effectif du workspace actif
    (celui de son owner) soit dans la liste. Un plan pro/business expiré est
    traité comme free. Retourne le UserDB authentifié (pas la membership),
    pour que les routes existantes continuent d'utiliser current_user.id
    sans changement de logique métier."""
    allowed = set(allowed_plans)

    def checker(
        x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> UserDB:
        owner_id = get_workspace_owner_id(current_user, x_workspace_id, db)
        owner = db.query(UserDB).filter(UserDB.id == owner_id).first()

        plan = getattr(owner, "plan", "free") if owner else "free"
        if owner and owner.plan_expires_at and owner.plan_expires_at < datetime.now(timezone.utc):
            plan = "free"

        if plan not in allowed:
            raise HTTPException(403, "Fonctionnalité réservée à un plan supérieur")

        return current_user

    return checker

require_pro_or_business = require_plan("pro", "business")
require_business = require_plan("business")
