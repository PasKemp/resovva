"""
API dependencies: Auth & DB injection.

- FastAPI Depends() für Magic-Link-Auth (später).
- DB-Session / Qdrant-Client Injection.
"""

from typing import Annotated

from fastapi import Depends

# Placeholder: Auth & DB werden hier injiziert
# from app.core.config import get_settings
# from app.infrastructure.qdrant_client import get_qdrant


def get_current_user_placeholder():
    """Placeholder: Magic-Link-Auth – später implementieren."""
    return None


# Für FastAPI-Router: Depends(get_current_user_placeholder)
CurrentUser = Annotated[str | None, Depends(get_current_user_placeholder)]
