import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Profile, WorkspaceUser, IssuingTopup
from backend.middleware.authorization import require_capability
from backend.services import stripe_issuing_service

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()

# Garde-fous POST /issuing/topup (voir conversation du 2026-11-11) -
# valeurs indicatives, à ajuster si besoin.
ISSUING_TOPUP_MIN_USD = 1
ISSUING_TOPUP_MAX_USD = 5000
ISSUING_TOPUP_DAILY_MAX_USD = 10000
# Une ligne "pending" sans stripe_topup_id plus vieille que ce délai n'a
# jamais atteint Stripe (process arrêté entre l'écriture de la ligne et
# l'appel Stripe) - ignorée par les deux requêtes ci-dessous, jamais
# nettoyée activement (pas de tâche de fond).
ISSUING_TOPUP_PENDING_SUBMIT_GRACE = timedelta(minutes=2)


def _get_active_issuing_account(profile: Profile) -> str:
    """Compte Issuing DÉDIÉ (dashboard: none, voir stripe_issuing_service) -
    distinct de profile.stripe_account_id (Express, paiements/payouts) :
    Issuing n'est pas compatible avec un compte Express, confirmé en
    sandbox le 2026-11-05. Créé via POST /onboarding/issuing. Lève une
    HTTPException actionnable (pas l'erreur Stripe brute) si le compte
    n'est pas encore configuré ou pas encore actif."""
    if not profile or not profile.stripe_issuing_account_id or not profile.stripe_issuing_program_id:
        raise HTTPException(400, "Compte Stripe Issuing non configuré - voir /onboarding/issuing")

    try:
        platform_program = stripe_issuing_service.get_default_platform_program()
        capability = stripe_issuing_service.get_issuing_capability_status(
            profile.stripe_issuing_account_id, platform_program["capability"]
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Erreur Stripe Issuing (vérification du compte) : {e}")

    if capability.get("status") != "active":
        # Erreur Stripe brute ici ("missing requirements to be activated")
        # n'est pas actionnable pour le marchand - on renvoie plutôt ce
        # qu'il reste à fournir (rempli via le même lien d'onboarding que
        # /onboarding/issuing).
        missing = capability.get("requirements", {}).get("currently_due") or capability.get(
            "requirements", {}
        ).get("past_due", [])
        raise HTTPException(
            400,
            "Le compte Stripe Issuing n'est pas encore actif "
            f"(statut: {capability.get('status')}) - complétez l'onboarding "
            f"via /onboarding/issuing. Informations manquantes : {missing}",
        )

    return profile.stripe_issuing_account_id


@router.get("/issuing/cards")
def list_virtual_cards(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Cartes + cardholders du compte Issuing du marchand, et le solde
    Issuing disponible (sert de fonds aux cartes) - voir vue Commerce
    "Émission de carte" (section 1)."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    account_id = _get_active_issuing_account(profile)

    try:
        cards = stripe.issuing.Card.list(
            limit=50, expand=["data.cardholder"], stripe_account=account_id
        )
        balance = stripe.Balance.retrieve(stripe_account=account_id)
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)}")

    issuing_balance = next(
        (b.amount for b in balance.issuing.available if b.currency == "usd"), 0
    ) if getattr(balance, "issuing", None) else 0

    return {
        "balance_available": issuing_balance,
        # Nécessaire côté frontend pour initialiser Stripe.js en contexte
        # Connect avant de pouvoir afficher le numéro/CVC via Issuing
        # Elements (voir /issuing/cards/{card_id}/ephemeral-key).
        "stripe_issuing_account_id": account_id,
        "cards": [
            {
                "id": card.id,
                "brand": card.brand,
                "last4": card.last4,
                "exp_month": card.exp_month,
                "exp_year": card.exp_year,
                "currency": card.currency,
                "status": card.status,
                "type": card.type,
                "cardholder_name": card.cardholder.name if card.cardholder else None,
                "cardholder_email": card.cardholder.email if card.cardholder else None,
                # Extraction explicite, champ par champ - passer les objets
                # Stripe bruts (StripeObject) tels quels fait fuiter leur
                # état interne lors de la sérialisation JSON, y compris la
                # clé API utilisée pour la requête (_requestor._options.
                # api_key) : confirmé le 2026-11-06 avec jsonable_encoder.
                "spending_limits": [
                    {"amount": sl.amount, "interval": sl.interval}
                    for sl in ((card.spending_controls.spending_limits if card.spending_controls else None) or [])
                ],
            }
            for card in cards.data
        ],
    }


