"""
Auth-Endpoint-Tests – Epic 1 (US-1.2, US-1.3, US-1.5, US-1.8).

Getestete Endpunkte:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  POST /api/v1/auth/forgot-password
  POST /api/v1/auth/reset-password
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import generate_reset_token
from app.domain.models.db import PasswordResetToken

# ── GET /me: Session-Status-Check ────────────────────────────────────────────


def test_me_authenticated(auth_client):
    """Eingeloggter Nutzer erhält seine Daten zurück."""
    client, user = auth_client
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == str(user.id)
    assert data["email"] == user.email


def test_me_unauthenticated(client):
    """Ohne Cookie → 401."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_me_after_login(client, test_user):
    """Nach Login liefert /me die korrekten Nutzerdaten."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "sicheresPasswort123",
    })
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == test_user.email


def test_me_after_logout(client, test_user):
    """Nach Logout ist /me nicht mehr erreichbar."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "sicheresPasswort123",
    })
    client.post("/api/v1/auth/logout")
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


# ── US-1.2: Registrierung ─────────────────────────────────────────────────────


def test_register_success(client):
    """Erfolgreiche Registrierung → 201 + JWT-Cookie gesetzt."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "neu@example.com",
        "password":       "sicheresPasswort123",
        "accepted_terms": True,
    })
    assert res.status_code == 201
    assert res.json()["status"] == "success"
    assert "user_id" in res.json()
    assert "access_token" in res.cookies


def test_register_password_too_short(client):
    """Passwort < 8 Zeichen → 422 Validation Error."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "neu@example.com",
        "password":       "kurz",
        "accepted_terms": True,
    })
    assert res.status_code == 422


def test_register_terms_not_accepted(client):
    """AGB nicht akzeptiert → 422."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "neu@example.com",
        "password":       "sicheresPasswort123",
        "accepted_terms": False,
    })
    assert res.status_code == 422


def test_register_duplicate_email(client, test_user):
    """Bereits registrierte E-Mail → 409."""
    res = client.post("/api/v1/auth/register", json={
        "email":          test_user.email,
        "password":       "anderesPasswort123",
        "accepted_terms": True,
    })
    assert res.status_code == 409


def test_register_auto_login(client):
    """Nach Registrierung ist der Nutzer direkt eingeloggt (Cookie gesetzt)."""
    res = client.post("/api/v1/auth/register", json={
        "email":          "autoLogin@example.com",
        "password":       "sicheresPasswort123",
        "accepted_terms": True,
    })
    assert res.status_code == 201
    # Cookie erlaubt sofortigen Zugriff auf geschützte Endpunkte
    cases = client.get("/api/v1/cases")
    assert cases.status_code == 200


# ── US-1.3: Login ─────────────────────────────────────────────────────────────


def test_login_success(client, test_user):
    """Korrekte Credentials → 200 + JWT-Cookie."""
    res = client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "sicheresPasswort123",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "access_token" in res.cookies


def test_login_wrong_password(client, test_user):
    """Falsches Passwort → 401."""
    res = client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "falschesPasswort!",
    })
    assert res.status_code == 401


def test_login_unknown_email(client):
    """Nicht registrierte E-Mail → 401 (kein Account-Enumeration-Leak)."""
    res = client.post("/api/v1/auth/login", json={
        "email":    "gibts.nicht@example.com",
        "password": "irgendeinPasswort123",
    })
    assert res.status_code == 401


def test_login_error_message_is_neutral(client, test_user):
    """
    Fehlermeldung für falsches Passwort und unbekannte E-Mail ist identisch.
    Verhindert Account-Enumeration.
    """
    wrong_pw = client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "falsch!",
    })
    unknown = client.post("/api/v1/auth/login", json={
        "email": "unbekannt@example.com", "password": "falsch!",
    })
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]


def test_login_grants_access_to_protected_routes(client, test_user):
    """Nach Login sind geschützte Endpunkte erreichbar."""
    client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "sicheresPasswort123",
    })
    res = client.get("/api/v1/cases")
    assert res.status_code == 200


# ── US-1.5: Logout ────────────────────────────────────────────────────────────


def test_logout_success(client, test_user):
    """Eingeloggter Nutzer kann sich abmelden → 200."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "sicheresPasswort123",
    })
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_logout_revokes_access(client, test_user):
    """Nach Logout sind geschützte Endpunkte nicht mehr erreichbar."""
    client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "sicheresPasswort123",
    })
    client.post("/api/v1/auth/logout")
    # Cookie ist gelöscht – nächster Request muss 401 zurückgeben
    res = client.get("/api/v1/cases")
    assert res.status_code == 401


def test_logout_without_auth(client):
    """Logout ohne Cookie → 401."""
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 401


# ── US-1.8: Passwort-Reset ────────────────────────────────────────────────────


def test_forgot_password_known_email(client, test_user):
    """Bekannte E-Mail → 200 mit Bestätigungsmeldung."""
    res = client.post("/api/v1/auth/forgot-password", json={"email": test_user.email})
    assert res.status_code == 200
    assert "message" in res.json()


def test_forgot_password_unknown_email(client):
    """Unbekannte E-Mail → trotzdem 200 (kein Enumeration-Leak)."""
    res = client.post("/api/v1/auth/forgot-password", json={"email": "nein@example.com"})
    assert res.status_code == 200
    assert "message" in res.json()


def test_forgot_password_response_is_identical(client, test_user):
    """
    Antwort für bekannte und unbekannte E-Mail ist exakt gleich.
    Verhindert, dass Angreifer gültige Accounts ermitteln können.
    """
    known   = client.post("/api/v1/auth/forgot-password", json={"email": test_user.email})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nein@example.com"})
    assert known.json()["message"] == unknown.json()["message"]


def test_reset_password_valid_token(client, db, test_user):
    """Gültiges Reset-Token → Passwort wird geändert, altes Passwort ungültig."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token":    raw_token,
        "password": "neuesPasswort456",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Altes Passwort schlägt fehl
    old_login = client.post("/api/v1/auth/login", json={
        "email": test_user.email, "password": "sicheresPasswort123",
    })
    assert old_login.status_code == 401

    # Neues Passwort funktioniert
    new_login = client.post("/api/v1/auth/login", json={
        "email": test_user.email, "password": "neuesPasswort456",
    })
    assert new_login.status_code == 200


def test_reset_password_expired_token(client, db, test_user):
    """Abgelaufenes Token → 400."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # abgelaufen
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "neuesPasswort456",
    })
    assert res.status_code == 400


def test_reset_password_wrong_token(client):
    """Komplett falsches Token → 400."""
    res = client.post("/api/v1/auth/reset-password", json={
        "token": "komplett-falsches-token-xyz123", "password": "neuesPasswort456",
    })
    assert res.status_code == 400


def test_reset_password_single_use(client, db, test_user):
    """Bereits verwendetes Token → 400 (Token ist einmalig)."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        used=True,  # bereits verwendet
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "neuesPasswort456",
    })
    assert res.status_code == 400


def test_reset_password_short_password(client, db, test_user):
    """Neues Passwort zu kurz → 422."""
    raw_token, token_hash = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    ))
    db.commit()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "kurz",
    })
    assert res.status_code == 422
