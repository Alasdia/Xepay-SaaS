from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import engine, get_db
from backend.models import UserDB, User, UserLogin, Wallet, ChangePasswordRequest, Payment, Profile, ProfileRequest, PlanUpdate, Link, SecurityAlertsRequest 
from backend.auth import get_current_user
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from backend.security import verify_password, create_access_token
from backend.middleware.authorization import require_admin, require_owner, require_member, require_manager
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from datetime import datetime, timezone
from uuid import uuid4
from backend.security import hash_password
from fastapi import Request
import hashlib
from datetime import datetime, timedelta
from backend.models import WorkspaceUser, Profile, WorkspaceInvite, ResetPasswordRequest
from uuid import UUID
from fastapi import Form, File, UploadFile, Header
from fastapi.responses import RedirectResponse
import os, shutil
from fastapi.responses import FileResponse
from fastapi import FastAPI, Request
from backend.services.email_service import send_invitation_email, send_login_alert_email
from backend.security import hash_password, verify_password, decrypt_secret
from math import ceil
import requests
import pyotp
import os
import stripe
from importlib.metadata import version
print("🔍 VERSION STRIPE ACTUELLE:", version("stripe"))
import secrets

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()

@router.post("/signup")
def signup(
    user: User, 
    db: Session = Depends(get_db)
    ):

    try:
        existing = db.query(UserDB).filter(UserDB.email == user.email).first()

        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        new_user = UserDB(
            email=user.email,
            password=hash_password(user.password)
        )
        db.add(new_user)
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
            
        else:
            print("OWNER WORKSPACE FLOW")
            membership = WorkspaceUser(
                user_id=new_user.id,
                workspace_id=new_user.id,
                role="owner"
            )
            db.add(membership)
            print("WORKSPACE OBJECT ADDED")

        try:
            print("🚀 SIGNUP START")
            print("👉 Creating Stripe account (v2) for:", new_user.email)

            account = stripe.v2.core.accounts.create(
                params={
                    "contact_email": new_user.email,
                    "configuration": {
                        "merchant": {
                            "payouts": {
                                "schedule": {
                                    "interval": "manual"
                                }
                            }
                        }
                    }
                }
            )

            print("✅ STRIPE ACCOUNT CREATED:", account["id"])

            profile = Profile(
                user_id=new_user.id,
                stripe_account_id=account["id"]
            )

            db.add(profile)
            db.commit()
            db.refresh(profile)
            
        except Exception as e:
            print("❌ ERROR TYPE:", type(e).__name__)
            print("❌ ERROR DETAILS:", str(e))
            db.rollback()
            raise e

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
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    email = form_data.username
    password = form_data.password

    user = db.query(UserDB).filter(UserDB.email == email).first()

    if user and user.is_deleted:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    workspace_user = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.role == "owner"
    ).first()

    if not workspace_user:
        workspace_user = db.query(WorkspaceUser).filter(
            WorkspaceUser.user_id == user.id
        ).first()

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    if user.two_factor_enabled:
        return {
            "requires_2fa": True,
            "email": user.email,
            "workspace_id": workspace_user.workspace_id
        }

    ip = request.client.host
    device = request.headers.get(
        "user-agent",
        "Appareil inconnu"
    )
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    print("LAST LOGIN SAVED:", user.last_login)

    token = create_access_token({"sub": user.email})

    if user.alert_login:
        send_login_alert_email(
            email=user.email,
            device=device,
            ip=ip
        )

    return {
        "access_token": token,
        "token_type": "bearer",
        "workspace_id": workspace_user.workspace_id,
        "account_id": user.account_id
    }


@router.get("/security/alerts")
def get_security_alerts(
    current_user: UserDB = Depends(get_current_user)
):

    return {
        "alert_login": current_user.alert_login,
        "alert_payment": current_user.alert_payment,
        "alert_suspect": current_user.alert_suspect
    }