@router.post("/issuing/cards/{card_id}/ephemeral-key")
def create_card_ephemeral_key(
    card_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Clé éphémère (15 min) pour afficher le numéro complet, la date
    d'expiration et le CVC d'une carte via Stripe Issuing Elements - ces
    données restent dans un iframe hébergé par Stripe, elles ne transitent
    JAMAIS par nos serveurs ni ne sont journalisées (voir
    stripe.com/docs/issuing/elements - seule méthode conforme PCI-DSS en
    mode test pour des cartes virtuelles, l'API brute number/cvc n'y
    fonctionne pas). Sur un compte Connect, nécessite que Stripe ait
    explicitement activé Issuing Elements pour notre plateforme (demande
    au support Stripe) - sans ça, EphemeralKey.create échoue avec une
    erreur d'autorisation, pas un bug de ce code."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    issuing_account_id = _get_active_issuing_account(profile)

    nonce = payload.get("nonce")
    if not nonce:
        raise HTTPException(400, "nonce manquant")

    try:
        # Vérifie que cette carte appartient bien au compte Issuing DE CE
        # marchand avant d'émettre quoi que ce soit - empêche un marchand
        # de récupérer les détails d'une carte d'un autre marchand en
        # devinant son id (Stripe.Card.retrieve échoue sinon : la carte
        # n'existe pas sur CE compte connecté).
        stripe.issuing.Card.retrieve(card_id, stripe_account=issuing_account_id)

        ephemeral_key = stripe.EphemeralKey.create(
            nonce=nonce,
            issuing_card=card_id,
            stripe_version=stripe.api_version,
            stripe_account=issuing_account_id,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)} (request_id: {e.request_id})")

    return {"ephemeral_key_secret": ephemeral_key.secret}


@router.get("/issuing/transactions")
def list_issuing_transactions(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Transactions Issuing (dépenses sur les cartes) du compte du
    marchand - alimente le tableau et le graphe de dépenses de la vue
    Commerce "Émission de carte" (sections 2 et 3)."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    account_id = _get_active_issuing_account(profile)

    try:
        transactions = stripe.issuing.Transaction.list(
            limit=100, expand=["data.card"], stripe_account=account_id
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)}")

    return {
        "transactions": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "currency": tx.currency,
                "type": tx.type,
                "created": tx.created,
                "merchant_name": tx.merchant_data.name if tx.merchant_data else None,
                "merchant_category": tx.merchant_data.category if tx.merchant_data else None,
                "card_last4": tx.card.last4 if tx.card else None,
            }
            for tx in transactions.data
        ],
    }


def _address_dict(address: dict | None) -> dict | None:
    """address est déjà un dict primitif ici (issu d'un .to_dict() plus
    haut) - jamais un StripeObject brut. Un champ non collecté par Stripe
    est carrément ABSENT du dict (pas juste null) : .get() est donc
    obligatoire, un accès direct lèverait un KeyError."""
    if not address:
        return None
    return {
        "line1": address.get("line1"),
        "line2": address.get("line2"),
        "city": address.get("city"),
        "state": address.get("state"),
        "postal_code": address.get("postal_code"),
        "country": address.get("country"),
    }


