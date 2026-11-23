"""Routes Buildness (anciennement "BildBus", renommé le 2026-11-22 -
formation de LLC US + EIN via doola, voir services/doola_service.py,
services/doola_mock_service.py, routes/webhook/doola.py) - prérequis à
l'activation du compte Stripe Connect d'un marchand non-résident."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import BuildnessCustomer, BuildnessCompany, BuildnessOnboardRequest, WorkspaceUser
from backend.middleware.authorization import require_capability
from backend.services.doola_client import get_doola_service, DoolaNotConfiguredError
from backend.services.doola_service import DoolaAPIError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/buildness/naics-codes")
async def get_buildness_naics_codes(
    membership: WorkspaceUser = Depends(require_capability("manage_company_formation")),
):
    """Secteurs d'activité acceptés par create_company (voir
    doola_service.list_naics_codes) - exposé pour peupler un menu
    déroulant côté formulaire Buildness plutôt que de laisser le
    marchand taper un texte libre que doola rejetterait."""
    try:
        doola = get_doola_service()
    except DoolaNotConfiguredError:
        raise HTTPException(503, "Buildness n'est pas encore disponible. Réessayez plus tard.")
    try:
        return await doola.list_naics_codes()
    except DoolaAPIError:
        logger.exception("Echec recuperation des codes NAICS doola")
        raise HTTPException(502, "Impossible de recuperer la liste des secteurs d'activite.")


@router.get("/buildness/countries")
async def get_buildness_countries(
    membership: WorkspaceUser = Depends(require_capability("manage_company_formation")),
):
    """Pays acceptés comme countryOfResidence/adresse (voir
    doola_service.list_countries)."""
    try:
        doola = get_doola_service()
    except DoolaNotConfiguredError:
        raise HTTPException(503, "Buildness n'est pas encore disponible. Réessayez plus tard.")
    try:
        return await doola.list_countries()
    except DoolaAPIError:
        logger.exception("Echec recuperation des pays doola")
        raise HTTPException(502, "Impossible de recuperer la liste des pays.")


@router.post("/buildness/onboard", status_code=202)
async def onboard_buildness(
    body: BuildnessOnboardRequest,
    membership: WorkspaceUser = Depends(require_capability("manage_company_formation")),
    db: Session = Depends(get_db),
):
    """Crée (si besoin) le customer doola du marchand, puis la LLC.
    Persistance immédiate après CHAQUE appel réseau réussi - même
    discipline que _get_locked_or_create_profile/create_verto_sub_account
    (routes/verto.py) : ne jamais laisser une ressource réellement créée
    chez le partenaire sans trace côté Xepay si l'étape suivante échoue.

    customer_id réutilisé si déjà créé pour ce marchand (xepay_merchant_id
    UNIQUE, voir models.py) - jamais un second customer doola pour la
    même tentative/un double-clic."""
    merchant_id = membership.workspace_id
    try:
        doola = get_doola_service()
    except DoolaNotConfiguredError:
        # Ni vraie clé doola, ni BUILDNESS_ALLOW_MOCK - voir doola_client.py.
        # 503 explicite plutôt qu'un appel réseau avec une clé vide/absente
        # qui échouerait plus bas de façon confuse, ou (pire) qu'un
        # basculement silencieux sur le mock en production.
        raise HTTPException(503, "Buildness n'est pas encore disponible. Réessayez plus tard.")

    customer = (
        db.query(BuildnessCustomer)
        .filter(BuildnessCustomer.xepay_merchant_id == merchant_id)
        .first()
    )
    if not customer:
        try:
            # countryOfResidence/phoneNumber requis par la vraie API doola
            # (confirmé le 2026-11-23) - manquaient avant cette correction,
            # ce qui aurait fait échouer tout appel réel en validation.
            doola_customer_id = await doola.create_customer({
                "email": body.email,
                "firstName": body.first_name,
                "lastName": body.last_name,
                "countryOfResidence": body.country,
                "phoneNumber": body.phone,
            })
        except DoolaAPIError:
            logger.exception("Echec creation customer doola pour merchant_id=%s", merchant_id)
            raise HTTPException(502, "Erreur lors de la creation du dossier. Reessayez plus tard.")

        customer = BuildnessCustomer(
            xepay_merchant_id=merchant_id,
            doola_customer_id=doola_customer_id,
            email=body.email,
            first_name=body.first_name,
            last_name=body.last_name,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # Ligne locale "draft" posée AVANT l'appel create_company (contrairement
    # au customer ci-dessus, qui lui a besoin de l'ID doola pour exister -
    # doola_company_id est nullable précisément pour permettre ce brouillon,
    # voir models.py) : même en cas d'échec total de l'appel doola
    # ci-dessous, le marchand garde une trace de sa demande.
    company = BuildnessCompany(
        customer_id=customer.id,
        company_name=body.company_name,
        state=body.state,
        status="draft",
        last_successful_step="draft",
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    # Adresse unique réutilisée à 3 endroits distincts du schéma doola
    # (responsibleParty, members[0], addresses[mailing]) - voir le
    # commentaire de BuildnessOnboardRequest (models.py) : doola exige ces
    # 3 adresses séparément, mais le marchand n'en a saisi qu'une seule
    # (lui-même étant le seul fondateur/responsable dans ce flux Buildness).
    address_dto = {
        "line1": body.address_line1,
        "city": body.address_city,
        "state": body.address_region,
        "postalCode": body.address_postal_code,
        "country": body.country,
        "phone": body.phone,
    }
    if body.address_line2:
        address_dto["line2"] = body.address_line2

    try:
        response = await doola.create_company(customer.doola_customer_id, {
            # nameOptions : liste de noms candidats par ordre de préférence
            # chez doola - un seul candidat ici (le formulaire Xepay ne
            # propose qu'un nom, pas plusieurs alternatives).
            "nameOptions": [{"name": body.company_name, "entityTypeEnding": "LLC"}],
            "state": body.state,
            "industry": body.industry,
            "description": body.description,
            "responsibleParty": {
                "legalFirstName": body.first_name,
                "legalLastName": body.last_name,
                "email": body.email,
                "address": address_dto,
            },
            # Adresse "business" fournie par doola lui-même (provider=
            # registeredAgent, pas d'adresse à donner) - le marchand cible
            # de Buildness est un fondateur non-résident, sans adresse
            # professionnelle US existante ; "mailing" reste la sienne.
            "addresses": [
                {"provider": "registeredAgent", "type": "business"},
                {"provider": "customer", "type": "mailing", "address": address_dto},
            ],
            "members": [
                {
                    "legalFirstName": body.first_name,
                    "legalLastName": body.last_name,
                    "isNaturalPerson": True,
                    "address": address_dto,
                    "ownershipPercent": 100,
                }
            ],
            # Formation (créer la LLC) + RegisteredAgent (adresse business
            # ci-dessus) + EinCreation (obtenir l'EIN - toute la raison
            # d'être de Buildness pour Xepay) - les 3 services nécessaires
            # au parcours complet annoncé au marchand.
            "services": [
                {"service": "Formation"},
                {"service": "RegisteredAgent"},
                {"service": "EinCreation"},
            ],
        })
    except DoolaAPIError as e:
        # 4xx doola (status_code < 500) : rejet métier probable (ex. nom
        # déjà pris, État invalide) - peu de chances qu'un simple retry
        # change le résultat, marqué "failed". 5xx/erreur réseau épuisée
        # (status_code None ou >= 500) : on ne sait pas si doola a ou non
        # traité la demande - laissé en "draft", à retenter plutôt qu'à
        # classer en échec définitif. last_successful_step n'est PAS touché
        # ici (reste "draft") - c'est précisément ce qui permet au
        # frontend de savoir où le processus s'est arrêté si le statut
        # finit "failed" plus tard, voir models.py.
        company.status = "failed" if (e.status_code and e.status_code < 500) else "draft"
        db.commit()
        logger.exception("Echec creation company doola pour company_id=%s", company.id)
        raise HTTPException(502, "Dossier enregistre, mais l'envoi a doola a echoue. Reessayez plus tard.")

    company.doola_company_id = response.get("doolaCompanyId")
    company.status = "submitted"
    company.last_successful_step = "submitted"
    db.commit()

    return {"status": company.status, "company_id": company.id}


@router.get("/buildness/status/{merchant_id}")
def get_buildness_status(
    merchant_id: str,
    membership: WorkspaceUser = Depends(require_capability("manage_company_formation")),
    db: Session = Depends(get_db),
):
    """merchant_id dans l'URL (demandé dans le cahier des charges) DOIT
    rester celui du workspace authentifié - sans ce contrôle, un membre
    pourrait lire l'avancement LLC/EIN d'un AUTRE marchand en changeant
    juste l'ID dans l'URL (IDOR). Pas de différence fonctionnelle avec un
    endpoint sans paramètre (comme GET /verto/status) : le contrôle existe
    uniquement pour honorer la forme d'URL demandée sans l'ouvrir à tous."""
    if merchant_id != membership.workspace_id:
        raise HTTPException(403, "Acces refuse.")

    customer = (
        db.query(BuildnessCustomer)
        .filter(BuildnessCustomer.xepay_merchant_id == merchant_id)
        .first()
    )
    if not customer:
        return {"status": "not_started"}

    company = (
        db.query(BuildnessCompany)
        .filter(BuildnessCompany.customer_id == customer.id)
        .order_by(BuildnessCompany.created_at.desc())
        .first()
    )
    if not company:
        return {"status": "not_started"}

    return {
        "status": company.status,
        "company_id": company.id,
        "company_name": company.company_name,
        "state": company.state,
        "last_successful_step": company.last_successful_step,
        "ein_number": company.ein_number,
        "updated_at": company.updated_at,
    }
