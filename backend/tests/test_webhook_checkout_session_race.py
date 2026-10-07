import json
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import Profile, UserDB, Wallet, WalletTransaction, Payment

# backend/routes/__init__.py ouvre une vraie connexion réseau à la base de
# prod (engine.connect()) au moment même de l'import du package — neutralisé
# le temps du seul import, sans toucher au fichier de prod (même technique
# que backend/tests/test_detail_endpoints.py).
import backend.database as _database


class _NullConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return None


_real_engine_connect = _database.engine.connect
_database.engine.connect = lambda *a, **kw: _NullConnection()
try:
    import backend.routes.webhook.paiement as paiement_module
finally:
    _database.engine.connect = _real_engine_connect

process_checkout_session_payment = paiement_module.process_checkout_session_payment
MAX_ATTEMPTS = paiement_module.MAX_SETTLEMENT_ATTEMPTS

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)

# La fonction utilise SessionLocal() directement (pas Depends(get_db)) : on
# remplace la référence que le module a importée pour pointer vers une base
# SQLite de test isolée, sans toucher au fichier de prod.
paiement_module.SessionLocal = TestingSessionLocal


class FakeCharge:
    """Stand-in minimal pour un Charge Stripe : seuls .id et .to_dict() sont
    lus par _fetch_settled_charge_data/process_checkout_session_payment.
    application_fee/transfer paramétrables pour simuler leur délai de
    propagation (observé en prod, y compris sur carte classique)."""

    def __init__(
        self,
        charge_id="ch_test_123",
        payment_method_details=None,
        application_fee=None,
        transfer=None,
        payment_method="pm_123",
    ):
        self.id = charge_id
        self._payment_method_details = payment_method_details or {
            "type": "card",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 1, "exp_year": 2030},
        }
        self._application_fee = application_fee
        self._transfer = transfer
        self._payment_method = payment_method

    def to_dict(self):
        return {
            "payment_method_details": self._payment_method_details,
            "application_fee": self._application_fee,
            "transfer": self._transfer,
            "payment_method": self._payment_method,
        }


def make_balance_tx(amount_cents=10000, fee_cents=100):
    bt = MagicMock()
    bt.amount = amount_cents
    bt.fee = fee_cents
    bt.available_on = int(datetime.now(timezone.utc).timestamp())
    return bt


def make_balance_tx_list(*transactions):
    """Stand-in pour le ListObject renvoyé par stripe.BalanceTransaction.list()
    (seul .data est lu)."""
    result = MagicMock()
    result.data = list(transactions)
    return result


def make_transfer(amount_cents=9400, destination="acct_merchant_1", reversed_=False, created=None):
    t = MagicMock()
    t.amount = amount_cents
    t.destination = destination
    t.reversed = reversed_
    t.created = created or int(datetime.now(timezone.utc).timestamp())
    return t


def make_fee(amount_cents=600):
    f = MagicMock()
    f.amount = amount_cents
    return f


def seed_merchant():
    db = TestingSessionLocal()
    merchant = UserDB(email=f"merchant-{uuid.uuid4().hex}@example.com", password="x")
    db.add(merchant)
    db.flush()
    db.add(Wallet(user_id=merchant.id, balance=0))
    db.add(Profile(user_id=merchant.id, stripe_account_id="acct_123"))
    db.commit()
    merchant_id = merchant.id
    db.close()
    return merchant_id


