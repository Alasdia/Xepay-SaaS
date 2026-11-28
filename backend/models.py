from pydantic import BaseModel, EmailStr, Field
from backend.database import Base
from sqlalchemy import Column, String, Boolean
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from typing import Literal, Optional
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship  
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Numeric
import secrets
import string
import uuid
from sqlalchemy import Index
from sqlalchemy import UniqueConstraint

def generate_prefixed_id(prefix: str, length: int = 24) -> str:
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}_{random_part}"

class User(BaseModel):
    email: EmailStr
    password: str
    invite_token: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

class TwoFAVerifyRequest(BaseModel):
    code: str

class ProfileRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    country: str
    account_type: str
    wallet_operator: str
    wallet_number: str
    doc_type: str

class ProfileUpdateRequest(BaseModel):
    # Les deux optionnels : seul le champ envoyé (non None) est modifié -
    # voir PATCH /profile (boutons "Ajouter votre nom"/"... téléphone").
    full_name: Optional[str] = None
    phone: Optional[str] = None

class GoogleLinkRequest(BaseModel):
    code: str
    redirect_uri: str

class NotificationPreferencesRequest(BaseModel):
    # {"<categorie>.<evenement>": true/false} - voir UserDB.notification_prefs.
    # Fusionné (pas remplacé) avec les préférences existantes, pour qu'une
    # sauvegarde partielle (un seul switch changé) n'efface pas les autres.
    prefs: dict[str, bool]

class PasskeyRegisterFinishRequest(BaseModel):
    credential: dict
    name: Optional[str] = None

class PasskeyRenameRequest(BaseModel):
    name: str

class LoginTwoFAVerify(BaseModel):
    email: str
    code: str
    pre_auth_token: str

class PaymentCreate(BaseModel):
    email: str
    amount: float
    status: str

class SecurityAlertsRequest(BaseModel):
    alert_login: bool
    alert_payment: bool
    alert_suspect: bool

class LinkCreate(BaseModel):
    name: Optional[str] = None
    # amount: None = montant flexible (voir min_amount/max_amount) ; sinon
    # montant fixe, identique à chaque paiement sur ce lien.
    amount: Optional[float] = None
    currency: str = "USD"
    source: str = "dashboard"
    # max_uses : None = illimité, 1 = usage unique, N = quota de paiements
    # réussis avant que le lien ne devienne inutilisable.
    max_uses: Optional[int] = None
    # Bornes optionnelles pour un montant flexible - ignorées (doivent être
    # absentes) si amount est fourni, voir la validation dans create_link.
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    # Durée de validité explicite, en minutes. Si absent, create_link
    # applique une valeur par défaut qui dépend de max_uses (courte pour un
    # usage unique, aucune expiration pour un lien multi-usage).
    expires_in_minutes: Optional[int] = None

class FlexibleLinkCheckout(BaseModel):
    """Montant choisi par le client sur pay-flexible.html pour un lien à
    montant flexible (Link.amount IS NULL) - revérifié contre
    min_amount/max_amount côté serveur avant de créer la session Stripe,
    jamais fait confiance tel quel (voir POST /pay/{token}/checkout)."""
    amount: float

class LinkResponse(BaseModel):
    id: str
    token: str
    amount: Optional[float] = None
    currency: str
    name: Optional[str]
    url: str
    active: bool
    max_uses: Optional[int] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

class LinkDashboardResponse(BaseModel):
    id: str
    name: str
    # None pour un lien à montant flexible sans paiement encore reçu.
    amount: Optional[float] = None
    currency: str
    status: str
    active: bool
    archived: bool
    url: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    metadata: Optional[dict] = None
    # Commission Xepay RÉELLEMENT appliquée au paiement de ce lien (None
    # pour un lien pas encore payé) - voir GET /links dans routes/lien.py,
    # qui la lit sur Payment.application_fee_requested. Utilisée par le
    # tableau de bord (dashboard.js) pour calculer un "Volume net" exact,
    # jamais un taux fixe par source : la commission est dégressive par
    # volume mensuel (backend/services/commission_service.py).
    fee_amount: Optional[float] = None
    max_uses: Optional[int] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    # Nombre de paiements réussis déjà reçus sur ce lien - toujours >= 0,
    # utile pour un lien multi-usage ("12 payés" / "12/50 payés") pour
    # lequel `status` reste "pending" tant que max_uses n'est pas atteint.
    successful_payments_count: int = 0

    class Config:
        from_attributes = True

class PaymentUpdate(BaseModel):
    email: str
    amount: float
    status: str

class PaymentResponse(BaseModel):
    email: str
    amount: float
    status: str
    created_at: Optional[datetime] = None

class PayRequest(BaseModel):
    email: str

class PlanUpdate(BaseModel):
    plan: str

class GoogleCodeExchange(BaseModel):
    code: str
    redirect_uri: str
    invite_token: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class WithdrawRequest(BaseModel):
    amount: float

class VertoSubAccountRequest(BaseModel):
    # Étape A (découpage du 2026-11-07) : UNIQUEMENT les champs requis par
    # Verto POST /sub-accounts, voir verto_service.create_sub_account - la
    # persistance de verto_company_id est immédiate après cet appel (voir
    # routes/verto.py), avant même la soumission KYB, pour ne jamais créer
    # de sous-compte orphelin si l'étape B échoue.
    country: str
    company_name: str
    sub_category: str
    identification_number: str
    tax_id_or_ein: str | None = None


class VertoKybDataRequest(BaseModel):
    # Étape B (découpage du 2026-11-07) : données KYC complémentaires
    # (UBO 25%+, adresse - documents NON CONFIRMÉS, voir le plan dédié) -
    # voir verto_service.submit_onboarding_data, forme exacte non figée
    # ici (transmise telle quelle à l'API Verto). Peut être rappelée
    # plusieurs fois tant que le sous-compte n'est pas approuvé/rejeté
    # (reprise d'un KYB incomplet) - NON CONFIRMÉ si Verto traite un second
    # appel comme une mise à jour ou un doublon, jamais testé (bloqué par
    # le 403 sandbox).
    kyc_payload: dict

