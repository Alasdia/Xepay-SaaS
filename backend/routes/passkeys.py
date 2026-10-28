# Clés d'accès (WebAuthn/Passkeys) - Paramètres > Informations
# personnelles > Clés d'accès. Gestion uniquement (enregistrer/lister/
# renommer/supprimer) : ne change rien au flux de LOGIN existant (email+
# mot de passe / 2FA / Google) - une clé enregistrée ici n'est pas encore
# utilisable pour se connecter, ce serait un changement séparé du flux de
# login lui-même.
#
# Le challenge de la cérémonie d'enregistrement est gardé en mémoire
# (process unique, voir deploy-ec2.yml : un seul service systemd) entre
# /passkeys/register/start et /passkeys/register/finish - jamais persisté,
# sa durée de vie utile est de quelques secondes/minutes.
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)
from webauthn.helpers.exceptions import InvalidRegistrationResponse

from backend.database import get_db
from backend.models import UserDB, PasskeyCredential, PasskeyRegisterFinishRequest, PasskeyRenameRequest
from backend.auth import get_current_user
from backend.services.security_log_service import log_security_event, resolve_log_workspace_id

router = APIRouter()

# xepay.finance couvre xepay.finance, www.xepay.finance ET app.xepay.finance
# (la SPA, qui appelle navigator.credentials.create) - jamais api.xepay.finance,
# qui ne fait que vérifier la cérémonie côté serveur.
RP_ID = "xepay.finance"
RP_NAME = "Xepay"
ALLOWED_ORIGINS = {"https://www.xepay.finance", "https://xepay.finance", "https://app.xepay.finance"}

_pending_challenges: dict[str, bytes] = {}


@router.get("/passkeys")
def list_passkeys(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    creds = (
        db.query(PasskeyCredential)
        .filter(PasskeyCredential.user_id == current_user.id)
        .order_by(PasskeyCredential.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "name": c.name or "Clé d'accès",
            "created_at": c.created_at,
            "last_used_at": c.last_used_at,
        }
        for c in creds
    ]


@router.post("/passkeys/register/start")
def start_registration(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(PasskeyCredential)
        .filter(PasskeyCredential.user_id == current_user.id)
        .all()
    )
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=current_user.id.encode("utf-8"),
        user_name=current_user.email,
        user_display_name=current_user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=bytes.fromhex(c.credential_id))
            for c in existing
        ],
    )
    _pending_challenges[current_user.id] = options.challenge
    return json.loads(options_to_json(options))


@router.post("/passkeys/register/finish")
def finish_registration(
    payload: PasskeyRegisterFinishRequest,
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    challenge = _pending_challenges.get(current_user.id)
    if not challenge:
        raise HTTPException(400, "Aucun enregistrement de clé en cours, recommencez")

    credential_dict = dict(payload.credential)
    origin = credential_dict.pop("origin", None) or next(iter(ALLOWED_ORIGINS))
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(400, "Origine non autorisée")

    try:
        verified = verify_registration_response(
            credential=json.dumps(credential_dict),
            expected_challenge=challenge,
            expected_origin=origin,
            expected_rp_id=RP_ID,
        )
    except InvalidRegistrationResponse as e:
        raise HTTPException(400, f"Clé d'accès invalide : {e}")
    finally:
        _pending_challenges.pop(current_user.id, None)

    row = PasskeyCredential(
        user_id=current_user.id,
        credential_id=verified.credential_id.hex(),
        public_key=verified.credential_public_key.hex(),
        sign_count=verified.sign_count,
        name=payload.name or "Clé d'accès",
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    log_security_event(db, current_user.id, "passkey_added", f"Clé d'accès ajoutée ({row.name})", workspace_id=resolve_log_workspace_id(request, current_user.id))
    return {"id": row.id, "name": row.name}


@router.patch("/passkeys/{passkey_id}")
def rename_passkey(
    passkey_id: str,
    payload: PasskeyRenameRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(PasskeyCredential).filter(
        PasskeyCredential.id == passkey_id,
        PasskeyCredential.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(404, "Clé d'accès introuvable")
    row.name = payload.name.strip() or row.name
    db.commit()
    return {"id": row.id, "name": row.name}


@router.delete("/passkeys/{passkey_id}")
def delete_passkey(
    passkey_id: str,
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(PasskeyCredential).filter(
        PasskeyCredential.id == passkey_id,
        PasskeyCredential.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(404, "Clé d'accès introuvable")
    deleted_name = row.name
    db.delete(row)
    db.commit()
    log_security_event(db, current_user.id, "passkey_removed", f"Clé d'accès supprimée ({deleted_name})", workspace_id=resolve_log_workspace_id(request, current_user.id))
    return {"ok": True}
