from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import engine, get_db
from backend.models import UserDB, User, UserLogin, Wallet, ChangePasswordRequest, Payment, Profile, ProfileRequest, PlanUpdate, Link
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from backend.security import verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from datetime import datetime, timezone
from uuid import uuid4
from backend.security import hash_password
from fastapi import Request
import hashlib
from datetime import datetime, timedelta
from backend.models import WorkspaceUser, Profile, WorkspaceInvite
from uuid import UUID
from fastapi import Form, File, UploadFile, Header
from fastapi.responses import RedirectResponse
import os, shutil
from fastapi.responses import FileResponse
from fastapi import FastAPI, Request
from backend.services.email_service import send_invitation_email
import requests
import os
import stripe
import secrets

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()


@router.post("/signup")
def signup(user: User, db: Session = Depends(get_db)):

    print("🔥 ENTER FUNCTION")

    print("USER OBJ:", user)
    print("USER DICT:", user.dict())
    print("EMAIL:", user.email)
    print("PASSWORD:", user.password)
    try:
        # ✅ vérifier si user existe
        existing = db.query(UserDB).filter(UserDB.email == user.email).first()

        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        # ✅ créer user (ORM → id auto généré)
        new_user = UserDB(
            email=user.email,
            password=hash_password(user.password)
        )
        print("🚀 START SIGNUP")
        db.add(new_user)

        print("👉 BEFORE FLUSH")

        db.flush()
        
        if user.invite_token:

            token_hash = hashlib.sha256(
                user.invite_token.encode()
            ).hexdigest()

            invite = db.query(WorkspaceInvite).filter(
                WorkspaceInvite.token_hash == token_hash,
                WorkspaceInvite.used == False
            ).first()

            if invite:
                membership = WorkspaceUser(
                    user_id=new_user.id,
                    workspace_id=invite.workspace_id,
                    role=invite.role
                )

                db.add(membership)

                invite.used = True

        try:
            print("🚀 SIGNUP START")
            print("👉 Creating Stripe account for:", new_user.email)
            account = stripe.Account.create(
                type="express",
                email=new_user.email
            )

            print("✅ STRIPE ACCOUNT CREATED:", account.id)

            profile = Profile(
                user_id=new_user.id,
                stripe_account_id=account.id 
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            
        except Exception as e:
            print("❌ ERROR:", e)
            db.rollback()
            raise e
        
        # ✅ créer wallet automatiquement
        wallet = Wallet(
            user_id=new_user.id,
            balance=0,
            created_at=datetime.now(timezone.utc)
        )

        db.add(wallet)
        db.commit()
        return {"success": True}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):

    email = form_data.username
    password = form_data.password

    user = db.query(UserDB).filter(UserDB.email == email).first()

    workspace_user = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id
    ).first()

    if user and user.is_deleted:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "workspace_id": workspace_user.workspace_id
    }



CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

from fastapi.responses import RedirectResponse
from fastapi import HTTPException
import requests