class VertoBeneficiaryRequest(BaseModel):
    # Compte bancaire local UEMOA du marchand (destination finale des
    # retraits) - voir verto_service.create_beneficiary. Format vérifié
    # côté serveur (28 car./pays UEMOA pour l'IBAN, 8 ou 11 pour le BIC,
    # cohérence pays IBAN/BIC) par verto_service.validate_iban_bic,
    # jamais ici (pas de validator Pydantic dans ce fichier).
    iban: str
    bic: str
    bank_name: str
    bank_country_code: str
    beneficiary_address_line1: str
    beneficiary_country_code: str
    beneficiary_city: str
    beneficiary_postal_code: str
    beneficiary_state_or_province: str

class BuildnessOnboardRequest(BaseModel):
    # Fondateur + LLC en un seul formulaire côté UI Xepay - voir
    # routes/buildness.py, qui scinde l'appel en create_customer (une seule
    # fois par marchand) puis create_company (voir services/
    # doola_service.py/doola_mock_service.py). state : code d'État US à 2
    # lettres (ex. "DE", État de FORMATION de la LLC) - pas de validation
    # de forme ici, doola rejette lui-même un code invalide.
    #
    # Champs ajoutés le 2026-11-23 (vérification contre la vraie API doola,
    # create_customer/create_company exigent bien plus que les 5 champs
    # d'origine) :
    # - country : pays de RÉSIDENCE du fondateur (countryOfResidence côté
    #   doola), ISO 3166-1 alpha-3 (ex. "FRA") - jamais le même "state" que
    #   ci-dessus (celui-là est l'État US de formation de la LLC).
    # - phone : E.164, utilisé à la fois comme phoneNumber du customer et
    #   comme téléphone de l'adresse ci-dessous (requis par doola pour une
    #   adresse de personne physique).
    # - address_* : UNE seule adresse collectée, réutilisée à 3 endroits
    #   côté doola (responsibleParty.address, members[0].address, et
    #   l'adresse "business" du couple addresses[] - PAS "mailing",
    #   corrigé le 2026-11-25 pour matcher l'exemple canonique de la doc
    #   doola, qui associe "mailing" à provider=registeredAgent) -
    #   doola exige ces 3 adresses séparément dans son schéma, mais rien
    #   n'empêche qu'elles soient identiques, et demander 3 fois la même
    #   adresse au marchand n'aurait aucune valeur ajoutée.
    # - industry : valeur "industry" d'un code NAICS doola (voir
    #   GET /buildness/naics-codes), à transmettre verbatim - jamais du
    #   texte libre, doola la rejette sinon.
    # - description : description courte de l'activité, 50 caractères max
    #   (limite imposée par doola).
    email: EmailStr
    first_name: str
    last_name: str
    company_name: str
    state: str
    country: str
    phone: str
    address_line1: str
    address_line2: str | None = None
    address_city: str
    address_region: str
    address_postal_code: str
    industry: str
    description: str

class BuildnessSignatureSessionRequest(BaseModel):
    # SS4/FORM8821 : les deux seules valeurs acceptées par doola (confirmé
    # dans sa doc le 2026-11-24) - Literal plutôt que str libre, pour que
    # FastAPI rejette lui-même toute autre valeur en 422 plutôt que de
    # laisser doola répondre 400 plus loin. SS4 est le cas réel courant
    # (fondateur non-résident sans SSN) ; FORM8821 n'apparaît que sur un
    # EIN en traitement accéléré.
    document_type: Literal["SS4", "FORM8821"] = "SS4"

class BuildnessCorrectionRequestCreate(BaseModel):
    # field_label en texte libre plutôt qu'un enum fermé (ajouté le
    # 2026-11-27) : doola traite ces demandes manuellement (voir
    # BuildnessCorrectionRequest ci-dessus) - un humain lit field_label/
    # requested_value/note, un Literal figé n'apporterait aucune garantie
    # supplémentaire côté API et empêcherait de couvrir un champ non
    # prévu à l'avance. L'UI (spa/views/monEntreprise.js) propose
    # toutefois une liste de champs courants + "Autre".
    field_label: str
    requested_value: str
    note: str | None = None

class ShopifyStoreRequestCreate(BaseModel):
    # "note" libre et optionnel (ajouté le 2026-11-27) : seul point
    # d'entrée pour un marchand qui demande une boutique Shopify
    # "prête à l'emploi" (Buildshop) - cette route n'assigne RIEN
    # automatiquement, voir ShopifyStoreRequest ci-dessous et
    # routes/shopify.py::create_shopify_store_request.
    note: str | None = Field(default=None, max_length=1000)

class AlhuChatMessage(BaseModel):
    # Historique envoyé tel quel par le client à chaque appel (ajouté le
    # 2026-11-27, voir services/alhu_service.py) - rien n'est persisté
    # côté serveur pour ce premier chantier, le contenu reste donc un
    # simple str (jamais la forme riche par blocs qu'Anthropic utilise
    # pour les tool_use/tool_result internes, reconstruite uniquement en
    # mémoire pendant le traitement d'une requête).
    role: Literal["user", "assistant"]
    content: str

class AlhuChatRequest(BaseModel):
    messages: list[AlhuChatMessage]

class ShopifyCustomerUpsertRequest(BaseModel):
    # Mêmes champs pour créer (POST /shopify/customers) et modifier
    # (PATCH /shopify/customers/{id}) - voir services/shopify_service.py
    # (create_customer/update_customer). Shopify exige au moins un
    # moyen de contact (email/phone/nom) pour CRÉER un client - vérifié
    # côté route, pas ici (PATCH peut légitimement ne changer qu'un
    # sous-ensemble des champs).
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

class ShopifyProductUpsertRequest(BaseModel):
    # "price" optionnel : productCreate (Admin API, confirmé le
    # 2026-11-24) ne crée qu'UNE variante et n'accepte pas son prix
    # directement - voir create_product, qui enchaîne un second appel
    # (productVariantsBulkUpdate) uniquement si price est fourni. Le
    # STOCK (inventaire) reste hors périmètre de cette itération -
    # nécessiterait un emplacement (location) + un appel distinct
    # (inventoryAdjustQuantities), jamais implémenté ici.
    title: str
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    status: Literal["ACTIVE", "DRAFT", "ARCHIVED"] = "ACTIVE"