class TestProcessCheckoutSessionPaymentRace(unittest.TestCase):
    def setUp(self):
        self.merchant_id = seed_merchant()
        self.session_dict = {
            "id": "cs_test_123",
            "currency": "xof",
            "customer_details": {"email": "client@example.com"},
        }

    @patch("backend.routes.webhook.paiement.time.sleep")
    @patch("backend.routes.webhook.paiement.send_webhook_event")
    @patch("backend.routes.webhook.paiement.send_merchant_notification")
    @patch("backend.routes.webhook.paiement.send_payment_email")
    @patch("backend.routes.webhook.paiement.generate_invoice_pdf")
    @patch("backend.routes.webhook.paiement.stripe.BalanceTransaction.list")
    @patch("backend.routes.webhook.paiement.stripe.Charge.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    def test_dedup_skips_without_any_stripe_call(
        self, mock_pi_retrieve, mock_charge_retrieve, mock_bt_list,
        mock_pdf, mock_email, mock_merchant_email, mock_webhook_event, mock_sleep,
    ):
        db = TestingSessionLocal()
        db.add(WalletTransaction(
            user_id=self.merchant_id, wallet_id="wa_x", type="deposit",
            direction="in", amount=100, status="success", reference="pi_dup",
        ))
        db.commit()
        db.close()

        process_checkout_session_payment(
            self.session_dict, self.merchant_id, "lk_1", "pi_dup", "pi_dup", "checkout.session.completed",
        )

        mock_pi_retrieve.assert_not_called()
        mock_charge_retrieve.assert_not_called()
        mock_bt_list.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("backend.routes.webhook.paiement.time.sleep")
    @patch("backend.routes.webhook.paiement.send_webhook_event")
    @patch("backend.routes.webhook.paiement.send_merchant_notification")
    @patch("backend.routes.webhook.paiement.send_payment_email")
    @patch("backend.routes.webhook.paiement.generate_invoice_pdf")
    @patch("backend.routes.webhook.paiement.stripe.Transfer.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.ApplicationFee.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.BalanceTransaction.list")
    @patch("backend.routes.webhook.paiement.stripe.Charge.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    def test_card_payment_resolves_in_one_attempt_when_everything_available(
        self, mock_pi_retrieve, mock_charge_retrieve, mock_bt_list,
        mock_fee_retrieve, mock_transfer_retrieve,
        mock_pdf, mock_email, mock_merchant_email, mock_webhook_event, mock_sleep,
    ):
        """Cas nominal : balance_transaction, application_fee et transfer
        tous disponibles dès le premier essai -> un seul appel à chaque
        méthode Stripe, aucun sleep."""
        mock_pi_retrieve.return_value = MagicMock(latest_charge="ch_card_1")
        mock_charge_retrieve.return_value = FakeCharge(
            charge_id="ch_card_1",
            payment_method_details={
                "type": "card",
                "card": {"brand": "visa", "last4": "4242", "exp_month": 1, "exp_year": 2030},
            },
            application_fee="fee_1",
            transfer="tr_1",
        )
        mock_bt_list.return_value = make_balance_tx_list(make_balance_tx(amount_cents=10000))
        mock_fee_retrieve.return_value = make_fee(amount_cents=600)
        mock_transfer_retrieve.return_value = make_transfer(amount_cents=9400)

        process_checkout_session_payment(
            self.session_dict, self.merchant_id, "lk_1", "pi_card", "pi_card", "checkout.session.completed",
        )

        mock_charge_retrieve.assert_called_once_with("ch_card_1")
        mock_bt_list.assert_called_once_with(source="ch_card_1", limit=1)
        mock_sleep.assert_not_called()
        mock_webhook_event.assert_called_once()

        db = TestingSessionLocal()
        payment = db.query(Payment).filter(Payment.stripe_payment_intent_id == "pi_card").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.fee_amount, 6.0)
        self.assertEqual(payment.transfer_amount, 94.0)
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == "pi_card").first()
        self.assertEqual(tx.status, "success")
        db.close()

    @patch("backend.routes.webhook.paiement.time.sleep")
    @patch("backend.routes.webhook.paiement.send_webhook_event")
    @patch("backend.routes.webhook.paiement.send_merchant_notification")
    @patch("backend.routes.webhook.paiement.send_payment_email")
    @patch("backend.routes.webhook.paiement.generate_invoice_pdf")
    @patch("backend.routes.webhook.paiement.stripe.Transfer.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.ApplicationFee.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.BalanceTransaction.list")
    @patch("backend.routes.webhook.paiement.stripe.Charge.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    def test_link_payment_retries_until_fee_and_transfer_propagate(
        self, mock_pi_retrieve, mock_charge_retrieve, mock_bt_list,
        mock_fee_retrieve, mock_transfer_retrieve,
        mock_pdf, mock_email, mock_merchant_email, mock_webhook_event, mock_sleep,
    ):
        """Reproduit le constat réel (Link) : balance_transaction disponible
        dès le 1er essai, mais application_fee/transfer n'apparaissent sur le
        Charge qu'au 3e essai -> la tâche de fond doit retenter plutôt que
        d'enregistrer fee_amount/transfer_amount à None alors qu'ils
        existent déjà chez Stripe."""
        mock_pi_retrieve.return_value = MagicMock(latest_charge="ch_link_1")
        not_yet = FakeCharge(
            charge_id="ch_link_1",
            payment_method_details={"type": "link", "link": {"country": "US"}},
            application_fee=None,
            transfer=None,
        )
        settled = FakeCharge(
            charge_id="ch_link_1",
            payment_method_details={"type": "link", "link": {"country": "US"}},
            application_fee="fee_link_1",
            transfer="tr_link_1",
        )
        mock_charge_retrieve.side_effect = [not_yet, not_yet, settled]
        mock_bt_list.return_value = make_balance_tx_list(make_balance_tx(amount_cents=4500))
        mock_fee_retrieve.return_value = make_fee(amount_cents=270)
        mock_transfer_retrieve.return_value = make_transfer(amount_cents=4230)

        process_checkout_session_payment(
            self.session_dict, self.merchant_id, "lk_1", "pi_link", "pi_link", "checkout.session.completed",
        )

        self.assertEqual(mock_charge_retrieve.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_webhook_event.assert_called_once()

        db = TestingSessionLocal()
        payment = db.query(Payment).filter(Payment.stripe_payment_intent_id == "pi_link").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.fee_amount, 2.7)
        self.assertEqual(payment.transfer_amount, 42.3)
        db.close()

    @patch("backend.routes.webhook.paiement.time.sleep")
    @patch("backend.routes.webhook.paiement.send_webhook_event")
    @patch("backend.routes.webhook.paiement.send_merchant_notification")
    @patch("backend.routes.webhook.paiement.send_payment_email")
    @patch("backend.routes.webhook.paiement.generate_invoice_pdf")
    @patch("backend.routes.webhook.paiement.stripe.BalanceTransaction.list")
    @patch("backend.routes.webhook.paiement.stripe.Charge.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    def test_retries_until_balance_transaction_itself_propagates(
        self, mock_pi_retrieve, mock_charge_retrieve, mock_bt_list,
        mock_pdf, mock_email, mock_merchant_email, mock_webhook_event, mock_sleep,
    ):
        """Reproduit le constat réel (carte classique) : balance_transaction
        absent aux 2 premiers essais, disponible à partir du 3e -> ne doit
        plus être traité comme un abandon définitif (c'était le bug). Le
        Charge par défaut n'expose pas application_fee/transfer : la boucle
        continue donc jusqu'à MAX_SETTLEMENT_ATTEMPTS, mais le paiement est
        bien enregistré grâce au balance_transaction récupéré dès le 3e essai."""
        mock_pi_retrieve.return_value = MagicMock(latest_charge="ch_999")
        mock_charge_retrieve.return_value = FakeCharge(charge_id="ch_999")
        found = make_balance_tx_list(make_balance_tx(amount_cents=10000))
        mock_bt_list.side_effect = [make_balance_tx_list(), make_balance_tx_list()] + [found] * (MAX_ATTEMPTS - 2)

        process_checkout_session_payment(
            self.session_dict, self.merchant_id, "lk_1", "pi_999", "pi_999", "checkout.session.completed",
        )

        self.assertEqual(mock_bt_list.call_count, MAX_ATTEMPTS)
        mock_webhook_event.assert_called_once()

        db = TestingSessionLocal()
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == "pi_999").first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, "success")
        db.close()

    @patch("backend.routes.webhook.paiement.time.sleep")
    @patch("backend.routes.webhook.paiement.send_webhook_event")
    @patch("backend.routes.webhook.paiement.send_merchant_notification")
    @patch("backend.routes.webhook.paiement.send_payment_email")
    @patch("backend.routes.webhook.paiement.generate_invoice_pdf")
    @patch("backend.routes.webhook.paiement.stripe.BalanceTransaction.list")
    @patch("backend.routes.webhook.paiement.stripe.Charge.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    def test_payment_is_kept_even_if_fee_and_transfer_never_propagate(
        self, mock_pi_retrieve, mock_charge_retrieve, mock_bt_list,
        mock_pdf, mock_email, mock_merchant_email, mock_webhook_event, mock_sleep,
    ):
        """balance_transaction disponible, mais application_fee/transfer ne
        se résolvent jamais même après MAX_SETTLEMENT_ATTEMPTS : le paiement
        ne doit JAMAIS être perdu pour cette seule raison, juste enregistré
        avec fee_amount/transfer_amount à None en dernier recours."""
        mock_pi_retrieve.return_value = MagicMock(latest_charge="ch_no_fee")
        mock_charge_retrieve.return_value = FakeCharge(
            charge_id="ch_no_fee", application_fee=None, transfer=None,
        )
        mock_bt_list.return_value = make_balance_tx_list(make_balance_tx(amount_cents=10000))

        process_checkout_session_payment(
            self.session_dict, self.merchant_id, "lk_1", "pi_no_fee", "pi_no_fee", "checkout.session.completed",
        )

        self.assertEqual(mock_charge_retrieve.call_count, MAX_ATTEMPTS)
        self.assertEqual(mock_sleep.call_count, MAX_ATTEMPTS - 1)
        mock_webhook_event.assert_called_once()

        db = TestingSessionLocal()
        payment = db.query(Payment).filter(Payment.stripe_payment_intent_id == "pi_no_fee").first()
        self.assertIsNotNone(payment)
        self.assertIsNone(payment.fee_amount)
        self.assertIsNone(payment.transfer_amount)
        db.close()

    @patch("backend.routes.webhook.paiement.time.sleep")
    @patch("backend.routes.webhook.paiement.send_webhook_event")
    @patch("backend.routes.webhook.paiement.send_merchant_notification")
    @patch("backend.routes.webhook.paiement.send_payment_email")
    @patch("backend.routes.webhook.paiement.generate_invoice_pdf")
    @patch("backend.routes.webhook.paiement.stripe.BalanceTransaction.list")
    @patch("backend.routes.webhook.paiement.stripe.Charge.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    def test_gives_up_after_max_attempts_when_balance_transaction_never_found(
        self, mock_pi_retrieve, mock_charge_retrieve, mock_bt_list,
        mock_pdf, mock_email, mock_merchant_email, mock_webhook_event, mock_sleep,
    ):
        """balance_transaction jamais trouvé après MAX_SETTLEMENT_ATTEMPTS :
        l'échec reste interne à la tâche de fond (pas de levée visible),
        mais borné (ne tourne pas indéfiniment)."""
        mock_pi_retrieve.return_value = MagicMock(latest_charge="ch_never")
        mock_charge_retrieve.return_value = FakeCharge(charge_id="ch_never")
        mock_bt_list.return_value = make_balance_tx_list()  # .data == [] à chaque essai

        process_checkout_session_payment(
            self.session_dict, self.merchant_id, "lk_1", "pi_never", "pi_never", "checkout.session.completed",
        )

        self.assertEqual(mock_charge_retrieve.call_count, MAX_ATTEMPTS)
        self.assertEqual(mock_bt_list.call_count, MAX_ATTEMPTS)
        self.assertEqual(mock_sleep.call_count, MAX_ATTEMPTS - 1)
        mock_webhook_event.assert_not_called()

        db = TestingSessionLocal()
        tx = db.query(WalletTransaction).filter(WalletTransaction.reference == "pi_never").first()
        self.assertIsNone(tx)
        db.close()


