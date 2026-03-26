"""
Kategorie-Feld-Konfiguration (US-9.5).

Definiert welche Felder für welche Streitpartei-Kategorie relevant sind.
Irrelevante Felder werden im Frontend ausgeblendet und beim Bestätigen ignoriert.
"""

from __future__ import annotations

from typing import Dict, Set

# Kategorien die MaStR-Lookup benötigen (US-9.1: nur Energie)
ENERGY_CATEGORIES: Set[str] = {"strom", "gas", "wasser"}

# Felder pro Kategorie: key → relevant (True = anzeigen, False = ausblenden)
CATEGORY_FIELDS: Dict[str, Dict[str, bool]] = {
    "strom": {
        "malo_id":        True,
        "meter_number":   True,
        "dispute_amount": True,
        "contract_number": False,
        "insurance_number": False,
    },
    "gas": {
        "malo_id":        True,
        "meter_number":   True,
        "dispute_amount": True,
        "contract_number": False,
        "insurance_number": False,
    },
    "wasser": {
        "malo_id":        True,
        "meter_number":   True,
        "dispute_amount": True,
        "contract_number": False,
        "insurance_number": False,
    },
    "versicherung": {
        "malo_id":         False,
        "meter_number":    False,
        "dispute_amount":  True,
        "contract_number": True,
        "insurance_number": True,
    },
    "mobilfunk_internet": {
        "malo_id":         False,
        "meter_number":    False,
        "dispute_amount":  True,
        "contract_number": True,
        "insurance_number": False,
    },
    "amt_behoerde": {
        "malo_id":         False,
        "meter_number":    False,
        "dispute_amount":  True,
        "contract_number": True,
        "insurance_number": False,
    },
    "vermieter_immobilien": {
        "malo_id":         False,
        "meter_number":    False,
        "dispute_amount":  True,
        "contract_number": True,
        "insurance_number": False,
    },
    "sonstiges": {
        "malo_id":         False,
        "meter_number":    False,
        "dispute_amount":  True,
        "contract_number": True,
        "insurance_number": False,
    },
}


def get_relevant_fields(category: str) -> Dict[str, bool]:
    """
    Gibt die Feld-Konfiguration für eine Kategorie zurück.

    Args:
        category: OpponentCategory-Wert (z.B. 'strom', 'versicherung').

    Returns:
        Dict mit Feldnamen → relevant (True/False).
        Unbekannte Kategorien erhalten die Konfiguration von 'sonstiges'.
    """
    return CATEGORY_FIELDS.get(category, CATEGORY_FIELDS["sonstiges"])


def is_energy_category(category: str) -> bool:
    """Gibt True zurück wenn für diese Kategorie ein MaStR-Lookup sinnvoll ist."""
    return category in ENERGY_CATEGORIES
