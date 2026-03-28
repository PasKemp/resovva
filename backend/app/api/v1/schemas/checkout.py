"""
Pydantic schemas for the payment checkout process.

Provides structures for Stripe Checkout session generation and status
reporting.
"""

from __future__ import annotations

from pydantic import BaseModel


# ── Response Schemas ──────────────────────────────────────────────────────────

class CheckoutResponse(BaseModel):
    """
    Response for a checkout session request.
    
    In development mode (no Stripe key), the checkout_url is an empty string,
    notifying the frontend to bypass the payment wall.
    """
    checkout_url: str
