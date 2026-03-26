"""
FastAPI Dependencies: Authentifizierung & DB-Injection.

get_current_user: Liest JWT aus HttpOnly-Cookie, verifiziert ihn
  und gibt den authentifizierten User zurück. Alle geschützten Routen
  nutzen Depends(get_current_user).

Sicherheitsprinzip: Fremde Case-IDs → 404 (nicht 403),
  um keine Information über existierende Ressourcen zu leaken.
"""

import uuid
from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.domain.models.db import Case, User
from app.infrastructure.database import get_db


def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Extrahiert und verifiziert JWT aus HttpOnly-Cookie.

    Raises:
        HTTPException 401: Kein Token oder ungültiger Token.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert.")

    payload = decode_access_token(access_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Ungültiger oder abgelaufener Token.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Ungültiger Token-Inhalt.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Nutzer nicht gefunden.")

    return user


# Typed Annotated Alias für saubere Router-Signaturen
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_owned_case(case_id: str, current_user: User, db: Session) -> Case:
    """
    Lädt einen Fall und prüft Eigentümerschaft.

    Gibt bei ungültiger UUID, nicht gefundenem Fall oder Fremdfall immer
    einen 404-Fehler zurück (kein Informationsleak über existierende IDs).

    Args:
        case_id: UUID-String des Falls.
        current_user: Authentifizierter Nutzer aus dem JWT-Cookie.
        db: SQLAlchemy-Datenbankverbindung.

    Returns:
        Das geladene Case-ORM-Objekt.

    Raises:
        HTTPException: 404 wenn die UUID ungültig ist, der Fall nicht existiert
            oder einem anderen Nutzer gehört.
    """
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    case = (
        db.query(Case)
        .filter(Case.id == case_uuid, Case.user_id == current_user.id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    return case
