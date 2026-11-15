import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DBSession

from app.models import Session, TaskEvent, SessionSignal, Alert
from app.services.session_service import get_session_transcript_text
from tests.conftest import TestingSessionLocal


def test_context_handling_in_chat(client: TestClient):
    """
    Test context handling in POST /chat:
    Accepts task, phase, current_tab, note, signals_summary.
    Logs event into task_events table and responds with task awareness.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 42})
    assert res_start.status_code == 201
    session_id = res_start.json()["session_id"]

    chat_payload = {
        "session_id": session_id,
        "message": "Starting the test right now.",
        "context": {
            "task": "Reaction Time Test",
            "phase": "started",
            "current_tab": "cognitive_eval",
            "note": "EVA rehearsal underway",
            "signals_summary": {"voice_stress_index": 0.25, "heart_rate_bpm": 68},
        },
    }
    res_chat = client.post("/chat", json=chat_payload)
    assert res_chat.status_code == 200
    data = res_chat.json()

    assert data["task_active"] is True
    assert "focus on your reaction time test" in data["reply"].lower()
    assert data["pending_question"] is not None

    # Verify task event was persisted in DB
    db: DBSession = TestingSessionLocal()
    try:
        events = db.query(TaskEvent).filter(TaskEvent.session_id == session_id).all()
        assert len(events) >= 1
        assert events[0].task == "Reaction Time Test"
        assert events[0].phase == "started"
    finally:
        db.close()


def test_task_queueing_question_held_and_released(client: TestClient):
    """
    Test question queueing:
    - While task phase is 'started', question is held/queued and bot replies with short pause acknowledgement.
    - Question counter does not advance during task pause.
    - When phase is 'ended', the held question is released gently referencing the completed task.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 50})
    assert res_start.status_code == 201
    session_id = res_start.json()["session_id"]

    # Check-in initial question #1 was delivered at session start
    db: DBSession = TestingSessionLocal()
    try:
        s = db.query(Session).filter(Session.id == session_id).first()
        assert s.question_count == 1
    finally:
        db.close()

    # User sends message while task is running (phase = 'started')
    res_during_task = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "I am working through the trials now.",
            "context": {"task": "Reaction Time Test", "phase": "started"},
        },
    )
    assert res_during_task.status_code == 200
    data_task = res_during_task.json()
    assert data_task["task_active"] is True
    assert "focus on your reaction time test" in data_task["reply"].lower()

    # Question counter must NOT advance while task is held
    db = TestingSessionLocal()
    try:
        s = db.query(Session).filter(Session.id == session_id).first()
        assert s.question_count == 1
        assert s.pending_question is not None
        assert s.pending_question_index == 2
    finally:
        db.close()

    # Now poll GET /sessions/{id}/pending upon task completion (or send phase = 'ended')
    res_pending = client.get(f"/sessions/{session_id}/pending?deliver=true")
    assert res_pending.status_code == 200
    data_pending = res_pending.json()
    assert data_pending["has_pending"] is True
    assert data_pending["pending"] is True
    assert data_pending["question"] is not None
    assert data_pending["question_index"] == 2

    # Verify pending question is now cleared and question count advanced to 2
    db = TestingSessionLocal()
    try:
        s = db.query(Session).filter(Session.id == session_id).first()
        assert s.pending_question is None
        assert s.question_count == 2
    finally:
        db.close()


