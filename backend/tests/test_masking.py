"""
Unit-Tests für die PII-Masking Engine (US-2.5).

Testet IBAN- und E-Mail-Maskierung mit realen Varianten inkl. Edge Cases.
Mindestens 10 Varianten pro Typ laut Akzeptanzkriterien.
"""

import pytest
from app.core.masking import mask_iban, mask_email, mask_pii, IBAN_REPLACEMENT, EMAIL_REPLACEMENT


# ── IBAN-Tests ────────────────────────────────────────────────────────────────

class TestMaskIban:
    """Deutsche IBANs in verschiedenen Formaten müssen maskiert werden."""

    def test_iban_kompakt(self):
        assert mask_iban("IBAN: DE89370400440532013000") == f"IBAN: {IBAN_REPLACEMENT}"

    def test_iban_mit_leerzeichen_standard(self):
        assert mask_iban("DE89 3704 0044 0532 0130 00") == IBAN_REPLACEMENT

    def test_iban_am_satzanfang(self):
        result = mask_iban("DE12500105170648489890 ist meine IBAN.")
        assert IBAN_REPLACEMENT in result
        assert "DE12500105170648489890" not in result

    def test_iban_am_satzende(self):
        result = mask_iban("Bitte überweisen Sie auf DE12500105170648489890")
        assert IBAN_REPLACEMENT in result

    def test_iban_grossbuchstaben(self):
        result = mask_iban("DE89370400440532013000")
        assert result == IBAN_REPLACEMENT

    def test_iban_kleinbuchstaben_de(self):
        # Regex ist case-insensitive → auch "de" am Anfang maskiert
        result = mask_iban("de89370400440532013000")
        assert IBAN_REPLACEMENT in result

    def test_mehrere_ibans_im_text(self):
        text = "Konto 1: DE89370400440532013000, Konto 2: DE12500105170648489890"
        result = mask_iban(text)
        assert result.count(IBAN_REPLACEMENT) == 2
        assert "DE89" not in result
        assert "DE12" not in result

    def test_iban_in_rechnung(self):
        text = "Bitte zahlen Sie €120,00 auf folgendes Konto: DE44 5001 0517 5407 3249 31 – Vielen Dank!"
        result = mask_iban(text)
        assert IBAN_REPLACEMENT in result
        assert "DE44" not in result

    def test_iban_mit_extra_leerzeichen(self):
        # Leerzeichen zwischen Gruppen
        text = "DE44 5001 0517 5407 3249 31"
        result = mask_iban(text)
        assert IBAN_REPLACEMENT in result

    def test_kein_false_positive_normale_zahl(self):
        # Zufällige Zahl ohne DE-Prefix → nicht maskiert
        text = "Rechnungsnummer: 12345678901234567890"
        assert mask_iban(text) == text

    def test_kein_false_positive_kurztext(self):
        # DE mit zu wenig Ziffern → kein Match
        text = "DE123"
        assert mask_iban(text) == text

    def test_iban_zwischen_text(self):
        text = "Zahlung an DE89370400440532013000 erfolgt am 01.01.2026."
        result = mask_iban(text)
        assert IBAN_REPLACEMENT in result
        assert "DE89" not in result

    def test_iban_gemischte_schreibweise(self):
        # Leerzeichen nur an manchen Stellen – Spec erlaubt optionale Leerzeichen
        text = "DE89 37040044 0532013000"
        result = mask_iban(text)
        assert IBAN_REPLACEMENT in result


# ── E-Mail-Tests ──────────────────────────────────────────────────────────────

class TestMaskEmail:
    """E-Mail-Adressen in verschiedenen Formaten müssen maskiert werden."""

    def test_standard_email(self):
        assert mask_email("test@example.com") == EMAIL_REPLACEMENT

    def test_email_mit_subdomain(self):
        assert mask_email("user@mail.example.de") == EMAIL_REPLACEMENT

    def test_email_mit_plus(self):
        assert mask_email("user+label@example.com") == EMAIL_REPLACEMENT

    def test_email_mit_punkt_im_local(self):
        assert mask_email("max.mustermann@beispiel.de") == EMAIL_REPLACEMENT

    def test_email_mit_bindestrich_in_domain(self):
        assert mask_email("info@my-company.de") == EMAIL_REPLACEMENT

    def test_email_in_satz(self):
        text = "Kontakt: support@resovva.de für Fragen."
        result = mask_email(text)
        assert EMAIL_REPLACEMENT in result
        assert "support@resovva.de" not in result

    def test_mehrere_emails(self):
        text = "Von: alice@example.com An: bob@firma.de"
        result = mask_email(text)
        assert result.count(EMAIL_REPLACEMENT) == 2
        assert "alice" not in result
        assert "bob" not in result

    def test_email_grossbuchstaben(self):
        result = mask_email("MAX.MUSTERMANN@BEISPIEL.DE")
        assert EMAIL_REPLACEMENT in result

    def test_email_zwei_buchstaben_tld(self):
        assert mask_email("info@firma.io") == EMAIL_REPLACEMENT

    def test_email_lange_tld(self):
        assert mask_email("test@example.energy") == EMAIL_REPLACEMENT

    def test_kein_false_positive_at_zeichen_allein(self):
        # @ ohne gültige Domain → kein Match
        assert mask_email("@username") == "@username"

    def test_email_in_rechnung(self):
        text = "Für Rückfragen: kundenservice@stadtwerke-muster.de, Tel: 0800 123"
        result = mask_email(text)
        assert EMAIL_REPLACEMENT in result
        assert "kundenservice" not in result


# ── Kombinierter mask_pii-Test ─────────────────────────────────────────────────

class TestMaskPii:
    """mask_pii() maskiert IBAN und E-Mail in einem Durchlauf."""

    def test_beide_typen_gleichzeitig(self):
        text = (
            "Konto: DE89370400440532013000\n"
            "E-Mail: billing@example.com\n"
            "Betrag: 120,00 €"
        )
        result = mask_pii(text)
        assert IBAN_REPLACEMENT in result
        assert EMAIL_REPLACEMENT in result
        assert "DE89" not in result
        assert "billing@example.com" not in result
        # Nicht-PII bleibt erhalten
        assert "120,00 €" in result

    def test_leerer_string(self):
        assert mask_pii("") == ""

    def test_none_input(self):
        assert mask_pii(None) == ""

    def test_kein_pii_unveraendert(self):
        text = "Die Ablesung des Zählers erfolgte am 01.03.2026."
        assert mask_pii(text) == text

    def test_reale_rechnung_simulation(self):
        text = (
            "Stadtwerke Muster GmbH\n"
            "Rechnungsnr.: 2026-003-001\n"
            "Empfänger: DE44 5001 0517 5407 3249 31\n"
            "Ansprechpartner: max.mustermann@stadtwerke-muster.de\n"
            "Betrag: 347,85 €\n"
            "MaLo-ID: 50599000000000"
        )
        result = mask_pii(text)
        assert IBAN_REPLACEMENT in result
        assert EMAIL_REPLACEMENT in result
        # Wichtige Fachdaten bleiben erhalten
        assert "2026-003-001" in result
        assert "347,85 €" in result
        assert "50599000000000" in result
