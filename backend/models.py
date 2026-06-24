from pydantic import BaseModel
from backend.database import Base
from sqlalchemy import Column, String, Boolean
from sqlalchemy import Column, Integer, String, Float, DateTime
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship  
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Numeric
import uuid
from sqlalchemy import Index

class User(BaseModel):
    email: str
    password: str
    invite_token: Optional[str] = None

class TwoFASetupRequest(BaseModel):
    phone: str

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

class UserLogin(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class TransferRequest(BaseModel):
    to_email: str
    amount: float

class WithdrawRequest(BaseModel):
    amount: float  

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0)
    pending = Column(Float, default=0)         
    available = Column(Float, default=0)
    residual_xof = Column(Numeric(18, 6), default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("UserDB", back_populates="wallet")

class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)

    amount = Column(Float, nullable=False)

    operator = Column(String)   # wave / orange / mtn
    phone = Column(String)
    reference = Column(String, unique=True, index=True)

    status = Column(String, default="pending")  # pending | success | failed

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    processed_at = Column(DateTime(timezone=True), nullable=True)

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)

    type = Column(String, nullable=False)
    # deposit / withdraw / internal_transfer / refund

    direction = Column(String, nullable=False)
    # in / out

    amount = Column(Float, nullable=False)

    status = Column(String, default="success")
    # pending / success / failed

    reference = Column(String, unique=True, index=True)

    related_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    # pour transfert interne

    description = Column(String, nullable=True)
    available_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    full_name = Column(String)
    phone = Column(String)
    phone_verified = Column(Boolean, default=False)
    stripe_account_id = Column(String, nullable=True, index=True)
    

class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, index=True, unique=True)
    password = Column(String)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_phone = Column(String, nullable=True)
    two_factor_code = Column(String, nullable=True)
    two_factor_code_expires_at = Column(DateTime, nullable=True)
    status = Column(String, default="active")
    last_login = Column(DateTime, nullable=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    token = Column(String)
    is_deleted = Column(Boolean, default=False)
    plan = Column(String, default="free")
    plan_started_at = Column(DateTime(timezone=True), nullable=True)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
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

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    workspace_id = Column(String, ForeignKey("users.id"))
    role = Column(String, default="member")



class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    url = Column(String, nullable=False)
    events = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    secret = Column(String, nullable=False)

    user = relationship("UserDB", back_populates="webhooks")

class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    webhook_id = Column(Integer, ForeignKey("webhooks.id"))
    url = Column(String)
    event = Column(String)
    status_code = Column(Integer)
    success = Column(Boolean)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ApiLog(Base):
    __tablename__ = "api_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    method = Column(String)
    path = Column(String)
    status_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
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
    
   
# --- SQLAlchemy (DB) ---
class Link(Base):
    __tablename__ = "links"

    id = Column(String, primary_key=True)
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





