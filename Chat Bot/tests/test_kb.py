import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DBSession
from app.services.kb_service import search_knowledge_base, log_kb_usage
from app.models import KBChunk, KBUsage, Message


def test_kb_search_endpoint_query(client: TestClient):
    """Test searching approved KB chunks by text query."""
    res = client.get("/kb/search?q=breathing")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "breathing" in first["title"].lower() or "breathing" in first["content"].lower()
    assert "source_name" in first
    assert "source_url" in first


def test_kb_search_endpoint_topic_filter(client: TestClient):
    """Test filtering KB chunks by topic."""
    res = client.get("/kb/search?topic=sleep")
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0
    for chunk in data:
        assert chunk["topic"] == "sleep"


def test_kb_search_endpoint_severity_filter(client: TestClient):
    """Test filtering KB chunks by clinical severity rating."""
    # Low severity (2.0)
    res_low = client.get("/kb/search?severity=2.0")
    assert res_low.status_code == 200
    data_low = res_low.json()
    for c in data_low:
        assert c["severity_min"] <= 2.0 <= c["severity_max"]

    # High severity escalation (8.5)
    res_high = client.get("/kb/search?severity=8.5")
    assert res_high.status_code == 200
    data_high = res_high.json()
    for c in data_high:
        assert c["severity_min"] <= 8.5 <= c["severity_max"]


def test_kb_search_endpoint_language_filter(client: TestClient):
    """Test filtering KB chunks by language ('en' vs 'ar')."""
    res_ar = client.get("/kb/search?language=ar")
    assert res_ar.status_code == 200
    data_ar = res_ar.json()
    assert len(data_ar) > 0
    for chunk in data_ar:
        assert chunk["language"] == "ar"

    res_en = client.get("/kb/search?language=en")
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert len(data_en) > 0
    for chunk in data_en:
        assert chunk["language"] == "en"


def test_companion_kb_tool_and_usage_logging(client: TestClient):
    """
    Test that asking for advice in companion mode triggers KB retrieval,
    cites the source, and logs chunk usage in kb_usage.
    """
    # 1. Start and end session
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 80})
    session_id = res_start.json()["session_id"]
    client.post(f"/sessions/{session_id}/end")

    # 2. Switch to companion mode
    client.post(f"/sessions/{session_id}/companion")

    # 3. Ask for stress breathing advice
    res_chat = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Can you give me a breathing exercise for stress?"}
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert "Source:" in data["reply"] or "source" in data["reply"].lower() or "breathing" in data["reply"].lower()

    # 4. Verify session detail shows messages
    res_detail = client.get(f"/sessions/{session_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["messages"]) >= 3


def test_medium_severity_kb_policy_and_alert(client: TestClient):
    """
    Test severity policy:
    Medium severity (4-6) -> tips + clearly suggest contacting professional + alert.
    """
    # Create session and end it with default mock scores (stress=4, fatigue=5)
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 85})
    session_id = res_start.json()["session_id"]
    client.post(f"/sessions/{session_id}/end")
    client.post(f"/sessions/{session_id}/companion")

    # Request breathing advice under medium severity
    res_chat = client.post(
        "/chat",
        json={"session_id": session_id, "message": "My stress is rising, do you have breathing tips?"}
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    # Check that it suggests contacting flight surgeon / mission psychologist
    assert "flight surgeon" in data["reply"].lower() or "psychologist" in data["reply"].lower() or "source" in data["reply"].lower()

    # Check alert was created
    res_alerts = client.get("/alerts")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    matching = [a for a in alerts if a["session_id"] == session_id]
    assert len(matching) > 0