class ShopifyOrderCancelRequest(BaseModel):
    # Enum EXACT confirmé contre la doc officielle Shopify le 2026-11-24
    # (OrderCancelReason) - Literal pour un 422 FastAPI plutôt qu'un
    # rejet Shopify plus loin. restock/reason sont OBLIGATOIRES côté
    # Shopify (orderCancel), jamais de valeur par défaut implicite ici.
    reason: Literal["CUSTOMER", "PAYMENT_DECLINED", "FRAUD", "INVENTORY", "STAFF_ERROR", "OTHER"]
    restock: bool
    notify_customer: bool = False
    staff_note: str | None = Field(default=None, max_length=255)

class BuildshopProvisionRequest(BaseModel):
    # shop_domain : la boutique pré-transfert déjà installée à la main
    # par l'équipe interne (voir services/buildshop_service.py) - jamais
    # déduite d'une session, cette route n'est pas rattachée à un
    # marchand. "catalog" optionnel réutilise ShopifyProductUpsertRequest
    # (mêmes champs/validation que la création produit "normale") pour
    # permettre un catalogue différent de BASE_CATALOG sans dupliquer de
    # modèle - None = BASE_CATALOG par défaut (voir buildshop_service.py).
    shop_domain: str
    catalog: list[ShopifyProductUpsertRequest] | None = None

class ConnectCustomerCreateRequest(BaseModel):
    # Aucun champ n'est obligatoire chez Stripe pour créer un Customer -
    # on garde cette même souplesse ici plutôt que d'imposer une
    # contrainte Xepay que l'API elle-même n'impose pas.
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None

class ConnectProductCreateRequest(BaseModel):
    name: str
    description: str | None = None
    unit_amount: int = Field(..., gt=0)
    currency: str = "xof"
    recurring: bool = False
    interval: str | None = None
    # Nombre de periodes entre deux facturations (ex: interval="month" +
    # interval_count=2 -> "tous les 2 mois"). Stripe plafonne ce total selon
    # l'intervalle (365 jours/52 semaines/12 mois/1 an) et renvoie une
    # erreur sinon - verifie par Stripe, pas ici.
    interval_count: int = Field(default=1, ge=1)

class ConnectInvoiceCreateRequest(BaseModel):
    customer_id: str
    price_id: str
    quantity: int = Field(default=1, ge=1)
    collection_method: str = "send_invoice"
    days_until_due: int | None = Field(default=7, ge=0)

class ConnectSubscriptionCreateRequest(BaseModel):
    customer_id: str
    price_id: str
    quantity: int = Field(default=1, ge=1)
    collection_method: str = "charge_automatically"
    payment_method_id: str | None = None

class ConnectSubscriptionQuantityUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1)

class ConnectInvoiceUpdateRequest(BaseModel):
    # Seul champ modifiable expose : l'echeance (due_date), recalculee a
    # partir d'aujourd'hui + days_until_due - Stripe n'autorise due_date
    # que pour collection_method="send_invoice", et uniquement sur une
    # facture encore en brouillon ou ouverte (jamais payee/annulee).
    days_until_due: int = Field(..., ge=0)

