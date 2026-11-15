import pytest
from fastapi.testclient import TestClient


def test_root_and_health(client: TestClient):
    """Test health and root endpoints."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["status"] == "online"
    assert data_root["mock_llm"] is True
    assert data_root["widget"] == "/widget.js"
    assert data_root["chat_ui"] == "/chat-ui"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"


def test_static_widget_and_chat_ui_endpoints(client: TestClient):
    """Test serving /widget.js and /chat-ui static assets."""
    res_widget = client.get("/widget.js")
    assert res_widget.status_code == 200
    assert "application/javascript" in res_widget.headers["content-type"]
    assert "class AstroChat extends HTMLElement" in res_widget.text

    res_ui = client.get("/chat-ui")
    assert res_ui.status_code == 200
    assert "text/html" in res_ui.headers["content-type"]
    assert "<astro-chat" in res_ui.text


def test_start_session_english(client: TestClient):
    """Test starting a check-in session for English astronaut."""
    payload = {"astronaut_id": 1, "mission_day": 42}
    res = client.post("/sessions/start", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "session_id" in data
    assert "first_message" in data
    assert "sleep" in data["first_message"].lower() or "commander" in data["first_message"].lower()


def test_start_session_arabic(client: TestClient):
    """Test starting a check-in session for Arabic astronaut."""
    payload = {"astronaut_id": 2, "mission_day": 15}
    res = client.post("/sessions/start", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "session_id" in data
    assert "مرحباً" in data["first_message"] or "قائد" in data["first_message"]


def test_start_session_invalid_astronaut(client: TestClient):
    """Test starting a session with non-existent astronaut ID."""
    payload = {"astronaut_id": 9999, "mission_day": 1}
    res = client.post("/sessions/start", json=payload)
    assert res.status_code == 404


def test_interviewer_flow_and_7_turn_limit(client: TestClient):
    """
    Test the multi-turn interviewer flow.
    Verifies that after 7 questions, the assistant delivers a warm closing summary
    and sets session_should_end=True.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 50})
    assert res_start.status_code == 201
    session_id = res_start.json()["session_id"]

    # Turns 1 through 6
    for i in range(1, 7):
        chat_res = client.post(
            "/chat",
            json={"session_id": session_id, "message": f"Turn {i} astronaut response: doing nominal work."}
        )
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert data["mode"] == "session"
        assert data["escalate"] is False
        assert data["session_should_end"] is False
        assert data["should_end"] is False
        assert len(data["reply"]) > 0

    # Turn 7 response (answering Question 7) -> should trigger closing summary and session_should_end=True!
    chat_res_7 = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Turn 7 response: Seeing the Earth curve was calming."}
    )
    assert chat_res_7.status_code == 200
    data_7 = chat_res_7.json()
    assert data_7["mode"] == "session"
    assert data_7["session_should_end"] is True
    assert data_7["should_end"] is True
    assert "conclude" in data_7["reply"].lower() or "summary" in data_7["reply"].lower() or "suggestion" in data_7["reply"].lower() or "session" in data_7["reply"].lower()


def test_end_session_and_analysis(client: TestClient):
    """
    Test ending a session and generating structured analysis with 6 dimensions.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 51})
    session_id = res_start.json()["session_id"]
    client.post("/chat", json={"session_id": session_id, "message": "Slept 5 hours, feel slightly tired."})

    res_end = client.post(f"/sessions/{session_id}/end")
    assert res_end.status_code == 200
    analysis = res_end.json()
    assert analysis["session_id"] == session_id
    assert "scores" in analysis
    scores = analysis["scores"]
    for dim in ["stress", "low_mood", "anxiety", "fatigue", "social_isolation", "concentration_difficulty"]:
        assert dim in scores
    assert "evidence" in analysis
    assert "screening_answers" in analysis
    assert 0.0 <= analysis["confidence"] <= 1.0
    assert "notes" in analysis
    assert isinstance(analysis["risk_flag"], bool)

    # Verify session detail reflects completed status
    res_detail = client.get(f"/sessions/{session_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["status"] == "completed"
    assert detail["analysis"] is not None


def test_chat_on_ended_session_rejected(client: TestClient):
    """Test that sending messages in session mode to an ended session is rejected with 400."""
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 52})
    session_id = res_start.json()["session_id"]
    client.post(f"/sessions/{session_id}/end")

    res_chat = client.post("/chat", json={"session_id": session_id, "message": "Can I still talk?"})
    assert res_chat.status_code == 400
    assert "completed" in res_chat.json()["detail"].lower()


def test_companion_mode_switch_and_chat(client: TestClient):
    """
    Test switching to companion mode and chatting freely without changing analysis scores.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 53})
    session_id = res_start.json()["session_id"]
    client.post("/chat", json={"session_id": session_id, "message": "Busy schedule with docking."})
    res_end = client.post(f"/sessions/{session_id}/end")
    initial_analysis_scores = res_end.json()["scores"]

    # Switch to companion mode
    res_comp = client.post(f"/sessions/{session_id}/companion")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["mode"] == "companion"
    assert "opening_message" in comp_data
    assert len(comp_data["opening_message"]) > 0

    # Chat in companion mode
    res_comp_chat = client.post("/chat", json={"session_id": session_id, "message": "I miss looking at the green trees on Earth."})
    assert res_comp_chat.status_code == 200
    comp_chat_data = res_comp_chat.json()
    assert comp_chat_data["mode"] == "companion"
    assert comp_chat_data["session_should_end"] is False
    assert len(comp_chat_data["reply"]) > 0

    # Verify that session analysis scores remain unchanged!
    res_detail = client.get(f"/sessions/{session_id}")
    assert res_detail.json()["analysis"]["scores"] == initial_analysis_scores


