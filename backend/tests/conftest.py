"""Pytest fixtures – App-Client, Mocks für DB/LLM, etc."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
