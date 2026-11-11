"""Treasury for platforms (Financial Account) - prototype de test (voir
conversation du 2026-11-11). Toutes les routes exigent
stripe_treasury_service.is_treasury_available() (interrupteur
TREASURY_ENABLED + clé sk_test_) : tant que ce n'est pas le cas, 503
"Fonctionnalité en cours de déploiement" - le frontend masque alors la
section entière (même contrat que VERTO_ENABLED sur backend/routes/verto.py).

Compte cible : toujours profile.stripe_issuing_account_id (le compte
Connect DÉDIÉ Issuing, jamais l'Express stripe_account_id) - résolu
depuis la session, jamais depuis le corps de la requête. La capacité
treasury se demande sur ce même compte (voir backend/models.py,
Profile.stripe_financial_account_id).

Capacités (3 niveaux, mêmes que pour Issuing dans routes/issuing.py/
routes/users.py) :
- manage_stripe_account_config (owner) : demander la capacité, créer le
  compte financier, activer une fonction - structurel, irréversible.
- view_stripe_account_info (manager) : lire statut/solde/coordonnées.
- manage_virtual_cards (manager) : ajouter des fonds de test - action
  quotidienne de test, pas une config de compte.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile, WorkspaceUser, TreasuryReceivedCredit
from backend.middleware.authorization import require_capability
from backend.services import stripe_treasury_service

router = APIRouter()

TEST_FUNDING_MIN_USD = 1
TEST_FUNDING_MAX_USD = 5000


def _require_available() -> None:
    if not stripe_treasury_service.is_treasury_available():
        raise HTTPException(503, "Fonctionnalité en cours de déploiement.")


def _get_issuing_account_id(profile: Profile) -> str:
    if not profile or not profile.stripe_issuing_account_id:
        raise HTTPException(400, "Compte Stripe Issuing non configuré - voir /onboarding/issuing")
    return profile.stripe_issuing_account_id


def _handle_stripe_error(logger: logging.Logger, action: str, account_id: str, e: "stripe.error.StripeError"):
    logger.error(
        "Echec Treasury (%s, compte=%s) : %s (code=%s request_id=%s)",
        action, account_id, e.user_message or str(e), getattr(e, "code", None), e.request_id,
    )
    raise HTTPException(503, "Compte financier non disponible pour le moment.")


@router.get("/treasury/financial-account")
def get_financial_account_status(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("view_stripe_account_info")),
):
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    try:
        capability = stripe_treasury_service.get_treasury_capability_status(account_id)
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "lecture capacite", account_id, e)

    financial_account = None
    if profile.stripe_financial_account_id:
        try:
            financial_account = stripe_treasury_service.get_financial_account(
                account_id, profile.stripe_financial_account_id
            )
        except stripe.error.StripeError as e:
            _handle_stripe_error(logger, "lecture compte financier", account_id, e)

    return {
        "capability_status": capability.get("status"),
        "capability_requirements": capability.get("requirements"),
        "financial_account": financial_account,
    }


@router.post("/treasury/financial-account/activate")
def activate_financial_account(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
):
    """Un seul bouton côté UI ("Activer le compte financier") :
    - demande la capacité treasury si elle n'est pas déjà active/pending ;
    - crée le compte financier (financial_addresses.aba + card_issuing
      demandés dans le même appel, voir create_financial_account) s'il
      n'existe pas encore pour ce marchand ;
    - relit et renvoie l'état de conformité restant (capability.
      requirements) - jamais rempli ici, c'est au marchand de le faire
      via POST /treasury/financial-account/account-session."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    try:
        capability = stripe_treasury_service.get_treasury_capability_status(account_id)
        if capability.get("status") not in ("active", "pending"):
            capability = stripe_treasury_service.request_treasury_capability(account_id)

        if not profile.stripe_financial_account_id:
            financial_account = stripe_treasury_service.create_financial_account(account_id)
            # Persisté seulement APRES le succès Stripe - jamais avant.
            profile.stripe_financial_account_id = financial_account["id"]
            db.commit()
        else:
            financial_account = stripe_treasury_service.get_financial_account(
                account_id, profile.stripe_financial_account_id
            )
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "activation compte financier", account_id, e)

    return {
        "capability_status": capability.get("status"),
        "capability_requirements": capability.get("requirements"),
        "financial_account": financial_account,
    }


