"""
PII-Masking Engine – Epic 2 (US-2.5).

Maskiert sensible Personendaten (IBAN, E-Mail) im extrahierten Dokumententext,
bevor dieser die KI-Pipeline erreicht. Das Originaldokument im S3-Bucket bleibt
strikt unangetastet – nur der Rohtext wird maskiert und im DB-Feld masked_text
gespeichert.

Regex-Muster:
  IBAN: Deutsche IBANs (DE + 20 Ziffern), kompakt oder mit Leerzeichen (4er-Gruppen)
  E-Mail: Alle gängigen E-Mail-Adressen

Optionales Upgrade: USE_PRESIDIO=1 aktiviert NLP-basierte Presidio-Maskierung
  (Namen, Telefon, Adressen etc.) – Fallback auf Regex falls Presidio fehlt.
"""

import re
from typing import Optional

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


def mask_pii(text: Optional[str]) -> str:
    """
    Wendet vollständige PII-Maskierung auf den extrahierten Text an.

    Reihenfolge: IBAN → E-Mail (Regex).
    Mit USE_PRESIDIO=1 wird Presidio für erweiterte NLP-Erkennung genutzt
    (Namen, Telefon, Adressen) – Fallback auf Regex falls Presidio fehlt.

    Args:
        text: Rohtext aus OCR/PDF-Extraktion.

    Returns:
        Maskierter Text (IBAN → ***IBAN***, E-Mail → ***@***.***).
    """
    if not text:
        return text or ""
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
