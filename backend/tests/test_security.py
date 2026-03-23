"""
Unit-Tests für Security-Utilities – kein DB, kein HTTP, reine Funktionslogik.

Abgedeckt (US-1.1):
  hash_password / verify_password   – bcrypt
  create_access_token / decode_*    – JWT (HS256)
  generate_reset_token / hash_*     – SHA-256 Reset-Token
  mask_iban / mask_email / mask_pii – PII-Maskierung
"""

import uuid

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    mask_email,
    mask_iban,
    mask_pii,
    verify_password,
)

# ── Passwort-Hashing (bcrypt) ─────────────────────────────────────────────────


def test_hash_is_not_plaintext():
    """Gespeicherter Hash ist niemals der Klartext."""
    assert hash_password("geheimesPasswort") != "geheimesPasswort"


def test_verify_correct_password():
    """Richtiges Passwort wird erfolgreich verifiziert."""
    h = hash_password("meinPasswort123")
    assert verify_password("meinPasswort123", h) is True


def test_verify_wrong_password():
    """Falsches Passwort schlägt fehl."""
    h = hash_password("meinPasswort123")
    assert verify_password("anderesPasswort!", h) is False


def test_hash_includes_salt():
    """Zwei Hashes desselben Passworts unterscheiden sich (bcrypt-Salt)."""
    assert hash_password("passwort") != hash_password("passwort")


def test_verify_works_across_different_hashes():
    """verify_password funktioniert korrekt mit verschiedenen Hashes desselben Passworts."""
    pw = "gleichesPasswort123"
    h1 = hash_password(pw)
    h2 = hash_password(pw)
    assert verify_password(pw, h1) is True
    assert verify_password(pw, h2) is True


# ── JWT ───────────────────────────────────────────────────────────────────────


def test_create_and_decode_token():
    """Erstelltes JWT enthält die korrekte User-ID im 'sub'-Claim."""
    user_id = str(uuid.uuid4())
    token   = create_access_token(user_id)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == user_id


def test_token_contains_expiry():
    """JWT enthält 'exp'-Claim."""
    token   = create_access_token(str(uuid.uuid4()))
    payload = decode_access_token(token)
    assert "exp" in payload


def test_decode_invalid_token_returns_none():
    """Manipuliertes Token → None (keine Exception)."""
    assert decode_access_token("ungültiges.token.xyz") is None


def test_decode_empty_string_returns_none():
    """Leeres Token → None."""
    assert decode_access_token("") is None


def test_different_users_get_different_tokens():
    """Jeder User erhält ein eigenes Token."""
    t1 = create_access_token(str(uuid.uuid4()))
    t2 = create_access_token(str(uuid.uuid4()))
    assert t1 != t2


# ── Reset-Token (SHA-256) ─────────────────────────────────────────────────────


def test_raw_and_hash_are_different():
    """Raw-Token und sein Hash sind verschieden (Hash wird in DB gespeichert)."""
    raw, h = generate_reset_token()
    assert raw != h


def test_hash_is_deterministic():
    """Gleicher Raw-Token erzeugt immer denselben Hash."""
    raw, _ = generate_reset_token()
    assert hash_reset_token(raw) == hash_reset_token(raw)


def test_generate_produces_unique_tokens():
    """Jeder Aufruf liefert ein anderes Token (kryptographisch zufällig)."""
    r1, _ = generate_reset_token()
    r2, _ = generate_reset_token()
    assert r1 != r2


def test_hash_reset_token_matches_generate_output():
    """hash_reset_token(raw) stimmt mit dem aus generate_reset_token() überein."""
    raw, expected = generate_reset_token()
    assert hash_reset_token(raw) == expected


def test_raw_token_is_url_safe():
    """Raw-Token enthält nur URL-sichere Zeichen (geeignet für E-Mail-Links)."""
    raw, _ = generate_reset_token()
    # URL-safe base64: Buchstaben, Ziffern, '-', '_'
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=")
    assert all(c in allowed for c in raw), f"Ungültige Zeichen: {raw}"


# ── PII-Maskierung ────────────────────────────────────────────────────────────


def test_mask_iban_compact():
    """Kompakte deutsche IBAN (22 Ziffern ohne Leerzeichen) wird maskiert."""
    text   = "Überweisung auf DE89370400440532013000 erwartet."
    result = mask_iban(text)
    assert "DE89370400440532013000" not in result
    assert "***IBAN***" in result


def test_mask_iban_preserves_surrounding_text():
    """Text um die IBAN herum bleibt erhalten."""
    text   = "Konto DE89370400440532013000 gesperrt"
    result = mask_iban(text)
    assert "Konto" in result
    assert "gesperrt" in result


def test_mask_iban_no_false_positive():
    """Text ohne IBAN bleibt unverändert."""
    text = "Keine IBAN in diesem Satz."
    assert mask_iban(text) == text


def test_mask_email_simple():
    """Einfache E-Mail-Adresse wird maskiert."""
    text   = "Schreibe an info@example.com bitte."
    result = mask_email(text)
    assert "info@example.com" not in result


def test_mask_email_preserves_surrounding_text():
    """Text um die E-Mail bleibt erhalten."""
    text   = "Kontakt: user@test.de – bitte antworten"
    result = mask_email(text)
    assert "Kontakt:" in result
    assert "bitte antworten" in result


def test_mask_email_no_false_positive():
    """Text ohne E-Mail bleibt unverändert."""
    assert mask_email("Kein AT-Zeichen hier.") == "Kein AT-Zeichen hier."


def test_mask_pii_masks_both_iban_and_email():
    """mask_pii maskiert sowohl IBAN als auch E-Mail in einem Durchlauf."""
    text   = "IBAN: DE89370400440532013000, Kontakt: user@test.de"
    result = mask_pii(text)
    assert "DE89370400440532013000" not in result
    assert "user@test.de" not in result


def test_mask_pii_empty_string():
    """Leerer String → leerer String (kein Fehler)."""
    assert mask_pii("") == ""


def test_mask_pii_none_input():
    """None-Input → leerer String (kein Fehler)."""
    assert mask_pii(None) == ""


def test_mask_pii_plain_text_unchanged():
    """Text ohne PII bleibt unverändert."""
    text = "Dieser Satz enthält keine sensiblen Daten."
    assert mask_pii(text) == text