@router.post("/treasury/financial-account/account-session")
def create_treasury_account_session(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
):
    """client_secret pour le composant Connect embarqué "account-
    onboarding" (ConnectJS) - confirmé dans la doc Stripe comme la
    méthode qui gère nativement l'étape "treasury_and_card_issuing_
    terms_of_service" (voir stripe_treasury_service.
    create_account_onboarding_session). Le marchand accepte ces
    conditions lui-même, dans ce composant Stripe - jamais un formulaire
    Xepay, jamais de date/IP fabriquées ici."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    try:
        client_secret = stripe_treasury_service.create_account_onboarding_session(account_id)
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "account-session onboarding", account_id, e)

    return {"client_secret": client_secret}


@router.post("/treasury/financial-account/activate-features")
def activate_financial_account_features(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config")),
):
    """Redemande financial_addresses.aba ET card_issuing - utile en
    retry manuel pour un compte financier créé AVANT l'ajustement qui
    les demande déjà à la création (voir create_financial_account).
    Jamais de passthrough générique : seules ces deux fonctions, utiles
    à ce prototype (voir conversation)."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    if not profile.stripe_financial_account_id:
        raise HTTPException(400, "Compte financier non créé - voir POST /treasury/financial-account/activate")

    try:
        features = stripe_treasury_service.update_financial_account_features(
            account_id,
            profile.stripe_financial_account_id,
            {
                "financial_addresses": {"aba": {"requested": True}},
                "card_issuing": {"requested": True},
            },
        )
        financial_account = stripe_treasury_service.get_financial_account(
            account_id, profile.stripe_financial_account_id
        )
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "activation des fonctions", account_id, e)

    return {
        "features": features,
        "active_features": financial_account.get("active_features"),
        "pending_features": financial_account.get("pending_features"),
        "restricted_features": financial_account.get("restricted_features"),
    }


@router.post("/treasury/financial-account/test-funding")
def create_test_funding(
    payload: dict,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards")),
):
    """Ajoute des fonds de test au compte financier (test_helpers, voir
    stripe_treasury_service.simulate_received_credit) - garde-fous
    identiques à create_issuing_topup (routes/issuing.py) : idempotence,
    une seule opération en vol, trace en base, montants en centimes."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).with_for_update().first()
    account_id = _get_issuing_account_id(profile)

    if not profile.stripe_financial_account_id:
        raise HTTPException(400, "Compte financier non créé - voir POST /treasury/financial-account/activate")

    # Vérifié AVANT tout appel au test helper (plutôt que de laisser
    # Stripe lever "has not requested access to financial_addresses.aba",
    # constaté lors des tests du 2026-11-11) : un financement test exige
    # cette fonction active sur ce compte financier précis.
    try:
        financial_account = stripe_treasury_service.get_financial_account(
            account_id, profile.stripe_financial_account_id
        )
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "lecture compte financier (test-funding)", account_id, e)

    if "financial_addresses.aba" not in (financial_account.get("active_features") or []):
        raise HTTPException(
            400,
            "Coordonnées bancaires pas encore actives sur ce compte financier - conformité à terminer.",
        )

    amount = payload.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise HTTPException(400, "Montant invalide")
    if amount < TEST_FUNDING_MIN_USD or amount > TEST_FUNDING_MAX_USD:
        raise HTTPException(
            400,
            f"Montant hors limites (entre {TEST_FUNDING_MIN_USD} et {TEST_FUNDING_MAX_USD} USD)",
        )

    existing_pending = db.query(TreasuryReceivedCredit).filter(
        TreasuryReceivedCredit.financial_account_id == profile.stripe_financial_account_id,
        TreasuryReceivedCredit.status == "pending",
    ).first()
    if existing_pending:
        raise HTTPException(
            409,
            "Un financement de test est déjà en cours pour ce compte financier.",
        )

    credit_row = TreasuryReceivedCredit(
        user_id=membership.workspace_id,
        stripe_account_id=account_id,
        financial_account_id=profile.stripe_financial_account_id,
        amount=int(round(amount * 100)),
        currency="usd",
        network="ach",
        status="pending",
        idempotency_key=f"xepay-treasury-credit-{uuid.uuid4()}",
    )
    db.add(credit_row)
    db.commit()

    try:
        received_credit = stripe_treasury_service.simulate_received_credit(
            account_id,
            profile.stripe_financial_account_id,
            credit_row.amount,
            idempotency_key=credit_row.idempotency_key,
        )
    except stripe.error.StripeError as e:
        logger.error(
            "Echec financement de test Treasury (ligne=%s, compte=%s) : %s (request_id=%s)",
            credit_row.id, account_id, e.user_message or str(e), e.request_id,
        )
        credit_row.status = "failed"
        credit_row.failure_code = getattr(e, "code", None) or str(e)
        db.commit()
        raise HTTPException(503, "Le financement de test a échoué, réessayez plus tard.")

    credit_row.stripe_received_credit_id = received_credit["id"]
    credit_row.status = received_credit.get("status", "pending")
    db.commit()

    return {"received_credit_id": received_credit["id"], "status": received_credit.get("status")}


@router.get("/treasury/financial-account/cardholders")
def list_financial_account_cardholders(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards")),
):
    """Cardholders déjà existants sur le compte Issuing - pour choisir à
    qui attacher une carte financée par le compte financier (voir
    create_financial_account_card). Jamais de création de cardholder ici,
    voir stripe_treasury_service.list_cardholders."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    try:
        cardholders = stripe_treasury_service.list_cardholders(account_id)
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "liste des cardholders", account_id, e)

    return {"cardholders": cardholders}


