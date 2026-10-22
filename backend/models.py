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

class UserLogin(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class WithdrawRequest(BaseModel):
    amount: float  

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
    
class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("us"))
    account_id = Column(String, unique=True, index=True, nullable=False, default=lambda: generate_prefixed_id("acct"))
    email = Column(String, index=True, unique=True)
    password = Column(String)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True) 
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

class WorkspaceUser(Base):
    __tablename__ = "workspace_users"

    id = Column(String, primary_key=True, default=lambda: generate_prefixed_id("wkus"))
    user_id = Column(String, ForeignKey("users.id"))
    workspace_id = Column(String, ForeignKey("users.id"))
    role = Column(String, default="member")

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
    user = relationship("UserDB", back_populates="links")
    def __repr__(self):
        return f"<Link id={self.id} name={self.name} amount={self.amount}>"