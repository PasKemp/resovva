"""
Checkout Router – Epic 5 (US-5.1 / US-5.2): Stripe Checkout & Webhook.

Endpunkte:
  POST   /cases/{case_id}/checkout     – Erstellt eine Stripe Checkout Session
  POST   /webhooks/stripe              – Verarbeitet Stripe-Events (checkout.session.completed)

Status-Flow:
  TIMELINE_READY → PAYMENT_PENDING (Checkout gestartet) → PAID (Webhook empfangen)

Dev-Modus (kein STRIPE_SECRET_KEY):
  - POST /checkout setzt den Fall direkt auf PAID und gibt checkout_url="" zurück
  - Das Frontend leitet dann direkt zum Dossier weiter (kein Stripe-Redirect)
"""

from __future__ import annotations

import logging

import stripe  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.core.config import get_settings
from app.domain.models.db import Case
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["checkout"])


# ── Response Schemas ──────────────────────────────────────────────────────────


class CheckoutResponse(BaseModel):
    checkout_url: str  # Leer im Dev-Modus → Frontend geht direkt zu Dossier


# ── POST /cases/{case_id}/checkout ────────────────────────────────────────────


@router.post("/cases/{case_id}/checkout", response_model=CheckoutResponse)
def create_checkout(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """
    Erstellt eine Stripe Checkout Session für den Fall (€20, einmalig).

    Dev-Modus (kein STRIPE_SECRET_KEY): Fall wird sofort auf PAID gesetzt,
    checkout_url ist leer → Frontend navigiert direkt zum Dossier.

    Args:
        case_id: UUID des Falls.

    Returns:
        CheckoutResponse: Stripe-Redirect-URL oder leer (Dev-Modus).

    Raises:
        HTTPException 404: Fall nicht gefunden oder nicht im Besitz des Nutzers.
        HTTPException 402: Stripe nicht konfiguriert (nur wenn kein Dev-Modus).
        HTTPException 500: Stripe API-Fehler.
    """
    case = get_owned_case(case_id, current_user, db)

    # Bereits bezahlt – idempotent zurückgeben
    if case.status == "PAID":
        return CheckoutResponse(checkout_url="")

    # ── Dev-Modus: kein Stripe-Key → direkt PAID setzen ──────────────────────
    if not settings.stripe_secret_key:
        logger.info("Dev-Modus: Fall %s wird ohne Stripe direkt auf PAID gesetzt.", case_id)
        case.status = "PAID"
        db.commit()
        return CheckoutResponse(checkout_url="")

    # ── Produktionsmodus: Stripe Checkout Session erstellen ──────────────────
    stripe.api_key = settings.stripe_secret_key

    if not settings.stripe_price_id:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_PRICE_ID ist nicht konfiguriert.",
        )

    success_url = f"{settings.app_base_url}/dashboard?payment=success&case_id={case_id}"
    cancel_url = f"{settings.app_base_url}/dashboard?payment=cancelled&case_id={case_id}"

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(current_user.id),
            metadata={"case_id": case_id, "user_id": str(current_user.id)},
            customer_email=current_user.email,
            allow_promotion_codes=True,
        )
    except stripe.StripeError as exc:
        logger.error("Stripe-Fehler für Fall %s: %s", case_id, exc)
        raise HTTPException(status_code=500, detail="Zahlung konnte nicht gestartet werden.")

    # Session-ID speichern + Status auf PAYMENT_PENDING setzen (in einer Transaktion)
    case.stripe_session_id = session.id
    case.status = "PAYMENT_PENDING"
    db.commit()

    logger.info("Stripe Checkout Session erstellt: %s (Fall: %s)", session.id, case_id)
    return CheckoutResponse(checkout_url=session.url)


# ── POST /webhooks/stripe ─────────────────────────────────────────────────────


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> dict[str, str]:
    """
    Verarbeitet Stripe Webhook-Events.

    Unterstützte Events:
    - checkout.session.completed → Fall wird auf PAID gesetzt

    Sicherheit: Signatur-Verifikation via STRIPE_WEBHOOK_SECRET (Pflicht in Prod).

    Returns:
        {"status": "ok"} bei Erfolg.

    Raises:
        HTTPException 400: Ungültige Signatur oder unbekanntes Event.
    """
    if not settings.stripe_secret_key:
        # Dev-Modus: kein Webhook nötig
        return {"status": "ok"}

    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()

    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.stripe_webhook_secret
            )
        except stripe.SignatureVerificationError:
            logger.warning("Stripe Webhook: ungültige Signatur.")
            raise HTTPException(status_code=400, detail="Ungültige Webhook-Signatur.")
    else:
        # Kein Webhook-Secret → Signatur überspringen (nur für lokales Testing)
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        case_id = session.get("metadata", {}).get("case_id")

        if not case_id:
            logger.warning("Stripe Webhook: case_id fehlt in Metadata.")
            return {"status": "ok"}

        case = db.query(Case).filter(Case.id == case_id).first()
        if case:
            # Idempotenz: bereits PAID → nichts tun
            if case.status == "PAID":
                logger.info("Webhook: Fall %s bereits PAID – übersprungen.", case_id)
                return {"status": "ok"}

            case.status = "PAID"
            case.stripe_session_id = session.get("id")

            # Bonus: payment_intent für Buchhaltungs-Referenz persistieren
            payment_intent = session.get("payment_intent")
            if payment_intent:
                extracted = dict(case.extracted_data or {})
                extracted["stripe_payment_intent"] = payment_intent
                case.extracted_data = extracted

            db.commit()
            logger.info("Zahlung bestätigt: Fall %s → PAID (intent: %s).", case_id, payment_intent)
        else:
            logger.warning("Stripe Webhook: Fall %s nicht gefunden.", case_id)

    return {"status": "ok"}
