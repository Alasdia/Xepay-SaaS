"""Webhook Verto - architecture "Zero-Custody" des retraits (voir
services/verto_service.py, routes/payout.py, routes/verto.py). Gère 4
transitions : approbation/rejet du sous-compte à l'onboarding (création
du wallet USD + récupération de ses coordonnées), puis "Wallet Credit"
quand le Payout Stripe atterrit (lance le virement vers la banque locale
UEMOA), puis la confirmation finale de ce virement. Gère aussi la
vérification automatique du rechargement de carte Issuing (voir plus bas).

AVERTISSEMENT : les noms exacts des types d'événements et la forme du
payload JSON ci-dessous ne sont PAS confirmés par la doc publique Verto
(seuls les libellés "Wallet Credit - Success" / "Inbound Bank Payments -
Completed/Requested/Disputed" ont été trouvés, sans schéma détaillé) - à
valider/ajuster contre un vrai événement sandbox avant mise en prod.

Pour les paiements entrants précisément (micro-dépôts Stripe, voir
bloc dédié plus bas) : la forme du payload EST confirmée par
docs.verto.co/docs/inbound-funds (champs amount/state/currency/walletId
imbriqués sous une clé "payload"), mais le nom exact du type d'événement
à écouter pour CE cas précis (distinct de "wallet.credit" ci-dessous) ne
l'est pas - à confirmer avec les "Webhook delivery logs" de Verto en
sandbox avant mise en prod réelle."""

import logging
import uuid