@router.post("/security/alerts")
def update_security_alerts(
    data: SecurityAlertsRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    current_user.alert_login = data.alert_login
    current_user.alert_payment = data.alert_payment
    current_user.alert_suspect = data.alert_suspect

    db.commit()

    return {
        "message": "Préférences de sécurité mises à jour"
    }


CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

from fastapi.responses import RedirectResponse
from fastapi import HTTPException
import requests

@router.get("/auth/google/callback")
def google_callback(
    code: str, 
    db: Session = Depends(get_db)
):
    token_url = "https://oauth2.googleapis.com/token"

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_res = requests.post(token_url, data=data)
    token_json = token_res.json()

    access_token = token_json.get("access_token")

    if not access_token:
        raise HTTPException(400, "Google auth failed")

    user_res = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    user_data = user_res.json()
    email = user_data.get("email")
    print(user_data)
    print("GOOGLE EMAIL =", email)

    if not email:
        raise HTTPException(400, "User info invalid")

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

        membership = WorkspaceUser(
            user_id=user.id,
            workspace_id=user.id,
            role="owner"
        )

        db.add(membership)
        db.commit()

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

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.email})

    membership = (
        db.query(WorkspaceUser)
        .filter(
            WorkspaceUser.user_id == user.id,
            WorkspaceUser.role == "owner"
        )
        .first()
    )

    if not membership:
        membership = (
            db.query(WorkspaceUser)
            .filter(WorkspaceUser.user_id == user.id)
            .first()
        )

    workspace_id = membership.workspace_id

    if user.two_factor_enabled:
        return RedirectResponse(
            url=f"https://alasdia.com/login.html?requires_2fa=true&email={user.email}&workspace_id={workspace_id}"
        )
    
    token = create_access_token({"sub": user.email})

    return RedirectResponse(
        url=f"https://alasdia.com/dashboard.html?token={token}&workspace_id={workspace_id}"
    )

@router.post("/onboarding")
def create_onboarding_link(
    membership: WorkspaceUser = Depends(require_owner),
    db: Session = Depends(get_db),
):
    owner_id = membership.workspace_id

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
    membership: WorkspaceUser = Depends(require_owner), 
    db: Session = Depends(get_db),
):

    owner_id = membership.workspace_id

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(status_code=400, detail="No Stripe account")

    login_link = stripe.Account.create_login_link(
        profile.stripe_account_id
    )

    return {"url": login_link.url}
    
@router.get("/stripe/status")
def stripe_status(
    membership: WorkspaceUser = Depends(require_manager),
    db: Session = Depends(get_db),
):
    owner_id = membership.workspace_id

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
        ),

        "future_requirements": (
            len(account.requirements.eventually_due) > 0
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
    membership: WorkspaceUser = Depends(require_owner),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        
        user = db.query(UserDB).filter(UserDB.email == current_user.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        if not verify_password(data.current_password, user.password):
            raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

        if data.new_password != data.confirm_password:
            raise HTTPException(status_code=400, detail="Les nouveaux mots de passe ne correspondent pas")

        if len(data.new_password) < 8:
            raise HTTPException(status_code=400, detail="Minimum 8 caractères")

        if verify_password(data.new_password, user.password):
            raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit être différent")

        user.password = hash_password(data.new_password)
        db.commit()

        return {"success": True, "message": "Mot de passe mis à jour"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(UserDB).filter(UserDB.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    if not user.two_factor_secret:
        raise HTTPException(status_code=400, detail="L'authentification 2FA n'est pas configurée pour ce compte")

    secret = decrypt_secret(user.two_factor_secret)
    totp = pyotp.TOTP(secret)

    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Code Google Authenticator invalide ou expiré")

    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas")

    user.password = hash_password(data.new_password)
    db.commit()

    return {"message": "Mot de passe mis à jour avec succès"}


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
    if workspace_owner:
        db.refresh(workspace_owner)

    return {
        "email": user.email,
        "plan": getattr(workspace_owner, "plan", "free"),
        "subscription_status": getattr(workspace_owner, "subscription_status", "active"),
        "cancel_at_period_end": getattr(workspace_owner, "cancel_at_period_end", False),
        "plan_expires_at": getattr(workspace_owner, "plan_expires_at", None),
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
    membership: WorkspaceUser = Depends(require_manager),
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
    
):
    
    owner_id = membership.workspace_id
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
        "phone": profile.phone,
        "two_factor_enabled": current_user.two_factor_enabled,
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
    membership: WorkspaceUser = Depends(require_manager),
    
):
    owner_id = membership.workspace_id
    
    PLAN_LIMITS = {
        "free": {"paid": 10, "links": 30},
        "pro": {"paid": 100, "links": 200},
        "business": {"paid": None, "links": None}
    }
    workspace_user = db.query(UserDB).filter(
        UserDB.id == owner_id
    ).first()

    if not workspace_user:
        raise HTTPException(status_code=404, detail="Propriétaire du workspace introuvable")
    
    db.refresh(workspace_user)

    plan = getattr(workspace_user, "plan", "free")
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

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
    is_expired = False
    if workspace_user.plan_expires_at:
        is_expired = workspace_user.plan_expires_at < now

    default_status = "none" if plan == "free" else "active"

    return {
        "plan": plan if not is_expired else "free",
        "subscription_status": getattr(workspace_user, "subscription_status", None) or default_status,
        "cancel_at_period_end": getattr(workspace_user, "cancel_at_period_end", False),
        "plan_started_at": workspace_user.plan_started_at,
        "plan_expires_at": workspace_user.plan_expires_at,
        "is_expired": is_expired,
        "stripe_customer_id": getattr(workspace_user, "stripe_customer_id", None),
        "stripe_subscription_id": getattr(workspace_user, "stripe_subscription_id", None),
        "usage": {
            "links_used": links_count,
            "links_limit": limits["links"],
            "paid_count": paid_count,
            "paid_limit": limits["paid"]
        }
    }
@router.post("/me/plan/cancel")
def cancel_user_subscription(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_owner),
    current_user: UserDB = Depends(get_current_user) 
):
    stripe_sub_id = current_user.stripe_subscription_id

    if not stripe_sub_id:
        raise HTTPException(status_code=400, detail="Aucun abonnement actif trouvé")

    try:
        stripe.Subscription.modify(
            stripe_sub_id,
            cancel_at_period_end=True
        )

        current_user.cancel_at_period_end = True
        db.commit()

        return {"message": "Abonnement résilié avec succès pour la fin de période"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
@router.post("/me/create-portal-session")
def create_portal_session(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_owner),
    current_user: UserDB = Depends(get_current_user)
):
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Aucun identifiant client Stripe trouvé")
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url="https://api.alasdia.com/profil.html", 
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-plan")
def change_plan(
    data: PlanUpdate,
    membership: WorkspaceUser = Depends(require_owner),
    db: Session = Depends(get_db),

):
    owner_id = membership.workspace_id

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
    else:
        user.plan_expires_at = None

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
def get_users(
    membership: WorkspaceUser = Depends(require_member),
    db: Session = Depends(get_db)
):
    workspace_id = membership.workspace_id

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
            "last": u.last_login.isoformat() if u.last_login else None
        }

        for u in users
    ]

