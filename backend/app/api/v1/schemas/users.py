"""
Pydantic schemas for user profile management.

Defines structures for updating personal information and changing passwords,
including validation for German address formats.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


# ── Request Schemas ───────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    """
    Profile update data for an existing user.
    """
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    street: str = Field(..., min_length=1)
    postal_code: str
    city: str = Field(..., min_length=1)

    @field_validator("postal_code")
    @classmethod
    def postal_code_format(cls, v: str) -> str:
        """Validate German postal code format (exactly 5 digits)."""
        if not re.match(r"^\d{5}$", v.strip()):
            raise ValueError("Postal code must be exactly 5 digits (e.g., 12345).")
        return v.strip()


class ChangePasswordRequest(BaseModel):
    """
    Password change request requiring the old password for verification.
    """
    old_password: str
    new_password: str = Field(..., min_length=8)