class RefundRequest(BaseModel):
    amount: Optional[int] = Field(default=None, gt=0)
    reason: Optional[str] = None

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wa"))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0)
    pending = Column(Float, default=0)         
    available = Column(Float, default=0)
    residual_xof = Column(Numeric(18, 6), default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("UserDB", back_populates="wallet")

class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wd"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    wallet_id = Column(String, ForeignKey("wallets.id"), nullable=False)
    amount = Column(Float, nullable=False)
    operator = Column(String)  
    phone = Column(String)
    reference = Column(String, unique=True, index=True)
    stripe_payout_id =Column(String, unique=True, index=True, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
    payout_method = Column(String, nullable=True)
    payout_arrival_date = Column(DateTime(timezone=True), nullable=True)
    payout_failure_message = Column(String, nullable=True)
    # Deuxième jambe du retrait (wallet USD Verto -> compte bancaire local
    # UEMOA du marchand) - voir services/verto_service.py et
    # webhook/verto.py. Rempli une fois le virement Verto initié, après
    # que le webhook Verto "Wallet Credit" confirme l'arrivée des fonds
    # envoyés par le Payout Stripe (voir routes/webhook/verto.py).
    verto_transfer_id = Column(String, nullable=True, index=True)

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("txn"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    wallet_id = Column(String, ForeignKey("wallets.id"), nullable=False)
    type = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="success")
    reference = Column(String, unique=True, index=True)
    refund_id = Column(String, nullable=True)
    fee_id = Column(String, nullable=True)
    fee_amount = Column(Float, nullable=True)
    transfer_id = Column(String, nullable=True)
    transfer_amount = Column(Float, nullable=True)
    payment_method_id = Column(String, nullable=True)
    card_brand = Column(String, nullable=True)
    card_last4 = Column(String, nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)
    related_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    description = Column(String, nullable=True)
    source = Column(String, nullable=False, default="payment_link", index=True)
    available_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("pf"))
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    full_name = Column(String)
    phone = Column(String)
    phone_verified = Column(Boolean, default=False)
    stripe_account_id = Column(String, nullable=True, index=True)
    # Évite de renvoyer l'email "compte.account_updated" à chaque webhook
    # account.updated reçu pendant l'onboarding (Stripe en envoie un par
    # champ rempli) - un seul envoi, au moment où le compte devient
    # pleinement opérationnel (voir webhook/stripe.py).
    verification_email_sent = Column(Boolean, default=False)
    # Architecture "Zero-Custody" des retraits (Stripe Connect -> Verto ->
    # banque locale UEMOA du marchand), voir services/verto_service.py.
    # Le sous-compte Verto (verto_company_id) est créé via l'API
    # onboarding-data, à partir des infos KYC entreprise du marchand
    # collectées côté Xepay - jamais via le dashboard Verto.
    verto_company_id = Column(String, nullable=True, index=True)
    verto_wallet_id = Column(String, nullable=True)
    # not_started -> sub_account_created -> kyb_submitted -> approved/rejected
    # (découpage en étapes du 2026-11-07, voir routes/verto.py) - les deux
    # premières transitions sont posées par Xepay (étapes A/B), les deux
    # dernières par webhook/verto.py sur company.approved/rejected (seuls
    # événements Verto confirmés par la doc, jamais testés en conditions
    # réelles - bloqué par le 403 sandbox).
    verto_onboarding_status = Column(String, default="not_started")
    # not_sent/sent/accepted - spécifique à PARTNER_REFERRED (Atlas for
    # Platform) : "Director of end company accepts Verto's Terms and
    # Conditions via Email", sans équivalent sous SUB_CLIENT. Voir le plan
    # du 2026-11-07, routes/verto.py (envoi + renvoi) et webhook/verto.py
    # (passage à "accepted", NON CONFIRMÉ - nom d'événement inconnu).
    verto_director_consent_status = Column(String, nullable=True, default="not_sent")
    # Coordonnées du wallet USD Verto (GET /fundingMethods, autoCreate=true)
    # - affichées dans l'UI Xepay pour que le marchand les colle lui-même
    # dans son Dashboard Stripe Express (Stripe interdit à la plateforme de
    # créer un external_account pour un compte Express ayant accès à son
    # propre dashboard - voir routes/payout.py).
    verto_usd_account_number = Column(String, nullable=True)
    verto_usd_bank_code = Column(String, nullable=True)
    verto_usd_bank_name = Column(String, nullable=True)
    # ID Stripe (ba_xxx) de cet external_account, une fois que le marchand
    # l'a ajouté lui-même et que webhook/stripe.py (account.updated) l'a
    # détecté par rapprochement avec verto_usd_account_number. C'est CET
    # ID qui est passé en `destination=` sur chaque Payout (payout.py),
    # jamais déduit du external account par défaut du compte.
    stripe_external_account_id = Column(String, nullable=True)
    # Compte bancaire local UEMOA du marchand (destination finale, saisi
    # par le marchand côté Xepay) - IBAN au format régional UEMOA, voir
    # verto_service.initiate_bank_transfer.
    beneficiary_bank_iban = Column(String, nullable=True)
    beneficiary_bank_name = Column(String, nullable=True)
    # ID du bénéficiaire Verto (`accounts.id` renvoyé par create_beneficiary,
    # distinct du companyId du sous-compte) - requis par create_payment_request.
    verto_beneficiary_id = Column(String, nullable=True)

    # Filet de sécurité au niveau base contre le double sous-compte Verto
    # (voir le découpage en étapes du 2026-11-07 et with_for_update() dans
    # routes/verto.py) - une contrainte UNIQUE sur une colonne nullable
    # autorise plusieurs NULL (comportement standard Postgres), donc sans
    # impact sur les profils n'ayant pas encore démarré l'onboarding.
    __table_args__ = (
        UniqueConstraint("verto_company_id", name="uq_profiles_verto_company_id"),
    )

class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("us"))
    account_id = Column(String, unique=True, index=True, nullable=False, default=lambda: generate_prefixed_id("acct"))
    email = Column(String, index=True, unique=True)
    password = Column(String)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True)
    # Code de sauvegarde 2FA (Authentification > Authentification à deux
    # facteurs) - un seul code persistant (pas à usage unique), hashé
    # (voir security.hash_backup_code), jamais stocké/affiché en clair
    # après sa génération. Effacé par /2fa/disable.
    two_factor_backup_code_hash = Column(String, nullable=True)
    two_factor_backup_code_generated_at = Column(DateTime(timezone=True), nullable=True) 
    status = Column(String, default="active")
    last_login = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    plan = Column(String, default="free")
    plan_started_at = Column(DateTime(timezone=True), nullable=True)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, index=True)
    subscription_status = Column(String, default="inactive")  
    cancel_at_period_end = Column(Boolean, default=False)
    api_key_public = Column(String, nullable=True)
    api_key_secret = Column(String, nullable=True)
    links = relationship("Link", back_populates="user", uselist=True)
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    webhooks = relationship("Webhook", back_populates="user")
    alert_login = Column(Boolean, default=True)
    alert_payment = Column(Boolean, default=True)
    alert_suspect = Column(Boolean, default=True)
    # Compte Google connecté (en plus de l'email) - voir /auth/google/link.
    # google_id (le "sub" du token Google) est ce qui permet a terme de se
    # reconnecter via un compte Google dont l'email differe de celui de la
    # connexion classique ; _exchange_google_code s'appuie sur ce champ en
    # repli si l'email ne correspond a aucun compte.
    google_id = Column(String, nullable=True, unique=True, index=True)
    google_email = Column(String, nullable=True)
    # Préférences de notification granulaires (Paramètres > Notifications) :
    # {"<categorie>.<evenement>": true/false}. Clé absente = active par
    # defaut, sauf pour "compte.new_device_login" qui retombe sur l'ancien
    # alert_login (voir services/email_service.is_notification_enabled) -
    # pour ne pas reactiver silencieusement l'alerte des utilisateurs qui
    # l'avaient deja desactivee via alert_login/payment/suspect ci-dessus
    # (jamais lus ailleurs desormais, conserves pour compat descendante).
    notification_prefs = Column(JSON, nullable=True)

