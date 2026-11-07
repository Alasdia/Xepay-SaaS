import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Profile, WorkspaceUser, VertoSubAccountRequest, VertoKybDataRequest, VertoBeneficiaryRequest
from backend.middleware.authorization import require_capability
from backend.services import verto_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_locked_or_create_profile(db: Session, owner_id: str) -> Profile:
    """Verrouille la ligne Profile
    (SELECT ... FOR UPDATE) si elle existe déjà - ferme la fenêtre de
    course du double-clic sur "Démarrer mon enregistrement" identifiée
    dans l'audit du 2026-11-07 (deux requêtes quasi simultanées liraient
    sinon toutes les deux verto_company_id=None avant qu'aucune n'ait
    committé). Une ligne neuve (juste insérée dans CETTE transaction) n'a
    besoin d'aucun verrou explicite - aucune autre transaction ne peut la
    voir avant son commit."""
    profile = db.query(Profile).filter(Profile.user_id == owner_id).with_for_update().first()
    if not profile:
        profile = Profile(user_id=owner_id)
        db.add(profile)
        db.flush()
    return profile


@router.post("/verto/onboarding/sub-account")
def create_verto_sub_account(
    body: VertoSubAccountRequest,
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Étape A du découpage du 2026-11-07 (remplace l'ancien
    POST /verto/onboarding, qui créait le sous-compte ET soumettait le
    KYB en un seul appel) : crée UNIQUEMENT le sous-compte Verto et
    persiste verto_company_id IMMÉDIATEMENT après le succès de cet appel
    réseau - jamais après un second appel (submit_onboarding_data, voir
    create_verto_kyb_data) qui pourrait échouer. Corrige le bug identifié
    dans l'audit : auparavant, un échec de soumission KYB après une
    création de sous-compte réussie ne persistait RIEN, et une nouvelle
    tentative créait un second sous-compte orphelin chez Verto à chaque
    fois, sans aucune limite.

    accountType="PARTNER_REFERRED" (Atlas for Platform) - voir le
    docstring de verto_service.create_sub_account. Protégé par
    VERTO_ENABLED (false par défaut) : testé empiriquement que ce
    changement de modèle seul ne débloque pas le 403 "Access Denied"
    actuel sur /sub-accounts, donc ce flux reste désactivé tant que
    Verto ne confirme pas l'accès.

    with_for_update() (voir _get_locked_or_create_profile) ferme la
    fenêtre de course du double-clic : deux requêtes quasi simultanées
    liraient sinon toutes les deux verto_company_id=None avant qu'aucune
    n'ait committé. UniqueConstraint("verto_company_id") côté base
    (migration d4a7c2e9f031) reste un filet de sécurité supplémentaire."""
    if not verto_service.VERTO_ENABLED:
        raise HTTPException(503, "Fonctionnalité en cours de déploiement.")

    owner_id = membership.workspace_id
    profile = _get_locked_or_create_profile(db, owner_id)

    if profile.verto_company_id:
        raise HTTPException(400, "Sous-compte Verto déjà créé")

    try:
        sub_account = verto_service.create_sub_account(
            account_type="PARTNER_REFERRED",
            country=body.country,
            name=body.company_name,
            sub_category=body.sub_category,
            identification_number=body.identification_number,
            tax_id_or_ein=body.tax_id_or_ein,
            external_id=owner_id,
        )
    except verto_service.VertoAtlasNotEnabledError:
        raise HTTPException(503, "L'enregistrement bancaire local n'est pas encore disponible. Réessayez plus tard.")
    except Exception:
        # Détail de l'exception (jamais le jeton ni VERTO_API_KEY/CLIENT_ID,
        # qui n'apparaissent dans aucun message d'erreur Verto renvoyé ici)
        # loggé côté serveur pour le diagnostic - jamais exposé au marchand.
        logger.exception("Echec création sous-compte Verto pour owner_id=%s", owner_id)
        raise HTTPException(502, "Erreur lors de la création. Réessayez plus tard.")

    # Persistance immédiate - avant tout autre appel réseau. C'est
    # précisément le correctif demandé : ne jamais laisser un
    # sous-compte réellement créé chez Verto sans trace côté Xepay.
    profile.verto_company_id = str(sub_account["id"])
    profile.verto_onboarding_status = "sub_account_created"
    db.commit()

    return {"status": "sub_account_created", "verto_company_id": profile.verto_company_id}


@router.post("/verto/onboarding/kyb-data")
def submit_verto_kyb_data(
    body: VertoKybDataRequest,
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Étape B du découpage du 2026-11-07 : soumet les données KYB sur un
    sous-compte déjà créé (voir create_verto_sub_account). Peut être
    rappelée plusieurs fois tant que le dossier n'est pas
    approuvé/rejeté par Verto (reprise d'un KYB incomplet) - NON
    CONFIRMÉ si Verto traite un second appel comme une mise à jour ou un
    doublon, jamais testé (bloqué par le 403 sandbox)."""
    if not verto_service.VERTO_ENABLED:
        raise HTTPException(503, "Fonctionnalité en cours de déploiement.")

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    if not profile or not profile.verto_company_id:
        raise HTTPException(400, "Sous-compte Verto non créé")
    if profile.verto_onboarding_status not in ("sub_account_created", "kyb_submitted"):
        raise HTTPException(400, f"Étape non disponible dans l'état actuel ({profile.verto_onboarding_status})")

    try:
        verto_service.submit_onboarding_data(profile.verto_company_id, body.kyc_payload)
    except Exception:
        logger.exception(
            "Echec soumission KYB Verto pour company_id=%s", profile.verto_company_id
        )
        raise HTTPException(502, "Erreur lors de la soumission. Réessayez plus tard.")

    profile.verto_onboarding_status = "kyb_submitted"

    # Consentement du dirigeant (PARTNER_REFERRED uniquement) - ne doit
    # jamais faire échouer la soumission KYB elle-même : le KYB est déjà
    # soumis, un échec d'envoi (y compris NotImplementedError tant que
    # l'endpoint n'est pas confirmé, voir send_director_consent_email)
    # laisse juste le statut à "not_sent", renvoyable via
    # POST /verto/resend-director-consent.
    try:
        verto_service.send_director_consent_email(profile.verto_company_id)
        profile.verto_director_consent_status = "sent"
    except Exception:
        logger.exception(
            "Echec envoi e-mail de consentement dirigeant pour company_id=%s", profile.verto_company_id
        )
        profile.verto_director_consent_status = "not_sent"

    db.commit()

    return {"status": "kyb_submitted"}


@router.get("/verto/status")
def get_verto_status(
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Statut d'onboarding + coordonnées USD à coller dans le Dashboard
    Stripe Express du marchand (voir routes/payout.py pour pourquoi Xepay
    ne peut pas le faire à sa place)."""
    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    if not profile:
        return {"status": "not_started"}
    return {
        "status": profile.verto_onboarding_status or "not_started",
        "director_consent_status": profile.verto_director_consent_status or "not_sent",
        "usd_account_number": profile.verto_usd_account_number,
        "usd_bank_code": profile.verto_usd_bank_code,
        "usd_bank_name": profile.verto_usd_bank_name,
        "stripe_external_account_linked": bool(profile.stripe_external_account_id),
        "beneficiary_registered": bool(profile.verto_beneficiary_id),
        "beneficiary_bank_name": profile.beneficiary_bank_name,
        "beneficiary_bank_iban_last4": (profile.beneficiary_bank_iban or "")[-4:] or None,
    }


@router.post("/verto/resend-director-consent")
def resend_director_consent(
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Renvoie l'e-mail de consentement Verto au dirigeant (PARTNER_REFERRED
    uniquement) - voir verto_service.send_director_consent_email, NON
    CONFIRMÉ tant que l'endpoint réel n'est pas vérifié."""
    if not verto_service.VERTO_ENABLED:
        raise HTTPException(503, "Fonctionnalité en cours de déploiement.")

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    if not profile or not profile.verto_company_id:
        raise HTTPException(400, "Onboarding Verto non démarré")

    try:
        verto_service.send_director_consent_email(profile.verto_company_id)
        profile.verto_director_consent_status = "sent"
        db.commit()
    except Exception:
        logger.exception(
            "Echec renvoi e-mail de consentement dirigeant pour company_id=%s", profile.verto_company_id
        )
        raise HTTPException(502, "Erreur lors de l'envoi. Réessayez plus tard.")

    return {"director_consent_status": profile.verto_director_consent_status}


@router.post("/verto/beneficiary")
def register_beneficiary(
    body: VertoBeneficiaryRequest,
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Enregistre le compte bancaire local UEMOA du marchand (destination
    finale des retraits, voir webhook/verto.py) - nécessite un sous-compte
    Verto déjà approuvé."""
    if not verto_service.VERTO_ENABLED:
        raise HTTPException(503, "Fonctionnalité en cours de déploiement.")

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    if not profile or not profile.verto_company_id:
        raise HTTPException(400, "Onboarding Verto non démarré")
    if profile.verto_onboarding_status != "approved":
        raise HTTPException(400, "Sous-compte Verto pas encore approuvé")

    try:
        verto_service.validate_iban_bic(body.iban, body.bic)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        result = verto_service.create_beneficiary(
            company_id=profile.verto_company_id,
            currency_id=verto_service.VERTO_XOF_CURRENCY_ID,
            company_name=profile.full_name or "",
            iban=body.iban,
            bic=body.bic,
            bank_name=body.bank_name,
            bank_country_code=body.bank_country_code,
            beneficiary_address_line1=body.beneficiary_address_line1,
            beneficiary_country_code=body.beneficiary_country_code,
            beneficiary_city=body.beneficiary_city,
            beneficiary_postal_code=body.beneficiary_postal_code,
            beneficiary_state_or_province=body.beneficiary_state_or_province,
        )
    except Exception as e:
        raise HTTPException(502, f"Echec création bénéficiaire Verto: {e}")

    accounts = result.get("accounts", result)
    profile.verto_beneficiary_id = str(accounts.get("id"))
    # Jamais l'IBAN complet en base - seulement les 4 derniers chiffres,
    # suffisant pour l'affichage (voir GET /verto/status) : aucune
    # fonctionnalité n'a besoin de la valeur complète après coup (les
    # virements utilisent verto_beneficiary_id, jamais l'IBAN
    # directement, voir webhook/verto.py).
    profile.beneficiary_bank_iban = body.iban[-4:]
    profile.beneficiary_bank_name = body.bank_name
    db.commit()

    return {"verto_beneficiary_id": profile.verto_beneficiary_id, "verification_state": accounts.get("verificationState")}
