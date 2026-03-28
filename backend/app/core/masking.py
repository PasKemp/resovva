"""
PII-Masking Engine – Epic 2 (US-2.5) + Epic 8 (US-8.3).

Maskiert sensible Personendaten im extrahierten Dokumententext, bevor dieser
die KI-Pipeline erreicht. Das Originaldokument im S3-Bucket bleibt unberührt –
nur der Rohtext wird maskiert und im DB-Feld masked_text gespeichert.

Maskierungs-Layer (in Reihenfolge):
  1. Regex        – IBAN → ***IBAN***, E-Mail → ***@***.*** (immer aktiv)
  2. Profil-Block – Straße/PLZ des Nutzers → ***ADRESSE*** (USE_PRESIDIO_DEEP=1)
  3. NER          – Telefon → ***TELEFON***, Datum → ***GEBURTSDATUM*** (USE_PRESIDIO_DEEP=1)

Fallback-Modus: USE_PRESIDIO=1 aktiviert die alte generische Presidio-Maskierung
  ohne entity-spezifische Tokens (rückwärtskompatibel, kein spaCy nötig).

Namen (PERSON-Entitäten) werden in Layer 3 bewusst nicht maskiert, damit
die Chronologie- und Analyse-Logik Gegner/Absender identifizieren kann.
"""

import re
from typing import Optional

from app.core.privacy_engine import (
    build_profile_blocklist,
    deep_masking_available,
    mask_ner,
    mask_profile_blocklist,
)

# ── Regex-Muster ──────────────────────────────────────────────────────────────

# Deutsche IBAN: DE + 2 Prüfziffern + 8 BLZ-Stellen + 10 Kto-Stellen = 22 Zeichen
# Spec (EPIC2 US-2.5): r'DE\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2}'
# Optionale Leerzeichen nach JEDER Zifferngruppe – deckt kompakt, standard und
# gemischte Schreibweisen (z.B. "DE89 37040044 0532013000") ab.
IBAN_PATTERN = re.compile(
    r"DE\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2}\b",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

IBAN_REPLACEMENT  = "***IBAN***"
EMAIL_REPLACEMENT = "***@***.***"


# ── Kern-Maskierung ───────────────────────────────────────────────────────────

def mask_iban(text: str) -> str:
    """Ersetzt alle deutschen IBANs (kompakt + mit Leerzeichen) im Text."""
    return IBAN_PATTERN.sub(IBAN_REPLACEMENT, text)


def mask_email(text: str) -> str:
    """Ersetzt alle E-Mail-Adressen im Text."""
    return EMAIL_PATTERN.sub(EMAIL_REPLACEMENT, text)


def mask_pii(
    text: Optional[str],
    *,
    street: Optional[str] = None,
    postal_code: Optional[str] = None,
) -> str:
    """
    Wendet vollständige PII-Maskierung auf den extrahierten Text an.

    Layer-Reihenfolge (Epic 8 US-8.3):
      1. Regex (IBAN → ***IBAN***, E-Mail → ***@***.***) – immer aktiv.
      2. Profil-Blockliste (Straße/PLZ → ***ADRESSE***) – nur mit USE_PRESIDIO_DEEP=1.
      3. NER (Telefon → ***TELEFON***, Datum → ***GEBURTSDATUM***) – nur mit USE_PRESIDIO_DEEP=1.

    Wenn USE_PRESIDIO_DEEP nicht gesetzt: Fallback auf USE_PRESIDIO (alte generische
    Presidio-Maskierung) oder reines Regex.

    Args:
        text:        Rohtext aus OCR/PDF-Extraktion.
        street:      Straße/Hausnummer des Nutzers für die Profil-Blockliste.
        postal_code: PLZ des Nutzers für die Profil-Blockliste.

    Returns:
        Maskierter Text.
    """
    if not text:
        return text or ""

    if deep_masking_available():
        # Layer 1: Regex
        result = mask_email(mask_iban(text))
        # Layer 2: Profil-Blockliste
        blocklist = build_profile_blocklist(street, postal_code)
        if blocklist:
            result = mask_profile_blocklist(result, blocklist)
        # Layer 3: NER (Telefon, Datum – PERSON ausgelassen)
        result = mask_ner(result)
        return result

    # Fallback: alte generische Presidio-Maskierung
    if _presidio_available():
        try:
            return _mask_presidio(text)
        except Exception:
            pass

    return mask_email(mask_iban(text))


# ── Presidio (optional) ───────────────────────────────────────────────────────

_presidio_checked: Optional[bool] = None


def _presidio_available() -> bool:
    global _presidio_checked
    if _presidio_checked is not None:
        return _presidio_checked
    import os
    if os.environ.get("USE_PRESIDIO", "").strip().lower() not in ("1", "true", "yes"):
        _presidio_checked = False
        return False
    try:
        import presidio_analyzer  # noqa: F401
        import presidio_anonymizer  # noqa: F401
        _presidio_checked = True
    except ImportError:
        _presidio_checked = False
    return _presidio_checked


def _mask_presidio(text: str) -> str:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    analyzer  = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    results = analyzer.analyze(text=text, language="de")
    if not results:
        return text
    return anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={"DEFAULT": OperatorConfig("replace", {"new_value": "***"})},
    ).text
