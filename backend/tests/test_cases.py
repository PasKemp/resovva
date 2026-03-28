"""
Case Management Integration Tests.

Covers US-1.4 (Tenant Isolation), US-1.6 (List & Create), and
US-1.7 (GDPR Hard-Delete).
Ensures data is strictly isolated between users.
"""

from __future__ import annotations

import uuid

from app.core.security import hash_password
from app.domain.models.db import Case, User


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_other_user_with_case(db) -> tuple[User, Case]:
    """Create a secondary user and an associated case for isolation testing."""
    other = User(
        email="other@example.com",
        hashed_password=hash_password("passwort123"),
        accepted_terms=True,
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    case = Case(user_id=other.id, status="DRAFT", extracted_data={})
    db.add(case)
    db.commit()
    db.refresh(case)
    return other, case


# ── US-1.6: List & create ────────────────────────────────────────────────────

def test_list_cases_empty(auth_client):
    """New users should have an empty case list (HTTP 200)."""
    client, _ = auth_client
    res = client.get("/api/v1/cases")
    assert res.status_code == 200
    assert res.json()["cases"] == []


def test_list_cases_unauthenticated(client):
    """Accessing cases without a session should return 401."""
    res = client.get("/api/v1/cases")
    assert res.status_code == 401


def test_create_case_success(auth_client):
    """Creating a case should return HTTP 201 with 'DRAFT' status."""
    client, _ = auth_client
    res = client.post("/api/v1/cases")
    assert res.status_code == 201
    data = res.json()
    assert "case_id" in data
    assert data["status"] == "DRAFT"


def test_create_case_unauthenticated(client):
    """Case creation must require authentication (HTTP 401)."""
    res = client.post("/api/v1/cases")
    assert res.status_code == 401


def test_list_cases_shows_created_case(auth_client):
    """Created cases must appear in the user's case list."""
    client, _ = auth_client
    case_id = client.post("/api/v1/cases").json()["case_id"]

    res = client.get("/api/v1/cases")
    ids = [c["case_id"] for c in res.json()["cases"]]
    assert case_id in ids


def test_list_cases_contains_metadata(auth_client):
    """Case summary must include essential tracking fields."""
    client, _ = auth_client
    client.post("/api/v1/cases")

    res = client.get("/api/v1/cases")
    case = res.json()["cases"][0]
    assert "case_id"       in case
    assert "created_at"    in case
    assert "status"        in case
    assert "document_count" in case


def test_create_multiple_cases(auth_client):
    """Users should be able to manage multiple independent cases."""
    client, _ = auth_client
    client.post("/api/v1/cases")
    client.post("/api/v1/cases")
    client.post("/api/v1/cases")

    res = client.get("/api/v1/cases")
    assert len(res.json()["cases"]) == 3


def test_cases_sorted_newest_first(auth_client):
    """Case list should be sorted by creation date descending."""
    client, _ = auth_client
    first_id  = client.post("/api/v1/cases").json()["case_id"]
    second_id = client.post("/api/v1/cases").json()["case_id"]

    cases = client.get("/api/v1/cases").json()["cases"]
    assert cases[0]["case_id"] == second_id
    assert cases[1]["case_id"] == first_id


# ── US-1.4: Tenant Isolation ─────────────────────────────────────────────────

def test_tenant_isolation_list(auth_client, db):
    """Users must never see cases belonging to other users."""
    client, _ = auth_client
    _, foreign_case = _create_other_user_with_case(db)

    res = client.get("/api/v1/cases")
    ids = [c["case_id"] for c in res.json()["cases"]]
    assert str(foreign_case.id) not in ids


def test_tenant_isolation_delete_returns_404(auth_client, db):
    """Deleting others' cases must return 404 to avoid existence leakage."""
    client, _ = auth_client
    _, foreign_case = _create_other_user_with_case(db)

    res = client.delete(f"/api/v1/cases/{foreign_case.id}")
    assert res.status_code == 404


# ── US-1.7: GDPR Hard-Delete ────────────────────────────────────────────────

def test_delete_case_success(auth_client):
    """Deleting own case should permanently remove it (HTTP 200)."""
    client, _ = auth_client
    case_id = client.post("/api/v1/cases").json()["case_id"]

    res = client.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    cases = client.get("/api/v1/cases").json()["cases"]
    assert not any(c["case_id"] == case_id for c in cases)


def test_delete_case_unauthenticated(client):
    """Deleting a case requires session ownership (HTTP 401)."""
    res = client.delete(f"/api/v1/cases/{uuid.uuid4()}")
    assert res.status_code == 401


def test_delete_invalid_uuid_returns_404(auth_client):
    """Invalid UUIDs in URL paths should be caught (HTTP 404)."""
    client, _ = auth_client
    res = client.delete("/api/v1/cases/not-a-uuid")
    assert res.status_code == 404


def test_delete_nonexistent_case_returns_404(auth_client):
    """Deleting non-existent cases returns 404."""
    client, _ = auth_client
    res = client.delete(f"/api/v1/cases/{uuid.uuid4()}")
    assert res.status_code == 404


def test_delete_only_removes_own_case(auth_client, db):
    """Ensures delete operation is scoped to the target case only."""
    client, _ = auth_client
    id_a = client.post("/api/v1/cases").json()["case_id"]
    id_b = client.post("/api/v1/cases").json()["case_id"]

    client.delete(f"/api/v1/cases/{id_a}")

    cases = client.get("/api/v1/cases").json()["cases"]
    ids = [c["case_id"] for c in cases]
    assert id_a not in ids
    assert id_b in ids