@router.get("/issuing/cardholder-defaults")
def get_cardholder_defaults(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Pré-remplissage du modal "Émettre une carte" à partir des données
    déjà collectées par Stripe pendant l'onboarding Issuing (KYC) - évite
    de redemander au marchand des informations qu'il a déjà fournies.

    Utilise EXCLUSIVEMENT le compte Issuing actif DE CE marchand, résolu
    côté backend (_get_active_issuing_account) - le frontend ne fournit et
    n'accepte jamais de stripe_account, et n'appelle jamais Stripe
    directement : tout passe par cet endpoint.

    Ne renvoie que ce qui est utile à un Cardholder (nom/email/téléphone/
    adresse) - jamais dob, id_number, tax_id ou autre donnée sensible non
    nécessaire ici, même si Stripe les renvoie dans les objets sous-jacents.

    Important (découvert en implémentant) : un champ Stripe non collecté
    est ABSENT de l'objet, pas juste null - un accès direct en attribut
    (person.phone) lève une AttributeError dans ce cas précis avec le SDK
    stripe installé ici (StripeObject n'est pas un dict, voir le bug
    api_key corrigé plus haut dans ce fichier). On convertit donc TOUT en
    dict primitif via .to_dict() avant la moindre lecture de champ, jamais
    d'accès direct en attribut sur un StripeObject optionnel."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    issuing_account_id = _get_active_issuing_account(profile)

    try:
        account = stripe.Account.retrieve(issuing_account_id).to_dict()
        persons = [p.to_dict() for p in stripe.Account.list_persons(issuing_account_id, limit=10).data]
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)} (request_id: {e.request_id})")

    representative = next(
        (p for p in persons if (p.get("relationship") or {}).get("representative")),
        None,
    )
    company = account.get("company") or {}

    rep_email = representative.get("email") if representative else None
    # Le téléphone du représentant n'est pas toujours collecté par
    # l'onboarding Stripe hébergé - peut être absent, le champ reste alors
    # vide et obligatoire côté formulaire (validation E.164 existante).
    rep_phone = representative.get("phone") if representative else None

    return {
        "representative": {
            "first_name": representative.get("first_name"),
            "last_name": representative.get("last_name"),
            "email": rep_email,
            "phone": rep_phone,
            "address": _address_dict(representative.get("address")),
        } if representative else None,
        "company": {
            "name": company.get("name"),
            # Repli sur l'email/téléphone du représentant si l'entreprise
            # n'a pas le sien - jamais l'inverse (le représentant est une
            # vraie personne, pas un repli acceptable pour un autre usage).
            "email": account.get("email") or rep_email,
            "phone": company.get("phone") or rep_phone,
            "address": _address_dict(company.get("address")),
        },
    }