def test_safety_escalation_english_keyword(client: TestClient):
    """
    Test crisis keyword detection in English triggers immediate escalation and creates alert with source='keyword'.
    """
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 54})
    session_id = res_start.json()["session_id"]

    res_chat = client.post(
        "/chat",
        json={"session_id": session_id, "message": "I feel completely hopeless and can't go on anymore."}
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert data["escalate"] is True
    assert "priority" in data["reply"].lower() or "alerted" in data["reply"].lower() or "safe" in data["reply"].lower()

    # Check alert was created with source="keyword"
    res_alerts = client.get("/alerts")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    matching = [a for a in alerts if a["session_id"] == session_id]
    assert len(matching) > 0
    assert matching[0]["handled"] is False
    assert matching[0]["source"] == "keyword"
    assert "hopeless" in matching[0]["reason"].lower()


def test_safety_escalation_arabic_keyword(client: TestClient):
    """Test crisis keyword detection in Arabic triggers escalation and alert."""
    res_start = client.post("/sessions/start", json={"astronaut_id": 2, "mission_day": 20})
    session_id = res_start.json()["session_id"]

    res_chat = client.post(
        "/chat",
        json={"session_id": session_id, "message": "أشعر أنه لا أمل في الاستمرار."}
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert data["escalate"] is True
    assert "سلامتك" in data["reply"] or "أولويتنا" in data["reply"]

    # Verify alert exists with source="keyword"
    res_alerts = client.get("/alerts")
    assert res_alerts.status_code == 200
    matching = [a for a in res_alerts.json() if a["session_id"] == session_id]
    assert len(matching) > 0
    assert matching[0]["source"] == "keyword"


def test_alerts_handling(client: TestClient):
    """Test retrieving open alerts and marking them as handled."""
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 55})
    session_id = res_start.json()["session_id"]
    client.post("/chat", json={"session_id": session_id, "message": "emergency situation in airlock"})

    # Get open alerts
    res_alerts = client.get("/alerts")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    assert len(alerts) > 0
    alert_to_handle = alerts[0]
    alert_id = alert_to_handle["id"]

    # Handle alert
    res_handle = client.patch(f"/alerts/{alert_id}/handle")
    assert res_handle.status_code == 200
    assert res_handle.json()["handled"] is True

    # Check that it no longer appears in default open alerts
    res_open = client.get("/alerts")
    open_ids = [a["id"] for a in res_open.json()]
    assert alert_id not in open_ids

    # Check that it appears when include_handled=true
    res_all = client.get("/alerts?include_handled=true")
    all_ids = [a["id"] for a in res_all.json()]
    assert alert_id in all_ids


def test_astronaut_history(client: TestClient):
    """Test fetching chronological history of astronaut sessions for trend charts."""
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 60})
    session_id = res_start.json()["session_id"]
    client.post(f"/sessions/{session_id}/end")

    res_history = client.get("/astronauts/1/history")
    assert res_history.status_code == 200
    history = res_history.json()
    assert isinstance(history, list)
    assert len(history) > 0
    item = history[-1]
    assert "session_id" in item
    assert "mission_day" in item
    assert "scores" in item
    assert "risk_flag" in item


def test_direct_companion_open_discussion_with_telemetry(client: TestClient):
    """Test starting directly in open discussion (companion) mode and conducting telemetry-aware dialogue."""
    res_start = client.post(
        "/sessions/start",
        json={"astronaut_id": 1, "mission_day": 42, "mode": "companion"},
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    assert start_data["mode"] == "companion"
    assert "open discussion" in start_data["first_message"].lower()

    session_id = start_data["session_id"]
    ctx = {
        "current_tab": "assistant.html",
        "signals_summary": {
            "heart_rate_bpm": 108,
            "sleep_hours": 5.4,
            "ai_decision": "Caution",
        },
    }

    res_hi = client.post(
        "/chat",
        json={"session_id": session_id, "message": "how are you", "context": ctx},
    )
    assert res_hi.status_code == 200
    hi_data = res_hi.json()
    assert hi_data["mode"] == "companion"
    assert "elevated heart rate" in hi_data["reply"].lower()
    assert "108" not in hi_data["reply"]
    assert "5.4" not in hi_data["reply"]

    res_vitals = client.post(
        "/chat",
        json={"session_id": session_id, "message": "How do my vitals and scan look right now?", "context": ctx},
    )
    assert res_vitals.status_code == 200
    vitals_reply = res_vitals.json()["reply"]
    assert vitals_reply != hi_data["reply"]
    assert "shorter sleep" in vitals_reply.lower() or "elevated heart rate" in vitals_reply.lower()
    assert "(placeholder)" not in vitals_reply.lower()
    assert "**" not in vitals_reply
    assert "108" not in vitals_reply
    assert "5.4" not in vitals_reply

    res_smalltalk = client.post(
        "/chat",
        json={"session_id": session_id, "message": "i am fine what about you", "context": ctx},
    )
    assert res_smalltalk.status_code == 200
    smalltalk_reply = res_smalltalk.json()["reply"]
    assert "grounding" not in smalltalk_reply.lower()
    assert "(placeholder)" not in smalltalk_reply.lower()
    assert "**" not in smalltalk_reply
    assert "doing well" in smalltalk_reply.lower() or "steady" in smalltalk_reply.lower()
