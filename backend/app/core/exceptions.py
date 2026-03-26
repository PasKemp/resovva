"""
Custom Exception-Hierarchie für die Resovva API.

Alle Exceptions erben von HTTPException, damit FastAPI sie nativ behandelt –
kein separater Exception-Handler in main.py nötig.

Klassen:
    APIError          – Basis-Exception mit status_code und detail.
    AuthenticationError – 401 Nicht authentifiziert.
    NotFoundError     – 404 Ressource nicht gefunden.
    ConflictError     – 409 Ressourcenkonflikt.
    ValidationError   – 422 Eingabe-Validierungsfehler.
"""

# third-party
from fastapi import HTTPException


class APIError(HTTPException):
    """
    Basis-Exception für alle Resovva-API-Fehler.

    Args:
        status_code: HTTP-Statuscode.
        detail: Fehlermeldung für den Client.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


class AuthenticationError(APIError):
    """
    Raised wenn Authentifizierung fehlschlägt (401).

    Args:
        detail: Fehlermeldung. Standard: 'Nicht authentifiziert.'
    """

    def __init__(self, detail: str = "Nicht authentifiziert.") -> None:
        super().__init__(status_code=401, detail=detail)


class NotFoundError(APIError):
    """
    Raised wenn eine Ressource nicht gefunden wird (404).

    Args:
        detail: Fehlermeldung. Standard: 'Ressource nicht gefunden.'
    """

    def __init__(self, detail: str = "Ressource nicht gefunden.") -> None:
        super().__init__(status_code=404, detail=detail)


class ConflictError(APIError):
    """
    Raised bei Ressourcenkonflikten, z.B. doppelte E-Mail (409).

    Args:
        detail: Fehlermeldung. Standard: 'Konflikt.'
    """

    def __init__(self, detail: str = "Konflikt.") -> None:
        super().__init__(status_code=409, detail=detail)


class ValidationError(APIError):
    """
    Raised bei Eingabe-Validierungsfehlern (422).

    Args:
        detail: Fehlermeldung. Standard: 'Validierungsfehler.'
    """

    def __init__(self, detail: str = "Validierungsfehler.") -> None:
        super().__init__(status_code=422, detail=detail)
