"""
MaStR-API Lookup – Marktstammdatenregister.

Ermittelt Netzbetreiber etc. anhand Marktlokation (MaLo).
"""

from typing import Optional

# Als LangChain/LangGraph Tool nutzbar
# from langchain_core.tools import tool


def mastr_lookup(malo_id: str, api_base_url: Optional[str] = None) -> dict:
    """
    Lookup in der MaStR-API für die gegebene Marktlokations-ID.
    TODO: HTTP-Client (httpx), API-Dokumentation einbinden.
    """
    return {"malo_id": malo_id, "network_operator": None, "status": "placeholder"}


# @tool
# def mastr_lookup_tool(malo_id: str) -> dict:
#     """Sucht in der MaStR-API nach der Marktlokation und liefert Netzbetreiber-Infos."""
#     return mastr_lookup(malo_id)

# Ohne LangChain-Decorator zunächst als einfache Funktion exportieren
mastr_lookup_tool = mastr_lookup
