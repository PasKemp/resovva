"""
Unit-Tests für den Deep Privacy Engine (Epic 8).

US-8.1: detect_pii erkennt Telefonnummern (Presidio NER).
US-8.2: Profil-Blockliste maskiert Straße und PLZ.
US-8.3: mask_ner – PERSON bleibt erhalten, Telefon wird maskiert.

NER-Tests laufen nur wenn USE_PRESIDIO_DEEP=1 und de_core_news_lg installiert.
"""

import pytest
from app.core.privacy_engine import (
    ADDRESS_TOKEN,
    PHONE_TOKEN,
    build_profile_blocklist,
    deep_masking_available,
    detect_pii,
    mask_ner,
    mask_profile_blocklist,
)


# ── US-8.2: build_profile_blocklist ─────────────────────────────────────────

class TestBuildProfileBlocklist:
    """Blockliste aus Nutzerprofil korrekt befüllt."""

    def test_beide_felder(self):
        result = build_profile_blocklist("Musterstraße 12", "80331")
        assert "Musterstraße 12" in result
        assert "80331" in result
        assert len(result) == 2

    def test_nur_strasse(self):
        result = build_profile_blocklist("Hauptstraße 1", None)
        assert result == ["Hauptstraße 1"]

    def test_nur_plz(self):
        result = build_profile_blocklist(None, "10115")
        assert result == ["10115"]

    def test_beide_none(self):
        assert build_profile_blocklist(None, None) == []

    def test_leerzeichen_only(self):
        assert build_profile_blocklist("  ", "  ") == []

    def test_leerzeichen_werden_getrimmt(self):
        result = build_profile_blocklist("  Musterweg 5  ", "  01234  ")
        assert "Musterweg 5" in result
        assert "01234" in result


# ── US-8.2: mask_profile_blocklist ──────────────────────────────────────────

class TestMaskProfileBlocklist:
    """Blocklisten-Einträge case-insensitiv durch ***ADRESSE*** ersetzen."""

    def test_strasse_maskiert(self):
        text = "Absender: Musterstraße 12, München"
        result = mask_profile_blocklist(text, ["Musterstraße 12"])
        assert ADDRESS_TOKEN in result
        assert "Musterstraße 12" not in result

    def test_plz_maskiert(self):
        text = "PLZ: 80331 München"
        result = mask_profile_blocklist(text, ["80331"])
        assert ADDRESS_TOKEN in result
        assert "80331" not in result

    def test_case_insensitive(self):
        text = "wohnhaft in musterstraße 12"
        result = mask_profile_blocklist(text, ["Musterstraße 12"])
        assert ADDRESS_TOKEN in result

    def test_beide_felder_maskiert(self):
        text = "Adresse: Musterstraße 12, 80331 München"
        result = mask_profile_blocklist(text, ["Musterstraße 12", "80331"])
        assert result.count(ADDRESS_TOKEN) == 2
        assert "Musterstraße 12" not in result
        assert "80331" not in result

    def test_leere_blockliste(self):
        text = "Keine Änderung erwartet"
        assert mask_profile_blocklist(text, []) == text

    def test_stadt_bleibt_erhalten(self):
        text = "Musterstraße 12, München"
        result = mask_profile_blocklist(text, ["Musterstraße 12"])
        assert "München" in result

    def test_kein_false_positive(self):
        text = "Rechnungsnummer: 80331-2024-01"
        result = mask_profile_blocklist(text, ["Musterstraße 12"])
        assert ADDRESS_TOKEN not in result

    def test_mehrfach_im_text(self):
        text = "Von: Musterstraße 12. An: Musterstraße 12."
        result = mask_profile_blocklist(text, ["Musterstraße 12"])
        assert result.count(ADDRESS_TOKEN) == 2


# ── US-8.1 / US-8.3: NER via Presidio ────────────────────────────────────────

_needs_ner = pytest.mark.skipif(
    not deep_masking_available(),
    reason="USE_PRESIDIO_DEEP=1 und de_core_news_lg erforderlich",
)


@_needs_ner
class TestDetectPii:
    """detect_pii erkennt Telefon-Entitäten, nicht PERSON."""

    def test_telefon_erkannt(self):
        detections = detect_pii("Rufen Sie uns an: 0176-123456")
        entity_types = [d["entity_type"] for d in detections]
        assert "PHONE_NUMBER" in entity_types

    def test_person_nicht_in_ergebnis(self):
        """PERSON wird nie zurückgegeben – nur PHONE_NUMBER, DATE_TIME, STREET_ADDRESS."""
        detections = detect_pii("Pascal Kempmann wohnt in München.")
        entity_types = [d["entity_type"] for d in detections]
        assert "PERSON" not in entity_types

    def test_strassenadresse_erkannt(self):
        detections = detect_pii("Absender: Musterstraße 12, München")
        entity_types = [d["entity_type"] for d in detections]
        assert "STREET_ADDRESS" in entity_types

    def test_ergebnis_hat_felder(self):
        detections = detect_pii("Telefon: 089-12345678")
        for d in detections:
            assert "entity_type" in d
            assert "start" in d
            assert "end" in d
            assert "score" in d

    def test_leerer_text(self):
        assert detect_pii("") == []


@_needs_ner
class TestMaskNer:
    """mask_ner: PERSON bleibt, Telefon wird zu ***TELEFON*** (US-8.3-Kerntest)."""

    def test_telefon_maskiert(self):
        result = mask_ner("Rufen Sie uns an: 0176-123456")
        assert PHONE_TOKEN in result
        assert "0176-123456" not in result

    def test_person_bleibt_erhalten(self):
        """
        US-8.3-Kerntest: „Pascal Kempmann" bleibt, „0176-123456" wird ***TELEFON***.
        PERSON ist aus der Entity-Liste ausgelassen (Allow-List).
        """
        text = "Pascal Kempmann hat folgende Nummer: 0176-123456"
        result = mask_ner(text)
        assert "Pascal Kempmann" in result
        assert PHONE_TOKEN in result
        assert "0176-123456" not in result

    def test_text_ohne_pii_unveraendert(self):
        text = "Jahresabrechnung 2025, Betrag: 347,85 €, MaLo: 50599000000000"
        result = mask_ner(text)
        # Keine Telefonnummer → Text weitgehend unverändert
        assert "347,85 €" in result
        assert "50599000000000" in result

    def test_leerer_string(self):
        assert mask_ner("") == ""

    def test_strassenadresse_nicht_maskiert(self):
        """NER maskiert keine Adressen – das übernimmt die Profil-Blockliste (US-8.2)."""
        text = "Wohnhaft in Musterstraße 12, Tel: 0176-123456"
        result = mask_ner(text)
        # Straßenname bleibt (Adress-Masking via Profil-Blockliste, nicht NER)
        assert "Musterstraße 12" in result
        # Telefon wird maskiert
        assert PHONE_TOKEN in result
