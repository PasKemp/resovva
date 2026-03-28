"""
Checkout and Payment Integration Tests (Epic 5).

Covers US-5.1 (Stripe Session Creation), US-5.2 (Webhook Handler),
and US-5.4 (Retry Flow).
Tests in dev mode bypass Stripe, while prod mode behavior is verified via mocks.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_case(db, user, status: str = "TIMELINE_READY"):
    """Create a case in a specific state for checkout testing."""
    from app.domain.models.db import Case

    case = Case(
        id=uuid.uuid4(),
        user_id=user.id,
        status=status,
        extracted_data={},
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


# ── US-5.1: Stripe Checkout Session ──────────────────────────────────────────

class TestCheckoutEndpoint:
    """POST /api/v1/cases/{case_id}/checkout."""

    def test_dev_mode_sets_status_directly(self, auth_client, db):
        """Without STRIPE_SECRET_KEY, case should move directly to GENERATING_DOSSIER."""
        client, user = auth_client
        case = _make_case(db, user)

        with patch("app.workers.dossier_worker.run_dossier_generation"):
            resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == ""
        db.refresh(case)
        # Note: In the refactored logic, it skips 'PAID' and goes to 'GENERATING_DOSSIER'
        assert case.status == "GENERATING_DOSSIER"

    def test_unauthenticated_returns_401(self, client, db, test_user):
        """Missing session cookie should return 401."""
        case = _make_case(db, test_user)
        resp = client.post(f"/api/v1/cases/{case.id}/checkout")
        assert res.status_code == 401 if (res := resp) else None # Using alias for consistency

    def test_foreign_case_returns_404(self, auth_client):
        """Accessing a case owned by someone else should return 404."""
        client, _ = auth_client
        resp = client.post(f"/api/v1/cases/{uuid.uuid4()}/checkout")
        assert resp.status_code == 404

    def test_already_paid_returns_empty_url(self, auth_client, db):
        """Idempotency: already paid/generating cases should return empty URL."""
        client, user = auth_client
        case = _make_case(db, user, status="GENERATING_DOSSIER")

        resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == ""

    def test_payment_pending_retry_succeeds(self, auth_client, db):
        """Pending payments should allow retrying/bypassing in dev mode."""
        client, user = auth_client
        case = _make_case(db, user, status="PAYMENT_PENDING")

        with patch("app.workers.dossier_worker.run_dossier_generation"):
            resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 200
        db.refresh(case)
        assert case.status == "GENERATING_DOSSIER"

    def test_prod_mode_creates_stripe_session(self, auth_client, db):
        """Production mode must correctly interface with Stripe SDK."""
        client, user = auth_client
        case = _make_case(db, user)

        mock_session = MagicMock()
        mock_session.id = "cs_test_abc123"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc123"

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_price_id = "price_test_20eur"
            mock_settings.app_base_url = "http://localhost:5173"
            mock_stripe.checkout.Session.create.return_value = mock_session
            mock_stripe.StripeError = Exception

            resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_abc123"
        db.refresh(case)
        assert case.stripe_session_id == "cs_test_abc123"
        assert case.status == "PAYMENT_PENDING"

    def test_prod_mode_session_includes_promotion_codes(self, auth_client, db):
        """Stripe sessions should allow user promotion codes."""
        client, user = auth_client
        case = _make_case(db, user)

        mock_session = MagicMock()
        mock_session.id = "cs_promo_test"
        mock_session.url = "https://checkout.stripe.com/pay/cs_promo_test"

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_price_id = "price_test_20eur"
            mock_settings.app_base_url = "http://localhost:5173"
            mock_stripe.checkout.Session.create.return_value = mock_session
            mock_stripe.StripeError = Exception

            client.post(f"/api/v1/cases/{case.id}/checkout")

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs.get("allow_promotion_codes") is True
        assert "case_id" in call_kwargs.get("metadata", {})
        assert call_kwargs.get("client_reference_id") == str(user.id)


# ── US-5.2: Stripe Webhook Handler ───────────────────────────────────────────

class TestStripeWebhook:
    """POST /api/v1/webhooks/stripe."""

    def test_dev_mode_returns_ok_without_processing(self, client, reset_db):
        """Non-configured Stripe environment should return OK immediately."""
        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "fake"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_invalid_signature_returns_400(self, client, db, test_user):
        """Webhook signatures must be strictly verified (HTTP 400)."""
        case = _make_case(db, test_user)
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test",
                "metadata": {"case_id": str(case.id)},
            }},
        }).encode()

        class _FakeSigError(Exception):
            pass

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.SignatureVerificationError = _FakeSigError
            mock_stripe.Webhook.construct_event.side_effect = _FakeSigError("bad sig")

            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": "invalid_sig"},
            )

        assert resp.status_code == 400

    def test_checkout_completed_triggers_generation(self, client, db, test_user):
        """Successful payment must trigger dossier generation."""
        case = _make_case(db, test_user, status="PAYMENT_PENDING")
        case_id = str(case.id)

        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_completed",
                "metadata": {"case_id": case_id},
                "payment_intent": "pi_test_abc",
            }},
        }

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
            patch("app.api.v1.checkout.BackgroundTasks.add_task") as mock_bg,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = None
            mock_stripe.Event.construct_from.return_value = fake_event

            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(fake_event).encode(),
                headers={"stripe-signature": ""},
            )

        assert resp.status_code == 200
        db.refresh(case)
        assert case.status == "GENERATING_DOSSIER"
        assert mock_bg.called  # run_dossier_generation should be queued