class TestCheckoutSessionWebhookRoute(unittest.TestCase):
    """Vérifie que la route répond immédiatement et délègue le traitement
    dépendant du règlement Stripe à la tâche de fond, sans jamais
    l'exécuter en ligne dans le handler de requête."""

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(paiement_module.router)
        cls.client = TestClient(app)

    @patch("backend.routes.webhook.paiement.process_checkout_session_payment")
    @patch("backend.routes.webhook.paiement.stripe.PaymentIntent.retrieve")
    @patch("backend.routes.webhook.paiement.stripe.Webhook.construct_event")
    def test_schedules_background_task_and_returns_ok_immediately(
        self, mock_construct_event, mock_pi_retrieve, mock_process,
    ):
        mock_construct_event.return_value = {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {
                "object": MagicMock(
                    mode="payment",
                    to_dict=lambda: {
                        "id": "cs_test_123",
                        "payment_intent": "pi_abc",
                        "metadata": {"user_id": "us_1", "link_id": "lk_1"},
                        "currency": "xof",
                        "customer_details": {"email": "client@example.com"},
                    },
                )
            },
        }

        res = self.client.post(
            "/webhook/payment",
            data=json.dumps({}).encode(),
            headers={"stripe-signature": "fake"},
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})
        mock_process.assert_called_once()
        # La partie synchrone ne doit plus jamais aller chercher le
        # PaymentIntent/Charge elle-même : c'est désormais la responsabilité
        # exclusive de la tâche de fond.
        mock_pi_retrieve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
