"""
Authentication and Session Integration Tests.

Covers US-1.2 (Registration), US-1.3 (Login), US-1.5 (Logout), and
US-1.8 (Password Reset).
Ensures cookie-based authentication and rate limiting are properly enforced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import generate_reset_token
from app.domain.models.db import PasswordResetToken


# ── GET /me: Session Status ──────────────────────────────────────────────────

def test_me_authenticated(auth_client):
    """Authenticated users should receive their profile data (HTTP 200)."""
    client, user = auth_client
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == str(user.id)
    assert data["email"] == user.email


def test_me_unauthenticated(client):
    """Missing session cookie should return Unauthorized (HTTP 401)."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_me_after_login(client, test_user):
    """Profile should be accessible immediately after successful login."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "SecurePassword123",
    })
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == test_user.email


def test_me_after_logout(client, test_user):
    """Profile access should be revoked immediately after logout."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "SecurePassword123",
    })
    client.post("/api/v1/auth/logout")
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


# ── US-1.2: Registration ─────────────────────────────────────────────────────

_REGISTER_PROFILE = {
    "first_name": "Max",
    "last_name":  "Mustermann",
    "street":     "Musterstraße 1",
    "postal_code": "12345",
    "city":       "Berlin",
}


def test_register_success(client):
    """Valid registration should return HTTP 201 and set a JWT cookie."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "new@example.com",
        "password":       "SecurePassword123",
        "accepted_terms": True,
        **_REGISTER_PROFILE,
    })
    assert res.status_code == 201
    assert res.json()["status"] == "success"
    assert "user_id" in res.json()
    assert "access_token" in res.cookies


def test_register_password_too_short(client):
    """Passwords shorter than 8 chars should return a validation error (HTTP 422)."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "new@example.com",
        "password":       "short",
        "accepted_terms": True,
    })
    assert res.status_code == 422


def test_register_terms_not_accepted(client):
    """Failing to accept terms should be blocked (HTTP 422)."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "new@example.com",
        "password":       "SecurePassword123",
        "accepted_terms": False,
    })
    assert res.status_code == 422


def test_register_duplicate_email(client, test_user):
    """Registering an existing email should return a Conflict error (HTTP 409)."""
    res = client.post("/api/v1/auth/register", json={
        "email":          test_user.email,
        "password":       "AnotherPassword123",
        "accepted_terms": True,
        **_REGISTER_PROFILE,
    })
    assert res.status_code == 409
    assert res.json()["error"] == "ConflictError"


def test_register_auto_login(client):
    """Users should be automatically logged in after registration."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "autoLogin@example.com",
        "password":       "SecurePassword123",
        "accepted_terms": True,
        **_REGISTER_PROFILE,
    })
    assert res.status_code == 201
    # Check if secured endpoint is reachable
    cases = client.get("/api/v1/cases")
    assert cases.status_code == 200


# ── US-1.3: Login ─────────────────────────────────────────────────────────────

def test_login_success(client, test_user):
    """Correct credentials should grant access and set session cookie."""
    res = client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "SecurePassword123",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "access_token" in res.cookies


def test_login_wrong_password(client, test_user):
    """Incorrect password should be rejected with HTTP 401."""
    res = client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "wrongPassword!",
    })
    assert res.status_code == 401
    assert res.json()["error"] == "AuthenticationError"


def test_login_unknown_email(client):
    """Unknown email should return HTTP 401 without leaking existence."""
    res = client.post("/api/v1/auth/login", json={
        "email":    "none@example.com",
        "password": "anyPassword123",
    })
    assert res.status_code == 401
    assert res.json()["error"] == "AuthenticationError"


def test_login_error_message_is_neutral(client, test_user):
    """Login failures must use identical neutral messages to prevent enumeration."""
    wrong_pw = client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "wrong",
    })
    unknown = client.post("/api/v1/auth/login", json={
        "email": "unknown@example.com", "password": "wrong",
    })
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]


def test_login_grants_access_to_protected_routes(client, test_user):
    """Session cookie should allow access to protected API resources."""
    client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "SecurePassword123",
    })
    res = client.get("/api/v1/cases")
    assert res.status_code == 200


# ── US-1.5: Logout ────────────────────────────────────────────────────────────

def test_logout_success(client, test_user):
    """Authenticated users should be able to end their session."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "SecurePassword123",
    })
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_logout_revokes_access(client, test_user):
    """Session cookies must be invalidated upon logout."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "SecurePassword123",
    })
    client.post("/api/v1/auth/logout")
    res = client.get("/api/v1/cases")
    assert res.status_code == 401


def test_logout_without_auth(client):
    """Logging out without an active session should return Unauthorized (HTTP 401)."""
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 401


# ── US-1.8: Password Reset ────────────────────────────────────────────────────

def test_forgot_password_known_email(client, test_user):
    """Requesting a reset for a known email return confirmation."""
    res = client.post("/api/v1/auth/forgot-password", json={"email": test_user.email})
    assert res.status_code == 200
    assert "message" in res.json()


def test_forgot_password_unknown_email(client):
    """Requesting reset for unknown email must return same 200 to mask existence."""
    res = client.post("/api/v1/auth/forgot-password", json={"email": "no@example.com"})
    assert res.status_code == 200
    assert "message" in res.json()


def test_forgot_password_response_is_identical(client, test_user):
    """Reset success/failure responses must be identical to block enumeration."""
    known   = client.post("/api/v1/auth/forgot-password", json={"email": test_user.email})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "no@example.com"})
    assert known.json()["message"] == unknown.json()["message"]


def test_reset_password_valid_token(client, db, test_user):
    """Valid tokens must allow changing the password and invalidate old ones."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token":    raw_token,
        "password": "NewPassword456",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Old password fails
    old_login = client.post("/api/v1/auth/login", json={
        "email": test_user.email, "password": "SecurePassword123",
    })
    assert old_login.status_code == 401

    # New one works
    new_login = client.post("/api/v1/auth/login", json={
        "email": test_user.email, "password": "NewPassword456",
    })
    assert new_login.status_code == 200


def test_reset_password_expired_token(client, db, test_user):
    """Expired reset tokens must be rejected."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # expired
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "NewPassword456",
    })
    assert res.status_code in (400, 401)


def test_reset_password_wrong_token(client):
    """Invalid reset tokens must be rejected."""
    res = client.post("/api/v1/auth/reset-password", json={
        "token": "invalid-token-xyz123", "password": "NewPassword456",
    })
    assert res.status_code in (400, 401)


def test_reset_password_single_use(client, db, test_user):
    """Reusing a consumed reset token must be blocked."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        used=True,
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "NewPassword456",
    })
    assert res.status_code in (400, 401)


def test_reset_password_short_password(client, db, test_user):
    """Reset passwords must meet length requirements (HTTP 422)."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "short",
    })
    assert res.status_code == 422
