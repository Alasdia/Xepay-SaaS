from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from backend.database import engine, get_db
from backend.models import UserDB, User, UserLogin, Wallet, ChangePasswordRequest, Payment, Profile, ProfileRequest, ProfileUpdateRequest, PlanUpdate, Link, SecurityAlertsRequest, GoogleCodeExchange, GoogleLinkRequest, NotificationPreferencesRequest
from backend.auth import get_current_user, issue_new_session
from backend.services.workspace_service import (
    get_workspace_owner_id
)
from backend.security import verify_password, create_2fa_pending_token
from backend.middleware.authorization import require_admin, require_owner, require_member, require_manager, normalize_role, require_business
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from datetime import datetime, timezone
from uuid import uuid4
from backend.security import hash_password
from fastapi import Request
import hashlib
from datetime import datetime, timedelta
from backend.models import WorkspaceUser, Profile, WorkspaceInvite, ResetPasswordRequest, SecurityEvent
from uuid import UUID
from fastapi import Form, File, UploadFile, Header
from fastapi.responses import RedirectResponse
import os, shutil
from fastapi.responses import FileResponse
from fastapi import FastAPI, Request
from backend.services.email_service import send_invitation_email, send_login_alert_email, is_notification_enabled
from backend.services.rate_limit import allow_attempt, reset as reset_rate_limit
from backend.services.security_log_service import log_security_event, resolve_log_workspace_id
from backend.security import hash_password, verify_password, decrypt_secret
from math import ceil
import requests
import pyotp
import os
import stripe
import secrets

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Voir backend/routes/lien.py pour le même principe - jamais en dur.
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://api.alasdia.com")

router = APIRouter()

# Rôles qu'un admin peut attribuer via PUT /users/{user_id}/role ou POST /invites.
# "owner" est volontairement exclu : le transfert de propriété est un flux distinct,
# non couvert ici, et ne doit pas pouvoir être obtenu par une simple attribution de rôle.
ASSIGNABLE_ROLES = {"admin", "manager", "membre", "lecteur"}