import stripe
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Profile, Withdrawal, Wallet, WalletTransaction, UserDB
from backend.services import verto_service, stripe_issuing_service
from backend.services.email_service import (
    send_payout_success_email,
    send_payout_failed_email,
    is_notification_enabled,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/verto")
async def verto_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    # Les paiements entrants (docs.verto.co/docs/inbound-funds) imbriquent
    # companyId sous "payload", contrairement aux autres events de ce
    # fichier qui l'ont au premier niveau - les trois formes sont donc
    # vérifiées, dans cet ordre.
    company_id = (
        payload.get("companyId")
        or payload.get("data", {}).get("companyId")
        or (payload.get("payload") or {}).get("companyId")
    )
    if not company_id:
        raise HTTPException(status_code=400, detail="companyId manquant")

    if not verto_service.verify_webhook_signature(dict(request.headers), str(company_id)):
        raise HTTPException(status_code=400, detail="Signature invalide")

    event_type = payload.get("eventType") or payload.get("type")

    profile = db.query(Profile).filter(Profile.verto_company_id == str(company_id)).first()
    if not profile:
        logger.warning("Webhook Verto reçu pour un company_id inconnu: %s", company_id)
        return {"ok": True}

    # --------------------------------------------------
    # ONBOARDING APPROUVÉ : crée le wallet USD + récupère ses coordonnées
    # bancaires receveuses, pour affichage dans l'UI Xepay (voir
    # routes/verto.py, GET /verto/status) - le marchand les colle ensuite
    # lui-même dans son Dashboard Stripe Express.
    # --------------------------------------------------
    if event_type in ("company.approved", "COMPANY_APPROVED") or payload.get("companyStatus") == "APPROVED":
        try:
            wallet = verto_service.create_wallet(str(company_id), currency="USD")
            profile.verto_wallet_id = str(wallet["id"])
            funding = verto_service.get_usd_funding_details(str(company_id), str(wallet["id"]))
            if funding.get("fundsType") not in ("SEGERATED", "SEGREGATED"):
                logger.warning(
                    "Wallet Verto %s en fundsType=%s (pas dédié) pour profile %s",
                    wallet["id"], funding.get("fundsType"), profile.id,
                )
            profile.verto_usd_account_number = funding.get("accountNumber")
            profile.verto_usd_bank_code = funding.get("bankCode")
            profile.verto_usd_bank_name = funding.get("bankName")
            profile.verto_onboarding_status = "approved"
            db.commit()
        except Exception:
            logger.exception("Echec création wallet/funding details Verto pour company %s", company_id)
        return {"ok": True}

    if event_type in ("company.rejected", "COMPANY_REJECTED") or payload.get("companyStatus") == "REJECTED":
        profile.verto_onboarding_status = "rejected"
        db.commit()
        return {"ok": True}

    # --------------------------------------------------
    # VÉRIFICATION AUTO DU RECHARGEMENT DE CARTE ISSUING : les 2 micro-
    # dépôts envoyés par Stripe (voir POST /issuing/bank-link) arrivent sur
    # ce même wallet Verto - on les capture ici par leur montant (toujours
    # < 1$), jamais vus par le marchand (son wallet n'a pas de relevé).
    # Payload confirmé par docs.verto.co/docs/inbound-funds : champs
    # imbriqués sous "payload" (id/amount/state/currency/walletId), state
    # "requested" dès réception (pas besoin d'attendre "completed" pour
    # connaître le montant). Vérifié AVANT le routage event_type générique
    # ci-dessous car la forme (imbriquée sous "payload") diffère des autres
    # events de ce fichier.
    # --------------------------------------------------
    inbound = payload.get("payload")
    if (
        isinstance(inbound, dict)
        and inbound.get("state") in ("requested", "REQUESTED")
        and str(inbound.get("walletId") or "") == str(profile.verto_wallet_id or "")
        and (inbound.get("currency") or "").upper() == "USD"
        and profile.stripe_issuing_bank_status == "pending_verification"
    ):
        try:
            amount_cents = int(round(float(inbound.get("amount", "0")) * 100))
        except (TypeError, ValueError):
            amount_cents = 0

        # Les micro-dépôts Stripe sont toujours < 1$ - un vrai dépôt (ex:
        # virement Payout Stripe) ne doit jamais être pris pour l'un
        # d'eux, même pendant la fenêtre de vérification.
        if 0 < amount_cents < 100:
            pending = list(profile.stripe_issuing_bank_pending_amounts or [])
            pending.append(amount_cents)
            profile.stripe_issuing_bank_pending_amounts = pending

            if len(pending) >= 2:
                try:
                    stripe_issuing_service.verify_issuing_bank_source(
                        profile.stripe_issuing_account_id,
                        profile.stripe_issuing_bank_source_id,
                        pending[:2],
                    )
                    profile.stripe_issuing_bank_status = "verified"
                except stripe.error.StripeError:
                    logger.exception(
                        "Echec vérification source bancaire Issuing pour profile %s", profile.id
                    )
                    profile.stripe_issuing_bank_status = "failed"
                profile.stripe_issuing_bank_pending_amounts = []

            db.commit()
        return {"ok": True}

    # --------------------------------------------------
    # LEG 1 CONFIRMÉ : le Payout Stripe a atterri sur le wallet USD Verto
    # --------------------------------------------------
    if event_type in ("wallet.credit", "WALLET_CREDIT"):
        wd = (
            db.query(Withdrawal)
            .filter(Withdrawal.user_id == profile.user_id, Withdrawal.status == "stripe_sent")
            .order_by(Withdrawal.created_at.desc())
            .first()
        )
        if not wd:
            logger.warning("Wallet Credit Verto sans Withdrawal en attente pour user %s", profile.user_id)
            return {"ok": True}

        if not profile.beneficiary_bank_iban or not profile.verto_beneficiary_id:
            logger.error("Profile %s sans bénéficiaire Verto enregistré - virement impossible", profile.id)
            return {"ok": True}

        try:
            purposes = verto_service.list_payment_purpose_codes(
                payment_direction="Outbound", currency="XOF", mode="LOCAL"
            )
            if not purposes:
                raise ValueError("Aucun purposeId Outbound/XOF renvoyé par Verto")
            # Choix du premier code disponible - NON VÉRIFIÉ qu'il n'y a
            # qu'un seul motif pertinent pour un retrait marchand ; si
            # plusieurs reviennent, il faudra choisir explicitement lequel
            # correspond (ex: "merchant settlement"/"supplier payment").
            purpose_id = purposes[0]["id"]

            result = verto_service.create_payment_request(
                beneficiary_id=int(profile.verto_beneficiary_id),
                purpose_id=purpose_id,
                amount_usd=wd.amount,
                wallet_id=int(profile.verto_wallet_id),
                client_reference=wd.reference,
                payment_id=str(uuid.uuid4()),
            )
        except Exception:
            logger.exception("Echec create_payment_request Verto pour withdrawal %s", wd.id)
            return {"ok": True}

        wd.verto_transfer_id = str(result.get("id") or result.get("paymentId") or "")
        wd.status = "verto_sent"
        db.commit()
        return {"ok": True}

    # --------------------------------------------------
    # LEG 2 TERMINÉ : virement bancaire local reçu ou échoué
    # --------------------------------------------------
    if event_type in ("payment.completed", "payment.failed", "PAYMENT_COMPLETED", "PAYMENT_FAILED"):
        transfer_id = str(payload.get("id") or payload.get("data", {}).get("id") or "")
        wd = db.query(Withdrawal).filter(Withdrawal.verto_transfer_id == transfer_id).first()
        if not wd or wd.status in ("success", "failed"):
            return {"ok": True}

        wallet = db.query(Wallet).filter(Wallet.id == wd.wallet_id).first()
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == wd.reference).first()
        merchant = db.query(UserDB).filter(UserDB.id == wd.user_id).first()

        if event_type in ("payment.completed", "PAYMENT_COMPLETED"):
            wd.status = "success"
            if tx:
                tx.status = "success"
                tx.description = "Retrait réussi"
            if merchant and merchant.email and is_notification_enabled(merchant, "virement.payout_success"):
                send_payout_success_email(merchant.email, wd.amount)
        else:
            wd.status = "failed"
            if wallet:
                wallet.pending -= wd.amount
                wallet.available += wd.amount
            if tx:
                tx.status = "failed"
                tx.description = "Retrait échoué"
            if merchant and merchant.email and is_notification_enabled(merchant, "virement.payout_failed"):
                send_payout_failed_email(merchant.email, wd.amount)

        db.commit()
        return {"ok": True}

    return {"ok": True}
