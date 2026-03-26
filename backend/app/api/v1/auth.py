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
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

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
    # Pflicht-Profildaten (US-7.3) – für rechtssicheres Dossier benötigt
    first_name: str
    last_name: str
    street: str
    postal_code: str
    city: str

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

    @field_validator("postal_code")
    @classmethod
    def postal_code_format(cls, v: str) -> str:
        if not re.match(r"^\d{5}$", v.strip()):
            raise ValueError("PLZ muss genau 5 Ziffern haben (z.B. 12345).")
        return v.strip()

    @field_validator("first_name", "last_name", "street", "city")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Pflichtfeld darf nicht leer sein.")
        return v.strip()


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


# ── Response Schemas ──────────────────────────────────────────────────────────


class RegisterResponse(BaseModel):
    """Response für POST /auth/register."""

    status: str
    user_id: str
    message: str


class LoginResponse(BaseModel):
    """Response für POST /auth/login."""

    status: str
    user_id: str


class MeResponse(BaseModel):
    """Response für GET /auth/me."""

    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    street: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    profile_complete: bool


class LogoutResponse(BaseModel):
    """Response für POST /auth/logout."""

    status: str
    message: str


class MessageResponse(BaseModel):
    """Generische Nachrichtenantwort (forgot-password)."""

    message: str


class StatusMessageResponse(BaseModel):
    """Response mit Status und Nachricht (reset-password)."""

    status: str
    message: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> RegisterResponse:
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

    logger.info("Neuer Nutzer registriert: %s", user.id)
    return RegisterResponse(
        status="success",
        user_id=str(user.id),
        message="Registrierung erfolgreich. Du bist eingeloggt.",
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/15 minutes")
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
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

    return LoginResponse(status="success", user_id=str(user.id))


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUser) -> MeResponse:
    """
    Gibt die Daten des aktuell eingeloggten Nutzers zurück.
    Wird vom Frontend beim App-Start aufgerufen, um den Session-Status zu prüfen.
    401 wenn kein gültiges Cookie vorhanden.

    profile_complete: True wenn alle Pflichtfelder (US-7.3) ausgefüllt sind.
    Ist False bei Bestandsnutzern ohne Profildaten → Frontend leitet zu /complete-profile.
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
    """Löscht das Session-Cookie und beendet die Session."""
    response.delete_cookie(key=COOKIE_NAME, samesite="lax")
    return LogoutResponse(status="success", message="Erfolgreich abgemeldet.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """
    Generiert Reset-Token und sendet E-Mail via Resend.

    Gibt immer dieselbe Antwort zurück – unabhängig ob E-Mail registriert ist
    (verhindert Enumeration).
    """
    _neutral_response = MessageResponse(
        message="Falls ein Account existiert, wurde eine E-Mail gesendet."
    )

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
    return _neutral_response  # type: ignore[return-value]


@router.post("/reset-password", response_model=StatusMessageResponse)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> StatusMessageResponse:
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
    return StatusMessageResponse(status="success", message="Passwort erfolgreich geändert.")


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
