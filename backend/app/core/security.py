"""
Security Utilities – PII-Maskierung, Passwort-Hashing und JWT.

PII Masking:
  Maskiert sensible Daten (IBAN, E-Mail) vor LLM-Transfer.
  Presidio (optional): pip install presidio-analyzer presidio-anonymizer
    + python -m spacy download de_core_news_sm
    Setze USE_PRESIDIO=1 für erweiterte NLP-basierte Maskierung.

Auth:
  hash_password / verify_password – bcrypt via passlib
  create_access_token / decode_access_token – HS256 JWT via python-jose
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# ── Passwort-Hashing (bcrypt) ─────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hasht ein Passwort mit bcrypt. Niemals Klartext speichern."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Prüft ein Klartextpasswort gegen den gespeicherten bcrypt-Hash."""
    return _pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    """Erstellt ein signiertes JWT mit user_id als Subject und 7-Tage-Ablauf."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """Verifiziert und dekodiert ein JWT. Gibt None zurück wenn ungültig/abgelaufen."""
    try:
        settings = get_settings()
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None


# ── Passwort-Reset-Token ──────────────────────────────────────────────────────

def generate_reset_token() -> tuple[str, str]:
    """
    Generiert ein kryptographisch sicheres Reset-Token.

    Returns:
        (raw_token, token_hash) – raw_token per Mail senden, hash in DB speichern.
    """
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def hash_reset_token(raw_token: str) -> str:
    """SHA-256-Hash eines Raw-Tokens (für DB-Lookup)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


# Presidio optional – bei Fehlern/fehlender Installation Fallback auf Regex
_USE_PRESIDIO: Optional[bool] = None

def _presidio_available() -> bool:
    global _USE_PRESIDIO
    if _USE_PRESIDIO is not None:
        return _USE_PRESIDIO
    try:
        import os
        if os.environ.get("USE_PRESIDIO", "").strip().lower() not in ("1", "true", "yes"):
            _USE_PRESIDIO = False
            return False
        from presidio_analyzer import AnalyzerEngine  # noqa: F401
        from presidio_anonymizer import AnonymizerEngine  # noqa: F401
        _USE_PRESIDIO = True
        return True
    except ImportError:
        _USE_PRESIDIO = False
        return False


# Deutsche IBAN: DE + 2 Prüfziffern + 8 BLZ + 10 Kontonummer = 22 Zeichen
# Erlaubt: mit Leerzeichen (4er-Gruppen) oder kompakt
_IBAN_DE_COMPACT = r"DE\d{20}\b"
_IBAN_DE_SPACED = r"DE\d{2}\s+\d{4}\s+\d{4}\s+\d{4}\s+\d{4}\s+\d{2}\b"
IBAN_PATTERN = re.compile(
    f"(?:{_IBAN_DE_COMPACT}|{_IBAN_DE_SPACED})",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


def mask_iban(text: str, replacement: str = "***IBAN***") -> str:
    """Ersetzt deutsche IBANs im Text (kompakt oder mit Leerzeichen)."""
    return IBAN_PATTERN.sub(replacement, text)


def mask_email(text: str, replacement: str = "***@***.***") -> str:
    """Ersetzt E-Mail-Adressen im Text."""
    return EMAIL_PATTERN.sub(replacement, text)


def _mask_pii_regex(text: str) -> str:
    """Reine Regex-Maskierung (Fallback ohne Presidio)."""
    if not text:
        return text
    return mask_email(mask_iban(text))


def _mask_pii_presidio(text: str) -> str:
    """Presidio-basierte Maskierung (Namen, Telefon, IBAN, E-Mail, etc.)."""
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    # Deutsche Sprache für bessere Erkennung (Rechnungen/Verträge)
    results = analyzer.analyze(text=text, language="de")
    if not results:
        return text
    return anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={"DEFAULT": OperatorConfig("replace", {"new_value": "***"})},
    ).text


def mask_pii(text: Optional[str]) -> str:
    """
    Wendet PII-Maskierung auf den Text an.
    Nutzt Presidio, wenn USE_PRESIDIO=1 gesetzt und Pakete installiert sind,
    sonst Regex für IBAN + E-Mail.
    """
    if not text:
        return text or ""
    if _presidio_available():
        try:
            return _mask_pii_presidio(text)
        except Exception:
            return _mask_pii_regex(text)
    return _mask_pii_regex(text)
