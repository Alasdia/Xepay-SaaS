from pydantic import BaseModel, EmailStr, Field
from backend.database import Base
from sqlalchemy import Column, String, Boolean
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from typing import Optional
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
    amount: float
    currency: str = "USD"
    source: str = "dashboard"

class LinkResponse(BaseModel):
    id: str
    token: str
    amount: float
    currency: str
    name: Optional[str] 
    url: str
    active: bool

class LinkDashboardResponse(BaseModel):
    id: str
    name: str
    amount: float
    currency: str
    status: str
    active: bool
    archived: bool
    url: str
    expires_at: datetime
    created_at: datetime
    metadata: Optional[dict] = None
    # Commission Xepay RÉELLEMENT appliquée au paiement de ce lien (None
    # pour un lien pas encore payé) - voir GET /links dans routes/lien.py,
    # qui la lit sur Payment.application_fee_requested. Utilisée par le
    # tableau de bord (dashboard.js) pour calculer un "Volume net" exact,
    # jamais un taux fixe par source : la commission est dégressive par
    # volume mensuel (backend/services/commission_service.py).
    fee_amount: Optional[float] = None

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
    # jamais ici (pas de validator Pydantic dans ce fichier - voir
    # routes/verto.py pour la convention déjà en place sur le téléphone
    # Issuing).
    iban: str
    bic: str
    bank_name: str
    bank_country_code: str
    beneficiary_address_line1: str
    beneficiary_country_code: str
    beneficiary_city: str
    beneficiary_postal_code: str
    beneficiary_state_or_province: str

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

class IssuingTopup(Base):
    """Historique des recharges du solde Issuing (pull funding ACH - voir
    routes/issuing.py create_issuing_topup, et backend/scripts/
    fund_issuing_balance.py pour l'équivalent test sur un compte
    arbitraire). stripe_topup_id reste NULL tant que l'appel
    stripe.Topup.create n'a pas abouti : une ligne "pending" sans
    stripe_topup_id plus vieille que quelques minutes n'a jamais atteint
    Stripe (process arrêté entre l'écriture de cette ligne et l'appel
    Stripe) - voir PENDING_SUBMIT_GRACE dans routes/issuing.py, qui
    l'ignore sans jamais la nettoyer activement."""
    __tablename__ = "issuing_topups"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("itu"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    stripe_account_id = Column(String, nullable=False, index=True)
    stripe_topup_id = Column(String, unique=True, index=True, nullable=True)
    stripe_source_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    # pending / succeeded / failed / canceled / reversed - cycle de vie
    # Stripe d'un Topup (webhook/stripe.py gère les quatre transitions
    # au-delà de la création, déjà connue de façon synchrone via la
    # réponse de l'appel API).
    status = Column(String, nullable=False, default="pending")
    failure_message = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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

    # Compte Stripe Connect DÉDIÉ à Issuing (dashboard: none), distinct de
    # stripe_account_id (Express, paiements/payouts) - Issuing n'est pas
    # compatible avec un compte Express, voir
    # backend/services/stripe_issuing_service.py. Même marchand, deux
    # comptes Stripe séparés.
    stripe_issuing_account_id = Column(String, nullable=True, index=True)
    # Programme Issuing (banque partenaire + réseau) créé sur ce compte -
    # nécessaire pour que la capacité card_issuing soit demandée.
    stripe_issuing_program_id = Column(String, nullable=True)

    # Rechargement de la carte Issuing depuis le wallet USD Verto DÉJÀ
    # existant du marchand (verto_usd_account_number/bank_code plus haut) -
    # jamais un compte bancaire américain générique ni le compte UEMOA
    # directement (Stripe ACH ne fonctionne qu'avec un compte US, voir
    # conversation du 2026-11-06). source ach_debit créée sur le compte
    # Issuing, vérifiée automatiquement via les webhooks Verto (montant des
    # micro-dépôts Stripe lus dans leur notification de paiement entrant),
    # jamais par le marchand lui-même (son wallet Verto n'a pas d'interface
    # où il pourrait les voir).
    stripe_issuing_bank_source_id = Column(String, nullable=True)
    # not_started / pending_verification / verified / failed
    stripe_issuing_bank_status = Column(String, nullable=True, default="not_started")
    # Montants (en cents) des micro-dépôts Stripe déjà vus via webhook
    # Verto, en attendant d'en avoir 2 pour vérifier la source auprès de
    # Stripe - vidé une fois la vérification tentée (succès ou échec).
    stripe_issuing_bank_pending_amounts = Column(JSON, nullable=True)
    stripe_issuing_bank_link_started_at = Column(DateTime, nullable=True)

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
    amount = Column(Float)
    currency = Column(String, nullable=False, default="USD")
    name = Column(String)
    url = Column(String)
    source = Column(String, default="dashboard") 
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    deleted = Column(Boolean, default=False)
    active = Column(Boolean)
    archived = Column(Boolean, default=False)
    # Createur (membership.user_id) + workspace (membership.workspace_id) au
    # moment de la creation du lien - nomme link_metadata (pas "metadata",
    # reserve par Base.metadata chez SQLAlchemy, voir Payment.stripe_metadata).
    # Link.user_id vaut deja l'ID du workspace (voir create_link), donc ce
    # champ est surtout utile pour retrouver QUI dans l'equipe a cree le lien.
    link_metadata = Column(JSON, nullable=True)
    user = relationship("UserDB", back_populates="links")
    def __repr__(self):
        return f"<Link id={self.id} name={self.name} amount={self.amount}>"