@router.post("/issuing/bank-link")
def start_issuing_bank_link(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Relie le wallet USD Verto DÉJÀ existant du marchand
    (profile.verto_usd_account_number/verto_usd_bank_code, voir
    routes/verto.py) au compte Issuing, pour pouvoir le recharger -
    jamais un compte bancaire US saisi manuellement, jamais le compte
    UEMOA directement (Stripe ACH ne fonctionne que sur le réseau
    bancaire américain, voir conversation du 2026-11-06). Rien à cocher
    côté marchand ici : la vérification par micro-dépôts se fait toute
    seule via le webhook Verto (voir webhook/verto.py) dès qu'ils
    arrivent sur son wallet - jamais via le solde de la plateforme
    (règle "zéro custody")."""
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    issuing_account_id = _get_active_issuing_account(profile)

    if not profile.verto_usd_account_number or not profile.verto_usd_bank_code:
        raise HTTPException(
            400,
            "Wallet Verto non configuré - complétez d'abord l'onboarding "
            "Verto (voir Paramètres produit > Retraits & comptes bancaires).",
        )

    try:
        account = stripe.Account.retrieve(issuing_account_id).to_dict()
        company_name = (account.get("company") or {}).get("name") or "Xepay Merchant"

        source = stripe_issuing_service.create_issuing_bank_source(
            issuing_account_id,
            account_number=profile.verto_usd_account_number,
            routing_number=profile.verto_usd_bank_code,
            account_holder_name=company_name,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)} (request_id: {e.request_id})")

    profile.stripe_issuing_bank_source_id = source["id"]
    profile.stripe_issuing_bank_status = "pending_verification"
    profile.stripe_issuing_bank_pending_amounts = []
    profile.stripe_issuing_bank_link_started_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "pending_verification"}


@router.get("/issuing/bank-link/status")
def get_issuing_bank_link_status(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    if not profile:
        return {"status": "not_started"}
    return {"status": profile.stripe_issuing_bank_status or "not_started"}


@router.post("/issuing/topup")
def create_issuing_topup(
    payload: dict,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    """Recharge le solde Issuing depuis le wallet Verto déjà vérifié -
    jamais depuis le solde de la plateforme.

    Garde-fous (voir conversation du 2026-11-11) :
    - une seule recharge "en vol" à la fois par compte (profile verrouillé
      via with_for_update pour serialiser deux requêtes concurrentes du
      même marchand) - un débit ACH peut échouer plusieurs jours après sa
      création, on ne laisse jamais s'empiler plusieurs débits en attente
      sur la même source bancaire ;
    - clé d'idempotence par ligne IssuingTopup, STABLE (jamais régénérée
      sur retry) ;
    - l'id de la ligne est aussi posé en metadata Stripe sur le Topup :
      filet de secours si le webhook topup.succeeded/failed/canceled/
      reversed arrive avant que stripe_topup_id soit écrit en base (voir
      webhook/stripe.py) ;
    - min/max par recharge + plafond glissant 24h, montants invalides
      (bool compris - bool est une sous-classe d'int en Python) rejetés.
    """
    import logging
    logger = logging.getLogger(__name__)

    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(
        Profile.user_id == owner_id
    ).with_for_update().first()
    issuing_account_id = _get_active_issuing_account(profile)

    if profile.stripe_issuing_bank_status != "verified" or not profile.stripe_issuing_bank_source_id:
        raise HTTPException(
            400, "Compte bancaire non vérifié - voir POST /issuing/bank-link"
        )

    amount = payload.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise HTTPException(400, "Montant invalide")
    if amount < ISSUING_TOPUP_MIN_USD or amount > ISSUING_TOPUP_MAX_USD:
        raise HTTPException(
            400,
            f"Montant hors limites (entre {ISSUING_TOPUP_MIN_USD} et "
            f"{ISSUING_TOPUP_MAX_USD} USD par recharge)",
        )

    now = datetime.now(timezone.utc)

    # "En vol" = Stripe a confirmé la création (stripe_topup_id connu) ou
    # c'est trop récent pour trancher (voir ISSUING_TOPUP_PENDING_SUBMIT_
    # GRACE ci-dessus).
    existing_pending = db.query(IssuingTopup).filter(
        IssuingTopup.stripe_account_id == issuing_account_id,
        IssuingTopup.status == "pending",
        (
            (IssuingTopup.stripe_topup_id.isnot(None))
            | (IssuingTopup.created_at > now - ISSUING_TOPUP_PENDING_SUBMIT_GRACE)
        ),
    ).first()
    if existing_pending:
        raise HTTPException(
            409,
            "Une recharge est déjà en cours pour ce compte - attendez "
            "qu'elle soit confirmée ou échoue avant d'en lancer une nouvelle.",
        )

    day_total = db.query(func.coalesce(func.sum(IssuingTopup.amount), 0)).filter(
        IssuingTopup.stripe_account_id == issuing_account_id,
        IssuingTopup.status.in_(("pending", "succeeded")),
        IssuingTopup.created_at > now - timedelta(hours=24),
    ).scalar()
    if float(day_total or 0) + amount > ISSUING_TOPUP_DAILY_MAX_USD:
        raise HTTPException(
            400,
            f"Plafond de {ISSUING_TOPUP_DAILY_MAX_USD} USD/24h atteint pour ce compte",
        )

    topup_row = IssuingTopup(
        user_id=owner_id,
        stripe_account_id=issuing_account_id,
        stripe_source_id=profile.stripe_issuing_bank_source_id,
        amount=float(amount),
        status="pending",
        idempotency_key=f"xepay-issuing-topup-{uuid.uuid4()}",
    )
    db.add(topup_row)
    db.commit()

    try:
        topup = stripe_issuing_service.topup_issuing_balance(
            issuing_account_id,
            profile.stripe_issuing_bank_source_id,
            int(round(amount * 100)),
            idempotency_key=topup_row.idempotency_key,
            metadata={"issuing_topup_id": topup_row.id},
        )
    except stripe.error.StripeError as e:
        logger.error(
            "Echec creation topup Issuing (topup_row=%s, compte=%s) : %s (request_id=%s)",
            topup_row.id, issuing_account_id, e.user_message or str(e), e.request_id,
        )
        topup_row.status = "failed"
        topup_row.failure_message = str(e)
        topup_row.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            502, "La recharge a échoué, réessayez plus tard ou contactez le support."
        )

    topup_row.stripe_topup_id = topup["id"]
    topup_row.status = topup["status"]
    topup_row.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"topup_id": topup["id"], "status": topup["status"]}


@router.post("/issuing/create-virtual-card")
def create_virtual_card(
    cardholder_data: dict,
    request: Request,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_virtual_cards"))
):
    owner_id = membership.workspace_id
    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    issuing_account_id = _get_active_issuing_account(profile)

    name = cardholder_data.get("name")
    if not name or not name.strip():
        raise HTTPException(400, "Le nom du porteur ou de la LLC est obligatoire.")

    # Stripe exige un phone_number sur le cardholder pour pouvoir émettre une
    # carte (3D Secure - voir stripe.com/docs/issuing/3d-secure), quel que
    # soit le type de porteur. Format E.164 strict (+ puis 7 à 15 chiffres,
    # premier chiffre non nul) : jamais validé côté UI avant, Stripe
    # refusait silencieusement la création de carte sinon.
    phone_number = (cardholder_data.get("phone_number") or "").strip()
    if not re.match(r"^\+[1-9]\d{6,14}$", phone_number):
        raise HTTPException(
            400,
            "Le numéro de téléphone du porteur est obligatoire, au format "
            "E.164 (ex : +14155550123).",
        )

    holder_type = cardholder_data.get("type", "individual")
    card_currency = cardholder_data.get("currency", "usd").lower()

    client_ip = None
    if holder_type == "individual":
        # Conditions d'utilisation Issuing PROPRES AU PORTEUR (individual.
        # card_issuing.user_terms_acceptance - distinctes de celles du
        # compte, déjà gérées par l'onboarding Stripe hébergé). N'existe
        # que pour les porteurs individuels (une entité "company" n'a pas
        # ces conditions côté Stripe). Jamais fabriqué ici : la case doit
        # être cochée explicitement par le soumissionnaire, qui atteste que
        # le porteur a lu et accepté ces conditions - l'IP et la date
        # enregistrées plus bas sont celles, réelles, de CETTE requête,
        # jamais une valeur de test.
        if not cardholder_data.get("accepted_terms"):
            raise HTTPException(
                400,
                "Le porteur de la carte doit avoir lu et accepté les "
                "conditions d'utilisation Stripe Issuing (case à cocher).",
            )
        # request.client.host seul renvoie l'IP du proxy (Cloudflare,
        # confirmé par les logs prod : 172.69.15.150 est dans une plage
        # Cloudflare publiée), pas celle du visiteur - inacceptable pour
        # une preuve d'acceptation de conditions. CF-Connecting-IP (posé
        # par Cloudflare) prioritaire, puis X-Forwarded-For (premier
        # maillon), puis repli sur request.client.host si absent.
        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_ip = (
            request.headers.get("cf-connecting-ip")
            or (forwarded_for.split(",")[0].strip() if forwarded_for else None)
            or (request.client.host if request.client else None)
        )
        if not client_ip:
            raise HTTPException(
                502, "Impossible de déterminer l'adresse IP de la requête, nécessaire à l'acceptation des conditions."
            )
    try:
        cardholder_params = {
            "type": holder_type,
            "name": name.strip(),
            "email": cardholder_data.get("email"),
            "phone_number": phone_number,
            "billing": {
                "address": {
                    "line1": cardholder_data.get("address_line1"),
                    "line2": cardholder_data.get("address_line2"),
                    "city": cardholder_data.get("city"),
                    "state": cardholder_data.get("state"),
                    "postal_code": cardholder_data.get("postal_code"),
                    "country": cardholder_data.get("country", "US"),
                }
            },
            "stripe_account": issuing_account_id,
        }
        if holder_type == "individual":
            # Stripe exige individual.first_name/last_name en plus du nom
            # complet au niveau racine (name) - jamais renseigné avant, la
            # carte se créait mais restait "inactive" indéfiniment
            # (requirements.past_due côté cardholder). Le ToS Issuing DU
            # PORTEUR (distinct de celui du compte) se fixe au même endroit,
            # individual.card_issuing.user_terms_acceptance - un objet plat
            # {ip, date}, PAS un dict par banque (cette dernière forme
            # n'existe que sous le header bêta issuing_program_beta=v2,
            # jamais utilisé par cet appel SDK nu - vérifié empiriquement
            # le 2026-11-06, voir conversation).
            first_name, _, last_name = name.strip().partition(" ")
            cardholder_params["individual"] = {
                "first_name": first_name,
                "last_name": last_name or first_name,
                "card_issuing": {
                    "user_terms_acceptance": {"ip": client_ip, "date": int(time.time())}
                },
            }

        cardholder = stripe.issuing.Cardholder.create(**cardholder_params)

        card = stripe.issuing.Card.create(
            cardholder=cardholder.id,
            currency=card_currency,
            type="virtual",
            spending_controls={
                "spending_limits": [{
                    "amount": int(cardholder_data.get("limit_amount", 50000)),
                    "interval": "per_authorization"
                }]
            },
            stripe_account=issuing_account_id,
        )
        return {
            "success": True,
            "cardholder_id": cardholder.id,
            "card_id": card.id,
            "currency": card.currency,
            "status": card.status
        }
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe Issuing : {e.user_message or str(e)} (request_id: {e.request_id})")
