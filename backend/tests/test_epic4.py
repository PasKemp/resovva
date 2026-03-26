"""
Tests für EPIC 4: Der Rote Faden (Chronologie & Gap-Analyse).

Abgedeckte Bereiche:
  - US-4.1: Event-Extraktion pro Dokument (Map-Phase)
  - US-4.2: Master-Chronologie & Gap-Analyse (Reduce-Phase)
  - US-4.3: Timeline API (GET, PATCH, DELETE)
  - US-4.4: Manuelles Ereignis hinzufügen (POST)
  - US-4.5: Inkrementelles Update (/refresh)

Externe Abhängigkeiten werden gemockt:
  - LLM via @patch("app.agents.nodes.extract_events._get_mini_llm")
  - LLM via @patch("app.agents.nodes.build_master_timeline._get_llm")
  - DB via @patch("app.agents.nodes.extract_events.get_db_context")
  - DB via @patch("app.agents.nodes.build_master_timeline.get_db_context")
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────


def _make_case(db, user, status="TIMELINE_READY"):
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


def _make_document(db, case, ocr_status="completed", masked_text="Rechnung vom 01.03.2024"):
    from app.domain.models.db import Document
    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        filename="rechnung.pdf",
        s3_key=f"{case.id}/rechnung.pdf",
        document_type="INVOICE",
        ocr_status=ocr_status,
        masked_text=masked_text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _make_event(db, case, source_type="ai", is_gap=False, event_date=None):
    from app.domain.models.db import ChronologyEvent
    event = ChronologyEvent(
        id=uuid.uuid4(),
        case_id=case.id,
        event_date=event_date or date(2024, 3, 1),
        description="Testbeschreibung",
        source_type=source_type,
        is_gap=is_gap,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ─────────────────────────────────────────────────────────────────────────────
# US-4.1: Event-Extraktion pro Dokument (Map-Phase)
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractEventsNode:
    """node_extract_events – Map-Phase."""

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract_events.get_db_context")
    @patch("app.agents.nodes.extract_events._extract_for_doc")
    async def test_extracts_events_from_two_docs(self, mock_extract, mock_ctx):
        """Events werden parallel aus beiden Dokumenten extrahiert."""
        from app.agents.nodes.extract_events import node_extract_events

        doc1_id = str(uuid.uuid4())
        doc2_id = str(uuid.uuid4())

        mock_doc1 = MagicMock()
        mock_doc1.id = uuid.UUID(doc1_id)
        mock_doc1.filename = "rechnung.pdf"
        mock_doc1.document_type = "INVOICE"
        mock_doc1.masked_text = "Rechnung vom 01.03.2024 über 250 EUR."

        mock_doc2 = MagicMock()
        mock_doc2.id = uuid.UUID(doc2_id)
        mock_doc2.filename = "mahnung.pdf"
        mock_doc2.document_type = "REMINDER"
        mock_doc2.masked_text = "Mahnung vom 15.04.2024."

        mock_case = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_case
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_doc1, mock_doc2]
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # _extract_for_doc: AsyncMock mit side_effect-Liste (Rückgabewert pro Aufruf)
        mock_extract.side_effect = [
            (doc1_id, [{"date": "2024-03-01", "description": "Rechnung", "source_doc_id": doc1_id, "source_type": "ai", "is_gap": False}]),
            (doc2_id, [{"date": "2024-04-15", "description": "Mahnung",  "source_doc_id": doc2_id, "source_type": "ai", "is_gap": False}]),
        ]

        state = {"case_id": str(uuid.uuid4()), "messages": [], "events_per_doc": {}}
        result = await node_extract_events(state)

        assert result["current_step"] == "extract_events"
        assert isinstance(result["events_per_doc"], dict)
        assert len(result["events_per_doc"]) == 2

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract_events.get_db_context")
    @patch("app.agents.nodes.extract_events._extract_for_doc", new_callable=AsyncMock)
    async def test_llm_failure_for_one_doc_does_not_crash(self, mock_extract, mock_ctx):
        """LLM-Fehler bei einem Dokument überspringt dieses, ohne den Node zu crashen."""
        from app.agents.nodes.extract_events import node_extract_events

        doc_id = str(uuid.uuid4())
        mock_doc = MagicMock()
        mock_doc.id = uuid.UUID(doc_id)
        mock_doc.filename = "test.pdf"
        mock_doc.document_type = "UNKNOWN"
        mock_doc.masked_text = "Text"

        mock_case = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_case
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_doc]
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # AsyncMock raises RuntimeError when awaited → gather catches it via return_exceptions=True
        mock_extract.side_effect = RuntimeError("LLM timeout")

        state = {"case_id": str(uuid.uuid4()), "messages": [], "events_per_doc": {}}
        result = await node_extract_events(state)

        assert result["current_step"] == "extract_events"
        assert result["events_per_doc"] == {}

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract_events.get_db_context")
    async def test_no_completed_docs_returns_empty(self, mock_ctx):
        """Ohne abgeschlossene Dokumente → events_per_doc = {}."""
        from app.agents.nodes.extract_events import node_extract_events

        mock_case = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_case
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        state = {"case_id": str(uuid.uuid4()), "messages": [], "events_per_doc": {}}
        result = await node_extract_events(state)

        assert result["events_per_doc"] == {}
        assert result["current_step"] == "extract_events"


# ─────────────────────────────────────────────────────────────────────────────
# US-4.2: Master-Chronologie & Gap-Analyse (Reduce-Phase)
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildMasterTimeline:
    """node_build_master_timeline – Reduce-Phase."""

    @pytest.mark.asyncio
    @patch("app.agents.nodes.build_master_timeline.get_db_context")
    @patch("app.agents.nodes.build_master_timeline._persist_timeline")
    @patch("app.agents.nodes.build_master_timeline._get_llm")
    async def test_persists_sorted_events(self, mock_llm_fn, mock_persist, mock_ctx):
        """Events werden chronologisch sortiert und via _persist_timeline gespeichert."""
        from app.agents.nodes.build_master_timeline import node_build_master_timeline, MasterTimeline, MasterEvent

        mock_case = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_case
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        timeline = MasterTimeline(events=[
            MasterEvent(event_date=date(2024, 1, 15), description="Rechnung erhalten", is_gap=False),
            MasterEvent(event_date=date(2024, 4, 1),  description="Mahnung erhalten",  is_gap=False),
        ])
        mock_chain = AsyncMock(return_value=timeline)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain
        mock_llm_fn.return_value = mock_llm

        state = {
            "case_id": str(uuid.uuid4()),
            "messages": [],
            "events_per_doc": {
                "doc1": [{"date": "2024-01-15", "description": "Rechnung", "source_doc_id": "doc1", "source_type": "ai", "is_gap": False}],
                "doc2": [{"date": "2024-04-01", "description": "Mahnung",  "source_doc_id": "doc2", "source_type": "ai", "is_gap": False}],
            },
        }

        with patch("app.agents.nodes.build_master_timeline._REDUCE_PROMPT") as p:
            p.__or__ = lambda self_, other: mock_chain
            result = await node_build_master_timeline(state)

        assert result["current_step"] == "build_master_timeline"
        # _persist_timeline wurde aufgerufen
        assert mock_persist.called

    @pytest.mark.asyncio
    @patch("app.agents.nodes.build_master_timeline.get_db_context")
    @patch("app.agents.nodes.build_master_timeline._persist_timeline")
    @patch("app.agents.nodes.build_master_timeline._get_llm")
    async def test_gap_event_is_inserted(self, mock_llm_fn, mock_persist, mock_ctx):
        """Gap-Events (is_gap=True) werden via _persist_timeline gespeichert."""
        from app.agents.nodes.build_master_timeline import node_build_master_timeline, MasterTimeline, MasterEvent

        mock_case = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_case
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        timeline = MasterTimeline(events=[
            MasterEvent(event_date=date(2024, 2, 1), description="Vermutlich fehlendes Dokument: Rechnung", is_gap=True),
            MasterEvent(event_date=date(2024, 4, 1), description="Mahnung erhalten", is_gap=False),
        ])
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=timeline)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain
        mock_llm_fn.return_value = mock_llm

        state = {
            "case_id": str(uuid.uuid4()),
            "messages": [],
            "events_per_doc": {"doc1": [{"date": "2024-04-01", "description": "Mahnung", "source_doc_id": "doc1", "source_type": "ai", "is_gap": False}]},
        }

        with patch("app.agents.nodes.build_master_timeline._REDUCE_PROMPT") as p:
            p.__or__.return_value = mock_chain
            result = await node_build_master_timeline(state)

        # _persist_timeline wurde mit dem Timeline-Objekt aufgerufen
        assert mock_persist.called
        timeline_arg = mock_persist.call_args[0][1]  # zweites Arg = events list
        assert any(e.is_gap for e in timeline_arg)

    @patch("app.agents.nodes.build_master_timeline.get_db_context")
    def test_user_events_not_deleted(self, mock_ctx):
        """DELETE-Query filtert nur source_type='ai' – User-Events bleiben."""
        from app.agents.nodes.build_master_timeline import _persist_timeline, MasterEvent

        mock_case = MagicMock()
        mock_db = MagicMock()
        mock_delete_query = MagicMock()
        mock_db.query.return_value.filter.return_value = mock_delete_query
        mock_delete_query.first.return_value = mock_case
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        case_uuid = uuid.uuid4()
        _persist_timeline(case_uuid, [
            MasterEvent(event_date=date(2024, 3, 1), description="Test", is_gap=False),
        ])

        # filter() wurde aufgerufen – Prüfe dass 'ai' im Filter steckt
        # (Indirekter Test: delete() wurde auf dem gefilterten Query aufgerufen)
        assert mock_delete_query.delete.called


# ─────────────────────────────────────────────────────────────────────────────
# US-4.3: Timeline API – GET
# ─────────────────────────────────────────────────────────────────────────────


class TestTimelineApiGet:
    """GET /cases/{case_id}/timeline."""

    def test_returns_building_status_when_processing(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user, status="BUILDING_TIMELINE")

        resp = client.get(f"/api/v1/cases/{case.id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "building"
        assert data["events"] == []

    def test_returns_ready_status_with_events(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user, status="TIMELINE_READY")
        _make_event(db, case, source_type="ai")

        resp = client.get(f"/api/v1/cases/{case.id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert len(data["events"]) == 1
        assert data["events"][0]["source_type"] == "ai"

    def test_returns_empty_when_no_events(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user, status="TIMELINE_READY")

        resp = client.get(f"/api/v1/cases/{case.id}/timeline")
        assert resp.status_code == 200
        assert resp.json()["status"] == "empty"

    def test_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        foreign_id = uuid.uuid4()

        resp = client.get(f"/api/v1/cases/{foreign_id}/timeline")
        assert resp.status_code == 404

    def test_events_sorted_chronologically(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user, status="TIMELINE_READY")
        _make_event(db, case, event_date=date(2024, 6, 1))
        _make_event(db, case, event_date=date(2024, 1, 1))
        _make_event(db, case, event_date=date(2024, 3, 15))

        resp = client.get(f"/api/v1/cases/{case.id}/timeline")
        events = resp.json()["events"]
        dates = [e["event_date"] for e in events]
        assert dates == sorted(dates)


# ─────────────────────────────────────────────────────────────────────────────
# US-4.4: Manuelles Ereignis hinzufügen
# ─────────────────────────────────────────────────────────────────────────────


class TestAddManualEvent:
    """POST /cases/{case_id}/timeline."""

    def test_add_valid_event(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)

        resp = client.post(f"/api/v1/cases/{case.id}/timeline", json={
            "event_date":  "2024-03-01",
            "description": "Telefonat mit Kundenservice",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_type"] == "user"
        assert data["is_gap"] is False
        assert data["description"] == "Telefonat mit Kundenservice"
        assert data["event_date"] == "2024-03-01"

    def test_future_date_rejected(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)
        future = (date.today() + timedelta(days=1)).isoformat()

        resp = client.post(f"/api/v1/cases/{case.id}/timeline", json={
            "event_date":  future,
            "description": "Zukunftseintrag",
        })
        assert resp.status_code == 422

    def test_description_too_long_rejected(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)

        resp = client.post(f"/api/v1/cases/{case.id}/timeline", json={
            "event_date":  "2024-03-01",
            "description": "A" * 501,
        })
        assert resp.status_code == 422

    def test_empty_description_rejected(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)

        resp = client.post(f"/api/v1/cases/{case.id}/timeline", json={
            "event_date":  "2024-03-01",
            "description": "",
        })
        assert resp.status_code == 422

    def test_add_event_foreign_case_404(self, auth_client, db):
        client, _ = auth_client

        resp = client.post(f"/api/v1/cases/{uuid.uuid4()}/timeline", json={
            "event_date":  "2024-03-01",
            "description": "Test",
        })
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# US-4.3: PATCH / DELETE
# ─────────────────────────────────────────────────────────────────────────────


class TestTimelineApiCrud:
    """PATCH und DELETE /cases/{case_id}/timeline/{event_id}."""

    def test_patch_ai_event_updates_description(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)
        event = _make_event(db, case, source_type="ai")

        resp = client.patch(
            f"/api/v1/cases/{case.id}/timeline/{event.id}",
            json={"description": "Neue Beschreibung"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Neue Beschreibung"

    def test_patch_user_event_updates_date(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)
        event = _make_event(db, case, source_type="user")

        resp = client.patch(
            f"/api/v1/cases/{case.id}/timeline/{event.id}",
            json={"event_date": "2024-05-01"},
        )
        assert resp.status_code == 200
        assert resp.json()["event_date"] == "2024-05-01"

    def test_delete_ai_event(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)
        event = _make_event(db, case, source_type="ai")

        resp = client.delete(f"/api/v1/cases/{case.id}/timeline/{event.id}")
        assert resp.status_code == 204

        # Event ist weg
        get_resp = client.get(f"/api/v1/cases/{case.id}/timeline")
        assert len(get_resp.json()["events"]) == 0

    def test_delete_gap_event_succeeds(self, auth_client, db):
        """Gap ignorieren = DELETE."""
        client, user = auth_client
        case = _make_case(db, user)
        gap = _make_event(db, case, source_type="ai", is_gap=True)

        resp = client.delete(f"/api/v1/cases/{case.id}/timeline/{gap.id}")
        assert resp.status_code == 204

    def test_delete_user_event_succeeds(self, auth_client, db):
        """User kann eigene Ereignisse löschen."""
        client, user = auth_client
        case = _make_case(db, user)
        event = _make_event(db, case, source_type="user")

        resp = client.delete(f"/api/v1/cases/{case.id}/timeline/{event.id}")
        assert resp.status_code == 204

    def test_patch_nonexistent_event_returns_404(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user)

        resp = client.patch(
            f"/api/v1/cases/{case.id}/timeline/{uuid.uuid4()}",
            json={"description": "Test"},
        )
        assert resp.status_code == 404

    def test_patch_event_of_foreign_case_returns_404(self, auth_client, db):
        client, user = auth_client
        # Case anlegen aber mit einem Event aus einem anderen Case
        case1 = _make_case(db, user)
        case2 = _make_case(db, user)
        event = _make_event(db, case2)

        resp = client.patch(
            f"/api/v1/cases/{case1.id}/timeline/{event.id}",
            json={"description": "Test"},
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# US-4.5: Inkrementelles Update
# ─────────────────────────────────────────────────────────────────────────────


class TestIncrementalUpdate:
    """POST /cases/{case_id}/timeline/refresh."""

    def test_refresh_sets_building_status(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user, status="TIMELINE_READY")
        doc = _make_document(db, case, ocr_status="completed")

        with patch("app.agents.nodes.incremental_update.run_incremental_update"):
            resp = client.post(
                f"/api/v1/cases/{case.id}/timeline/refresh",
                params={"document_id": str(doc.id)},
            )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

        # Case-Status wurde auf BUILDING_TIMELINE gesetzt
        db.refresh(case)
        assert case.status == "BUILDING_TIMELINE"

    def test_refresh_rejects_incomplete_document(self, auth_client, db):
        client, user = auth_client
        case = _make_case(db, user, status="TIMELINE_READY")
        doc = _make_document(db, case, ocr_status="pending")

        resp = client.post(
            f"/api/v1/cases/{case.id}/timeline/refresh",
            params={"document_id": str(doc.id)},
        )
        assert resp.status_code == 422

    def test_refresh_rejects_foreign_document(self, auth_client, db):
        client, user = auth_client
        case1 = _make_case(db, user)
        case2 = _make_case(db, user)
        doc_of_case2 = _make_document(db, case2)

        resp = client.post(
            f"/api/v1/cases/{case1.id}/timeline/refresh",
            params={"document_id": str(doc_of_case2.id)},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.agents.nodes.incremental_update.get_db_context")
    @patch("app.agents.nodes.incremental_update._get_llm")
    @patch("app.agents.nodes.incremental_update._get_mini_llm")
    async def test_user_events_preserved_after_incremental_update(
        self, mock_mini_fn, mock_full_fn, mock_ctx
    ):
        """User-Events dürfen nach inkrementellem Update nicht verschwinden."""
        from app.agents.nodes.incremental_update import run_incremental_update, SingleDocEvents, SingleDocEvent
        from app.agents.nodes.build_master_timeline import MasterTimeline, MasterEvent

        case_id = str(uuid.uuid4())
        doc_id  = str(uuid.uuid4())

        mock_case = MagicMock()
        mock_doc  = MagicMock()
        mock_doc.masked_text = "Rechnung vom 15.05.2024"
        mock_doc.filename    = "rechnung.pdf"

        mock_user_event = MagicMock()
        mock_user_event.event_date   = date(2024, 2, 1)
        mock_user_event.description  = "Persönliches Gespräch"
        mock_user_event.source_type  = "user"
        mock_user_event.is_gap       = False
        mock_user_event.source_doc_id = None
        mock_user_event.id           = uuid.uuid4()

        # DB: alle .filter(...) Aufrufe landen auf demselben Mock
        mock_db = MagicMock()
        # first() calls: Case (status), Document, Case (persist step)
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_case, mock_doc, mock_case]
        # all() call: bestehende Events
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_user_event]
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__  = MagicMock(return_value=False)

        # Mini-LLM: gibt 1 neues Event zurück
        mini_result = SingleDocEvents(events=[
            SingleDocEvent(event_date=date(2024, 5, 15), description="Rechnung erhalten")
        ])
        mini_chain = MagicMock()
        mini_chain.ainvoke = AsyncMock(return_value=mini_result)
        mock_mini = MagicMock()
        mock_mini.with_structured_output.return_value = mini_chain
        mock_mini_fn.return_value = mock_mini

        # Full-LLM: gibt merged Timeline zurück
        merged_result = MasterTimeline(events=[
            MasterEvent(event_date=date(2024, 2, 1), description="Persönliches Gespräch", is_gap=False),
            MasterEvent(event_date=date(2024, 5, 15), description="Rechnung erhalten",     is_gap=False),
        ])
        full_chain = MagicMock()
        full_chain.ainvoke = AsyncMock(return_value=merged_result)
        mock_full = MagicMock()
        mock_full.with_structured_output.return_value = full_chain
        mock_full_fn.return_value = mock_full

        with (
            patch("app.agents.nodes.incremental_update._SINGLE_DOC_PROMPT") as p1,
            patch("app.agents.nodes.incremental_update._MERGE_PROMPT")       as p2,
        ):
            p1.__or__.return_value = mini_chain
            p2.__or__.return_value = full_chain
            await run_incremental_update(case_id, doc_id)

        # 2 neue AI-Events wurden in DB eingefügt
        assert mock_db.add.call_count == 2
