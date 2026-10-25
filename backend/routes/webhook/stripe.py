from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import stripe

from backend.database import get_db
from backend.models import Profile, Wallet, WalletTransaction, Withdrawal, UserDB, WorkspaceUser, ConnectInvoiceCreateRequest, ConnectSubscriptionCreateRequest, ConnectSubscriptionQuantityUpdateRequest, ConnectProductCreateRequest, ConnectCustomerCreateRequest, ConnectInvoiceUpdateRequest, Payment
from backend.middleware.authorization import require_capability
from backend.services.stripe_service import (create_connect_invoice, create_connect_product, create_connect_customer, update_connect_customer)
from backend.services import commission_service
from backend.services.email_service import send_account_updated_email, send_payout_success_email, send_payout_failed_email, is_notification_enabled
import stripe  
import os

STRIPE_WEBHOOK_SECRET_CONNECT = os.getenv("STRIPE_WEBHOOK_SECRET_CONNECT")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter()

# Les montants Stripe sont exprimés dans l'unité minimale de la devise.
# XOF est une devise sans sous-unité (partagé entre PaymentIntent et facture).
ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK",
    "JPY", "KMF", "KRW", "PYG", "RWF",
    "UGX", "VND", "VUV", "XAF", "XOF",
    "XPF",
}


def _convert_merchant_amount_to_xof(db, merchant_amount, currency):
    """merchant_amount : Decimal, net de commission, dans `currency`.
    Retourne (montant arrondi ROUND_DOWN en XOF, taux utilisé) — le taux est
    renvoyé pour être enregistré tel quel sur Payment.rate_used, comme le
    fait déjà process_checkout_session_payment (paiement.py) pour le
    paiement par lien."""
    from decimal import Decimal, ROUND_DOWN
    from sqlalchemy import text

    if currency == "XOF":
        return merchant_amount.quantize(Decimal("1"), rounding=ROUND_DOWN), Decimal("1")

    rate_row = db.execute(
        text("""
            SELECT rate
            FROM exchange_rates
            WHERE from_currency = :currency
              AND to_currency = 'XOF'
        """),
        {"currency": currency},
    ).fetchone()

    if not rate_row:
        raise ValueError(f"Taux {currency}/XOF introuvable")

    rate = Decimal(str(rate_row.rate))
    return (merchant_amount * rate).quantize(Decimal("1"), rounding=ROUND_DOWN), rate