def test_task_events_table_and_endpoints(client: TestClient):
    """
    Test POST /sessions/{id}/events and GET /sessions/{id}/events.
    Verifies that task events are stored and included in session transcript for the analyzer.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 45})
    session_id = res_start.json()["session_id"]

    # Log task event via endpoint
    event_payload = {
        "task": "Docking Simulation Test",
        "phase": "started",
        "info": {"simulation_difficulty": "high", "runs": 3},
    }
    res_evt = client.post(f"/sessions/{session_id}/events", json=event_payload)
    assert res_evt.status_code == 201
    data_evt = res_evt.json()
    assert data_evt["task"] == "Docking Simulation Test"
    assert data_evt["phase"] == "started"
    assert data_evt["info"]["simulation_difficulty"] == "high"

    # Retrieve all events for session
    res_list = client.get(f"/sessions/{session_id}/events")
    assert res_list.status_code == 200
    events_list = res_list.json()
    assert len(events_list) >= 1
    assert any(e["task"] == "Docking Simulation Test" for e in events_list)

    # Verify that get_session_transcript_text includes the task event chronologically
    db: DBSession = TestingSessionLocal()
    try:
        transcript = get_session_transcript_text(db, session_id, include_task_events=True)
        assert "Docking Simulation Test" in transcript
        assert "phase=started" in transcript
    finally:
        db.close()


def test_signals_table_and_endpoints(client: TestClient):
    """
    Test POST /sessions/{id}/signals and GET /sessions/{id}/signals
    for logging teammate's acoustic, facial, and physiological telemetry.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 46})
    session_id = res_start.json()["session_id"]

    signals_payload = {
        "signals": {
            "mean_pitch_f0_hz": 126.8,
            "pitch_variability_semitones": 2.2,
            "speech_rate_sps": 3.4,
            "facial_expressivity_index": 0.72,
            "autonomic_strain_score": 1.2,
        }
    }
    res_sig = client.post(f"/sessions/{session_id}/signals", json=signals_payload)
    assert res_sig.status_code == 201
    data_sig = res_sig.json()
    assert data_sig["session_id"] == session_id
    assert data_sig["signals"]["mean_pitch_f0_hz"] == 126.8

    # Query recent signals
    res_get = client.get(f"/sessions/{session_id}/signals")
    assert res_get.status_code == 200
    signals_list = res_get.json()
    assert len(signals_list) >= 1
    assert signals_list[0]["signals"]["facial_expressivity_index"] == 0.72


def test_escalation_during_task(client: TestClient):
    """
    Test that the safety layer is active at all times, including during tasks:
    Even when task phase='started', crisis keywords immediately trigger escalation and alert.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 47})
    session_id = res_start.json()["session_id"]

    crisis_payload = {
        "session_id": session_id,
        "message": "I can't take this anymore, want to end it all.",
        "context": {
            "task": "Reaction Time Test",
            "phase": "started",
        },
    }
    res_crisis = client.post("/chat", json=crisis_payload)
    assert res_crisis.status_code == 200
    data = res_crisis.json()

    assert data["escalate"] is True
    assert data["session_should_end"] is True
    assert "surgeon" in data["reply"].lower() or "support" in data["reply"].lower()

    # Verify emergency alert logged in database
    db: DBSession = TestingSessionLocal()
    try:
        alerts = db.query(Alert).filter(Alert.session_id == session_id).all()
        assert len(alerts) >= 1
        assert any("Emergency safety keyword" in a.reason for a in alerts)
    finally:
        db.close()


def test_safety_no_raw_scores_revealed(client: TestClient):
    """
    Test safety rule:
    This is an early-warning support tool, never a diagnosis tool.
    The bot never reveals raw scores or labels like 'your stress score is high' to the astronaut.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 48})
    session_id = res_start.json()["session_id"]

    # Provide telemetry with high numbers in signals_summary
    telemetry_payload = {
        "session_id": session_id,
        "message": "Routine maintenance checklist complete.",
        "context": {
            "signals_summary": {
                "voice_stress_index": 0.89,
                "fatigue_score": 9.4,
                "heart_rate_bpm": 135,
            }
        },
    }
    res_chat = client.post("/chat", json=telemetry_payload)
    assert res_chat.status_code == 200
    reply = res_chat.json()["reply"]

    # Verify raw numbers and diagnostic labels are NOT revealed in the reply
    forbidden_tokens = ["0.89", "9.4", "135", "stress score is high", "diagnos"]
    for token in forbidden_tokens:
        assert token not in reply.lower(), f"Forbidden token '{token}' found in bot response!"


def test_static_routes_and_demo_page(client: TestClient):
    """
    Verify static serving of chatbot-demo.html and widget.js for teammate localhost:8000.
    """
    res_demo = client.get("/chatbot-demo.html")
    assert res_demo.status_code == 200
    assert "text/html" in res_demo.headers["content-type"]
    assert "AstroCheck Widget HUD" in res_demo.text

    res_demo_web = client.get("/web/chatbot-demo.html")
    assert res_demo_web.status_code == 200
    assert "text/html" in res_demo_web.headers["content-type"]

    res_widget = client.get("/widget.js")
    assert res_widget.status_code == 200
    assert "application/javascript" in res_widget.headers["content-type"]
    assert "class AstroChat extends HTMLElement" in res_widget.text
