"""
PII Masking Utilities – Local Presidio/Regex.

Maskiert sensible Daten (IBAN, E-Mail, etc.) vor Anzeige oder LLM-Transfer.
Privacy-by-Design: Nur maskierte Texte an Dienste senden wo nötig.

Presidio (optional): pip install presidio-analyzer presidio-anonymizer
  + python -m spacy download de_core_news_sm
  Setze USE_PRESIDIO=1 um Presidio statt reiner Regex-Maskierung zu nutzen.
"""

import re
from typing import Optional

# Presidio optional – bei Fehlern/fehlender Installation Fallback auf Regex
_USE_PRESIDIO: Optional[bool] = None

def _presidio_available() -> bool:
    global _USE_PRESIDIO
    if _USE_PRESIDIO is not None:
        return _USE_PRESIDIO
    try:
        import os
        if not os.environ.get("USE_PRESIDIO", "").strip().lower() in ("1", "true", "yes"):
            _USE_PRESIDIO = False
            return False
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
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