class SecurityEvent(Base):
    """Journal d'activité (Paramètres > Équipe et sécurité). Une ligne par
    action sensible, rattachée à son acteur (user_id) ET au workspace actif
    au moment de l'action (workspace_id - l'en-tête X-Workspace-Id envoyé
    par apiFetch à chaque requête, avec repli sur user_id pour une action
    sans contexte d'équipe). GET /security/events filtre sur workspace_id :
    un membre consultant le workspace de quelqu'un d'autre y voit le
    journal de CE workspace (ses propres actions ET celles du reste de
    l'équipe), pas seulement son propre historique personnel. Jamais
    modifié/supprimé après coup - purement un journal."""
    __tablename__ = "security_events"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("sec"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    ip = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PasskeyCredential(Base):
    """Clé d'accès WebAuthn (Paramètres > Informations personnelles). Le
    challenge de la cérémonie d'enregistrement n'est jamais persisté ici -
    uniquement en mémoire côté backend/routes/passkeys.py, le temps très
    court entre /register/start et /register/finish."""
    __tablename__ = "passkey_credentials"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("pk"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    credential_id = Column(String, nullable=False, unique=True)
    public_key = Column(String, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)

class WorkspaceUser(Base):
    __tablename__ = "workspace_users"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wkus"))
    user_id = Column(String, ForeignKey("users.id"))
    workspace_id = Column(String, ForeignKey("users.id"))
    role = Column(String, default="member")
    # Date d'entree dans ce workspace (Parametres > Informations
    # personnelles > Workspaces) - NULL pour les lignes anterieures a
    # l'ajout de la colonne, jamais reconstitue retroactivement.
    created_at = Column(DateTime(timezone=True), nullable=True, default=lambda: datetime.now(timezone.utc))

# Permissions par rôle, configurables par le owner d'un workspace (voir
# backend/services/permission_service.py pour la liste des capacités et
# leur rôle minimal par défaut, et backend/middleware/authorization.py
# pour require_capability qui les applique). Une ligne par capacité
# EXPLICITEMENT redéfinie par ce workspace - l'absence de ligne pour une
# capacité donnée signifie "comportement par défaut", jamais recréée pour
# toutes les capacités à chaque workspace (la config actuelle de l'app EST
# le défaut, voir la conversation produit du 2026-10-25 : "tout la
# configuration actuelle... est considérée comme la configuration par
# défaut").
class WorkspacePermissionOverride(Base):
    __tablename__ = "workspace_permission_overrides"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wkpo"))
    workspace_id = Column(String, ForeignKey("users.id"), nullable=False)
    capability_key = Column(String, nullable=False)
    # Rôle minimal requis pour cette capacité dans ce workspace - une des
    # valeurs de permission_service.ROLE_ORDER ("owner", "admin",
    # "manager", "membre", "lecteur").
    min_role = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_wkpo_workspace_capability", "workspace_id", "capability_key", unique=True),
    )

class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wkin"))
    email = Column(String, nullable=False)
    workspace_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String, default="member")
    token_hash = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("UserDB", foreign_keys=[workspace_id])

    __table_args__ = (
        Index("idx_invite_token", "token_hash"),
        Index("idx_invite_email_workspace", "email", "workspace_id"),
    )

class RefreshToken(Base):
    """Refresh token de session (cookie HttpOnly côté client) — seul le hash
    est stocké, jamais la valeur brute. `family_id` identifie une même chaîne
    de connexion : à la rotation, l'ancien jeton est révoqué et un enfant est
    créé dans la même famille ; en cas de réutilisation d'un jeton déjà
    révoqué (vol potentiel), toute la famille est révoquée d'un coup
    (voir backend/services/refresh_token_service.py).

    `session_started_at` fixe la limite de session ABSOLUE (30 jours,
    ABSOLUTE_SESSION_MAX_DAYS) : posé une seule fois à la connexion initiale,
    puis copié tel quel sur chaque jeton enfant à la rotation — jamais
    réinitialisé. C'est ce qui empêche la rotation de repousser
    indéfiniment la session."""
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("rtk"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    family_id = Column(String, nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by = Column(String, nullable=True)
    session_started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    # Capturés à l'émission (login) et propagés/rafraîchis à chaque rotation
    # (voir refresh_token_service.py) - pour la liste "Sessions actives"
    # (un seul jeton non révoqué par famille à un instant donné, cf. le
    # mécanisme de rotation : une ligne = un appareil/session réel).
    device = Column(String, nullable=True)
    ip = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_refresh_token_hash", "token_hash"),
        Index("idx_refresh_token_family", "family_id"),
        Index("idx_refresh_token_user", "user_id"),
    )

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wh"))
    user_id = Column(String, ForeignKey("users.id"))
    url = Column(String, nullable=False)
    events = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    secret = Column(String, nullable=False)
    status = Column(String, default="active")
    last_status_code = Column(Integer, nullable=True)

    user = relationship("UserDB", back_populates="webhooks")

class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("whlg"))
    user_id = Column(String, ForeignKey("users.id"))
    webhook_id = Column(String, ForeignKey("webhooks.id", ondelete="CASCADE"))
    url = Column(String)
    event = Column(String)
    status_code = Column(Integer)
    success = Column(Boolean)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ApiLog(Base):
    __tablename__ = "api_logs"
    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("lg"))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    method = Column(String)
    path = Column(String)
    status_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("py"))
    user_id = Column(String, ForeignKey("users.id"))
    client_email = Column(String)
    amount = Column(Float)
    currency = Column(String, default="USD", nullable=False)
    amount_local = Column(Float)
    currency_local = Column(String, default="XOF")
    rate_used = Column(Float)
    status = Column(String)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    link_id = Column(String, ForeignKey("links.id"))
    link = relationship("Link")
    stripe_session_id = Column(String, nullable=True)
    stripe_account_id = Column(String, nullable=True)
    stripe_payment_intent_id = Column(String, nullable=True, index=True)
    # ID du Charge Stripe (intent.latest_charge côté lien, latest_charge.id
    # côté facture/abonnement) - capturé tel quel à la création du Payment.
    # Seul moyen fiable de retrouver ce Payment depuis le webhook
    # application_fee.created : ApplicationFee.charge n'est pas exploitable
    # (format d'ID "py_..." non reconnu par stripe.Charge.retrieve(), voir
    # routes/webhook/paiement.py), donc on matche directement sur cette
    # colonne plutôt que de rappeler Stripe.
    charge_id = Column(String, nullable=True, index=True)
    fee_id = Column(String, nullable=True)
    fee_amount = Column(Float, nullable=True)
    # Commission GLOBALE (StripeFee + part Xepay réelle), pas la part Xepay
    # seule : = ApplicationFee.balance_transaction.amount (montant
    # effectivement réglé sur le solde de la plateforme, rempli par le
    # webhook application_fee.created - voir routes/webhook/paiement.py),
    # dans la même devise que amount/currency. Confirmé par Stripe ("The
    # application fee amount minus the Stripe fees remains in your platform
    # account's balance") : la part Xepay réelle = application_fee_requested
    # - stripe_fee_amount. Distinct de fee_amount (ApplicationFee.amount,
    # qui reste dans la devise d'origine du lien).
    application_fee_requested = Column(Float, nullable=True)
    stripe_fee_amount = Column(Float, nullable=True)
    # True = stripe_fee_amount est une ESTIMATION (taux publiés Stripe -
    # 2,9% + 0,30 $ domestique, +1,5% carte internationale - voir
    # _estimate_stripe_fee_amount, routes/webhook/paiement.py), pas le
    # chiffre exact facturé par Stripe. Direct charge sur un compte
    # fees_collector="application" (comptes existants) : aucune
    # BalanceTransaction par transaction ne porte ce frais (confirmé avec
    # le support Stripe), donc toujours une estimation. None/False pour un
    # destination charge (legacy) : stripe_fee_amount y est le vrai montant
    # lu sur balance_tx.fee. Le frontend affiche la distinction plutôt que
    # de présenter une estimation comme un chiffre exact.
    stripe_fee_is_estimated = Column(Boolean, nullable=True)
    # amount - application_fee_requested (voir routes/webhook/paiement.py) -
    # c'est le montant réellement réglé par Stripe au compte connecté
    # (amount - application_fee_amount). stripe_fee_amount n'est PAS
    # soustrait en plus : il est déjà inclus dans application_fee_requested
    # (commission globale), donc le soustraire aussi double-compterait ce
    # même frais.
    balance_transaction_net = Column(Float, nullable=True)
    # balance_transaction.available_on de la charge - quand les fonds
    # deviennent disponibles côté Stripe. Déjà calculé pour
    # WalletTransaction.available_at ; manquait sur Payment.
    available_at = Column(DateTime(timezone=True), nullable=True)
    transfer_id = Column(String, nullable=True)
    transfer_amount = Column(Float, nullable=True)
    transfer_destination = Column(String, nullable=True)
    transfer_reversed = Column(Boolean, nullable=True)
    transfer_amount_reversed = Column(Float, nullable=True)
    transfer_created_at = Column(DateTime(timezone=True), nullable=True)
    payment_method_id = Column(String, nullable=True)
    payment_method_type = Column(String, nullable=True)
    card_brand = Column(String, nullable=True)
    card_last4 = Column(String, nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)
    # Origine du paiement : "link" (paiement.py), "invoice" ou "subscription"
    # (webhook/stripe.py, process_invoice_paid_event - memes valeurs que
    # WalletTransaction.source pour ce flux). NULL sur les paiements crees
    # avant l'ajout de ce champ (toujours des paiements par lien a cette
    # epoque, mais pas devine ici - voir PAYMENT_SOURCE_LABELS cote API).
    source = Column(String, nullable=True)
    # "destination" ou "direct" - type de charge Stripe réellement utilisé
    # pour CE paiement, posé explicitement à la création (jamais déduit de
    # link_id/source : un paiement par lien peut être l'un ou l'autre depuis
    # le passage des liens en direct charge, voir stripe_service.py). Seul
    # signal fiable pour savoir si les appels Stripe de relecture
    # (PaymentIntent/Charge/BalanceTransaction) ont besoin de stripe_account=
    # - voir routes/webhook/paiement.py et routes/payout.py (remboursement).
    # Backfillé sur les lignes antérieures à ce champ par la migration
    # d9efd7c7893e (link_id rempli -> "destination", sinon "direct" -
    # exact à 100% pour tout ce qui existait avant ce changement).
    charge_type = Column(String, nullable=True)
    # metadata du PaymentIntent Stripe qui a regle ce paiement (deja
    # recupere en memoire dans les deux flux de creation, aucun appel
    # Stripe supplementaire) - nomme stripe_metadata (pas "metadata",
    # reserve par Base.metadata chez SQLAlchemy). Vide/absent si rien n'a
    # ete envoye a la creation (ex: factures/abonnements, dont le
    # PaymentIntent qui regle la facture n'herite pas automatiquement des
    # metadata poses sur l'Invoice/la Subscription elles-memes).
    stripe_metadata = Column(JSON, nullable=True)