@router.post("/treasury/financial-account/cards")
def create_financial_account_card(
    payload: dict,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards")),
):
    """Carte financée par le compte financier (financial_account=) -
    coexiste avec les cartes classiques (solde Issuing, /issuing/
    create-virtual-card, jamais modifiée). Réutilise un cardholder déjà
    existant (payload.cardholder_id) - ne crée jamais de cardholder ici,
    pour ne jamais dupliquer la logique de conformité/ToS déjà en place
    dans create_virtual_card (routes/issuing.py)."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    if not profile.stripe_financial_account_id:
        raise HTTPException(400, "Compte financier non créé - voir POST /treasury/financial-account/activate")

    cardholder_id = payload.get("cardholder_id")
    if not cardholder_id or not isinstance(cardholder_id, str):
        raise HTTPException(400, "cardholder_id manquant")

    limit_amount = payload.get("limit_amount")
    if isinstance(limit_amount, bool) or not isinstance(limit_amount, (int, float)) or limit_amount <= 0:
        raise HTTPException(400, "Plafond invalide")

    # Vérifié AVANT tout appel de création (même logique que test-funding
    # pour financial_addresses.aba) : card_issuing doit être actif sur CE
    # compte financier, sinon Stripe refuserait la carte avec une erreur
    # moins lisible.
    try:
        financial_account = stripe_treasury_service.get_financial_account(
            account_id, profile.stripe_financial_account_id
        )
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "lecture compte financier (creation carte)", account_id, e)

    if "card_issuing" not in (financial_account.get("active_features") or []):
        raise HTTPException(
            400,
            "L'émission de carte n'est pas encore active sur ce compte financier - conformité à terminer.",
        )

    try:
        # Vérifie que ce cardholder appartient bien à CE marchand avant
        # toute création - même garde que create_card_ephemeral_key
        # (routes/issuing.py) : empêche de cibler le cardholder d'un
        # autre marchand en devinant son id.
        stripe.issuing.Cardholder.retrieve(cardholder_id, stripe_account=account_id)

        card = stripe_treasury_service.create_card_funded_by_financial_account(
            account_id,
            profile.stripe_financial_account_id,
            cardholder_id,
            "usd",
            int(round(limit_amount * 100)),
        )
    except stripe.error.StripeError as e:
        logger.error(
            "Echec creation carte financee par le compte financier (compte=%s) : %s (request_id=%s)",
            account_id, e.user_message or str(e), e.request_id,
        )
        raise HTTPException(502, "Impossible de créer la carte, réessayez plus tard.")

    return {"card_id": card["id"], "status": card.get("status")}


@router.get("/treasury/financial-account/transactions")
def list_financial_account_transactions(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("view_stripe_account_info")),
):
    """Historique du compte financier (financements, OutboundTransfer,
    OutboundPayment...) - voir vue Commerce "Comptes financiers"."""
    _require_available()
    logger = logging.getLogger(__name__)

    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    account_id = _get_issuing_account_id(profile)

    if not profile.stripe_financial_account_id:
        return {"transactions": []}

    try:
        transactions = stripe_treasury_service.list_transactions(
            account_id, profile.stripe_financial_account_id
        )
    except stripe.error.StripeError as e:
        _handle_stripe_error(logger, "liste des transactions", account_id, e)

    return {
        "transactions": [
            {
                "id": t["id"],
                "amount": t["amount"],
                "currency": t["currency"],
                "status": t["status"],
                "flow_type": t.get("flow_type"),
                "created": t["created"],
                "description": t.get("description"),
            }
            for t in transactions
        ]
    }
