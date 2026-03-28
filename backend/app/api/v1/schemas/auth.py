"""
Pydantic schemas for authentication and user sessions.

Defines the request and response structures for the auth blueprint,
including complex field validation for registration and passwords.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Request Schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """
    Data required to register a new user account.
    
    Includes core profile fields (Epic 7) to ensure dossiers can be
    generated legally even for new users.
    """
    email: EmailStr
    password: str = Field(..., min_length=8)
    accepted_terms: bool
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    street: str = Field(..., min_length=1)
    postal_code: str
    city: str = Field(..., min_length=1)

    @field_validator("accepted_terms")
    @classmethod
    def terms_must_be_accepted(cls, v: bool) -> bool:
        """Ensure the user agreed to the legal terms."""
        if not v:
            raise ValueError("Terms and privacy policy must be accepted.")
        return v

    @field_validator("postal_code")
    @classmethod
    def postal_code_format(cls, v: str) -> str:
        """Validate German postal code format (exactly 5 digits)."""
        if not re.match(r"^\d{5}$", v.strip()):
            raise ValueError("Postal code must be exactly 5 digits (e.g., 12345).")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        """Enforce password strength: 1+ uppercase, 1+ number."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        return v


class LoginRequest(BaseModel):
    """Credentials for user login."""
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Email address for password reset request."""
    email: EmailStr


    token: str
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        """Enforce password strength for reset: 1+ uppercase, 1+ number."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        return v


# ── Response Schemas ──────────────────────────────────────────────────────────

class RegisterResponse(BaseModel):
    """Result of a successful registration."""
    status: str = "success"
    user_id: str
    message: str


class LoginResponse(BaseModel):
    """Result of a successful login."""
    status: str = "success"
    user_id: str


class MeResponse(BaseModel):
    """Detailed profile data for the current user."""
    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    street: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    profile_complete: bool


class LogoutResponse(BaseModel):
    """Status of a logout operation."""
    status: str = "success"
    message: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class StatusMessageResponse(BaseModel):
    """Response containing a status and a message."""
    status: str
    message: str