# --- SQLAlchemy (DB) ---
class Link(Base):
    __tablename__ = "links"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("lk"))
    token = Column(String, unique=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    email = Column(String)
    # NULL = montant flexible, le client choisit (voir min_amount/max_amount).
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=False, default="USD")
    name = Column(String)
    url = Column(String)
    source = Column(String, default="dashboard")
    # NULL = pas d'expiration (lien multi-usage sans limite de durée).
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True))
    deleted = Column(Boolean, default=False)
    active = Column(Boolean)
    archived = Column(Boolean, default=False)
    # NULL = illimité, 1 = usage unique, N = quota de paiements réussis.
    max_uses = Column(Integer, nullable=True)
    min_amount = Column(Float, nullable=True)
    max_amount = Column(Float, nullable=True)
    # Createur (membership.user_id) + workspace (membership.workspace_id) au
    # moment de la creation du lien - nomme link_metadata (pas "metadata",
    # reserve par Base.metadata chez SQLAlchemy, voir Payment.stripe_metadata).
    # Link.user_id vaut deja l'ID du workspace (voir create_link), donc ce
    # champ est surtout utile pour retrouver QUI dans l'equipe a cree le lien.
    link_metadata = Column(JSON, nullable=True)
    user = relationship("UserDB", back_populates="links")
    def __repr__(self):
        return f"<Link id={self.id} name={self.name} amount={self.amount}>"

# --- Buildness (renommé le 2026-11-22, anciennement "BildBus" - tables/
# routes/fichiers renommés en conséquence, voir la migration dédiée et
# routes/buildness.py ; doola_service.py/doola_mock_service.py/doola_
# client.py gardent leur nom, nommés d'après le partenaire doola, pas le
# produit Xepay). Création de LLC US + EIN via l'API partenaire doola -
# prérequis pour qu'un marchand non-résident obtienne les papiers
# nécessaires à l'activation de son compte Stripe Connect. ---

class BuildnessCustomer(Base):
    """Le "customer" doola (personne/fondateur) correspondant à un
    workspace Xepay - distinct de la société elle-même (voir
    BuildnessCompany). xepay_merchant_id UNIQUE : un seul customer doola
    par marchand, jamais recréé à chaque appel - même raison que
    UniqueConstraint("verto_company_id") sur Profile (voir
    services/verto_service.py/routes/verto.py) : ferme la fenêtre de
    course d'un double-clic sur "Démarrer" qui créerait sinon un second
    customer doola orphelin à chaque tentative."""
    __tablename__ = "buildness_customers"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("bncus"))
    xepay_merchant_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    doola_customer_id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    companies = relationship("BuildnessCompany", back_populates="customer")


