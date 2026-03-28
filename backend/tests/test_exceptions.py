"""
Tests for global exception handling and ResovvaError hierarchy.

Ensures that custom domain exceptions are correctly caught by the 
standardized exception handler in main.py and returned as structured JSON.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    ResovvaError,
)


def test_exception_handler_not_found():
    """NotFoundError should return 404 with structured JSON."""
    from app.main import app
    client = TestClient(app)
    
    @app.get("/_test/not-found")
    def raise_not_found():
        raise NotFoundError(resource="Case", identifier="123")
        
    response = client.get("/_test/not-found")
    assert response.status_code == 404
    assert response.json() == {
        "error": "NotFoundError",
        "detail": "Case with 123 not found"
    }


def test_exception_handler_conflict():
    """ConflictError should return 409."""
    from app.main import app
    client = TestClient(app)
    
    @app.get("/_test/conflict")
    def raise_conflict():
        raise ConflictError("Data collision")
        
    response = client.get("/_test/conflict")
    assert response.status_code == 409
    assert response.json()["error"] == "ConflictError"


def test_exception_handler_authentication_error():
    """AuthenticationError should return 401."""
    from app.main import app
    client = TestClient(app)
    
    @app.get("/_test/unauthorized")
    def raise_unauthorized():
        # AuthenticationError defaults to 401
        raise AuthenticationError("Invalid credentials")
        
    response = client.get("/_test/unauthorized")
    assert response.status_code == 401
    assert response.json()["error"] == "AuthenticationError"


def test_exception_handler_internal_server_error():
    """InternalServerError should return 500."""
    from app.main import app
    client = TestClient(app)
    
    @app.get("/_test/internal")
    def raise_internal():
        raise InternalServerError("Something went wrong")
        
    response = client.get("/_test/internal")
    assert response.status_code == 500
    assert response.json()["error"] == "InternalServerError"
