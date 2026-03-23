"""
Cases-Endpoint-Tests – Epic 1 (US-1.4, US-1.6, US-1.7).

Getestete Endpunkte:
  GET    /api/v1/cases
  POST   /api/v1/cases
  DELETE /api/v1/cases/{case_id}

Schwerpunkte: Mandantenfähigkeit (Tenant Isolation), DSGVO Hard-Delete.
"""

import uuid

from app.core.security import hash_password
from app.domain.models.db import Case, User


# ── Hilfsfunktion: zweiten Nutzer + Fall in DB anlegen ───────────────────────

def _create_other_user_with_case(db) -> tuple[User, Case]:
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


# ── US-1.6: Liste & Anlegen ───────────────────────────────────────────────────


def test_list_cases_empty(auth_client):
    """Frisch angemeldeter Nutzer hat keine Fälle."""
    client, _ = auth_client
    res = client.get("/api/v1/cases")
    assert res.status_code == 200
    assert res.json()["cases"] == []


def test_list_cases_unauthenticated(client):
    """Ohne Cookie → 401."""
    res = client.get("/api/v1/cases")
    assert res.status_code == 401


def test_create_case_success(auth_client):
    """Neuen Fall anlegen → 201, Status DRAFT, case_id im Response."""
    client, _ = auth_client
    res = client.post("/api/v1/cases")
    assert res.status_code == 201
    data = res.json()
    assert "case_id" in data
    assert data["status"] == "DRAFT"


def test_create_case_unauthenticated(client):
    """Ohne Cookie → 401."""
    res = client.post("/api/v1/cases")
    assert res.status_code == 401


def test_list_cases_shows_created_case(auth_client):
    """Angelegter Fall erscheint in der Fallliste."""
    client, _ = auth_client
    case_id = client.post("/api/v1/cases").json()["case_id"]

    res = client.get("/api/v1/cases")
    ids = [c["case_id"] for c in res.json()["cases"]]
    assert case_id in ids


def test_list_cases_contains_metadata(auth_client):
    """Fallübersicht enthält die erwarteten Felder."""
    client, _ = auth_client
    client.post("/api/v1/cases")

    res = client.get("/api/v1/cases")
    case = res.json()["cases"][0]
    assert "case_id"       in case
    assert "created_at"    in case
    assert "status"        in case
    assert "document_count" in case


def test_create_multiple_cases(auth_client):
    """Nutzer kann mehrere Fälle parallel verwalten."""
    client, _ = auth_client
    client.post("/api/v1/cases")
    client.post("/api/v1/cases")
    client.post("/api/v1/cases")

    res = client.get("/api/v1/cases")
    assert len(res.json()["cases"]) == 3


def test_cases_sorted_newest_first(auth_client):
    """Fälle werden nach Erstelldatum absteigend sortiert (neueste zuerst)."""
    client, _ = auth_client
    first_id  = client.post("/api/v1/cases").json()["case_id"]
    second_id = client.post("/api/v1/cases").json()["case_id"]

    cases = client.get("/api/v1/cases").json()["cases"]
    assert cases[0]["case_id"] == second_id
    assert cases[1]["case_id"] == first_id


# ── US-1.4: Tenant Isolation ─────────────────────────────────────────────────


def test_tenant_isolation_list(auth_client, db):
    """Nutzer sieht ausschließlich seine eigenen Fälle."""
    client, _ = auth_client
    _, foreign_case = _create_other_user_with_case(db)

    res = client.get("/api/v1/cases")
    ids = [c["case_id"] for c in res.json()["cases"]]
    assert str(foreign_case.id) not in ids


def test_tenant_isolation_delete_returns_404(auth_client, db):
    """
    Fremden Fall löschen → 404 (nicht 403).
    Verhindert, dass Angreifer existierende Case-IDs ermitteln können.
    """
    client, _ = auth_client
    _, foreign_case = _create_other_user_with_case(db)

    res = client.delete(f"/api/v1/cases/{foreign_case.id}")
    assert res.status_code == 404


# ── US-1.7: DSGVO Hard-Delete ────────────────────────────────────────────────


def test_delete_case_success(auth_client):
    """Eigenen Fall löschen → 200, Fall danach nicht mehr in der Liste."""
    client, _ = auth_client
    case_id = client.post("/api/v1/cases").json()["case_id"]

    res = client.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    cases = client.get("/api/v1/cases").json()["cases"]
    assert not any(c["case_id"] == case_id for c in cases)


def test_delete_case_unauthenticated(client):
    """Ohne Cookie → 401."""
    res = client.delete(f"/api/v1/cases/{uuid.uuid4()}")
    assert res.status_code == 401


def test_delete_invalid_uuid_returns_404(auth_client):
    """Ungültige UUID als case_id → 404."""
    client, _ = auth_client
    res = client.delete("/api/v1/cases/nicht-eine-uuid")
    assert res.status_code == 404


def test_delete_nonexistent_case_returns_404(auth_client):
    """Gültige UUID, aber kein passender Fall → 404."""
    client, _ = auth_client
    res = client.delete(f"/api/v1/cases/{uuid.uuid4()}")
    assert res.status_code == 404


def test_delete_only_removes_own_case(auth_client, db):
    """Nach Hard-Delete sind andere eigene Fälle noch vorhanden."""
    client, _ = auth_client
    id_a = client.post("/api/v1/cases").json()["case_id"]
    id_b = client.post("/api/v1/cases").json()["case_id"]

    client.delete(f"/api/v1/cases/{id_a}")

    cases = client.get("/api/v1/cases").json()["cases"]
    ids = [c["case_id"] for c in cases]
    assert id_a not in ids
    assert id_b in ids