def process_invoice_paid_event(
    invoice_data: dict,
    connected_account_id: str,
    db: Session,
):
    """Crédite le wallet du marchand à la facturation d'une Facture Connect
    ou au règlement d'un cycle d'abonnement Connect (les abonnements Stripe
    se règlent eux aussi via une Invoice, portant `subscription` non nul :
    voir create_merchant_subscription/create_connect_invoice dans
    stripe_service.py, qui posent déjà application_fee_percent/
    application_fee_amount sur ce flux). Schéma défensif classique
    (idempotence par référence, lock du wallet) partagé avec
    process_checkout_session_payment (paiement par lien, paiement.py).

    Depuis l'API Stripe 2025-03-31.basil, l'Invoice du webhook n'a plus
    payment_intent, charge, application_fee_amount ni subscription à plat
    (retirés au profit de invoice.payments/invoice.parent — voir le
    changelog "add-support-for-multiple-partial-payments-on-invoices"). Lire
    ces champs sur invoice_data renvoyait donc toujours None/0, en silence
    (fee toujours à 0, available_at toujours None, abonnements classés
    "invoice"). Plutôt que de deviner/recalculer depuis un payload dont la
    forme a changé sous nos pieds, cette fonction relit l'objet PaymentIntent
    réel qui a réglé la facture (2 à 3 appels Stripe, détaillés plus bas) et
    lit directement dessus tout ce qui peut l'être : montant, devise, frais,
    moyen de paiement, carte, description, date de création, date de
    disponibilité des fonds (avec repli sur BalanceTransaction.list si
    l'expand ne suffit pas — constaté peu fiable sur ce flux, contrairement
    au paiement par lien). Si ce PaymentIntent ne peut pas être retrouvé,
    on lève plutôt que de créditer avec des valeurs devinées : l'exception
    remonte jusqu'au handler webhook, qui répond 500 à Stripe, qui retentera
    la livraison (l'idempotence par référence empêche tout double crédit)."""
    import logging
    from decimal import Decimal
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)

    invoice_id = invoice_data["id"]

    # Seules les factures effectivement payées créditent le wallet.
    if invoice_data.get("status") != "paid":
        return {
            "status": "ignored",
            "invoice_id": invoice_id,
        }

    if not connected_account_id:
        raise ValueError("Compte Connect absent de l'événement facture")

    # Idempotence : ne jamais créditer deux fois la même facture.
    existing = db.query(WalletTransaction).filter(
        WalletTransaction.reference == invoice_id
    ).first()

    if existing:
        return {
            "status": "already_processed",
            "invoice_id": invoice_id,
        }

    profile = db.query(Profile).filter(
        Profile.stripe_account_id == connected_account_id
    ).first()

    if not profile:
        raise ValueError(
            f"Profil introuvable : {connected_account_id}"
        )

    merchant_id = profile.user_id

    wallet = db.query(Wallet).filter(
        Wallet.user_id == merchant_id
    ).with_for_update().first()

    if not wallet:
        raise ValueError(
            f"Portefeuille introuvable : {merchant_id}"
        )

    # Un abonnement Connect se règle via une Invoice portant `subscription` —
    # c'est le seul signal fiable qui distingue un sous-solde "Abonnements"
    # d'un sous-solde "Factures" (customer.subscription.* ne porte, lui,
    # aucune garantie de paiement réussi). Depuis l'API Stripe
    # 2025-03-31.basil, invoice.subscription est retiré au profit de
    # invoice.parent.subscription_details.subscription (avec
    # invoice.parent.type == "subscription_details") — exactement la même
    # vague de retrait que payment_intent/charge. Lire l'ancien champ seul
    # classait donc TOUTE facture d'abonnement comme "invoice" (jamais
    # "subscription"), silencieusement, sur cette clé API (pinnée sur une
    # version postérieure à basil). On garde l'ancien champ en repli, au cas
    # où l'API version du compte changerait.
    parent = invoice_data.get("parent") or {}
    if parent.get("type") == "subscription_details":
        subscription_id = (parent.get("subscription_details") or {}).get("subscription")
    else:
        subscription_id = invoice_data.get("subscription")
    source = "subscription" if subscription_id else "invoice"

    # Retrouve le PaymentIntent qui a réglé cette facture : invoice.payments
    # supporte plusieurs paiements (partiels) par facture, donc on cherche
    # l'entrée réellement payée. expand=["payments.data.payment.payment_intent"]
    # est à la limite Stripe de 4 niveaux d'expand ; aller jusqu'à
    # latest_charge.balance_transaction dans la même requête dépasserait
    # cette limite, d'où le second appel sur le PaymentIntent lui-même.
    inv = stripe.Invoice.retrieve(
        invoice_id,
        expand=["payments.data.payment.payment_intent"],
        stripe_account=connected_account_id,
    )
    payment_intent_ref = None
    for entry in (inv.payments.data if inv.payments else []):
        if entry.status == "paid" and entry.payment.type == "payment_intent":
            payment_intent_ref = entry.payment.payment_intent
            break
    if not payment_intent_ref:
        raise ValueError(
            f"Aucun PaymentIntent réglé trouvé pour la facture {invoice_id}"
        )

    intent = stripe.PaymentIntent.retrieve(
        payment_intent_ref.id,
        expand=["latest_charge.balance_transaction"],
        stripe_account=connected_account_id,
    )

    # Montant et devise directement depuis le PaymentIntent réglé : déjà
    # dans la devise de facturation du marchand (XOF pour ce projet), donc
    # _convert_merchant_amount_to_xof ne fait qu'arrondir (pas de taux de
    # change appliqué) — mais reste générique si une facture est un jour
    # libellée dans une autre devise.
    currency = intent.currency.upper()
    divisor = (
        Decimal("1")
        if currency in ZERO_DECIMAL_CURRENCIES
        else Decimal("100")
    )
    gross_amount = Decimal(intent.amount_received or intent.amount or 0) / divisor
    fee_amount = Decimal(intent.application_fee_amount or 0) / divisor

    # Montant crédité au marchand après la commission Xepay.
    merchant_amount = gross_amount - fee_amount

    if merchant_amount < 0:
        raise ValueError(
            f"Commission supérieure à la facture : {invoice_id}"
        )

    amount_local, rate_used = _convert_merchant_amount_to_xof(db, merchant_amount, currency)

    latest_charge = intent.latest_charge
    payment_method_details = (
        getattr(latest_charge, "payment_method_details", None) if latest_charge else None
    )
    card_info = (
        getattr(payment_method_details, "card", None) if payment_method_details else None
    )

    # expand=["latest_charge.balance_transaction"] n'est pas honoré de façon
    # fiable sur ce flux (constaté : balance_transaction revient comme un ID
    # brut "txn_..." plutôt qu'expandé en objet, contrairement au paiement
    # par lien). Même filet de sécurité que process_checkout_session_payment
    # (paiement.py) : BalanceTransaction.list(source=charge_id) retrouve
    # l'objet complet indépendamment de ce que l'expand a renvoyé.
    balance_tx = (
        getattr(latest_charge, "balance_transaction", None) if latest_charge else None
    )
    if latest_charge and (not balance_tx or isinstance(balance_tx, str)):
        balance_txs = stripe.BalanceTransaction.list(
            source=latest_charge.id,
            limit=1,
            stripe_account=connected_account_id,
        )
        balance_tx = balance_txs.data[0] if balance_txs.data else None
    has_balance_tx = bool(balance_tx) and not isinstance(balance_tx, str)
    available_at = (
        datetime.fromtimestamp(balance_tx.available_on, tz=timezone.utc)
        if has_balance_tx else None
    )
    created_at = datetime.fromtimestamp(intent.created, tz=timezone.utc)

    # StripeFee réel pour cette charge directe (fees_collector="application"
    # sur ce compte Connect) : jamais sur la balance_transaction du compte
    # connecté ci-dessus (son "fee" n'y est que l'Application Fee, pas de
    # ligne fee_details de type stripe_fee), ni sur celle de l'ApplicationFee
    # elle-même (fee=0 dessus) - c'est une BalanceTransaction séparée, de
    # type "stripe_fee", sur le solde de la PLATEFORME elle-même (jamais de
    # stripe_account= ici), avec pour source l'ID de cette même charge.
    # Confirmé sur un vrai paiement test. Disponible immédiatement - pas
    # besoin du rapport "All Fees" (mode live uniquement, délai de 96h).
    stripe_fee_amount = None
    if latest_charge:
        platform_txs = stripe.BalanceTransaction.list(
            source=latest_charge.id,
            limit=10,
        )
        stripe_fee_tx = next(
            (t for t in platform_txs.data if t.type == "stripe_fee"), None
        )
        if stripe_fee_tx:
            stripe_fee_amount = float(abs(Decimal(stripe_fee_tx.amount)) / divisor)

    stripe_description = (
        getattr(latest_charge, "description", None) if latest_charge else None
    )

    # charge.transfer (destination charges) est systématiquement absent sur
    # ce flux : c'est un direct charge (stripe_account=connected_account_id
    # partout), l'argent est déjà sur le compte connecté dès le départ (pas
    # de Transfer) — transfer_* ne sont donc pas renseignés sur Payment/
    # WalletTransaction. stripe_fee_amount, lui, EST récupéré (voir
    # stripe_fee_amount ci-dessus) depuis le solde plateforme, pas depuis
    # cette charge.
    fee_id = getattr(latest_charge, "application_fee", None) if latest_charge else None

    # status reste notre vocabulaire domaine, pas le statut brut Stripe
    # ("succeeded", "processing"...) : les agrégats SQL de payout.py (solde
    # disponible, breakdown) filtrent littéralement sur
    # WalletTransaction.status == "success", et Payment utilise sa propre
    # convention "paid"/"pending"/"failed"/"refunded" (voir lien.py,
    # webhooks_api.py, payout.py). Les deux sont dérivés du vrai
    # intent.status plutôt qu'écrits en dur — un paiement qui ne serait pas
    # "succeeded" ici (cas limite : l'InvoicePayment était "paid" mais le
    # PaymentIntent a depuis été contesté/annulé) ne doit pas compter comme
    # crédité ni réglé.
    if intent.status == "succeeded":
        status = "success"
        payment_status = "paid"
    elif intent.status == "processing":
        status = "pending"
        payment_status = "pending"
    else:
        status = "failed"
        payment_status = "failed"

    if status != "success":
        # La facture/l'entrée de paiement est "paid" côté Stripe, mais le
        # PaymentIntent qui l'a réglée ne l'est plus (contesté/annulé entre
        # temps) : ne pas créditer le wallet sur la base d'une incohérence.
        raise ValueError(
            f"PaymentIntent {intent.id} non succeeded ({intent.status}) "
            f"pour la facture {invoice_id}"
        )

    card_brand = getattr(card_info, "brand", None) if card_info else None
    card_last4 = getattr(card_info, "last4", None) if card_info else None
    card_exp_month = getattr(card_info, "exp_month", None) if card_info else None
    card_exp_year = getattr(card_info, "exp_year", None) if card_info else None
    # Apple Pay/Google Pay/Link payés par carte arrivent avec
    # payment_method_details.type == "card" (le wallet est un sous-champ,
    # card.wallet.type) — sans ça, payment_method_type vaut toujours "card"
    # et l'UI affiche le logo Visa/Mastercard au lieu du logo du wallet.
    card_wallet = getattr(card_info, "wallet", None) if card_info else None
    wallet_type = getattr(card_wallet, "type", None) if card_wallet else None
    payment_method_type = wallet_type or (
        getattr(payment_method_details, "type", None) if payment_method_details else None
    )
    description = stripe_description or (
        f"Paiement {'abonnement' if source == 'subscription' else 'facture'} "
        f"Stripe {invoice_id}"
    )

    # S'assure que le client a bien un moyen de paiement par défaut
    # (colonne "Moyen de paiement" de la vue Clients, qui lit
    # customer.invoice_settings.default_payment_method) : pour les
    # factures send_invoice payées via la page hébergée Stripe, ce champ
    # n'est PAS mis à jour automatiquement par Stripe (contrairement aux
    # abonnements créés via Checkout, qui le font déjà eux-mêmes) - posé
    # ici au mieux, sans jamais faire échouer le crédit du wallet si ça rate.
    customer_id = invoice_data.get("customer")
    if customer_id and intent.payment_method:
        try:
            stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": intent.payment_method},
                stripe_account=connected_account_id,
            )
        except stripe.error.StripeError:
            pass

    # Le PaymentIntent qui règle une facture/un abonnement n'hérite jamais
    # automatiquement des metadata posées sur l'Invoice/la Subscription à
    # leur création (create_connect_invoice/create_merchant_subscription) -
    # intent.metadata est donc toujours vide sur ce flux. On retrouve donc
    # les vraies metadata (user_id/workspace_id/xepay_type) directement sur
    # l'Invoice (déjà récupérée ci-dessus, aucun appel en plus), avec repli
    # sur la Subscription elle-même si l'Invoice n'en porte pas (un seul
    # appel Stripe supplémentaire, uniquement dans ce cas précis).
    stripe_metadata = intent.metadata.to_dict() if intent.metadata else {}
    if not stripe_metadata:
        stripe_metadata = inv.metadata.to_dict() if inv.metadata else {}
    if not stripe_metadata and subscription_id:
        try:
            sub = stripe.Subscription.retrieve(
                subscription_id,
                stripe_account=connected_account_id,
            )
            stripe_metadata = sub.metadata.to_dict() if sub.metadata else {}
        except stripe.error.StripeError:
            pass

    # Payment n'était jusqu'ici créé que pour le paiement par lien
    # (process_checkout_session_payment) : factures/abonnements ne
    # créditaient que WalletTransaction. Même table, même schéma, pour que
    # les deux flux soient exploitables de la même façon (ex. relevés,
    # rapports). transfer_* ne sont pas renseignés ici (toujours absents sur
    # ce compte Connect pour ce type de charge, voir le commentaire
    # au-dessus de fee_id) ; stripe_fee_amount l'est, voir plus haut.
    payment = Payment(
        user_id=merchant_id,
        client_email=invoice_data.get("customer_email"),
        amount=float(gross_amount),
        currency=currency,
        amount_local=float(amount_local),
        currency_local="XOF",
        rate_used=float(rate_used),
        status=payment_status,
        created_at=created_at,
        source=source,
        stripe_metadata=stripe_metadata or None,
        stripe_account_id=connected_account_id,
        stripe_payment_intent_id=intent.id,
        charge_id=latest_charge.id if latest_charge else None,
        fee_id=fee_id,
        fee_amount=float(fee_amount),
        stripe_fee_amount=stripe_fee_amount,
        # brut - commission globale, jamais - StripeFee en plus : le
        # StripeFee ne touche jamais le marchand sur ce flux (payé par la
        # plateforme, voir stripe_fee_amount ci-dessus) - même principe que
        # pour les liens de paiement, confirmé par la balance_transaction
        # réelle du compte connecté (net = amount - fee, sans autre
        # déduction).
        balance_transaction_net=float(gross_amount - fee_amount),
        available_at=available_at,
        payment_method_id=intent.payment_method,
        payment_method_type=payment_method_type,
        card_brand=card_brand,
        card_last4=card_last4,
        card_exp_month=card_exp_month,
        card_exp_year=card_exp_year,
    )

    tx = WalletTransaction(
        user_id=merchant_id,
        wallet_id=wallet.id,
        source=source,
        type="deposit",
        direction="in",
        amount=amount_local,
        status=status,
        reference=invoice_id,
        fee_id=fee_id,
        fee_amount=fee_amount,
        payment_method_id=intent.payment_method,
        card_brand=card_brand,
        card_last4=card_last4,
        card_exp_month=card_exp_month,
        card_exp_year=card_exp_year,
        available_at=available_at,
        created_at=created_at,
        description=description,
    )

    try:
        db.add(payment)
        db.flush()

        db.add(tx)
        db.flush()

        wallet.balance = (
            Decimal(str(wallet.balance or 0)) + amount_local
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    logger.info(
        "Facture Connect traitée : id=%s marchand=%s source=%s montant_XOF=%s",
        invoice_id,
        merchant_id,
        source,
        amount_local,
    )

    return {
        "status": "processed",
        "invoice_id": invoice_id,
        "merchant_id": merchant_id,
        "source": source,
        "currency": currency,
        "gross_amount": str(gross_amount),
        "application_fee_amount": str(fee_amount),
        "credited_amount_xof": str(amount_local),
    }

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    import logging

    logger = logging.getLogger(__name__) 

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Signature manquante")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET_CONNECT
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload invalide")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Signature invalide")

    event_type = event["type"]
    object_data = event["data"]["object"]

    # Identifiant du compte Connect à l'origine de l'événement.
    connected_account_id = event.account

    try:
        # --------------------------------------------------
        # MISE À JOUR DU COMPTE CONNECT
        # --------------------------------------------------
        if event_type == "account.updated":
            stripe_id = object_data["id"]
            account = stripe.Account.retrieve(stripe_id)

            profile = db.query(Profile).filter(
                Profile.stripe_account_id == stripe_id
            ).first()

            if profile:
                individual = getattr(account, "individual", None)

                first_name = getattr(individual, "first_name", "") or ""
                last_name = getattr(individual, "last_name", "") or ""
                phone = getattr(individual, "phone", None)

                profile.full_name = f"{first_name} {last_name}".strip()

                if phone:
                    profile.phone = phone

                db.commit()

                user = db.query(UserDB).filter(
                    UserDB.id == profile.user_id
                ).first()

                # Stripe envoie un account.updated par champ rempli pendant
                # l'onboarding - un email à chaque fois serait un spam
                # ("chaque clic -> un mail"). On ne notifie qu'une fois,
                # au moment où le compte devient réellement opérationnel.
                is_ready = bool(account.charges_enabled) and bool(account.payouts_enabled)
                if (
                    is_ready
                    and not profile.verification_email_sent
                    and user and user.email
                    and is_notification_enabled(user, "compte.account_updated")
                ):
                    send_account_updated_email(user.email)
                    profile.verification_email_sent = True
                    db.commit()

        # --------------------------------------------------
        # RETRAITS CONNECT
        # --------------------------------------------------
        elif event_type in (
            "payout.paid",
            "payout.failed",
            "payout.canceled"
        ):
            payout_id = object_data["id"]

            wd = db.query(Withdrawal).filter(
                Withdrawal.stripe_payout_id == payout_id
            ).first()

            if wd and wd.status not in ("success", "failed"):
                wallet = db.query(Wallet).filter(
                    Wallet.id == wd.wallet_id
                ).first()

                tx = db.query(WalletTransaction).filter(
                    WalletTransaction.reference == wd.reference
                ).first()

                if event_type == "payout.paid":
                    wd.status = "success"

                    if tx:
                        tx.status = "success"
                        tx.description = "Retrait réussi"

                else:
                    wd.status = "failed"
                    wd.payout_failure_message = object_data.get(
                        "failure_message"
                    )

                    if wallet:
                        wallet.pending -= wd.amount
                        wallet.available += wd.amount

                    if tx:
                        tx.status = "failed"
                        tx.description = "Retrait échoué"

                db.commit()

                merchant = db.query(UserDB).filter(
                    UserDB.id == wd.user_id
                ).first()

                if merchant and merchant.email:
                    if event_type == "payout.paid":
                        if is_notification_enabled(merchant, "virement.payout_success"):
                            send_payout_success_email(
                                merchant.email, wd.amount
                            )
                    else:
                        if is_notification_enabled(merchant, "virement.payout_failed"):
                            send_payout_failed_email(
                                merchant.email, wd.amount
                            )
        # --------------------------------------------------
        # FACTURES CONNECT
        # --------------------------------------------------
        elif event_type in (
            "invoice.paid",
            "invoice.payment_failed",
            "invoice.finalized",
            "invoice.voided",
        ):
            invoice_data = (
                object_data.to_dict()
                if hasattr(object_data, "to_dict")
                else dict(object_data)
            )

            if event_type == "invoice.paid":
                result = process_invoice_paid_event(
                    invoice_data=invoice_data,
                    connected_account_id=connected_account_id,
                    db=db,
                )

                logger.info(
                    "Traitement facture/abonnement Connect : %s",
                    result,
                )
            else:
                logger.info(
                    "Événement facture Connect : type=%s invoice_id=%s",
                    event_type,
                    invoice_data.get("id"),
                )
        # --------------------------------------------------
        # CYCLE DE VIE DES ABONNEMENTS CONNECT
        # --------------------------------------------------
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted"
        ):
            subscription_id = object_data["id"]
            subscription_status = object_data.status

            profile = None

            if connected_account_id:
                profile = db.query(Profile).filter(
                    Profile.stripe_account_id == connected_account_id
                ).first()

            logger.info(
                "Stripe subscription event: type=%s "
                "subscription_id=%s status=%s connected_account=%s",
                event_type,
                subscription_id,
                subscription_status,
                connected_account_id
            )

            if not connected_account_id or not profile:
                logger.warning(
                    "Compte Connect ou profil introuvable "
                    "pour l'abonnement %s",
                    subscription_id
                )

            # Relier ici l'événement à la notification d'abonnement
            # de Xepay. Un abonnement créé ou modifié ne signifie
            # pas nécessairement qu'un paiement a réussi.

        else:
            return {"status": "ignored", "event_type": event_type}

        return {"ok": True, "event_type": event_type}

    except Exception:
        db.rollback()
        logger.exception(
            "Erreur lors du traitement du webhook Stripe %s",
            event_type
        )
        raise HTTPException(
            status_code=500,
            detail="Erreur de traitement du webhook"
        )


