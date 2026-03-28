"""
Deep Privacy Engine – Epic 8 (US-8.1, US-8.2, US-8.3).

Erweiterte PII-Maskierung mit Microsoft Presidio + spaCy de_core_news_lg.
Ergänzt die Regex-Basisschicht aus masking.py um:
  - US-8.2: Profil-Blockliste (Straße/PLZ des Nutzers → ***ADRESSE***)
  - US-8.3: NER – Telefon → ***TELEFON***, Geburtsdaten → ***GEBURTSDATUM***

Erkennung (detect_pii) umfasst zusätzlich physische Straßenadressen via
Custom PatternRecognizer (außer Städten – nur Straße + Hausnummer). Die
Adress-Maskierung selbst erfolgt jedoch über die Profil-Blockliste (US-8.2),
nicht über NER, damit Straßennamen in Gegner-Adressen nicht maskiert werden.

PERSON-Entitäten werden bewusst nicht maskiert: Namen bleiben für die
Fall-Analyse (Chronologie, Gegner-Identifikation) erhalten.

Aktivierung:
  USE_PRESIDIO_DEEP=1 in der Umgebung setzen.

Voraussetzungen:
  pip install presidio-analyzer presidio-anonymizer spacy
  python -m spacy download de_core_news_lg
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Replacement-Tokens ───────────────────────────────────────────────────────

PHONE_TOKEN   = "***TELEFON***"
DATE_TOKEN    = "***GEBURTSDATUM***"
ADDRESS_TOKEN = "***ADRESSE***"

# Entities to return in detect_pii() – includes custom street address
_DETECT_ENTITIES: list[str] = ["PHONE_NUMBER", "DATE_TIME", "STREET_ADDRESS"]

# Entities → Token für mask_ner() (Adressen werden über Profil-Blockliste gehandhabt)
_MASK_ENTITY_TOKENS: dict[str, str] = {
    "PHONE_NUMBER": PHONE_TOKEN,
    "DATE_TIME":    DATE_TOKEN,
}

# ── Verfügbarkeits-Check (gecacht) ────────────────────────────────────────────

_available: Optional[bool] = None


def deep_masking_available() -> bool:
    """
    Prüft, ob USE_PRESIDIO_DEEP=1 gesetzt und alle Abhängigkeiten installiert sind.

    Returns:
        True wenn Deep Masking aktiv genutzt werden kann.
    """
    global _available
    if _available is not None:
        return _available

    import os
    if os.environ.get("USE_PRESIDIO_DEEP", "").strip().lower() not in ("1", "true", "yes"):
        _available = False
        return False

    try:
        import presidio_analyzer  # noqa: F401
        import presidio_anonymizer  # noqa: F401
        import spacy

        if not spacy.util.is_package("de_core_news_lg"):
            logger.warning(
                "spaCy-Modell 'de_core_news_lg' nicht gefunden – Deep Masking deaktiviert."
            )
            _available = False
            return False

        _available = True
    except ImportError as exc:
        logger.warning(
            "Presidio/spaCy nicht installiert – Deep Masking deaktiviert.",
            extra={"error": str(exc)},
        )
        _available = False

    return _available


# ── NLP-Engine (gecacht, lazy) ─────────────────────────────────────────────────

_analyzer: Optional[Any] = None
_anonymizer: Optional[Any] = None


def _get_analyzer() -> Any:
    """
    Lazy-Singleton AnalyzerEngine mit de_core_news_lg und Custom-Recognizern.

    Registriert einen PatternRecognizer für deutsche Straßenadressen
    (Straße + Hausnummer, ohne Städte) für US-8.1.
    """
    global _analyzer
    if _analyzer is not None:
        return _analyzer

    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer import PatternRecognizer, Pattern
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()

    # Custom Recognizer: Deutsche Straßenadressen (Straße + Hausnummer)
    # Erkennt z.B. "Musterstraße 12", "Hauptweg 4a", "Am Marktplatz 3"
    # Städtenamen werden nicht erkannt (kein Ortsname-Pattern)
    street_recognizer = PatternRecognizer(
        supported_entity="STREET_ADDRESS",
        supported_language="de",
        patterns=[
            Pattern(
                name="Deutsche Straßenadresse",
                regex=(
                    r"\b\w+(?:straße|strasse|weg|allee|gasse|platz|ring|damm"
                    r"|ufer|steig|str\.)\s+\d+[a-zA-Z]?\b"
                ),
                score=0.65,
            )
        ],
    )

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine)
    registry.add_recognizer(street_recognizer)

    _analyzer = AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["de"],
    )
    return _analyzer


def _get_anonymizer() -> Any:
    """Lazy-Singleton AnonymizerEngine."""
    global _anonymizer
    if _anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine
        _anonymizer = AnonymizerEngine()
    return _anonymizer


# ── US-8.1: PII-Erkennung ─────────────────────────────────────────────────────

def detect_pii(text: str) -> list[dict]:
    """
    Erkennt PII-Entitäten im Text mit Presidio NER (ohne PERSON).

    Erkennt:
      - PHONE_NUMBER  – Telefonnummern
      - DATE_TIME     – Datums- und Geburtsdaten
      - STREET_ADDRESS – Physische Straßenadressen (außer Städten)

    PERSON-Entitäten sind bewusst ausgelassen.

    Args:
        text: Eingabetext.

    Returns:
        Liste von Dicts (entity_type, start, end, score).
        Leere Liste wenn Deep Masking nicht verfügbar.
    """
    if not text or not deep_masking_available():
        return []

    try:
        analyzer = _get_analyzer()
        results = analyzer.analyze(
            text=text,
            language="de",
            entities=_DETECT_ENTITIES,
        )
        return [
            {
                "entity_type": r.entity_type,
                "start":       r.start,
                "end":         r.end,
                "score":       r.score,
            }
            for r in results
        ]
    except Exception as exc:
        logger.warning("detect_pii fehlgeschlagen", extra={"error": str(exc)})
        return []


# ── US-8.2: Profil-Blockliste ─────────────────────────────────────────────────

def build_profile_blocklist(
    street: Optional[str],
    postal_code: Optional[str],
) -> list[str]:
    """
    Erstellt eine Blockliste aus dem Nutzerprofil.

    Args:
        street:      Straße und Hausnummer (z.B. "Musterstraße 12").
        postal_code: Postleitzahl (z.B. "80331").

    Returns:
        Liste nicht-leerer Strings, die im Text maskiert werden sollen.
    """
    entries: list[str] = []
    if street and street.strip():
        entries.append(street.strip())
    if postal_code and postal_code.strip():
        entries.append(postal_code.strip())
    return entries


def mask_profile_blocklist(text: str, blocklist: list[str]) -> str:
    """
    Ersetzt Blocklisten-Einträge case-insensitiv durch ***ADRESSE***.

    Args:
        text:      Eingabetext.
        blocklist: Strings aus build_profile_blocklist().

    Returns:
        Text mit maskierten Adress-Bestandteilen.
    """
    for entry in blocklist:
        if not entry:
            continue
        pattern = re.compile(re.escape(entry), re.IGNORECASE)
        text = pattern.sub(ADDRESS_TOKEN, text)
    return text


# ── US-8.3: NER-Maskierung ────────────────────────────────────────────────────

def mask_ner(text: str) -> str:
    """
    Wendet NER-basierte Maskierung an (Telefon → ***TELEFON***, Datum → ***GEBURTSDATUM***).

    Adressen werden nicht über NER maskiert – das übernimmt die Profil-Blockliste
    (US-8.2). PERSON-Entitäten werden übersprungen (Allow-List): Namen bleiben für
    die Fall-Analyse erhalten.

    Gibt den unveränderten Text zurück wenn Deep Masking nicht verfügbar oder
    bei Ausnahmen (nie blockierend).

    Args:
        text: Eingabetext (nach Regex- und Blocklisten-Maskierung).

    Returns:
        Text mit maskierten NER-Entitäten.
    """
    if not text or not deep_masking_available():
        return text

    try:
        from presidio_anonymizer.entities import OperatorConfig

        analyzer   = _get_analyzer()
        anonymizer = _get_anonymizer()

        results = analyzer.analyze(
            text=text,
            language="de",
            entities=list(_MASK_ENTITY_TOKENS.keys()),
        )
        if not results:
            return text

        operators = {
            entity: OperatorConfig("replace", {"new_value": token})
            for entity, token in _MASK_ENTITY_TOKENS.items()
        }
        return anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        ).text

    except Exception as exc:
        logger.warning("mask_ner fehlgeschlagen – Text unverändert", extra={"error": str(exc)})
        return text
