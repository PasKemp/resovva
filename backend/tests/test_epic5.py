"""
Tests für EPIC 5: Checkout & Monetization (Die Paywall).

Abgedeckte Bereiche:
  - US-5.1: Stripe Checkout Session erstellen (Backend)
  - US-5.2: Webhook-Handler für Zahlungsbestätigung
  - US-5.4: Abgebrochene Zahlungen – Retry via neuer Session

Alle Tests laufen im Dev-Modus ohne echte Stripe-Verbindung.
Prod-Modus-Verhalten wird via Mocking abgedeckt.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────


def _make_case(db, user, status: str = "TIMELINE_READY"):
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


# ─────────────────────────────────────────────────────────────────────────────
# US-5.1: Stripe Checkout Session
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckoutEndpoint:
    """POST /api/v1/cases/{case_id}/checkout."""

    def test_dev_mode_sets_paid_directly(self, auth_client, db):
        """Ohne STRIPE_SECRET_KEY → Fall direkt auf PAID, checkout_url leer."""
        client, user = auth_client
        case = _make_case(db, user)

        resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == ""
        db.refresh(case)
        assert case.status == "PAID"

    def test_unauthenticated_returns_401(self, client, db, test_user):
        """Ohne Auth-Cookie → 401."""
        case = _make_case(db, test_user)

        resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 401

    def test_foreign_case_returns_404(self, auth_client):
        """Nicht existierende oder fremde Case-ID → 404."""
        client, _ = auth_client

        resp = client.post(f"/api/v1/cases/{uuid.uuid4()}/checkout")

        assert resp.status_code == 404

    def test_already_paid_returns_empty_url(self, auth_client, db):
        """Bereits PAID → idempotent checkout_url='' zurück (kein zweiter Charge)."""
        client, user = auth_client
        case = _make_case(db, user, status="PAID")

        resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == ""
        db.refresh(case)
        assert case.status == "PAID"

    def test_payment_pending_retry_succeeds(self, auth_client, db):
        """PAYMENT_PENDING-Fall → neue Checkout-Session erstellbar (US-5.4 Retry)."""
        client, user = auth_client
        case = _make_case(db, user, status="PAYMENT_PENDING")

        resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        # Im Dev-Modus → direkt PAID (Session wurde nicht gesperrt)
        assert resp.status_code == 200
        db.refresh(case)
        assert case.status == "PAID"

    def test_prod_mode_creates_stripe_session(self, auth_client, db):
        """Mit gemocktem Stripe-SDK → PAYMENT_PENDING gesetzt, checkout_url zurück."""
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
        """Stripe-Session wird mit allow_promotion_codes=True erstellt (US-5.1 AK)."""
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

    def test_prod_mode_cancel_url_points_to_dashboard(self, auth_client, db):
        """cancel_url enthält /dashboard?payment=cancelled (US-5.4 AK)."""
        client, user = auth_client
        case = _make_case(db, user)

        mock_session = MagicMock()
        mock_session.id = "cs_cancel_test"
        mock_session.url = "https://checkout.stripe.com/pay/cs_cancel_test"

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
        assert "dashboard" in call_kwargs["cancel_url"]
        assert "payment=cancelled" in call_kwargs["cancel_url"]
        assert "dashboard" in call_kwargs["success_url"]
        assert "payment=success" in call_kwargs["success_url"]

    def test_prod_mode_stripe_error_returns_500(self, auth_client, db):
        """Stripe-API-Fehler → 500."""
        client, user = auth_client
        case = _make_case(db, user)

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_price_id = "price_test_20eur"
            mock_settings.app_base_url = "http://localhost:5173"
            mock_stripe.StripeError = Exception
            mock_stripe.checkout.Session.create.side_effect = Exception("Network error")

            resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 500

    def test_prod_mode_missing_price_id_returns_500(self, auth_client, db):
        """Kein STRIPE_PRICE_ID konfiguriert → 500."""
        client, user = auth_client
        case = _make_case(db, user)

        with patch("app.api.v1.checkout.settings") as mock_settings:
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_price_id = None

            resp = client.post(f"/api/v1/cases/{case.id}/checkout")

        assert resp.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# US-5.2: Webhook-Handler für Zahlungsbestätigung
# ─────────────────────────────────────────────────────────────────────────────


class TestStripeWebhook:
    """POST /api/v1/webhooks/stripe."""

    def test_dev_mode_returns_ok_without_processing(self, client, reset_db):
        """Kein STRIPE_SECRET_KEY → sofort 200 ok, kein Stripe-Aufruf."""
        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "fake"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_invalid_signature_returns_400(self, client, db, test_user):
        """Ungültige Stripe-Webhook-Signatur → 400 Bad Request (Sicherheits-AK)."""
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

    def test_checkout_completed_sets_case_to_paid(self, client, db, test_user):
        """checkout.session.completed → Fall-Status von PAYMENT_PENDING auf PAID."""
        case = _make_case(db, test_user, status="PAYMENT_PENDING")
        case_id = str(case.id)

        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_completed",
                "metadata": {"case_id": case_id},
                "payment_intent": "pi_test_abc",
            }},
        }).encode()

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
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = None
            mock_stripe.Event.construct_from.return_value = fake_event

            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": ""},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        db.refresh(case)
        assert case.status == "PAID"

    def test_checkout_completed_logs_payment_intent(self, client, db, test_user):
        """Bonus: payment_intent wird in extracted_data für Buchhaltung persistiert."""
        case = _make_case(db, test_user, status="PAYMENT_PENDING")
        case_id = str(case.id)
        payment_intent_id = "pi_test_xyz789"

        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_intent",
                "metadata": {"case_id": case_id},
                "payment_intent": payment_intent_id,
            }},
        }).encode()

        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_intent",
                "metadata": {"case_id": case_id},
                "payment_intent": payment_intent_id,
            }},
        }

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = None
            mock_stripe.Event.construct_from.return_value = fake_event

            client.post(
                "/api/v1/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": ""},
            )

        db.refresh(case)
        assert case.extracted_data.get("stripe_payment_intent") == payment_intent_id

    def test_webhook_idempotency_already_paid(self, client, db, test_user):
        """Doppeltes Webhook-Event (Stripe kann Events mehrfach senden) → kein Fehler, PAID bleibt."""
        case = _make_case(db, test_user, status="PAID")
        case_id = str(case.id)

        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_duplicate",
                "metadata": {"case_id": case_id},
                "payment_intent": "pi_dup",
            }},
        }).encode()

        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_duplicate",
                "metadata": {"case_id": case_id},
                "payment_intent": "pi_dup",
            }},
        }

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = None
            mock_stripe.Event.construct_from.return_value = fake_event

            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": ""},
            )

        assert resp.status_code == 200
        db.refresh(case)
        assert case.status == "PAID"  # unverändert

    def test_webhook_missing_case_id_returns_ok(self, client, reset_db):
        """Fehlende case_id in Metadata → 200 ok, kein Crash."""
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_no_meta", "metadata": {}}},
        }).encode()

        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_no_meta", "metadata": {}}},
        }

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = None
            mock_stripe.Event.construct_from.return_value = fake_event

            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": ""},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_unrelated_event_type_returns_ok(self, client, reset_db):
        """Nicht-relevante Event-Typen werden ignoriert."""
        payload = json.dumps({
            "type": "customer.created",
            "data": {"object": {}},
        }).encode()

        fake_event = {"type": "customer.created", "data": {"object": {}}}

        with (
            patch("app.api.v1.checkout.settings") as mock_settings,
            patch("app.api.v1.checkout.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = None
            mock_stripe.Event.construct_from.return_value = fake_event

            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": ""},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
