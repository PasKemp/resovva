"""
Users Router – Epic 7 (US-7.4): Profilseite – Daten ändern & Account löschen.

Endpunkte:
  PUT    /users/me           – Profildaten aktualisieren (Name, Adresse)
  PUT    /users/me/password  – Passwort ändern (altes Passwort erforderlich)
  DELETE /users/me           – Account unwiderruflich löschen (DSGVO Hard-Delete)
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.security import hash_password, verify_password
from app.domain.models.db import Case, User
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ── Request Schemas ───────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    first_name: str
    last_name: str
    street: str
    postal_code: str
    city: str

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


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein.")
        return v


# ── PUT /users/me ─────────────────────────────────────────────────────────────

@router.put("/me")
def update_profile(
    body:         UpdateProfileRequest,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
):
    """
    Aktualisiert Profildaten (Name, Adresse) des eingeloggten Nutzers.
    Wird sowohl von der Profilseite (US-7.4) als auch von der
    Profil-Vervollständigung (US-7.3 Bestandsnutzer) aufgerufen.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Nutzer nicht gefunden.")

    user.first_name  = body.first_name
    user.last_name   = body.last_name
    user.street      = body.street
    user.postal_code = body.postal_code
    user.city        = body.city
    db.commit()

    logger.info("Profildaten aktualisiert: %s", current_user.id)
    return {"status": "success", "message": "Profil erfolgreich aktualisiert."}


# ── PUT /users/me/password ────────────────────────────────────────────────────

@router.put("/me/password")
def change_password(
    body:         ChangePasswordRequest,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
):
    """
    Ändert das Passwort. Erfordert das aktuelle Passwort zur Bestätigung.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Nutzer nicht gefunden.")

    if not verify_password(body.old_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Aktuelles Passwort ist falsch.")

    user.hashed_password = hash_password(body.new_password)
    db.commit()

    logger.info("Passwort geändert: %s", current_user.id)
    return {"status": "success", "message": "Passwort erfolgreich geändert."}


# ── DELETE /users/me ──────────────────────────────────────────────────────────

@router.delete("/me", status_code=204)
def delete_account(
    current_user: CurrentUser,
    response:     Response,
    db:           Session = Depends(get_db),
):
    """
    Löscht den Account und alle zugehörigen Daten permanent (DSGVO Hard-Delete).

    Reihenfolge: Storage (S3) → Qdrant → PostgreSQL (User inkl. aller Cases via CASCADE).
    Session-Cookie wird nach dem Löschen entfernt.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Nutzer nicht gefunden.")

    # 1. S3-Dateien aller Cases löschen
    _delete_all_storage(user, db)

    # 2. Qdrant-Embeddings löschen (Stub – aktivieren wenn Epic 3 fertig)
    _delete_all_qdrant(str(current_user.id))

    # 3. User löschen (CASCADE löscht Cases → Documents → ChronologyEvents)
    db.delete(user)
    db.commit()

    # Session-Cookie entfernen
    response.delete_cookie(key="access_token", samesite="lax")

    logger.info("Account und alle Daten gelöscht: %s", current_user.id)
    # 204 No Content – kein Body


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _delete_all_storage(user: User, db: Session) -> None:
    """Löscht alle S3-Dateien aller Cases des Nutzers."""
    from app.infrastructure.storage import get_storage
    storage = get_storage()
    cases = db.query(Case).filter(Case.user_id == user.id).all()
    for case in cases:
        for document in case.documents:
            try:
                storage.delete_file(document.s3_key)
            except Exception as exc:
                logger.error("Storage-Fehler beim Account-Delete (%s): %s", document.s3_key, exc)


def _delete_all_qdrant(user_id: str) -> None:
    """Löscht alle Vektor-Embeddings des Nutzers (Stub)."""
    try:
        logger.debug("Qdrant-Delete (Stub) für User: %s", user_id)
    except Exception as exc:
        logger.error("Qdrant-Fehler beim Account-Delete (User %s): %s", user_id, exc)
