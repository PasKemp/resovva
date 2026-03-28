"""
Checkout Router.

Handles payment integration via Stripe, creating checkout sessions
and processing webhooks to finalize case payment and start dossier generation.
"""

from __future__ import annotations

import logging
from typing import Dict

import stripe  # type: ignore[import-untyped]
from fastapi import (
    APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
)
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.api.v1.schemas.checkout import CheckoutResponse
from app.core.config import get_settings
from app.domain.models.db import Case
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["checkout"])


# ── Checkout Endpoints ───────────────────────────────────────────────────────

@router.post("/cases/{case_id}/checkout", response_model=CheckoutResponse)
def create_checkout(
    case_id: str,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """
    Create a Stripe Checkout Session for a legal dossier fee (€20).

    In development mode (STRIPE_SECRET_KEY not set), the payment is bypassed
    and the case is immediately moved to 'GENERATING_DOSSIER' status.

    Args:
        case_id: UUID of the case to pay for.
        current_user: Authenticated user (owner).
        db: Database session.

    Returns:
        CheckoutResponse: Stripe session URL or indicating bypass.

    Raises:
        HTTPException:
            404: Case not found or not owned.
            500: Missing configuration or Stripe API failure.
    """
    case = get_owned_case(case_id, current_user, db)

    # Idempotency check: already paid or generating
    if case.status in ("PAID", "GENERATING_DOSSIER", "COMPLETED"):
        return CheckoutResponse(checkout_url="")

    # ── Development Mode Bypass ───────────────────────────────────────────────
    if not settings.stripe_secret_key:
        logger.info(
            "Dev-Mode: bypassing payment",
            extra={"case_id": case_id, "user_id": str(current_user.id)}
        )
        case.status = "GENERATING_DOSSIER"
        db.commit()

        # Immediately start background worker (Epic 6)
        from app.workers.dossier_worker import run_dossier_generation
        background_tasks.add_task(run_dossier_generation, case_id)
        
        return CheckoutResponse(checkout_url="")

    # ── Production Stripe Integration ─────────────────────────────────────────
    stripe.api_key = settings.stripe_secret_key

    if not settings.stripe_price_id:
        raise HTTPException(
            status_code=500,
            detail="STRIPE_PRICE_ID missing in backend configuration."
        )

    success_url = f"{settings.app_base_url}/dashboard?payment=success&case_id={case_id}"
    cancel_url = f"{settings.app_base_url}/dashboard?payment=cancelled&case_id={case_id}"

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": settings.stripe_price_id,
                "quantity": 1
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(current_user.id),
            metadata={
                "case_id": case_id,
                "user_id": str(current_user.id)
            },
            customer_email=current_user.email,
            allow_promotion_codes=True,
        )
    except stripe.StripeError as exc:
        logger.error(
            "Stripe API error creating session",
            extra={"case_id": case_id, "error": str(exc)},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Could not initiate payment session.")

    # Record specific Stripe metadata to DB
    case.stripe_session_id = session.id
    case.status = "PAYMENT_PENDING"
    db.commit()

    logger.info(
        "Stripe checkout session initialized",
        extra={"case_id": case_id, "session_id": str(session.id)}
    )
    return CheckoutResponse(checkout_url=session.url)


# ── Webhook Integration ───────────────────────────────────────────────────────

@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> Dict[str, str]:
    """
    Handle Stripe webhook notifications for session completion.

    Validates the event signature if STRIPE_WEBHOOK_SECRET is set.
    Updates case status and triggers dossier generation on success.

    Returns:
        Dict[str, str]: Status object.
    """
    if not settings.stripe_secret_key:
        return {"status": "ok"}

    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()

    # 1. Signature Verification
    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.stripe_webhook_secret
            )
        except stripe.SignatureVerificationError:
            logger.warning("Stripe Webhook: signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature.")
    else:
        # Non-secure fallback (tests/dev only)
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)

    # 2. Event Processing
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        case_id = session.get("metadata", {}).get("case_id")

        if not case_id:
            logger.warning("Stripe Webhook: 'case_id' missing in session metadata")
            return {"status": "ok"}

        case = db.query(Case).filter(Case.id == case_id).first()
        if case:
            # Idempotency check: only process if status is not already advanced
            if case.status in ("PAID", "GENERATING_DOSSIER", "COMPLETED"):
                logger.debug("Stripe Webhook: case already paid/completed", extra={"case_id": case_id})
                return {"status": "ok"}

            case.status = "GENERATING_DOSSIER"
            case.stripe_session_id = session.get("id")

            # Persist Reference
            payment_intent = session.get("payment_intent")
            if payment_intent:
                data = dict(case.extracted_data or {})
                data["stripe_payment_intent"] = payment_intent
                case.extracted_data = data

            db.commit()
            logger.info(
                "Payment confirmed via webhook",
                extra={"case_id": case_id, "payment_intent": str(payment_intent)}
            )

            # 3. Trigger Async Document Generation
            from app.workers.dossier_worker import run_dossier_generation
            background_tasks.add_task(run_dossier_generation, case_id)
        else:
            logger.warning("Stripe Webhook: session case_id target not found in DB", extra={"case_id": case_id})

    return {"status": "ok"}
