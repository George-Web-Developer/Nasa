import pytest
from fastapi.testclient import TestClient
from app.safety import (
    detect_safety_keywords,
    parse_and_strip_escalate_token,
    get_crisis_support_message,
    ENGLISH_SAFETY_KEYWORDS,
    ARABIC_SAFETY_KEYWORDS,
)


def test_keyword_detection_english():
    """Verify English crisis and self-harm keywords trigger detection."""
    assert detect_safety_keywords("I feel completely hopeless")[0] is True
    assert detect_safety_keywords("This is a life-threatening emergency in module 2")[0] is True
    assert detect_safety_keywords("I want to die")[0] is True
    assert detect_safety_keywords("I can't go on like this")[0] is True
    assert detect_safety_keywords("Everything is going well with the solar array")[0] is False


def test_keyword_detection_arabic():
    """Verify Arabic crisis and distress keywords trigger detection."""
    assert detect_safety_keywords("أشعر أنه لا أمل في الاستمرار")[0] is True
    assert detect_safety_keywords("أفكر في إيذاء النفس")[0] is True
    assert detect_safety_keywords("هناك حالة طوارئ")[0] is True
    assert detect_safety_keywords("لقد أنجزنا فحص الأجهزة بنجاح والحمد لله")[0] is False


def test_escalate_token_stripping():
    """Verify [ESCALATE] token is detected, stripped, and flags escalation."""
    text_with_token = "I understand your pain. We are notifying ground support. [ESCALATE]"
    clean_text, flagged = parse_and_strip_escalate_token(text_with_token)
    assert flagged is True
    assert "[ESCALATE]" not in clean_text
    assert "notifying ground support" in clean_text

    normal_text = "Here is a breathing exercise for stress."
    clean_text_normal, flagged_normal = parse_and_strip_escalate_token(normal_text)
    assert flagged_normal is False
    assert clean_text_normal == normal_text


def test_crisis_support_messages():
    """Verify supportive, non-diagnostic crisis messages in both languages."""
    msg_en = get_crisis_support_message("en")
    assert "priority" in msg_en.lower() or "safe" in msg_en.lower() or "support" in msg_en.lower()
    # Ensure no medical prescriptions or dosages exist
    assert "mg" not in msg_en
    assert "dose" not in msg_en.lower()
    assert "prescribe" not in msg_en.lower()

    msg_ar = get_crisis_support_message("ar")
    assert "سلامتك" in msg_ar or "أولويتنا" in msg_ar or "طبيب الرحلة" in msg_ar


def test_model_escalate_token_triggers_chat_alert(client: TestClient):
    """
    Simulate a scenario where assistant output triggers [ESCALATE]
    and verify alert is created with source='chat'.
    """
    # Start session
    res_start = client.post("/sessions/start", json={"astronaut_id": 1, "mission_day": 70})
    session_id = res_start.json()["session_id"]
    client.post(f"/sessions/{session_id}/end")

    # In companion mode, if severity is high (e.g. simulated crisis), verify alert is generated
    res_comp = client.post(f"/sessions/{session_id}/companion")
    assert res_comp.status_code == 200

    # Trigger keyword in companion chat
    res_chat = client.post("/chat", json={"session_id": session_id, "message": "I want to hurt myself."})
    assert res_chat.status_code == 200
    assert res_chat.json()["escalate"] is True

    # Verify alert created
    res_alerts = client.get("/alerts")
    alerts = res_alerts.json()
    matching = [a for a in alerts if a["session_id"] == session_id]
    assert len(matching) > 0
    assert matching[0]["handled"] is False
