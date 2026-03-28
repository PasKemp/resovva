"""
Authentication Router.

Handles user registration, login, logout, and password resets.
Implements session management via HttpOnly cookies and brute-force protection.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.api.v1.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    StatusMessageResponse,
)
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.domain.exceptions import AuthenticationError, ConflictError
from app.domain.models.db import PasswordResetToken, User
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT Cookie Configuration
COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


def _set_auth_cookie(response: Response, token: str) -> None:
    """
    Set the HttpOnly session cookie with the JWT.

    Args:
        response: The FastAPI response object.
        token: The signed JWT string.
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
        # secure=True,  # Enable in production (requires HTTPS)
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(
    body: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db)
) -> RegisterResponse:
    """
    Register a new user and set the session cookie.

    Args:
        body: Registration details including profile data.
        response: FastAPI response object for cookie setting.
        db: Database session.

    Returns:
        RegisterResponse: Status and created user ID.

    Raises:
        HTTPException: If the email is already in use (Conflict 409).
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        logger.warning("Registration failed: email already exists", extra={"email": body.email})
        raise ConflictError("Email already registered.")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        accepted_terms=body.accepted_terms,
        first_name=body.first_name,
        last_name=body.last_name,
        street=body.street,
        postal_code=body.postal_code,
        city=body.city,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    _set_auth_cookie(response, token)

    logger.info("New user registered", extra={"user_id": str(user.id)})
    return RegisterResponse(
        status="success",
        user_id=str(user.id),
        message="Registration successful. You are now logged in.",
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/15 minutes")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """
    Verify credentials and set the session cookie.

    Includes rate limiting (5 attempts per 15 mins per IP) to prevent brute force.

    Args:
        request: FastAPI request (used by rate limiter).
        body: Login credentials.
        response: FastAPI response for cookie setting.
        db: Database session.

    Returns:
        LoginResponse: Status and user ID.

    Raises:
        HTTPException: If credentials are invalid (Unauthorized 401).
    """
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        logger.warning("Login failed", extra={"email": body.email})
        raise AuthenticationError("Invalid email or password.")

    token = create_access_token(str(user.id))
    _set_auth_cookie(response, token)

    logger.info("User logged in", extra={"user_id": str(user.id)})
    return LoginResponse(status="success", user_id=str(user.id))


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUser) -> MeResponse:
    """
    Retrieve data for the currently authenticated user.

    Used by the frontend on application load to check session status.

    Args:
        current_user: The authenticated User model instance from dependency.

    Returns:
        MeResponse: User profile and session status.
    """
    profile_complete = bool(
        current_user.first_name and current_user.last_name and
        current_user.street and current_user.postal_code and current_user.city
    )
    return MeResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        street=current_user.street,
        postal_code=current_user.postal_code,
        city=current_user.city,
        profile_complete=profile_complete,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response, _: CurrentUser) -> LogoutResponse:
    """
    Clear the session cookie and terminate the session.

    Args:
        response: FastAPI response object.
        _: Current user (ensures user is logged in).

    Returns:
        LogoutResponse: Status and success message.
    """
    response.delete_cookie(key=COOKIE_NAME, samesite="lax")
    return LogoutResponse(status="success", message="Logged out successfully.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Generate a reset token and send an email notification.

    Always returns a generic success message to prevent account enumeration.

    Args:
        body: The user's email address.
        db: Database session.

    Returns:
        MessageResponse: Generic success message.
    """
    generic_response = MessageResponse(
        message="If an account exists for this email, a reset link has been sent."
    )

    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        return generic_response

    # Invalidate previous active tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,  # noqa: E712
    ).delete()

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    db.commit()

    _send_reset_email(user.email, raw_token)
    return generic_response


@router.post("/reset-password", response_model=StatusMessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db)
) -> StatusMessageResponse:
    """
    Reset user password using a valid reset token.

    Args:
        body: Token and new password.
        db: Database session.

    Returns:
        StatusMessageResponse: Success status.

    Raises:
        HTTPException: If token is invalid, expired, or already used (400).
    """
    token_hash = hash_reset_token(body.token)
    now = datetime.now(timezone.utc)

    record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > now,
        )
        .first()
    )

    if not record:
        logger.warning("Invalid or expired password reset attempt")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token. Please request a new one.",
        )

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    user.hashed_password = hash_password(body.password)
    record.used = True
    db.commit()

    logger.info("Password successfully reset", extra={"user_id": str(user.id)})
    return StatusMessageResponse(status="success", message="Password changed successfully.")


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _send_reset_email(email: str, raw_token: str) -> None:
    """
    Send the password reset email via Resend SDK.

    Falls back to logging the reset URL in development mode.

    Args:
        email: Recipient address.
        raw_token: The non-hashed reset token for the link.
    """
    settings = get_settings()
    reset_url = f"{settings.app_base_url}/reset-password?token={raw_token}"

    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY not set. Reset URL (DEV ONLY): %s", reset_url
        )
        return

    try:
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": settings.email_from,
            "to": email,
            "subject": "Reset your Resovva password",
            "html": (
                f"<p>You requested a password reset for your Resovva account.</p>"
                f"<p><a href='{reset_url}'>Reset my password</a></p>"
                f"<p>This link is valid for 15 minutes.</p>"
                f"<p>If you didn't request this, you can safely ignore this email.</p>"
            ),
        })
    except Exception as exc:
        logger.error("Failed to send reset email: %s", str(exc), exc_info=True)