@router.post("/stripe/account-session")
def create_account_session(
    db: Session = Depends(get_db),
    # Owner par défaut : ce widget permet de MODIFIER les informations
    # Stripe du compte (Paramètres > Entreprise > Informations sur votre
    # entreprise), pas seulement les consulter - configurable par le
    # owner du workspace (voir permission_service.CAPABILITY_DEFAULTS,
    # "manage_stripe_account_config"), jamais pour les autres workspaces.
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_account_config"))
):
    profile = db.query(Profile).filter(Profile.user_id == membership.workspace_id).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(status_code=404, detail="Compte Stripe introuvable")
    try:
        session = stripe.AccountSession.create(
            account=profile.stripe_account_id,
            components={
                "account_management": {
                    "enabled": True
                }
            }
        )
        return {
            "client_secret": session.client_secret
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=e.user_message or str(e))
    

def get_authorized_connect_profile(
    account_id: str,
    db: Session,
    membership: WorkspaceUser
):
    profile = db.query(Profile).filter(Profile.stripe_account_id == account_id,Profile.user_id == membership.workspace_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Compte Connect introuvable ou non autorisé")
    return profile

@router.post("/stripe/connect/{account_id}/account-session")
def create_connect_activity_session(
    account_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing"))
):
    get_authorized_connect_profile(account_id, db, membership)
    try:
        session = stripe.AccountSession.create(
            account=account_id,
            components={
                "payments": {
                    "enabled": True,
                    "features": {
                        "refund_management": True,
                        "dispute_management": True,
                        # Notre flux de paiement (backend/services/stripe_service.py)
                        # ne définit jamais capture_method="manual" : toutes les
                        # charges sont capturées automatiquement par Stripe, il
                        # n'existe donc aucune charge "non capturée" à traiter
                        # dans notre flux — ne pas activer une action qui ne
                        # correspond à aucun état réel chez nous.
                        "capture_payments": False
                    }
                },
                "payment_details": {
                    "enabled": True,
                    "features": {
                        "capture_payments": False
                    }
                },
                "payouts": {
                    "enabled": True,
                    "features": {
                        "standard_payouts": False,
                        "instant_payouts": False
                    }
                }
            }
        )
        return {
            "account_id": account_id,
            "client_secret": session.client_secret
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=e.user_message or str(e))

@router.post("/stripe/connect/invoices")
def create_merchant_invoice(
    data: ConnectInvoiceCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    price = stripe.Price.retrieve(
        data.price_id,
        stripe_account=profile.stripe_account_id,
    )

    amount = price.unit_amount * data.quantity
    # Commission dégressive par volume mensuel du marchand (voir
    # backend/services/commission_service.py), résolue AVANT la création de
    # cette facture pour qu'elle ne compte jamais dans son propre volume -
    # palier 0 (6%) par défaut pour un marchand neuf (anciennement fixé à
    # 1%, insuffisant : le StripeFee réel dépasse souvent ce taux sur ce
    # flux, ce qui faisait perdre de l'argent à la plateforme sur chaque
    # facture, voir process_invoice_paid_event). `amount` est déjà en
    # centimes (price.unit_amount) - contrairement au flux lien de paiement
    # (stripe_service.create_checkout_session), aucune conversion de devise
    # ultérieure ne dépend de ce calcul (voir process_invoice_paid_event qui
    # relit directement intent.application_fee_amount), donc aucun besoin de
    # dupliquer le taux dans une metadata ici.
    application_fee_amount = int(amount * commission_service.resolve_commission_rate(db, membership.workspace_id))

    try:
        invoice = create_connect_invoice(
            merchant_account=profile.stripe_account_id,
            customer_id=data.customer_id,
            price_id=data.price_id,
            quantity=data.quantity,
            collection_method=data.collection_method,
            days_until_due=data.days_until_due,
            application_fee_amount=application_fee_amount,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_invoice",
            },
        )

        return {
            "id": invoice.id,
            "object": invoice.object,
            "status": invoice.status,
            "customer": invoice.customer,
            "currency": invoice.currency,
            "amount_due": invoice.amount_due,
            "amount_paid": invoice.amount_paid,
            "collection_method": invoice.collection_method,
            "hosted_invoice_url": invoice.hosted_invoice_url,
            "invoice_pdf": invoice.invoice_pdf,
        }

    except stripe.error.StripeError as e:
        print(f"❌ ERREUR création facture (merchant={profile.stripe_account_id}): {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/invoices/{invoice_id}")
def update_merchant_invoice(
    invoice_id: str,
    data: ConnectInvoiceUpdateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    from datetime import datetime, timedelta, timezone

    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        current = stripe.Invoice.retrieve(
            invoice_id,
            stripe_account=profile.stripe_account_id,
        )
        # Seules les factures encore brouillon ou ouvertes (jamais payees/
        # annulees/irrecouvrables) peuvent etre modifiees chez Stripe.
        if current.status not in ("draft", "open"):
            raise HTTPException(
                status_code=400,
                detail=f"Facture non modifiable (statut actuel : {current.status})"
            )
        due_date = int(
            (datetime.now(timezone.utc) + timedelta(days=data.days_until_due)).timestamp()
        )
        invoice = stripe.Invoice.modify(
            invoice_id,
            due_date=due_date,
            stripe_account=profile.stripe_account_id,
        )
        return {"id": invoice.id, "due_date": invoice.due_date, "status": invoice.status}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/invoices/{invoice_id}/void")
def void_merchant_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        current = stripe.Invoice.retrieve(
            invoice_id,
            stripe_account=profile.stripe_account_id,
        )
        # Stripe distingue les deux cas : un brouillon se SUPPRIME
        # (Invoice.delete, jamais payé/finalisé donc rien à annuler), une
        # facture ouverte s'ANNULE (Invoice.void_invoice, passe à "void" -
        # jamais recouvrable, contrairement à "uncollectible").
        if current.status == "draft":
            stripe.Invoice.delete(
                invoice_id,
                stripe_account=profile.stripe_account_id,
            )
            return {"id": invoice_id, "status": "deleted"}
        elif current.status == "open":
            invoice = stripe.Invoice.void_invoice(
                invoice_id,
                stripe_account=profile.stripe_account_id,
            )
            return {"id": invoice.id, "status": invoice.status}
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Facture non annulable (statut actuel : {current.status})"
            )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/invoices")
def list_merchant_invoices(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        invoices = stripe.Invoice.list(
            limit=100,
            stripe_account=profile.stripe_account_id,
        )
        invoices_list = list(invoices.auto_paging_iter())
        emails_by_id = _emails_by_user_id(
            db, [i.metadata.to_dict() if i.metadata else {} for i in invoices_list]
        )
        result = []
        for invoice in invoices_list:
            invoice_data = invoice.to_dict()
            invoice_data["metadata"] = _enrich_metadata(
                invoice_data.get("metadata"), emails_by_id
            )
            result.append(invoice_data)
        return {
            "object": "list",
            "data": result,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/subscriptions")
def create_merchant_subscription(
    data: ConnectSubscriptionCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        metadata = {
            "user_id": str(membership.user_id),
            "workspace_id": str(membership.workspace_id),
            "customer_id": str(data.customer_id),
            "price_id": str(data.price_id),
            "quantity": str(data.quantity),
            "xepay_type": "merchant_subscription",
        }
        # Commission dégressive par volume mensuel du marchand (voir
        # backend/services/commission_service.py), résolue UNE SEULE FOIS
        # ici, à la création de l'abonnement - Stripe applique ensuite ce
        # même application_fee_percent à CHAQUE facture future générée
        # automatiquement par cet abonnement, sans recalcul possible par
        # cycle sans logique webhook supplémentaire (voir la limite connue
        # documentée dans le docstring du module commission_service). Le
        # taux de ce marchand n'est donc réévalué qu'à la création d'un
        # NOUVEL abonnement, pas à chaque renouvellement d'un abonnement
        # existant.
        commission_rate = commission_service.resolve_commission_rate(db, membership.workspace_id)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=data.customer_id,
            line_items=[
                {
                    "price": data.price_id,
                    "quantity": data.quantity,
                }
            ],
            metadata=metadata,
            subscription_data={
                "application_fee_percent": float(commission_rate * 100),
                "metadata": metadata,
            },
            success_url="https://alasdia.com/signup",
            cancel_url="https://alasdia.com/signup",
            stripe_account=profile.stripe_account_id,
        )
        return {
            "id": session.id,
            "url": session.url,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/subscriptions/{subscription_id}/cancel")
def cancel_merchant_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        # Annulation immediate (pas cancel_at_period_end) : Stripe arrete
        # aussitot de facturer, l'abonnement passe directement a "canceled".
        subscription = stripe.Subscription.cancel(
            subscription_id,
            stripe_account=profile.stripe_account_id,
        )
        return {"id": subscription.id, "status": subscription.status}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/subscriptions/{subscription_id}/quantity")
def update_merchant_subscription_quantity(
    subscription_id: str,
    data: ConnectSubscriptionQuantityUpdateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        current = stripe.Subscription.retrieve(
            subscription_id,
            stripe_account=profile.stripe_account_id,
        )
        item = current.items.data[0] if current.items.data else None
        if not item:
            raise HTTPException(
                status_code=400,
                detail="Aucun élément trouvé sur cet abonnement"
            )
        subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{"id": item.id, "quantity": data.quantity}],
            stripe_account=profile.stripe_account_id,
        )
        return {"id": subscription.id, "quantity": subscription.items.data[0].quantity}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/subscriptions")
def list_merchant_subscriptions(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        # status="all" : par défaut, Stripe exclut les abonnements annulés
        # de la liste — nécessaire ici pour que les KPI "Annulés"/"Tout" de
        # la sous-vue Abonnements comptent des valeurs réelles.
        subscriptions = stripe.Subscription.list(
            limit=100,
            status="all",
            stripe_account=profile.stripe_account_id,
        )
        subscriptions_list = list(subscriptions.auto_paging_iter())

        # price.product n'est jamais expand par defaut (juste l'ID en
        # string) - un Product.retrieve par ID UNIQUE (pas par abonnement)
        # pour afficher le nom du produit concerne sans multiplier les
        # appels Stripe si plusieurs abonnements partagent le meme produit.
        product_ids = {
            sub.items.data[0].price.product
            for sub in subscriptions_list
            if sub.items.data and sub.items.data[0].price
        }
        product_names = {}
        for product_id in product_ids:
            try:
                product_names[product_id] = stripe.Product.retrieve(
                    product_id,
                    stripe_account=profile.stripe_account_id,
                ).name
            except stripe.error.StripeError:
                product_names[product_id] = None

        result = []
        for subscription in subscriptions_list:
            sub_data = subscription.to_dict()
            product_id = (
                subscription.items.data[0].price.product
                if subscription.items.data and subscription.items.data[0].price
                else None
            )
            sub_data["product_name"] = product_names.get(product_id)
            result.append(sub_data)

        return {
            "object": "list",
            "data": result,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/customers")
def create_merchant_customer(
    data: ConnectCustomerCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        customer = create_connect_customer(
            merchant_account=profile.stripe_account_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            country=data.country,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_customer",
            },
        )
        return {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/customers/{customer_id}")
def update_merchant_customer(
    customer_id: str,
    data: ConnectCustomerCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        customer = update_connect_customer(
            merchant_account=profile.stripe_account_id,
            customer_id=customer_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            country=data.country,
        )
        return {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

def _emails_by_user_id(db: Session, metadata_dicts: list[dict]) -> dict[str, str]:
    """Resout en un seul aller-retour DB les emails des user_id/workspace_id/
    merchant_id presents dans une liste de metadata Stripe (ce sont tous des
    ID UserDB, workspace_id = l'ID du compte proprietaire - voir
    WorkspaceUser) - pour enrichir l'affichage "qui a cree / quel workspace /
    quel marchand" sans un aller-retour par ligne (customer_id, product_id,
    etc.)."""
    ids = {
        metadata.get("user_id") for metadata in metadata_dicts if metadata
    } | {
        metadata.get("workspace_id") for metadata in metadata_dicts if metadata
    } | {
        metadata.get("merchant_id") for metadata in metadata_dicts if metadata
    }
    ids.discard(None)
    if not ids:
        return {}
    users = db.query(UserDB).filter(UserDB.id.in_(ids)).all()
    return {user.id: user.email for user in users}

def _enrich_metadata(metadata: dict | None, emails_by_id: dict[str, str]) -> dict | None:
    """Remplace user_id/workspace_id/merchant_id par "<id> (email)" quand
    l'email est connu - ne modifie rien d'autre (xepay_type, etc. restent
    tels quels)."""
    if not metadata:
        return metadata
    enriched = dict(metadata)
    for key in ("user_id", "workspace_id", "merchant_id"):
        value = enriched.get(key)
        if value and value in emails_by_id:
            enriched[key] = f"{value} ({emails_by_id[value]})"
    return enriched

@router.get("/stripe/connect/customers")
def list_merchant_customers(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()

    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )

    stripe_account = profile.stripe_account_id

    try:
        customers = stripe.Customer.list(
            limit=100,
            stripe_account=stripe_account,
        )

        emails_by_id = _emails_by_user_id(
            db, [c.metadata.to_dict() if c.metadata else {} for c in customers.data]
        )

        result = []

        for customer in customers.data:

            # ==========================================
            # MOYEN DE PAIEMENT PRINCIPAL
            # ==========================================

            default_payment_method = (
                customer.invoice_settings.default_payment_method
            )

            payment_method_data = None

            if default_payment_method:

                payment_method_id = (
                    default_payment_method.id
                    if hasattr(default_payment_method, "id")
                    else default_payment_method
                )

                payment_method = stripe.PaymentMethod.retrieve(
                    payment_method_id,
                    stripe_account=stripe_account,
                )

                payment_method_data = {
                    "id": payment_method.id,
                    "type": payment_method.type,
                }

                if payment_method.type == "card" and payment_method.card:
                    payment_method_data["card"] = {
                        "brand": payment_method.card.brand,
                        "last4": payment_method.card.last4,
                        "exp_month": payment_method.card.exp_month,
                        "exp_year": payment_method.card.exp_year,
                    }

            # ==========================================
            # PAIEMENTS DU CLIENT
            # ==========================================

            charges = stripe.Charge.list(
                customer=customer.id,
                limit=100,
                stripe_account=stripe_account,
            )

            total_spent = 0
            payments_count = 0
            refunds_total = 0
            disputes_total = 0
            last_payment_at = None

            for charge in charges.data:

                # Paiement réussi
                if charge.paid and not charge.refunded:
                    total_spent += charge.amount
                    payments_count += 1

                # Si le paiement a été partiellement remboursé,
                # on conserve le montant réellement encaissé.
                elif charge.paid:
                    total_spent += (
                        charge.amount - charge.amount_refunded
                    )

                    payments_count += 1

                # Remboursements
                refunds_total += charge.amount_refunded or 0

                # Litiges
                if charge.disputed:
                    disputes_total += charge.amount

                # Dernier paiement réussi
                if charge.paid:
                    if (
                        last_payment_at is None
                        or charge.created > last_payment_at
                    ):
                        last_payment_at = charge.created

            # ==========================================
            # PAYS
            # ==========================================

            country = None

            if customer.address:
                country = customer.address.country
            # ==========================================
            # CLIENT ENRICHI
            # ==========================================
            result.append({
                "id": customer.id,
                "object": customer.object,

                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,

                "created": customer.created,
                "currency": customer.currency,
                "description": customer.description,
                "delinquent": customer.delinquent,
                # Positif = le client doit ce montant sur sa prochaine
                # facture ("solde restant") ; négatif = crédit. Utilisé par
                # le KPI "Soldes restants" de la sous-vue Clients.
                "balance": customer.balance,

                "address": customer.address,
                "shipping": customer.shipping,

                "country": country,

                "invoice_prefix": customer.invoice_prefix,
                "invoice_settings": customer.invoice_settings,

                "metadata": _enrich_metadata(
                    customer.metadata.to_dict() if customer.metadata else {},
                    emails_by_id,
                ),
                "tax_exempt": customer.tax_exempt,
                "preferred_locales": customer.preferred_locales,

                "default_payment_method": payment_method_data,
                "total_spent": total_spent,
                "payments_count": payments_count,
                "refunds_total": refunds_total,
                "disputes_total": disputes_total,
                "last_payment_at": last_payment_at,
            })

        return {
            "object": "list",
            "data": result,
            "has_more": customers.has_more,
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/products")
def list_merchant_products(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    stripe_account = profile.stripe_account_id
    try:
        products = stripe.Product.list(
            limit=100,
            stripe_account=stripe_account,
        )
        products_list = list(products.auto_paging_iter())
        emails_by_id = _emails_by_user_id(
            db, [p.metadata.to_dict() if p.metadata else {} for p in products_list]
        )
        result = []
        for product in products_list:
            prices = stripe.Price.list(
                product=product.id,
                limit=100,
                stripe_account=stripe_account,
            )
            product_data = product.to_dict()
            product_data["metadata"] = _enrich_metadata(
                product_data.get("metadata"), emails_by_id
            )
            product_data["prices"] = [
                price.to_dict()
                for price in prices.auto_paging_iter()
            ]
            result.append(product_data)
        return {
            "object": "list",
            "data": result,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/products")
def create_merchant_product(
    data: ConnectProductCreateRequest,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        product, price = create_connect_product(
            merchant_account=profile.stripe_account_id,
            name=data.name,
            description=data.description,
            unit_amount=data.unit_amount,
            currency=data.currency,
            recurring=data.recurring,
            interval=data.interval,
            interval_count=data.interval_count,
            metadata={
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "xepay_type": "merchant_product",
            },
        )
        return {
            "product": {
                "id": product.id,
                "name": product.name,
            },
            "price": {
                "id": price.id,
                "unit_amount": price.unit_amount,
                "currency": price.currency,
                "recurring": price.recurring,
            },
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

def _set_merchant_product_active(
    product_id: str,
    active: bool,
    db: Session,
    membership: WorkspaceUser,
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        product = stripe.Product.modify(
            product_id,
            active=active,
            stripe_account=profile.stripe_account_id,
        )
        # Les tarifs restent utilisables indefiniment chez Stripe meme si le
        # produit est archive (ils ne sont pas lies automatiquement) : on
        # les desactive/reactive avec le produit pour qu'un produit archive
        # ne reste pas selectionnable dans un nouvel abonnement/facture.
        prices = stripe.Price.list(
            product=product_id,
            limit=100,
            stripe_account=profile.stripe_account_id,
        )
        for price in prices.auto_paging_iter():
            if price.active != active:
                stripe.Price.modify(
                    price.id,
                    active=active,
                    stripe_account=profile.stripe_account_id,
                )
        return {"id": product.id, "active": product.active}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.post("/stripe/connect/products/{product_id}/archive")
def archive_merchant_product(
    product_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    return _set_merchant_product_active(product_id, False, db, membership)

@router.post("/stripe/connect/products/{product_id}/unarchive")
def unarchive_merchant_product(
    product_id: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    return _set_merchant_product_active(product_id, True, db, membership)

@router.get("/stripe/connect/payment-methods")
def list_merchant_payment_methods(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    try:
        configurations = stripe.PaymentMethodConfiguration.list(
            limit=100,
            stripe_account=profile.stripe_account_id,
        )
        return {
            "object": configurations.object,
            "data": [
                configuration.to_dict()
                for configuration in configurations.auto_paging_iter()
            ],
        }
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )

@router.get("/stripe/connect/risk")
def list_merchant_risk(
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_capability("manage_stripe_billing")),
):
    """Vue Risque complète pour le compte connecté. Un Dispute (litige) ne
    représente qu'une contestation déjà déposée par la banque du client -
    un évènement tardif et rare. Le niveau de risque de fraude réel
    (visible dans le Dashboard Stripe) vient de sources distinctes, jamais
    interrogées auparavant ici, d'où une vue vide pour des comptes
    pourtant signalés à risque élevé côté Stripe :
    - Radar Early Fraud Warning : la banque émettrice signale une charge
      comme probablement frauduleuse, souvent bien avant qu'un Dispute
      ne soit (ou soit jamais) déposé.
    - Charge.outcome.risk_level/risk_score : l'évaluation Radar propre à
      CHAQUE charge (confirmé : coexiste avec disputed=False). risk_score
      n'existe que pour les charges par carte (confirmé sur de vraies
      charges : absent - pas juste null - pour cashapp ; outcome entier
      absent pour les paiements par lien, voir ci-dessous).
    - Account.requirements/future_requirements : restrictions côté
      plateforme pouvant découler d'une revue de risque Stripe
      (disabled_reason, errors).

    Pas de score de risque global (ex: le 74/100 du Dashboard) : aucune
    API publique ne l'expose. Les seules API "Account Signals/
    Evaluations" (preview, 2026-08-26) couvrent un sujet différent
    (partage de compte/multi-comptes) et exigent d'envoyer ses propres
    données d'activité - jamais une simple lecture d'un score existant.

    stripe.Charge.list(stripe_account=...) mélange deux natures de
    charges bien distinctes, toutes deux object="charge" (vérifié - ce
    ne sont jamais des objets invalides) :
    - les vraies charges directes (factures/abonnements : carte, cashapp)
      - seules celles-ci ont une évaluation de risque exploitable.
    - le miroir, côté compte connecté, du règlement d'un paiement par
      lien (destination charge) : payment_method_details.type ==
      "stripe_account", source_transfer renseigné, outcome TOUJOURS None
      (vérifié sur un vrai paiement) - aucune évaluation de risque n'a
      jamais lieu sur cette entrée, la vraie charge (avec risque) vit
      sur la PLATEFORME, jamais sur ce compte connecté. Exclues d'abord,
      puis complétées via Payment.charge_id (lien = pas de
      stripe_account, charge sur la plateforme)."""
    profile = db.query(Profile).filter(
        Profile.user_id == membership.workspace_id
    ).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(
            status_code=404,
            detail="Compte Stripe introuvable"
        )
    stripe_account = profile.stripe_account_id
    try:
        disputes = stripe.Dispute.list(limit=100, stripe_account=stripe_account)
        disputes_data = [d.to_dict() for d in disputes.auto_paging_iter()]

        early_fraud_warnings = stripe.radar.EarlyFraudWarning.list(
            limit=100, stripe_account=stripe_account
        )
        early_fraud_warnings_data = [
            efw.to_dict() for efw in early_fraud_warnings.auto_paging_iter()
        ]

        # Charges directes (factures/abonnements) : exclut les miroirs de
        # paiement par lien (payment_method_details.type ==
        # "stripe_account", jamais de vrai outcome - voir docstring).
        direct_charges = stripe.Charge.list(limit=100, stripe_account=stripe_account)
        charges_risk_data = [
            {
                "id": c.id,
                "amount": c.amount,
                "currency": c.currency,
                "created": c.created,
                "disputed": c.disputed,
                "outcome": c.outcome.to_dict() if c.outcome else None,
            }
            for c in direct_charges.auto_paging_iter()
            if not (
                c.payment_method_details
                and c.payment_method_details.type == "stripe_account"
            )
        ]

        # Paiements par lien (destination charge) : la vraie charge, avec
        # son évaluation de risque, vit sur la PLATEFORME - jamais
        # stripe_account= ici. Retrouvée via Payment.charge_id (déjà
        # stocké à la création du paiement), pas via stripe_account=.
        link_payments = (
            db.query(Payment)
            .filter(
                Payment.user_id == membership.workspace_id,
                Payment.link_id.isnot(None),
                Payment.charge_id.isnot(None),
            )
            .order_by(Payment.created_at.desc())
            .limit(100)
            .all()
        )
        for p in link_payments:
            try:
                c = stripe.Charge.retrieve(p.charge_id)
            except stripe.error.StripeError as e:
                print(f"⚠️ Charge.retrieve (risque, lien) a échoué pour {p.charge_id}: {e}")
                continue
            charges_risk_data.append({
                "id": c.id,
                "amount": c.amount,
                "currency": c.currency,
                "created": c.created,
                "disputed": c.disputed,
                "outcome": c.outcome.to_dict() if c.outcome else None,
            })

        account = stripe.Account.retrieve(stripe_account)
        account_status = {
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
            "requirements": account.requirements.to_dict() if account.requirements else None,
            "future_requirements": account.future_requirements.to_dict() if account.future_requirements else None,
        }

        return {
            "disputes": disputes_data,
            "early_fraud_warnings": early_fraud_warnings_data,
            "charges_risk": charges_risk_data,
            "account_status": account_status,
        }
    except stripe.error.StripeError as e:
        print(f"❌ ERREUR récupération risque (merchant={stripe_account}): {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=400,
            detail=e.user_message or str(e)
        )