class BuildnessCompany(Base):
    """Une société (LLC) en cours de formation ou formée chez doola pour
    un BuildnessCustomer. status reflète le cycle de vie côté Xepay, PAS
    le statut brut doola (voir routes/webhook/doola.py pour le mapping
    événement -> status) :
    - draft : formulaire reçu côté Xepay, appel doola pas encore confirmé.
    - submitted : create_company a réussi, doola a accusé réception.
    - processing : doola traite la formation (État + EIN en cours).
    - completed : LLC formée ET EIN émis (ein_number renseigné).
    - failed : doola a rejeté ou abandonné la demande.

    last_successful_step (ajouté le 2026-11-22) : dernière étape qui a
    RÉELLEMENT réussi (draft/submitted/processing/completed - jamais
    "failed", qui n'est pas une étape mais l'absence de la suivante) -
    mis à jour UNIQUEMENT sur les branches de succès (routes/buildness.py,
    routes/webhook/doola.py), jamais touché sur un échec. Un statut
    "failed" garde donc toujours la trace du point d'arrêt réel, pour que
    le frontend affiche le stepper à la bonne étape plutôt que de
    supposer que l'échec a eu lieu à la toute dernière étape."""
    __tablename__ = "buildness_companies"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("bnco"))
    customer_id = Column(String, ForeignKey("buildness_customers.id"), nullable=False)
    doola_company_id = Column(String, unique=True, nullable=True)
    company_name = Column(String, nullable=False)
    state = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    last_successful_step = Column(String, nullable=True, default="draft")
    ein_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("BuildnessCustomer", back_populates="companies")


class BuildnessLlcCredit(Base):
    """Un paiement de 500 USD confirmé (Stripe, compte PLATEFORME Xepay -
    jamais Connect) pour UNE formation de LLC - voir routes/
    buildness_payment.py. "paid_unused" dès la réception du webhook
    checkout.session.completed ; "consumed" UNIQUEMENT quand ce crédit a
    réellement servi à former une LLC (create_company a réussi côté
    doola, voir onboard_buildness dans routes/buildness.py) - jamais sur
    un échec, pour que le marchand puisse réessayer sans repayer."""
    __tablename__ = "buildness_llc_credits"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("bnllccr"))
    workspace_id = Column(String, ForeignKey("users.id"), nullable=False)
    stripe_checkout_session_id = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default="paid_unused")
    buildness_company_id = Column(String, ForeignKey("buildness_companies.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    consumed_at = Column(DateTime(timezone=True), nullable=True)


class BuildnessWebhookLog(Base):
    """Trace de chaque événement webhook doola déjà traité - event_id
    UNIQUE est le filet de sécurité qui empêche un même événement
    (livraison dupliquée, retry doola) d'être appliqué deux fois à
    BuildnessCompany (voir routes/webhook/doola.py, qui vérifie d'abord
    cette table avant tout traitement)."""
    __tablename__ = "buildness_webhook_logs"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("bnwhlg"))
    event_id = Column(String, unique=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BuildnessCorrectionRequest(Base):
    """Demande de correction sur une info déjà soumise à doola (adresse,
    raison sociale, secteur, description...) - ajouté le 2026-11-27 :
    vérifié dans la doc officielle de doola (docs.doola.com, API +
    Embedded SDK + spec OpenAPI) qu'il n'existe AUCUN endpoint PUT/PATCH
    pour modifier une société déjà créée, et que leur mécanisme de
    "required actions" est exclusivement RÉACTIF (doola nous demande une
    info précise, on ne peut jamais soumettre une correction de notre
    propre initiative). doola n'a de relation directe qu'avec Xepay (pas
    avec nos marchands) : cette table trace donc une demande à relayer
    MANUELLEMENT par un humain côté Xepay vers le support doola, jamais
    une mise à jour automatique - voir routes/buildness.py
    (create_correction_request) et services/email_service.py
    (send_buildness_correction_request_internal_email, envoyé à une
    adresse interne Xepay, jamais à doola directement ni au marchand)."""
    __tablename__ = "buildness_correction_requests"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("bncorr"))
    workspace_id = Column(String, ForeignKey("users.id"), nullable=False)
    company_id = Column(String, ForeignKey("buildness_companies.id"), nullable=False)
    field_label = Column(String, nullable=False)
    requested_value = Column(String, nullable=False)
    note = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class ShopifyStoreRequest(Base):
    """Demande d'une boutique Shopify "prête à l'emploi" (Buildshop) par
    un marchand - ajouté le 2026-11-27, même esprit que
    BuildnessCorrectionRequest ci-dessus : le transfert réel d'une
    boutique pré-provisionnée (voir services/buildshop_service.py,
    backend/routes/shopify.py section "Buildshop") est une action
    PUREMENT MANUELLE (Partner Dashboard "Transfer store" - confirmé
    impossible à automatiser via l'API publique Shopify aujourd'hui).
    Cette table trace donc UNIQUEMENT la demande à traiter par un
    humain côté Xepay (voir routes/shopify.py::
    create_shopify_store_request, services/email_service.py::
    send_shopify_store_request_internal_email) - AUCUNE assignation ni
    transfert automatique. C'est notamment la table que l'outil Alhu
    request_shopify_store (alhu_service.py) écrit : Alhu ne peut QUE
    créer cette ligne + déclencher l'email, jamais aller plus loin."""
    __tablename__ = "shopify_store_requests"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("ssr"))
    workspace_id = Column(String, ForeignKey("users.id"), nullable=False)
    note = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class ShopifyShop(Base):
    """Une boutique Shopify connectée à "Xepay Sync" (voir routes/shopify.py,
    services/shopify_service.py) via GET /auth/shopify/callback -
    shop_domain UNIQUE : une ré-installation (même boutique, nouveau code)
    met à jour la ligne existante plutôt que d'en créer une seconde.

    access_token stocké CHIFFRÉ (encrypt_secret, même mécanisme que
    UserDB.two_factor_secret, voir security.py) - jamais en clair en base,
    jamais loggé ni renvoyé dans une réponse HTTP (voir routes/shopify.py).

    merchant_id (workspace Xepay) nullable : résolu via le paramètre
    "state" du callback (jeton shopify_install signé, voir
    security.create_shopify_state_token/decode_shopify_state_token et
    GET /shopify/install, routes/shopify.py) - reste NULL pour une
    boutique jamais explicitement rattachée à un marchand Xepay.

    access_token NOT NULL (revenu en arrière le 2026-11-24, demande
    explicite - "la colonne access_token ne doit jamais être vide") :
    pas de mécanisme de déconnexion qui viderait cette colonne - une
    ligne ShopifyShop n'existe QUE si un vrai token est en main (voir
    shopify_callback, routes/shopify.py, qui ne crée/met à jour la ligne
    qu'après un échange OAuth réussi).

    uninstalled_at (ajouté le 2026-11-28, webhook app/uninstalled) :
    SEUL signal de désinstallation - access_token reste tel quel
    (contrainte ci-dessus, jamais vidé), devenu simplement obsolète/
    révoqué côté Shopify. _get_connected_shop (routes/shopify.py)
    l'exclut désormais explicitement. Remis à NULL automatiquement sur
    une ré-installation (shopify_callback, même ligne réutilisée via
    shop_domain UNIQUE)."""
    __tablename__ = "shopify_shops"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("shp"))
    shop_domain = Column(String, unique=True, nullable=False)
    merchant_id = Column(String, ForeignKey("users.id"), nullable=True)
    access_token = Column(String, nullable=False)
    scope = Column(String, nullable=True)
    installed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    uninstalled_at = Column(DateTime(timezone=True), nullable=True)


