import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import Link, Profile, UserDB
from backend.services.stripe_service import create_checkout_session

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)


class TestCreateCheckoutSessionPayment(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        now = datetime.now(timezone.utc)

        merchant = UserDB(email=f"merchant-{uuid.uuid4().hex}@example.com", password="x")
        self.db.add(merchant)
        self.db.flush()

        token = f"tok-checkout-{uuid.uuid4().hex}"
        profile = Profile(user_id=merchant.id, stripe_account_id="acct_123")
        link = Link(
            user_id=merchant.id,
            token=token,
            amount=10,
            currency="USD",
            name="Lien de paiement",
            url=f"https://api.alasdia.com/pay/{token}",
            created_at=now,
            expires_at=now + timedelta(minutes=10),
            active=True,
            deleted=False,
            archived=False,
        )
        self.db.add_all([profile, link])
        self.db.commit()

        self.link_id = link.id

    def tearDown(self):
        self.db.close()

    @patch("backend.services.stripe_service.stripe.checkout.Session.create")
    def test_builds_direct_charge_session_on_connected_account(self, mock_create):
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/abc")

        url = create_checkout_session(
            db=self.db,
            mode="payment",
            email="client@example.com",
            user_id="user_x",
            amount=100,
            link_id=self.link_id,
            currency="USD",
        )

        self.assertEqual(url, "https://checkout.stripe.com/pay/abc")
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        self.assertNotIn("payment_method_types", kwargs)
        self.assertEqual(kwargs["mode"], "payment")
        # Direct charge : la session vit sur le compte connecté
        # (stripe_account=), plus de transfer_data/on_behalf_of (propres
        # au destination charge, l'ancien modèle) - voir stripe_service.py.
        self.assertEqual(kwargs["stripe_account"], "acct_123")
        self.assertNotIn("transfer_data", kwargs["payment_intent_data"])
        self.assertNotIn("on_behalf_of", kwargs["payment_intent_data"])
        self.assertIn("application_fee_amount", kwargs["payment_intent_data"])
        self.assertEqual(kwargs["metadata"]["link_id"], str(self.link_id))

    @patch("backend.services.stripe_service.stripe.checkout.Session.create")
    def test_raises_clear_error_when_connected_account_rejects_direct_charge(self, mock_create):
        # Cas attendu en pratique : le compte connecté n'a pas (ou pas
        # encore) la capacité card_payments active, requise pour un direct
        # charge (contrairement à l'ancien destination charge, qui ne
        # demandait que transfers) - voir le try/except dans
        # create_checkout_session.
        import stripe as stripe_module
        mock_create.side_effect = stripe_module.error.StripeError(
            "Your destination account needs to have at least one of the "
            "following capabilities enabled: card_payments"
        )

        with self.assertRaises(Exception) as ctx:
            create_checkout_session(
                db=self.db,
                mode="payment",
                email="client@example.com",
                user_id="user_x",
                amount=100,
                link_id=self.link_id,
                currency="USD",
            )
        self.assertIn("acct_123", str(ctx.exception))

    @patch("backend.services.stripe_service.stripe.checkout.Session.create")
    def test_unknown_link_raises(self, mock_create):
        with self.assertRaises(Exception):
            create_checkout_session(
                db=self.db,
                mode="payment",
                email="client@example.com",
                user_id="user_x",
                amount=100,
                link_id="lk_does_not_exist",
                currency="USD",
            )
        mock_create.assert_not_called()


class TestCreateCheckoutSessionSubscription(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()

    @patch("backend.services.stripe_service.stripe.checkout.Session.create")
    def test_builds_session_without_payment_method_types(self, mock_create):
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/pay/sub")

        url = create_checkout_session(
            db=self.db,
            mode="subscription",
            email="client@example.com",
            user_id="user_x",
            plan="pro",
        )

        self.assertEqual(url, "https://checkout.stripe.com/pay/sub")
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        self.assertNotIn("payment_method_types", kwargs)
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(kwargs["line_items"][0]["price"], "price_1ULaX80I86XW25IrFJBTIif0")

    @patch("backend.services.stripe_service.stripe.checkout.Session.create")
    def test_invalid_plan_raises(self, mock_create):
        with self.assertRaises(Exception):
            create_checkout_session(
                db=self.db,
                mode="subscription",
                email="client@example.com",
                user_id="user_x",
                plan="not-a-plan",
            )
        mock_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
