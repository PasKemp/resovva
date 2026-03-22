"""
Auth Router – Epic 1: User Onboarding & Session Management.

Endpunkte:
  POST /auth/register       – Registrierung + automatischer Login
  POST /auth/login          – Login (mit Brute-Force-Schutz: 5/15min)
  POST /auth/logout         – Session-Cookie löschen
  POST /auth/forgot-password – Reset-Token generieren + Mail senden
  POST /auth/reset-password  – Passwort mit Token zurücksetzen

Session-Management: JWT in HttpOnly + Secure + SameSite=Lax Cookie.
Brute-Force-Schutz: slowapi Rate Limiting auf /login (5 Versuche/15min/IP).
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.domain.models.db import PasswordResetToken, User
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT-Cookie-Konfiguration
COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 Tage in Sekunden


def _set_auth_cookie(response: Response, token: str) -> None:
    """Setzt das HttpOnly-Session-Cookie mit dem JWT."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        # secure=True,  # In Production aktivieren (HTTPS erforderlich)
    )


# ── Request / Response Schemas ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    accepted_terms: bool

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein.")
        return v

    @field_validator("accepted_terms")
    @classmethod
    def terms_must_be_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("AGB und Datenschutzerklärung müssen akzeptiert werden.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein.")
        return v


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """
    Legt neuen Nutzer an und setzt direkt das Session-Cookie (kein separater Login nötig).

    Gibt generische Fehlermeldung bei bereits registrierter E-Mail zurück,
    um Account-Enumeration zu verhindern.
    """
    # Prüfen ob E-Mail bereits existiert (generische Meldung – kein Enumeration-Leak)
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="E-Mail wird bereits verwendet.")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        accepted_terms=body.accepted_terms,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    _set_auth_cookie(response, token)

    logger.info("Neuer Nutzer registriert: %s", user.id)
    return {
        "status": "success",
        "user_id": str(user.id),
        "message": "Registrierung erfolgreich. Du bist eingeloggt.",
    }


@router.post("/login")
@limiter.limit("5/15 minutes")
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Prüft Credentials und setzt Session-Cookie.
    Rate-Limit: max. 5 Versuche pro IP in 15 Minuten (Brute-Force-Schutz).

    Gibt neutrale Fehlermeldung zurück (kein Account-Enumeration-Leak).
    """
    # Neutrale Fehlermeldung – egal ob User nicht existiert oder Passwort falsch
    _auth_error = HTTPException(
        status_code=401,
        detail="E-Mail oder Passwort falsch.",
    )

    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise _auth_error

    token = create_access_token(str(user.id))
    _set_auth_cookie(response, token)

    return {"status": "success", "user_id": str(user.id)}


@router.post("/logout")
def logout(response: Response, _: CurrentUser):
    """Löscht das Session-Cookie und beendet die Session."""
    response.delete_cookie(key=COOKIE_NAME, samesite="lax")
    return {"status": "success", "message": "Erfolgreich abgemeldet."}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generiert Reset-Token und sendet E-Mail via Resend.

    Gibt immer dieselbe Antwort zurück – unabhängig ob E-Mail registriert ist
    (verhindert Enumeration).
    """
    _neutral_response = {
        "message": "Falls ein Account existiert, wurde eine E-Mail gesendet."
    }

    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        # Kein Leak – trotzdem 200 zurückgeben
        return _neutral_response

    # Altes Token invalidieren (1 aktives Token pro User)
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
    return _neutral_response


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Setzt Passwort mit gültigem Reset-Token zurück.
    Token wird danach invalidiert (einmalige Verwendung).
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
        raise HTTPException(
            status_code=400,
            detail="Token ungültig oder abgelaufen. Bitte neuen Reset anfragen.",
        )

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Nutzer nicht gefunden.")

    user.hashed_password = hash_password(body.password)
    record.used = True
    db.commit()

    logger.info("Passwort zurückgesetzt für User: %s", user.id)
    return {"status": "success", "message": "Passwort erfolgreich geändert."}


# ── E-Mail-Hilfsfunktion ─────────────────────────────────────────────────────

def _send_reset_email(email: str, raw_token: str) -> None:
    """
    Sendet Passwort-Reset-Mail via Resend SDK.
    Fallback: Reset-URL wird im Log ausgegeben (für lokale Entwicklung).
    """
    from app.core.config import get_settings

    settings = get_settings()
    reset_url = f"http://localhost:5173/reset-password?token={raw_token}"

    if not settings.resend_api_key:
        # Lokale Entwicklung: URL ins Log schreiben statt Mail senden
        logger.warning(
            "RESEND_API_KEY nicht gesetzt. Reset-URL (nur für DEV): %s", reset_url
        )
        return

    try:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": settings.email_from,
            "to": email,
            "subject": "Dein Resovva Passwort zurücksetzen",
            "html": (
                f"<p>Du hast eine Passwort-Zurücksetzung angefragt.</p>"
                f"<p><a href='{reset_url}'>Passwort zurücksetzen</a></p>"
                f"<p>Dieser Link ist 15 Minuten gültig.</p>"
                f"<p>Falls du diese Anfrage nicht gestellt hast, ignoriere diese Mail.</p>"
            ),
        })
    except Exception as exc:
        # Mail-Fehler dürfen den API-Request nicht zum Absturz bringen
        logger.error("Fehler beim Senden der Reset-Mail: %s", exc)