class ShopifyProductMirror(Base):
    """Copie locale d'un produit Shopify, tenue à jour par webhooks
    (products/create|update|delete - ajouté le 2026-11-28, demande
    explicite de l'utilisateur de mirrorer produits/commandes/clients,
    PAS juste réagir au cycle de vie de l'app comme initialement
    recommandé). Remplace, pour un futur usage qui en aurait besoin,
    la lecture live GraphQL (list_products, services/shopify_service.py,
    toujours utilisée telle quelle par l'onglet Commerce > Shopify - ce
    mirroir est un magasin SUPPLÉMENTAIRE, il ne remplace aucune route
    existante).

    shopify_product_id : id NUMÉRIQUE brut du payload REST webhook
    (jamais le GID GraphQL "gid://shopify/Product/123" utilisé par
    list_products - DEUX représentations différentes de la même
    ressource selon qu'on vient d'un webhook REST ou d'un appel
    GraphQL direct, jamais confondues)."""
    __tablename__ = "shopify_product_mirrors"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("spm"))
    shop_domain = Column(String, nullable=False, index=True)
    shopify_product_id = Column(String, nullable=False)
    title = Column(String, nullable=True)
    status = Column(String, nullable=True)
    vendor = Column(String, nullable=True)
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    image_url = Column(String, nullable=True)
    shopify_created_at = Column(DateTime(timezone=True), nullable=True)
    shopify_updated_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("shop_domain", "shopify_product_id", name="uq_shopify_product_mirror_shop_product"),
    )


class ShopifyOrderMirror(Base):
    """Copie locale d'une commande Shopify, tenue à jour par webhooks
    (orders/create pour la création - voir le handler existant, étendu
    pour mirrorer EN PLUS de sa logique Link Xepay déjà en place -, et
    orders/update pour le reste du cycle de vie) - ajouté le
    2026-11-28, même contexte que ShopifyProductMirror ci-dessus.
    AUCUN rapport avec ShopifyOrderPayment (qui, lui, ne trace que les
    commandes payées via la méthode manuelle "Xepay" + le Link associé)
    - celle-ci mirrore TOUTES les commandes, quelle que soit leur
    méthode de paiement."""
    __tablename__ = "shopify_order_mirrors"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("som"))
    shop_domain = Column(String, nullable=False, index=True)
    shopify_order_id = Column(String, nullable=False)
    name = Column(String, nullable=True)
    financial_status = Column(String, nullable=True)
    fulfillment_status = Column(String, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    total_price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    shopify_created_at = Column(DateTime(timezone=True), nullable=True)
    shopify_updated_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("shop_domain", "shopify_order_id", name="uq_shopify_order_mirror_shop_order"),
    )


class ShopifyCustomerMirror(Base):
    """Copie locale d'un client Shopify, tenue à jour par webhooks
    (customers/create|update|delete) - ajouté le 2026-11-28, même
    contexte que ShopifyProductMirror ci-dessus. Purgée entièrement sur
    customers/redact ou shop/redact (RGPD, voir routes/webhook/
    shopify.py) - jamais conservée après une demande de suppression."""
    __tablename__ = "shopify_customer_mirrors"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("scm"))
    shop_domain = Column(String, nullable=False, index=True)
    shopify_customer_id = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    orders_count = Column(Integer, nullable=True)
    total_spent = Column(Float, nullable=True)
    shopify_created_at = Column(DateTime(timezone=True), nullable=True)
    shopify_updated_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("shop_domain", "shopify_customer_id", name="uq_shopify_customer_mirror_shop_customer"),
    )


class ShopifyOrderPayment(Base):
    """Une commande Shopify payée via un lien de paiement Xepay plutôt que
    Shopify Payments (voir routes/webhook/shopify.py, services/
    shopify_order_sync_service.py) - le marchand crée côté Shopify une
    méthode de paiement MANUELLE (gratuite, configurée à la main dans
    Settings > Payments, aucune API ne permet de la créer - voir le
    docstring de routes/webhook/shopify.py) ; quand un client la choisit
    au checkout, Shopify crée la commande avec financial_status="pending"
    et envoie le webhook orders/create, qui crée la ligne ci-dessous +
    un Link Xepay (voir Link.link_metadata, xepay_type=
    "shopify_order_payment").

    UniqueConstraint(shop_domain, shopify_order_id) : SEUL filet de
    sécurité contre une livraison dupliquée du même webhook (même
    principe que BuildnessWebhookLog.event_id) - un doublon lève une
    IntegrityError, rattrapée par l'appelant, jamais un second Link créé
    pour la même commande.

    marked_paid_at/xepay_reference : renseignés APRÈS coup, quand le Link
    associé est payé (voir sync_order_paid_with_shopify, appelée depuis
    process_checkout_session_payment dans routes/webhook/paiement.py) -
    NULL tant que la commande reste impayée côté Xepay."""
    __tablename__ = "shopify_order_payments"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("sop"))
    shop_domain = Column(String, nullable=False, index=True)
    shopify_order_id = Column(String, nullable=False)
    shopify_order_gid = Column(String, nullable=False)
    link_id = Column(String, ForeignKey("links.id"), nullable=False)
    merchant_id = Column(String, ForeignKey("users.id"), nullable=False)
    marked_paid_at = Column(DateTime(timezone=True), nullable=True)
    xepay_reference = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("shop_domain", "shopify_order_id", name="uq_shopify_order_payment_shop_order"),
    )