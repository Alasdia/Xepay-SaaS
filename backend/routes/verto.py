import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Profile, WorkspaceUser, VertoOnboardingRequest, VertoBeneficiaryRequest
from backend.middleware.authorization import require_capability
from backend.services import verto_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_or_create_profile(db: Session, owner_id: str) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    if not profile:
        profile = Profile(user_id=owner_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.post("/verto/onboarding")
def start_verto_onboarding(
    body: VertoOnboardingRequest,
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Démarre l'onboarding Verto du marchand (leg USD de l'architecture
    Zero-Custody, voir services/verto_service.py) : crée le sous-compte,
    puis soumet les données KYC - tout via API, aucun passage par le
    dashboard Verto. Le sous-compte reste en statut "pending" jusqu'à la
    confirmation du webhook (voir webhook/verto.py)."""
    owner_id = membership.workspace_id
    profile = _get_or_create_profile(db, owner_id)

    if profile.verto_company_id:
        raise HTTPException(400, "Onboarding Verto déjà démarré")

    try:
        sub_account = verto_service.create_sub_account(
            account_type="SUB_CLIENT",
            country=body.country,
            name=body.company_name,
            sub_category=body.sub_category,
            identification_number=body.identification_number,
            tax_id_or_ein=body.tax_id_or_ein,
            external_id=owner_id,
        )
        company_id = str(sub_account["id"])
        verto_service.submit_onboarding_data(company_id, body.kyc_payload)
    except verto_service.VertoAtlasNotEnabledError:
        raise HTTPException(503, "L'enregistrement bancaire local n'est pas encore disponible. Réessayez plus tard.")
    except Exception:
        # Détail de l'exception (jamais le jeton ni VERTO_API_KEY/CLIENT_ID,
        # qui n'apparaissent dans aucun message d'erreur Verto renvoyé ici)
        # loggé côté serveur pour le diagnostic - jamais exposé au marchand.
        logger.exception("Echec onboarding Verto pour owner_id=%s", owner_id)
        raise HTTPException(502, "Erreur lors de l'enregistrement. Réessayez plus tard.")

    profile.verto_company_id = company_id
    profile.verto_onboarding_status = "pending"
    db.commit()

    return {"status": "pending", "verto_company_id": company_id}


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
        "usd_account_number": profile.verto_usd_account_number,
        "usd_bank_code": profile.verto_usd_bank_code,
        "usd_bank_name": profile.verto_usd_bank_name,
        "stripe_external_account_linked": bool(profile.stripe_external_account_id),
        "beneficiary_registered": bool(profile.verto_beneficiary_id),
        "beneficiary_bank_name": profile.beneficiary_bank_name,
        "beneficiary_bank_iban_last4": (profile.beneficiary_bank_iban or "")[-4:] or None,
    }


@router.post("/verto/beneficiary")
def register_beneficiary(
    body: VertoBeneficiaryRequest,
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
    db: Session = Depends(get_db),
):
    """Enregistre le compte bancaire local UEMOA du marchand (destination
    finale des retraits, voir webhook/verto.py) - nécessite un sous-compte
    Verto déjà approuvé."""
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