@router.get("/auth/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):

    token_url = "https://oauth2.googleapis.com/token"

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    # 🔁 échange code → token
    token_res = requests.post(token_url, data=data)
    token_json = token_res.json()

    access_token = token_json.get("access_token")

    if not access_token:
        raise HTTPException(400, "Google auth failed")

    # 👤 récupérer user
    user_res = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    user_data = user_res.json()
    email = user_data.get("email")

    if not email:
        raise HTTPException(400, "User info invalid")

    # 🧠 créer ou récupérer user
    user = db.query(UserDB).filter(UserDB.email == email).first()

    if not user:

        stripe_account = stripe.Account.create(
            type="express",
            email=email,
            capabilities={
                "transfers": {"requested": True},
                "card_payments": {"requested": True},
            }
        )

        user = UserDB(
            email=email,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        profile = Profile(
            user_id=user.id,
            stripe_account_id=stripe_account.id
        )

        db.add(profile)
        db.commit()

        wallet = Wallet(
            user_id=user.id,
            balance=0
        )

        db.add(wallet)
        db.commit()

    token = create_access_token({"sub": user.email})

    return RedirectResponse(
        url=f"https://alasdia.com/dashboard.html?token={token}"
    )

@router.post("/onboarding")
def create_onboarding_link(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        current_user,
        workspace_id,
        db
    )

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    if not profile:
        profile = Profile(user_id=owner_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    if not profile.stripe_account_id:
        workspace_user = db.query(UserDB).filter(
            UserDB.id == owner_id
        ).first()
        account = stripe.Account.create(
            type="express",
            email=workspace_user.email,
        )
        profile.stripe_account_id = account.id
        db.commit()
    else:
        account = stripe.Account.retrieve(profile.stripe_account_id)

    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url="http://alasdia.com/profil.html",
        return_url="http://alasdia.com/profil.html",
        type="account_onboarding",
    )

    return {"url": account_link.url}

@router.get("/stripe/login-link")
def get_login_link(
    current_user: UserDB = Depends(get_current_user), 
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):

    owner_id = get_workspace_owner_id(
        current_user,
        workspace_id,
        db
    )

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(status_code=400, detail="No Stripe account")

    login_link = stripe.Account.create_login_link(
        profile.stripe_account_id
    )

    return {"url": login_link.url}
    
@router.get("/stripe/status")
def stripe_status(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        current_user,
        workspace_id,
        db
    )

    print("🔥 STRIPE STATUS HIT 🔥")

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    # ❌ pas de compte Stripe
    if not profile or not profile.stripe_account_id:
        return {
            "connected": False,
            "needs_kyc": False
        }

    account = stripe.Account.retrieve(
        profile.stripe_account_id,
        expand=["requirements"]
    )
    print("CURRENTLY DUE:", account.requirements.currently_due)
    print("EVENTUALLY DUE:", account.requirements.eventually_due)

    is_ready = account.charges_enabled and account.payouts_enabled

    return {
        "connected": is_ready,
        "needs_kyc": (
            len(account.requirements.currently_due) > 0
            or len(account.requirements.eventually_due) > 0
        ),

        "stripe": {
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
                "requirements": {
                    "currently_due": account.requirements.currently_due,
                    "eventually_due": account.requirements.eventually_due
                }
        },

        "profile": {
            "full_name": profile.full_name,
            "phone": profile.phone,
            "stripe_account_id": profile.stripe_account_id
        }
    }


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # récupérer user en base
        user = db.query(UserDB).filter(UserDB.email == current_user.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        # vérifier mot de passe actuel
        if not verify_password(data.current_password, user.password):
            raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

        # vérifier confirmation
        if data.new_password != data.confirm_password:
            raise HTTPException(status_code=400, detail="Les nouveaux mots de passe ne correspondent pas")

        # sécurité mini
        if len(data.new_password) < 8:
            raise HTTPException(status_code=400, detail="Minimum 8 caractères")

        # empêcher même mdp
        if verify_password(data.new_password, user.password):
            raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit être différent")

        # hash nouveau mdp
        user.password = hash_password(data.new_password)

        db.commit()

        return {"success": True, "message": "Mot de passe mis à jour"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
def get_me(
    request: Request,
    user = Depends(get_current_user), 
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        user,
        workspace_id,
        db
    )

    # 🔹 garantir wallet (idempotent)
    wallet = db.query(Wallet).filter(Wallet.user_id == owner_id).first()

    if not wallet:
        wallet = Wallet(
            user_id=owner_id,
            balance=0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(wallet)
        db.commit()
    
    user_agent = request.headers.get("user-agent", "Inconnu")
    ip = request.client.host if request.client else "Inconnue"

    workspace_owner = db.query(UserDB).filter(
        UserDB.id == owner_id
    ).first()

    return {
        "email": user.email,
        "plan": getattr(workspace_owner, "plan", "free"),
        "wallet": {
            "balance": wallet.balance,
            "created_at": wallet.created_at
        },
        "session": {
            "device": user_agent,
            "ip": ip,
            "last_seen": "Maintenant"
        }
    }

@router.delete("/delete-account")
def delete_account(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user.is_deleted = True
        db.commit()

        return {"message": "Compte désactivé"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/profile")
def get_profile(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    
    owner_id = get_workspace_owner_id(
        current_user,
        workspace_id,
        db
    )
    print("ROUTE PROFILE LOADED")
    
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    if not profile:
        profile = Profile(
            user_id=owner_id,
            full_name=None,
            phone=None,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        print("PROFILE:", profile)

    return {
        "full_name": profile.full_name,
        "email": current_user.email,
        "phone": profile.phone
    }


@router.get("/me/user-plan")
def get_my_plan(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        current_user,
        workspace_id,
        db
    )

    user = db.query(UserDB).filter(UserDB.id == owner_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return {
        "email": user.email,
        "plan": user.plan
    }

@router.get("/me/plan")
def get_plan(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        user,
        workspace_id,
        db
    )
    
    PLAN_LIMITS = {
        "free": {"paid": 10, "links": 30},
        "pro": {"paid": 100, "links": 200},
        "business": {"paid": None, "links": None}
    }
    workspace_user = db.query(UserDB).filter(
        UserDB.id == owner_id
    ).first()

    plan = getattr(workspace_user, "plan", "free")
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    
    start = workspace_user.plan_started_at
    end = workspace_user.plan_expires_at

    if not start or not end:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        end = now 

    links_count = db.query(Link).filter(
        Link.user_id == owner_id,
        Link.created_at >= start,
        Link.created_at < end
    ).count()

    paid_count = (
      db.query(Payment.link_id)
        .join(Link, Payment.link_id == Link.id)
        .filter(Link.user_id == owner_id)
        .filter(Payment.status.in_(["paid", "success", "réussi"]))
        .filter(Payment.created_at >= start)
        .filter(Payment.created_at < end)
        .distinct()
    )   .count()

    links = db.query(Link).all()

    for l in links:
        print(
            "LINK:",
            l.id,
            "USER_ID:",
            l.user_id,
            "CREATED_AT:",
            l.created_at
        )

    return {
        "plan": plan,
        "links_used": links_count,
        "links_limit": limits["links"],
        "paid_count": paid_count,
        "paid_limit": limits["paid"]
    }

@router.post("/change-plan")
def change_plan(
    data: PlanUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    workspace_id: str = Header(
        None,
        alias="X-Workspace-Id"
    )
):
    owner_id = get_workspace_owner_id(
        current_user,
        workspace_id,
        db
    )

    user = db.query(UserDB).filter(UserDB.id == owner_id).first()
    print("===== CHANGE PLAN =====")
    print("USER:", user.email)
    print("OLD PLAN:", user.plan)
    print("NEW PLAN:", data.plan)

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    allowed_plans = ["free", "starter", "pro", "business"]

    if data.plan not in allowed_plans:
        raise HTTPException(status_code=400, detail="Plan invalide")

    user.plan = data.plan

    if data.plan in ["pro", "business"]:
        now = datetime.now(timezone.utc)

        user.plan_started_at = now
        user.plan_expires_at = now + timedelta(days=30)

        print("START:", user.plan_started_at)
        print("END:", user.plan_expires_at)

    db.commit()

    print("COMMIT DONE")

    return {
        "message": "Plan mis à jour",
        "plan": user.plan
    }


@router.get("/dashboard")
def dashboard():
    return FileResponse("html/dashboard.html")


@router.get("/users")
def get_users(x_workspace_id: str = Header(None), current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    print("CURRENT USER:", current_user.id)

    workspace_id = x_workspace_id or current_user.id

    membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id
    ).first()

    if not membership:
        membership = WorkspaceUser(
            user_id=current_user.id,
            workspace_id=current_user.id,
            role="owner"
        )
        db.add(membership)
        db.commit()

    memberships = db.query(WorkspaceUser).filter(
        WorkspaceUser.workspace_id == workspace_id
    ).all()

    user_ids = [m.user_id for m in memberships]

    users = db.query(UserDB).filter(
        UserDB.id.in_(user_ids)
    ).all()
    print("USER IDS:", user_ids)
    print("USERS FOUND:", users)

    return [
        {
            "id": u.id,
            "name": u.email.split("@")[0],
            "email": u.email,
            "role": next((m.role for m in memberships if m.user_id == u.id), "member"),
            "status": getattr(u, "status", "active"),
            "last": "—"
        }
        for u in users
    ]

@router.post("/users")
def create_user(
    data: dict,
    x_workspace_id: str = Header(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # workspace = user.id (ton modèle actuel)
    workspace_id = x_workspace_id or current_user.id

    # vérifier si user existe
    existing = db.query(UserDB).filter(
        UserDB.email == data.get("email")
    ).first()

    if existing:
        # juste ajouter au workspace
        membership = WorkspaceUser(
            user_id=existing.id,
            workspace_id=workspace_id,
            role=data.get("role", "member")
        )
        db.add(membership)
        db.commit()

        return {"message": "User ajouté"}

    temp_password = secrets.token_urlsafe(8)

    user = UserDB(
        email=data.get("email"),
        password=hash_password(temp_password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    membership = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace_id,
        role=data.get("role", "member")
    )
    db.add(membership)
    db.commit()

    return {
        "message": "User créé",
        "temp_password": temp_password,
        "type": "new_user"
    }

@router.post("/invites")
def create_invite(
    data: dict,
    x_workspace_id: str = Header(None),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    workspace_id = x_workspace_id or current_user.id
    email = data.get("email")
    role = data.get("role", "member")

    if not email:
        raise HTTPException(400, "Email requis")

    # éviter double invitation
    existing_invite = db.query(WorkspaceInvite).filter(
        WorkspaceInvite.email == email,
        WorkspaceInvite.workspace_id == workspace_id,
        WorkspaceInvite.used == False
    ).first()

    if existing_invite:
        raise HTTPException(400, "Invitation déjà envoyée")

    # éviter inviter quelqu’un déjà membre
    existing_user = db.query(UserDB).filter(UserDB.email == email).first()
    if existing_user:
        existing_membership = db.query(WorkspaceUser).filter(
            WorkspaceUser.user_id == existing_user.id,
            WorkspaceUser.workspace_id == workspace_id
        ).first()

        if existing_membership:
            raise HTTPException(400, "Utilisateur déjà dans le workspace")

    # génération token sécurisé
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    invite = WorkspaceInvite(
        email=email,
        workspace_id=workspace_id,
        role=role,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    db.add(invite)
    db.commit()

    invite_link = f"https://api.alasdia.com/invites/accept?token={token}"

    send_invitation_email(
        to_email=email,
        invite_link=invite_link,
        inviter_email=current_user.email,
        role=role
    )

    return {
        "message": "Invitation créée",
        "invite_link": invite_link
    }

@router.get("/invites/accept")
def accept_invite(
    token: str,
    db: Session = Depends(get_db)
):


    if not token:
        raise HTTPException(400, "Token requis")

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    invite = db.query(WorkspaceInvite).filter(
        WorkspaceInvite.token_hash == token_hash,
        WorkspaceInvite.used == False
    ).first()

    if not invite:
        raise HTTPException(400, "Invitation invalide")

    if invite.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invitation expirée")

    # 🔥 vérifier si user existe déjà
    existing_user = db.query(UserDB).filter(
        UserDB.email == invite.email
    ).first()

    # ==================================================
    # CAS 1 → USER EXISTANT
    # ==================================================
    if existing_user:

        already_member = db.query(WorkspaceUser).filter(
            WorkspaceUser.user_id == existing_user.id,
            WorkspaceUser.workspace_id == invite.workspace_id
        ).first()

        if not already_member:

            membership = WorkspaceUser(
                user_id=existing_user.id,
                workspace_id=invite.workspace_id,
                role=invite.role
            )

            db.add(membership)

        invite.used = True

        db.commit()

        jwt_token = create_access_token({
            "sub": existing_user.email
        })

        return RedirectResponse(
            url=f"https://alasdia.com/multi-users.html?token={jwt_token}"
        )
    # ==================================================
    # CAS 2 → NOUVEL UTILISATEUR
    # ==================================================

    return RedirectResponse(
        url=f"https://alasdia.com/signup.html?token={token}"
    )

@router.post("/auth/register")
def register(data: dict, db: Session = Depends(get_db)):

    user = UserDB(
        email=data.get("email"),
        name=data.get("name"),
        role="Admin"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # 🔥 ici seulement
    user.owner_id = user.id

    membership = WorkspaceUser(
        id=str(uuid4()),  
        user_id=user.id,
        workspace_id=user.id,
        role="OWNER"
    )

    db.add(membership)
    db.commit()

    return {"message": "Compte créé"}

@router.put("/users/{user_id}/role")
def update_role(
    user_id: str,
    data: dict,
    x_workspace_id: str = Header(None),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):

    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    workspace_id = x_workspace_id or current_user.id

    current_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not current_membership:
        current_membership = WorkspaceUser(
            user_id=current_user.id,
            workspace_id=workspace_id,
            role="owner"
        )
        db.add(current_membership)
        db.commit()
        db.refresh(current_membership)

    target_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not target_membership:
        raise HTTPException(403, "User hors workspace")

    current_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if current_membership:
        print("ROLE:", current_membership.role)

    if current_membership.role.lower() not in ["owner", "admin"]:
        print("❌ 403: mauvais rôle ->", current_membership.role)
        raise HTTPException(403, "Permission insuffisante")
    
    # owner protégé
    if user.id == workspace_id:
        raise HTTPException(400, "Impossible de modifier le propriétaire")

    target_membership.role = data.get("role")
    db.commit()

    return {"message": "Rôle mis à jour"}

@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    x_workspace_id: str = Header(None),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        raise HTTPException(404)

    workspace_id = x_workspace_id or current_user.id

    current_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not current_membership:
        current_membership = WorkspaceUser(
            user_id=current_user.id,
            workspace_id=workspace_id,
            role="owner"
        )
        db.add(current_membership)
        db.commit()
        db.refresh(current_membership)

    target_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not target_membership:
        raise HTTPException(403, "User hors workspace")

    current_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if current_membership.role.lower() not in ["owner", "admin"]:
        raise HTTPException(403, "Permission insuffisante")

    if user.id == workspace_id :
        raise HTTPException(400, "Impossible de suspendre le propriétaire")

    user.status = "suspended" if user.status == "active" else "active"

    db.commit()

    return {"message": "Statut modifié"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    x_workspace_id: str = Header(None),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        raise HTTPException(404)

    workspace_id = x_workspace_id or current_user.id

    current_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not current_membership:
        current_membership = WorkspaceUser(
            user_id=current_user.id,
            workspace_id=workspace_id,
            role="owner"
        )
        db.add(current_membership)
        db.commit()
        db.refresh(current_membership)

    target_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not target_membership:
        raise HTTPException(403, "User hors workspace")

    current_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if current_membership.role.lower() not in ["owner", "admin"]:
        raise HTTPException(403, "Permission insuffisante")

    if user.id == workspace_id:
        raise HTTPException(400, "Impossible de supprimer le propriétaire")

    if user.id == current_user.id:
        raise HTTPException(400, "Tu ne peux pas te supprimer")


    db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id
    ).delete()

    db.delete(user)
    db.commit()

    return {"message": "Utilisateur supprimé"}

@router.get("/workspaces/me")
def get_my_workspaces(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    memberships = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id
    ).all()

    workspaces = []

    for membership in memberships:

        owner = db.query(UserDB).filter(
            UserDB.id == membership.workspace_id
        ).first()

        workspace_name = (
            f"{owner.email.split('@')[0]} Workspace"
            if owner else
            "Workspace"
        )

        workspaces.append({
            "id": membership.workspace_id,
            "name": workspace_name,
            "role": membership.role
        })

    return workspaces