@router.post("/users")
def create_user(
    data: dict,
    membership: WorkspaceUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    workspace_id = membership.workspace_id

    existing = db.query(UserDB).filter(
        UserDB.email == data.get("email")
    ).first()

    if existing:
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
    membership: WorkspaceUser = Depends(require_admin),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    workspace_id = membership.workspace_id
    email = data.get("email")
    role = data.get("role", "member")

    if not email:
        raise HTTPException(400, "Email requis")

    existing_invite = db.query(WorkspaceInvite).filter(
        WorkspaceInvite.email == email,
        WorkspaceInvite.workspace_id == workspace_id,
        WorkspaceInvite.used == False
    ).first()

    if existing_invite:
        raise HTTPException(400, "Invitation déjà envoyée")

    existing_user = db.query(UserDB).filter(UserDB.email == email).first()
    if existing_user:
        existing_membership = db.query(WorkspaceUser).filter(
            WorkspaceUser.user_id == existing_user.id,
            WorkspaceUser.workspace_id == workspace_id
        ).first()

        if existing_membership:
            raise HTTPException(400, "Utilisateur déjà dans le workspace")

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    invite = WorkspaceInvite(
        email=email,
        workspace_id=workspace_id,
        role=role,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=7)
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

@router.get("/invites")
def get_invites(
    membership: WorkspaceUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    workspace_id = membership.workspace_id

    invites = db.query(WorkspaceInvite).filter(
        WorkspaceInvite.workspace_id == workspace_id,
        WorkspaceInvite.used == False
    ).all()
    result = []

    for invite in invites:
        result.append({
            "id": str(invite.id),
            "email": invite.email,
            "role": invite.role,
            "expires_at": invite.expires_at,
            "days_remaining": max( 0, ceil( (invite.expires_at - datetime.utcnow()).total_seconds() / 86400 ) )
        })

    return result

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
        return RedirectResponse(
            url="https://alasdia.com/login.html"
        )

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
            url=f"https://alasdia.com/multi-users.html?token={jwt_token}&workspace_id={invite.workspace_id}"
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
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_admin)
):

    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    workspace_id = membership.workspace_id

    target_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not target_membership:
        raise HTTPException(403, "User hors workspace")

    # owner protégé
    if user.id == workspace_id:
        raise HTTPException(400, "Impossible de modifier le propriétaire")

    target_membership.role = data.get("role")
    db.commit()

    return {"message": "Rôle mis à jour"}

@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_admin)
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        raise HTTPException(404)

    workspace_id = membership.workspace_id

    target_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not target_membership:
        raise HTTPException(403, "User hors workspace")

    if user.id == workspace_id :
        raise HTTPException(400, "Impossible de suspendre le propriétaire")

    user.status = "suspended" if user.status == "active" else "active"

    db.commit()

    return {"message": "Statut modifié"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_admin),
    current_user: UserDB = Depends(get_current_user)
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()

    if not user:
        raise HTTPException(404)

    workspace_id = membership.workspace_id

    target_membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).first()

    if not target_membership:
        raise HTTPException(403, "User hors workspace")

    if user.id == workspace_id:
        raise HTTPException(400, "Impossible de supprimer le propriétaire")

    if user.id == current_user.id:
        raise HTTPException(400, "Tu ne peux pas te supprimer")


    db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).delete()

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