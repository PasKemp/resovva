"""
Timeline and Chronology Integration Tests (Epic 4).

Covers US-4.1 (Event Extraction), US-4.2 (Master Timeline),
US-4.3 (Timeline API), and US-4.4 (Manual Events).
Verifies AI-driven chronology building and manual corrections.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_case(db, user, status="TIMELINE_READY"):
    """Create a case for timeline testing."""
    from app.domain.models.db import Case
    case = Case(
        id=uuid.uuid4(),
        user_id=user.id,
        status=status,
        extracted_data={},
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _make_event(db, case, source_type="ai", is_gap=False, event_date=None):
    """Create a chronology event in the database."""
    from app.domain.models.db import ChronologyEvent
    event = ChronologyEvent(
        id=uuid.uuid4(),
        case_id=case.id,
        event_date=event_date or date(2024, 3, 1),
        description="Test Event",
        source_type=source_type,
        is_gap=is_gap,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ── US-4.1: Event Extraction (Map Phase) ─────────────────────────────────────

class TestExtractEventsNode:
    """Tests for the LangGraph node 'extract_events'."""

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract_events.get_db_context")
    @patch("app.agents.nodes.extract_events._extract_for_doc")
    async def test_extracts_events_from_two_docs(self, mock_extract, mock_ctx):
        """Should parallelize extraction across all completed documents."""
        from app.agents.nodes.extract_events import node_extract_events

        doc1_id = str(uuid.uuid4())
        doc2_id = str(uuid.uuid4())

        mock_doc1 = MagicMock(id=uuid.UUID(doc1_id), filename="inv.pdf", masked_text="Text")
        mock_doc2 = MagicMock(id=uuid.UUID(doc2_id), filename="rem.pdf", masked_text="Text")

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_doc1, mock_doc2]
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)

        mock_extract.side_effect = [
            (doc1_id, [{"date": "2024-03-01", "description": "Inv", "source_doc_id": doc1_id, "source_type": "ai", "is_gap": False}]),
            (doc2_id, [{"date": "2024-04-15", "description": "Rem", "source_doc_id": doc2_id, "source_type": "ai", "is_gap": False}]),
        ]

        state = {"case_id": str(uuid.uuid4()), "events_per_doc": {}}
        result = await node_extract_events(state)

        assert len(result["events_per_doc"]) == 2


# ── US-4.3: Timeline API ─────────────────────────────────────────────────────

class TestTimelineApiGet:
    """GET /cases/{case_id}/timeline."""

    def test_returns_building_status_when_processing(self, auth_client, db):
        """Should return building status if the AI agent is still working."""
        client, user = auth_client
        case = _make_case(db, user, status="BUILDING_TIMELINE")

        res = client.get(f"/api/v1/cases/{case.id}/timeline")
        assert res.status_code == 200
        assert res.json()["status"] == "building"

    def test_returns_ready_status_with_events(self, auth_client, db):
        """Should return all timeline events if status is ready."""
        client, user = auth_client
        case = _make_case(db, user, status="TIMELINE_READY")
        _make_event(db, case)

        res = client.get(f"/api/v1/cases/{case.id}/timeline")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"
        assert len(res.json()["events"]) == 1

    def test_foreign_case_returns_404(self, auth_client, db):
        """Accessing a timeline owned by another user should return a 404."""
        client, _ = auth_client
        res = client.get(f"/api/v1/cases/{uuid.uuid4()}/timeline")
        assert res.status_code == 404


class TestAddManualEvent:
    """POST /cases/{case_id}/timeline."""

    def test_add_valid_event(self, auth_client, db):
        """Users should be able to manually add their own chronology events."""
        client, user = auth_client
        case = _make_case(db, user)

        res = client.post(f"/api/v1/cases/{case.id}/timeline", json={
            "event_date":  "2024-03-01",
            "description": "Phone call with support",
        })
        assert res.status_code == 201
        assert res.json()["source_type"] == "user"
        assert res.json()["description"] == "Phone call with support"

    def test_future_date_rejected(self, auth_client, db):
        """Events in the future must be rejected by validation (HTTP 422).."""
        client, user = auth_client
        case = _make_case(db, user)
        res = client.post(f"/api/v1/cases/{case.id}/timeline", json={
            "event_date": (date.today() + timedelta(days=1)).isoformat(),
            "description": "Future",
        })
        assert res.status_code == 422