def _validate_assignable_role(role) -> str:
    normalized = normalize_role(role) if isinstance(role, str) else ""
    if normalized not in ASSIGNABLE_ROLES:
        raise HTTPException(400, "Rôle invalide")
    return normalized


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
        joined_workspace_id = None
        if user.invite_token:
            token_hash = hashlib.sha256(
                user.invite_token.encode()
            ).hexdigest()
            invite = db.query(WorkspaceInvite).filter(WorkspaceInvite.token_hash == token_hash, WorkspaceInvite.used == False).first()
            if invite:
                membership = WorkspaceUser(user_id=new_user.id, workspace_id=invite.workspace_id, role=invite.role)
                db.add(membership)
                invite.used = True
                joined_workspace_id = invite.workspace_id
        else:
            membership = WorkspaceUser(user_id=new_user.id, workspace_id=new_user.id, role="owner")
            db.add(membership)
        try:
            client = stripe.StripeClient(os.getenv("STRIPE_SECRET_KEY"))
            user_country = getattr(user, "country", "US").upper() if hasattr(user, "country") and user.country else "US"
            account_configuration = {
                "merchant": {
                    "capabilities": {
                        "card_payments": {
                            "requested": True
                        }
                    }
                },
                "recipient": {
                    "capabilities": {
                        "stripe_balance": {
                            "stripe_transfers": {
                                "requested": True
                            }
                        }
                    }
                }
            }
            account = client.v2.core.accounts.create(
                params={
                    "contact_email": new_user.email,
                    "identity": {
                        "country": user_country
                    },
                    "dashboard": "express",
                    "configuration": account_configuration,
                    "defaults": {
                        "responsibilities": {
                            "fees_collector": "application",
                            "losses_collector": "application"
                        }
                    }
                }
            )
            stripe.Account.modify(
                account.id,
                settings={
                    "payouts": {
                        "schedule": {
                            "interval": "manual"
                        }
                    }
                }
            )
            try:
                stripe.Account.modify(
                    account.id,
                    capabilities={
                        "card_issuing": {"requested": True}
                    }
                )
            except stripe.error.StripeError as e:
                print("❌ ERREUR ISSUING")
                print("type:", type(e).__name__)
                print("message:", str(e))
                print("code:", getattr(e, "code", None))
                print("param:", getattr(e, "param", None))
                print("request_id:", getattr(e, "request_id", None))
            profile = Profile(user_id=new_user.id, stripe_account_id=account.id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        except Exception as e:
            print("❌ ERREUR CRITIQUE:", repr(e))
            import traceback
            traceback.print_exc()
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        wallet = Wallet(user_id=new_user.id, balance=0, created_at=datetime.now(timezone.utc))
        db.add(wallet)
        db.commit()
        if joined_workspace_id:
            log_security_event(db, new_user.id, "workspace_joined", "Invitation acceptée, a rejoint l'équipe", workspace_id=joined_workspace_id)
        return {"success": True}
    except Exception as e:
        db.rollback()
        print("❌ ERREUR SIGNUP :", repr(e))
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/login")
def login(
    request: Request,
    response: Response,
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
    workspace_user = db.query(WorkspaceUser).filter(WorkspaceUser.user_id == user.id, WorkspaceUser.role == "owner").first()
    if not workspace_user:
        workspace_user = db.query(WorkspaceUser).filter(WorkspaceUser.user_id == user.id).first()
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    if user.two_factor_enabled:
        pre_auth_token = create_2fa_pending_token(user.email)
        return {
            "requires_2fa": True,
            "email": user.email,
            "workspace_id": workspace_user.workspace_id,
            "pre_auth_token": pre_auth_token
        }
    ip = request.client.host
    device = request.headers.get("user-agent", "Appareil inconnu")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    issue_new_session(db, response, user, request=request)
    if is_notification_enabled(user, "compte.new_device_login", legacy_flag=user.alert_login):
        send_login_alert_email(email=user.email, device=device, ip=ip)
    return {
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


@router.get("/notification-preferences")
def get_notification_preferences(
    current_user: UserDB = Depends(get_current_user)
):
    """Paramètres > Notifications (grille Compte/Paiements/Virement/Solde/
    Produits/Client/Mises à jour Xepay). Clé absente côté frontend = case
    cochée par défaut (voir is_notification_enabled, même logique opt-out)."""
    return current_user.notification_prefs or {}


@router.post("/notification-preferences")
def update_notification_preferences(
    data: NotificationPreferencesRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    merged = dict(current_user.notification_prefs or {})
    merged.update(data.prefs)
    current_user.notification_prefs = merged
    db.commit()
    return {"prefs": merged}


CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# Origines autorisées à passer leur propre redirect_uri lors de l'échange
# POST (GIS initCodeClient en ux_mode:'popup' impose comme redirect_uri
# l'origine de la page appelante — jamais l'URL /auth/google/callback —
# donc le frontend doit nous dire laquelle). Aligné sur CORSMiddleware
# (backend/main.py) : seules ces origines sont de toute façon autorisées à
# appeler cet endpoint depuis un navigateur ; cette liste protège aussi les
# appels directs hors navigateur (non soumis au CORS).
ALLOWED_GOOGLE_EXCHANGE_ORIGINS = {"https://www.alasdia.com", "https://alasdia.com"}

from fastapi.responses import RedirectResponse
from fastapi import HTTPException
import requests

def _exchange_google_code(code: str, db: Session, redirect_uri: str, invite_token: str = None) -> dict:
    """Logique partagée par le callback GET (redirect_uri = GOOGLE_REDIRECT_URI)
    et l'endpoint POST /auth/google/exchange (redirect_uri = origine de la
    page qui a appelé initCodeClient). Retourne un dict, jamais de réponse
    HTTP : chaque appelant construit la réponse qui lui correspond
    (redirection pour le GET, JSON pour le POST)."""
    token_url = "https://oauth2.googleapis.com/token"

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": redirect_uri,
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

    google_id = user_data.get("id")
    # Email d'abord (comportement historique), puis repli sur google_id -
    # permet de se connecter via un compte Google lié (Paramètres > Compte
    # Google) même si son email differe de celui du compte Xepay.
    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user and google_id:
        user = db.query(UserDB).filter(UserDB.google_id == google_id).first()

    if not user:
        user = UserDB(email=email)
        db.add(user)
        db.flush()

        # Invitation d'équipe acceptée via Google (voir GET /invites/accept,
        # qui redirige vers signup.html?token=... pour un email pas encore
        # inscrit - signup.js transmet ce token jusqu'ici désormais) :
        # rejoint le workspace de l'inviteur avec le rôle prévu, au lieu de
        # créer un nouveau workspace "owner" - jamais fait avant que
        # signup.js ne transmette le token (l'invitation restait "en
        # attente" pour toujours, même après inscription).
        invite = None
        if invite_token:
            token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
            invite = db.query(WorkspaceInvite).filter(
                WorkspaceInvite.token_hash == token_hash,
                WorkspaceInvite.used == False,
                WorkspaceInvite.email == email,
            ).first()

        if invite:
            membership = WorkspaceUser(
                user_id=user.id,
                workspace_id=invite.workspace_id,
                role=invite.role
            )
            db.add(membership)
            invite.used = True
        else:
            membership = WorkspaceUser(
                user_id=user.id,
                workspace_id=user.id,
                role="owner"
            )
            db.add(membership)

        # Même création de compte Stripe que /signup (client.v2.core.accounts,
        # pas l'ancien stripe.Account.create(type="express", ...) qui était
        # utilisé ici jusque-là - cohérence avec la plateforme Stripe
        # actuelle, et surtout : jamais exercé en prod avant que signup.js
        # soit corrigé (l'inscription Google a toujours redirigé vers une
        # URL cassée), donc jamais remarqué que cette version plantait.
        # Toute erreur ici annule la création du compte (rollback) plutôt
        # que de laisser passer un 500 brut qui saute CORSMiddleware et
        # s'affiche à tort comme "Failed to fetch" côté navigateur.
        try:
            client = stripe.StripeClient(os.getenv("STRIPE_SECRET_KEY"))
            account_configuration = {
                "merchant": {
                    "capabilities": {
                        "card_payments": {"requested": True}
                    }
                },
                "recipient": {
                    "capabilities": {
                        "stripe_balance": {
                            "stripe_transfers": {"requested": True}
                        }
                    }
                }
            }
            account = client.v2.core.accounts.create(
                params={
                    "contact_email": user.email,
                    "identity": {"country": "US"},
                    "dashboard": "express",
                    "configuration": account_configuration,
                    "defaults": {
                        "responsibilities": {
                            "fees_collector": "application",
                            "losses_collector": "application"
                        }
                    }
                }
            )
            stripe.Account.modify(
                account.id,
                settings={
                    "payouts": {
                        "schedule": {
                            "interval": "manual"
                        }
                    }
                }
            )
            try:
                stripe.Account.modify(
                    account.id,
                    capabilities={
                        "card_issuing": {"requested": True}
                    }
                )
            except stripe.error.StripeError as e:
                print("❌ ERREUR ISSUING (google signup):", repr(e))

            profile = Profile(user_id=user.id, stripe_account_id=account.id)
            db.add(profile)

            wallet = Wallet(user_id=user.id, balance=0)
            db.add(wallet)

            db.commit()
            db.refresh(user)
            if invite:
                log_security_event(db, user.id, "workspace_joined", "Invitation acceptée, a rejoint l'équipe", workspace_id=invite.workspace_id)
        except Exception as e:
            print("❌ ERREUR CRITIQUE (google signup):", repr(e))
            import traceback
            traceback.print_exc()
            db.rollback()
            raise HTTPException(status_code=500, detail="Impossible de créer le compte Stripe pour cette inscription")

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

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
        return {
            "requires_2fa": True,
            "email": user.email,
            "workspace_id": workspace_id,
            # Calculé pour le POST (qui en a besoin pour /auth/2fa/verify-login,
            # cf. UserLogin /login) ; le GET existant l'ignore et garde son
            # URL de redirection inchangée.
            "pre_auth_token": create_2fa_pending_token(user.email),
        }

    return {
        "requires_2fa": False,
        "user": user,
        "email": user.email,
        "workspace_id": workspace_id,
        "account_id": user.account_id,
    }


@router.get("/auth/google/callback")
def google_callback(
    code: str,
    request: Request,
    db: Session = Depends(get_db)
):
    result = _exchange_google_code(code, db, redirect_uri=REDIRECT_URI)

    if result["requires_2fa"]:
        return RedirectResponse(
            url=f"https://alasdia.com/login.html?requires_2fa=true&email={result['email']}&workspace_id={result['workspace_id']}"
        )

    # Plus aucun jeton dans l'URL de redirection (ni dans les logs du
    # navigateur/serveur) : le cookie de session est posé directement sur
    # cette RedirectResponse, avant de renvoyer vers le dashboard.
    redirect = RedirectResponse(
        url=f"https://alasdia.com/dashboard.html?workspace_id={result['workspace_id']}"
    )
    issue_new_session(db, redirect, result["user"], request=request)
    return redirect


@router.post("/auth/google/exchange")
def google_exchange(
    payload: GoogleCodeExchange,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Variante JSON du callback ci-dessus, pour le widget GIS
    (initCodeClient, ux_mode:'popup') : le code arrive via un callback JS
    frontend plutôt que par une redirection Google directe, donc la réponse
    doit être du JSON exploitable en JS, pas une redirection HTTP."""
    if payload.redirect_uri not in ALLOWED_GOOGLE_EXCHANGE_ORIGINS:
        raise HTTPException(400, "Origine non autorisée")

    result = _exchange_google_code(payload.code, db, redirect_uri=payload.redirect_uri, invite_token=payload.invite_token)

    if result["requires_2fa"]:
        return {
            "requires_2fa": True,
            "email": result["email"],
            "workspace_id": result["workspace_id"],
            "pre_auth_token": result["pre_auth_token"],
        }

    issue_new_session(db, response, result["user"], request=request)
    return {
        "email": result["email"],
        "workspace_id": result["workspace_id"],
        "account_id": result["account_id"],
    }


@router.post("/auth/google/link")
def link_google_account(
    payload: GoogleLinkRequest,
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Associe un compte Google à l'utilisateur déjà connecté (Paramètres >
    Informations personnelles > Compte Google) - ne crée jamais de session,
    contrairement à _exchange_google_code (login). google_id permet ensuite
    de se connecter via ce compte Google même si son email diffère de celui
    du compte Xepay (voir le repli dans _exchange_google_code)."""
    if payload.redirect_uri not in ALLOWED_GOOGLE_EXCHANGE_ORIGINS:
        raise HTTPException(400, "Origine non autorisée")

    token_res = requests.post("https://oauth2.googleapis.com/token", data={
        "code": payload.code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": payload.redirect_uri,
        "grant_type": "authorization_code",
    })
    access_token = token_res.json().get("access_token")
    if not access_token:
        raise HTTPException(400, "Échec de l'authentification Google")

    user_res = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    user_data = user_res.json()
    google_id = user_data.get("id")
    google_email = user_data.get("email")
    if not google_id or not google_email:
        raise HTTPException(400, "Informations Google invalides")

    already_linked = db.query(UserDB).filter(
        UserDB.google_id == google_id,
        UserDB.id != current_user.id,
    ).first()
    if already_linked:
        raise HTTPException(409, "Ce compte Google est déjà lié à un autre compte Xepay")

    current_user.google_id = google_id
    current_user.google_email = google_email
    db.commit()
    log_security_event(db, current_user.id, "google_linked", f"Compte Google connecté ({google_email})", workspace_id=resolve_log_workspace_id(request, current_user.id))
    return {"google_email": google_email}


@router.post("/auth/google/unlink")
def unlink_google_account(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.google_id = None
    current_user.google_email = None
    db.commit()
    log_security_event(db, current_user.id, "google_unlinked", "Compte Google déconnecté", workspace_id=resolve_log_workspace_id(request, current_user.id))
    return {"ok": True}


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

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    # ❌ pas de compte Stripe
    if not profile or not profile.stripe_account_id:
        return {
            "connected": False,
            "needs_kyc": False
        }

    try:
        account = stripe.Account.retrieve(
            profile.stripe_account_id,
            expand=["requirements"]
        )
    except Exception as e:
        print("STRIPE STATUS - retrieve failed:", repr(e))
        raise HTTPException(status_code=502, detail="Impossible de récupérer le statut Stripe")

    # Protégé : account.requirements peut être absent/None (ex: comptes créés
    # via l'API v2 Accounts, voir /signup et _exchange_google_code) même
    # avec expand=["requirements"] - un accès direct à .currently_due
    # plantait alors en AttributeError, masqué en erreur CORS côté
    # navigateur (même classe de bug que /stripe/business-details).
    try:
        requirements = getattr(account, "requirements", None)
        currently_due = list(requirements.currently_due) if requirements and requirements.currently_due else []
        eventually_due = list(requirements.eventually_due) if requirements and requirements.eventually_due else []

        is_ready = bool(account.charges_enabled) and bool(account.payouts_enabled)

        return {
            "connected": is_ready,
            "needs_kyc": len(currently_due) > 0,
            "future_requirements": len(eventually_due) > 0,

            "stripe": {
                "charges_enabled": bool(account.charges_enabled),
                "payouts_enabled": bool(account.payouts_enabled),
                "details_submitted": bool(getattr(account, "details_submitted", False)),
                "created": datetime.fromtimestamp(account.created, tz=timezone.utc).isoformat() if getattr(account, "created", None) else None,
                "business_name": (account.business_profile.name if getattr(account, "business_profile", None) else None) or getattr(account, "email", None),
                "country": getattr(account, "country", None),
                "requirements": {
                    "currently_due": currently_due,
                    "eventually_due": eventually_due,
                }
            },

            "profile": {
                "full_name": profile.full_name,
                "phone": profile.phone,
                "stripe_account_id": profile.stripe_account_id
            }
        }
    except Exception as e:
        print("STRIPE STATUS - shaping failed:", repr(e))
        raise HTTPException(status_code=500, detail="Erreur lors de la lecture du statut Stripe")


def _format_address(addr) -> Optional[str]:
    if not addr:
        return None
    parts = [addr.get("line1"), addr.get("line2"), addr.get("postal_code"), addr.get("city"), addr.get("state"), addr.get("country")]
    return ", ".join(p for p in parts if p) or None


@router.get("/stripe/business-details")
def stripe_business_details(
    membership: WorkspaceUser = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Paramètres > Entreprise > Informations du compte - identité de base
    du compte Connect, en lecture seule. Le détail (entreprise, représentant
    légal, documents...) est géré par le widget Stripe intégré plutôt que
    reconstruit ici champ par champ - voir Paramètres > Entreprise >
    Informations sur votre entreprise (/stripe/account-session)."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(status_code=400, detail="Aucun compte Stripe connecté")

    try:
        account = stripe.Account.retrieve(profile.stripe_account_id)
    except Exception as e:
        print("STRIPE BUSINESS DETAILS - retrieve failed:", repr(e))
        raise HTTPException(status_code=502, detail="Impossible de récupérer les informations Stripe")

    # Chaque champ est lu isolément : une surprise sur l'un (ex: forme de
    # compte Stripe inattendue) ne doit jamais faire échouer les autres ni
    # renvoyer un 500 brut (qui saute CORSMiddleware et s'affiche à tort
    # comme une erreur CORS côté navigateur) - on préfère un champ manquant
    # à toute la vue vide.
    def _safe(label, fn):
        try:
            return fn()
        except Exception as e:
            print(f"STRIPE BUSINESS DETAILS - {label} failed:", repr(e))
            return None

    bp = _safe("business_profile", lambda: account.business_profile)
    company = _safe("company", lambda: getattr(account, "company", None))
    individual = _safe("individual", lambda: getattr(account, "individual", None))

    company_address = (
        _safe("company.address", lambda: _format_address(company.address) if company else None)
        or _safe("individual.address", lambda: _format_address(individual.address) if individual else None)
    )
    legal_name = (
        _safe("company.name", lambda: company.name if company else None)
        or _safe("business_profile.name", lambda: bp.name if bp else None)
    )
    account_id = _safe("account.id", lambda: account.id)
    # Pour les comptes créés via l'API v2 Accounts (voir /signup et
    # _exchange_google_code), le champ legacy account.type vaut toujours
    # "none" - le vrai type de dashboard est sous
    # account.controller.stripe_dashboard.type ("express"/"full"/"none").
    # Repli sur account.type pour les comptes legacy qui l'ont encore.
    def _controller_dashboard_type():
        controller = getattr(account, "controller", None)
        dashboard = getattr(controller, "stripe_dashboard", None) if controller else None
        return getattr(dashboard, "type", None) if dashboard else None

    account_type = (
        _safe("controller.stripe_dashboard.type", _controller_dashboard_type)
        or _safe("account.type", lambda: account.type if account.type != "none" else None)
    )
    # business_type (company/individual/non_profit/government_entity/null) :
    # exposé pour diagnostiquer pourquoi l'adresse peut rester vide (ex: si
    # Stripe considère encore le compte "individual" alors que l'adresse
    # d'entreprise a été saisie côté "company" lors de l'onboarding, ou
    # inversement) plutôt que de deviner à l'aveugle.
    business_type = _safe("account.business_type", lambda: account.business_type)

    return {
        "account": {
            "name": legal_name,
            "id": account_id,
            "type": account_type,
            "business_type": business_type,
            "address": company_address,
        },
    }


@router.post("/security/log-workspace-access")
def log_workspace_access(
    membership: WorkspaceUser = Depends(require_member),
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Appelé par le sélecteur de workspace (bascule explicite) ET une fois
    par chargement de l'app (app.js, init) - pour que le propriétaire
    puisse répondre à "qui a accédé à mon workspace, et quand ?", y
    compris quand une session déjà ouverte reprend directement sur ce
    workspace sans repasser par le sélecteur. Ignore silencieusement son
    propre workspace : pas utile de se journaliser soi-même, et ça
    éviterait de polluer le journal à chaque simple rechargement de page."""
    if membership.workspace_id == current_user.id:
        return {"ok": True}
    log_security_event(
        db, current_user.id, "workspace_accessed", "A accédé à ce workspace",
        workspace_id=membership.workspace_id,
    )
    return {"ok": True}


@router.get("/security/events")
def get_security_events(
    membership: WorkspaceUser = Depends(require_member),
    db: Session = Depends(get_db),
):
    """Paramètres > Équipe et sécurité > Journal d'activité - événements
    survenus DANS LE WORKSPACE ACTIF (X-Workspace-Id), pas seulement ceux
    de l'utilisateur courant : actions personnelles de chaque membre
    (connexion, mot de passe, 2FA, clés d'accès, compte Google) effectuées
    en consultant ce workspace, et actions d'équipe qui s'y rapportent
    (inviter/changer un rôle/suspendre/retirer un membre)."""
    events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.workspace_id == membership.workspace_id)
        .order_by(SecurityEvent.created_at.desc())
        .limit(50)
        .all()
    )
    actor_ids = {e.user_id for e in events}
    actor_emails = (
        {u.id: u.email for u in db.query(UserDB).filter(UserDB.id.in_(actor_ids)).all()}
        if actor_ids else {}
    )
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "actor_email": actor_emails.get(e.user_id),
            "ip": e.ip,
            "created_at": e.created_at,
        }
        for e in events
    ]


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Action purement personnelle (le mot de passe de current_user, jamais
    celui d'un workspace) - ne doit dépendre d'aucun rôle dans le workspace
    actif. Dépendait à tort de require_owner (jamais lu dans le corps de la
    fonction) : un membre invité (jamais "owner" d'aucun workspace, ou
    simplement en train de consulter un workspace où il n'est pas owner)
    ne pouvait tout simplement jamais changer son propre mot de passe."""
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
        log_security_event(db, user.id, "password_changed", "Mot de passe modifié", workspace_id=resolve_log_workspace_id(request, user.id))

        return {"success": True, "message": "Mot de passe mis à jour"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    normalized_email = data.email.strip().lower()
    email_ip_key = f"reset-password:{normalized_email}:{ip}"
    ip_key = f"reset-password:ip:{ip}"
    email_key = f"reset-password:email:{normalized_email}"

    if not allow_attempt(email_ip_key) or not allow_attempt(ip_key) or not allow_attempt(email_key):
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez plus tard.")

    generic_error = HTTPException(status_code=400, detail="Impossible de vérifier les informations de réinitialisation.")

    user = db.query(UserDB).filter(UserDB.email == data.email).first()
    if not user:
        raise generic_error

    if not user.two_factor_secret:
        raise generic_error

    secret = decrypt_secret(user.two_factor_secret)
    totp = pyotp.TOTP(secret)

    if not totp.verify(data.code):
        raise generic_error

    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas")

    user.password = hash_password(data.new_password)
    db.commit()

    reset_rate_limit(email_ip_key)
    reset_rate_limit(ip_key)
    reset_rate_limit(email_key)

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
        "profile": {
            "stripe_account_id": (
                db.query(Profile)
                .filter(Profile.user_id == owner_id)
                .first()
                .stripe_account_id
            )
        },
        "session": {
            "device": user_agent,
            "ip": ip,
            "last_seen": user.last_login.isoformat() if user.last_login else None
        }
    }

@router.delete("/delete-account")
def delete_account(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Désactivation, jamais une suppression : is_deleted=True seulement,
    aucune ligne (paiements, factures, clients, liens...) n'est jamais
    effacée - conservé pour les obligations comptables/légales et pour
    pouvoir réactiver le compte. Si cet utilisateur est propriétaire d'un
    workspace avec un compte Stripe Connect, on tente aussi de couper
    l'accès de Xepay à ce compte côté Stripe (Account.delete) - cela ne
    supprime jamais les données Stripe du marchand (qui restent gérées
    depuis son propre Dashboard), et échoue silencieusement pour les
    comptes "standard" que la plateforme ne peut pas détacher via l'API
    (Stripe l'interdit) - la désactivation Xepay reste valide dans tous
    les cas."""
    try:
        user.is_deleted = True
        db.commit()

        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if profile and profile.stripe_account_id:
            try:
                stripe.Account.delete(profile.stripe_account_id)
            except Exception as e:
                print("DELETE ACCOUNT - Stripe disconnect failed:", repr(e))

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

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()

    if not profile:
        profile = Profile(user_id=owner_id, full_name=None, phone=None)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    owner = db.query(UserDB).filter(UserDB.id == owner_id).first()

    return {
        # Coordonnées : partagées par le workspace actif (son propriétaire),
        # vues/modifiables par n'importe quel manager+ - comportement
        # intentionnel (facturation/Stripe sont au nom du propriétaire).
        "full_name": profile.full_name,
        "email": owner.email,
        "phone": profile.phone,
        "phone_verified": profile.phone_verified,
        "plan": owner.plan,
        "plan_started_at": owner.plan_started_at,
        "plan_expires_at": owner.plan_expires_at,
        "subscription_status": owner.subscription_status,
        "cancel_at_period_end": owner.cancel_at_period_end,
        # Personnel à current_user, jamais au propriétaire du workspace
        # actif : un membre invité consultant un workspace dont il n'est
        # pas propriétaire voyait/pilotait la 2FA et le compte Google du
        # PROPRIÉTAIRE à la place des siens (Authentification, Équipe et
        # sécurité > Sécurité du compte).
        "two_factor_enabled": current_user.two_factor_enabled,
        "two_factor_backup_code_generated_at": current_user.two_factor_backup_code_generated_at,
        "google_linked": current_user.google_id is not None,
        "google_email": current_user.google_email,
        "account_id": current_user.account_id,
        "last_login": current_user.last_login,
    }


@router.patch("/profile")
def update_profile(
    data: ProfileUpdateRequest,
    membership: WorkspaceUser = Depends(require_manager),
    db: Session = Depends(get_db),
):
    """Seuls full_name/phone sont modifiables ici (email/compte géré par
    Stripe/auth) - voir Paramètres > Informations personnelles > Coordonnées.
    Seul un champ non-None est modifié, l'autre reste inchangé."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    if not profile:
        profile = Profile(user_id=owner_id)
        db.add(profile)
    if data.full_name is not None:
        profile.full_name = data.full_name.strip() or None
    if data.phone is not None:
        profile.phone = data.phone.strip() or None
    db.commit()
    return {"full_name": profile.full_name, "phone": profile.phone}


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
            return_url=f"{PUBLIC_API_URL}/profil.html",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard")
def dashboard():
    return FileResponse("html/dashboard.html")


@router.get("/users")
def get_users(
    membership: WorkspaceUser = Depends(require_member),
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_business)
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
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_business)
):
    workspace_id = membership.workspace_id

    existing = db.query(UserDB).filter(
        UserDB.email == data.get("email")
    ).first()

    if existing:
        membership = WorkspaceUser(
            user_id=existing.id,
            workspace_id=workspace_id,
            role=_validate_assignable_role(data.get("role", "membre"))
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
        role=_validate_assignable_role(data.get("role", "membre"))
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
    current_user: UserDB = Depends(get_current_user),
    _: UserDB = Depends(require_business)
):
    workspace_id = membership.workspace_id
    email = data.get("email")
    role = _validate_assignable_role(data.get("role", "membre"))

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

    invite_link = f"{PUBLIC_API_URL}/invites/accept?token={token}"

    send_invitation_email(
        to_email=email,
        invite_link=invite_link,
        inviter_email=current_user.email,
        role=role
    )
    log_security_event(db, current_user.id, "member_invited", f"Invitation envoyée à {email} (rôle {role.capitalize()})", workspace_id=workspace_id)

    return {
        "message": "Invitation créée",
        "invite_link": invite_link
    }

@router.get("/invites")
def get_invites(
    membership: WorkspaceUser = Depends(require_admin),
    db: Session = Depends(get_db),
    _: UserDB = Depends(require_business)
):
    workspace_id = membership.workspace_id

    invites = db.query(WorkspaceInvite).filter(
        WorkspaceInvite.workspace_id == workspace_id,
        WorkspaceInvite.used == False,
        # Sans ce filtre, une invitation expirée (7 jours) restait affichée
        # "en attente" indéfiniment - elle n'est jamais marquée used=True
        # tant que personne ne clique dessus, expirée ou pas.
        WorkspaceInvite.expires_at >= datetime.utcnow(),
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
    request: Request,
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
        log_security_event(db, existing_user.id, "workspace_joined", "Invitation acceptée, a rejoint l'équipe", workspace_id=invite.workspace_id)

        # Plus de jeton dans l'URL de redirection : cookie de session posé
        # directement ici, comme pour /auth/google/callback. multi-users.html
        # est l'ancienne page retirée - next=parametres/equipe fait
        # atterrir directement sur Équipe et sécurité (voir app.js,
        # consumeOAuthBootstrap) plutôt que sur le tableau de bord nu.
        redirect = RedirectResponse(
            url=f"https://alasdia.com/dashboard.html?workspace_id={invite.workspace_id}&next=parametres/equipe"
        )
        issue_new_session(db, redirect, existing_user, request=request)
        return redirect
    # ==================================================
    # CAS 2 → NOUVEL UTILISATEUR
    # ==================================================

    return RedirectResponse(
        url=f"https://alasdia.com/signup.html?token={token}"
    )

@router.put("/users/{user_id}/role")
def update_role(
    user_id: str,
    data: dict,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_admin),
    _: UserDB = Depends(require_business)
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

    new_role = _validate_assignable_role(data.get("role"))
    target_membership.role = new_role
    db.commit()
    log_security_event(db, membership.user_id, "member_role_changed", f"Rôle de {user.email} changé en {new_role.capitalize()}", workspace_id=membership.workspace_id)

    return {"message": "Rôle mis à jour"}

@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_admin),
    _: UserDB = Depends(require_business)
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
    status_label = "suspendu" if user.status == "suspended" else "actif"
    log_security_event(db, membership.user_id, "member_status_changed", f"Statut de {user.email} changé en « {status_label} »", workspace_id=membership.workspace_id)

    return {"message": "Statut modifié"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_admin),
    current_user: UserDB = Depends(get_current_user),
    _: UserDB = Depends(require_business)
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


    removed_email = user.email

    db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == user.id,
        WorkspaceUser.workspace_id == workspace_id
    ).delete()

    db.commit()
    log_security_event(db, current_user.id, "member_removed", f"{removed_email} retiré de l'équipe", workspace_id=workspace_id)

    return {"message": "Utilisateur supprimé"}

@router.get("/workspaces/me")
def get_my_workspaces(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    memberships = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id
    ).all()
    # Le propre workspace de l'utilisateur (workspace_id == son propre id,
    # où il est "owner") doit toujours arriver en premier : sans ce tri, un
    # utilisateur invité comme membre/lecteur ailleurs pouvait voir CE
    # workspace-là listé en premier, et le frontend (multiUsers.js,
    # sélection automatique si workspace_id sauvegardé est invalide)
    # persistait alors silencieusement le mauvais workspace_id — perte du
    # rôle owner sur tous les appels suivants.
    memberships.sort(key=lambda m: m.workspace_id != current_user.id)

    workspace_ids = [m.workspace_id for m in memberships]
    owners_by_id = {
        u.id: u
        for u in db.query(UserDB).filter(UserDB.id.in_(workspace_ids)).all()
    } if workspace_ids else {}

    workspaces = []

    for membership in memberships:

        owner = owners_by_id.get(membership.workspace_id)

        workspace_name = (
            f"{owner.email.split('@')[0]} Workspace"
            if owner else
            "Workspace"
        )

        workspaces.append({
            "id": membership.workspace_id,
            "name": workspace_name,
            "owner_email": owner.email if owner else "—",
            "role": membership.role,
            "created_at": membership.created_at,
            "is_own_workspace": membership.workspace_id == current_user.id,
        })

    return workspaces


@router.post("/workspaces/{workspace_id}/leave")
def leave_workspace(
    workspace_id: str,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paramètres > Informations personnelles > Workspaces > "..." >
    Quitter le workspace. Jamais permis sur son propre workspace (celui où
    il est owner, workspace_id == son propre id) - il n'y a personne
    d'autre à qui le transférer ici."""
    if workspace_id == current_user.id:
        raise HTTPException(400, "Impossible de quitter votre propre workspace")

    membership = db.query(WorkspaceUser).filter(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id,
    ).first()
    if not membership:
        raise HTTPException(404, "Vous n'êtes pas membre de ce workspace")

    db.delete(membership)
    db.commit()
    return {"ok": True}