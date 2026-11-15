"""
Tests for LLM client abstractions, prompt injection fallback, analyzer retry,
and widget static files and contracts.
NASA Space Apps Challenge 2026 - Health Monitoring Software.
"""

import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_client import (
    format_tools_for_openai,
    inject_knowledge_into_prompt,
    call_llm_text,
)
from app.services.analyzer_service import run_analyzer_with_retry, clean_json_string
from app.services.kb_service import KB_TOOL_DEFINITION


@pytest.fixture
def client():
    return TestClient(app)


def test_format_tools_for_openai():
    """Verify Anthropic tool definition maps cleanly to standard OpenAI function format."""
    anthropic_tools = [KB_TOOL_DEFINITION]
    openai_tools = format_tools_for_openai(anthropic_tools)

    assert len(openai_tools) == 1
    t = openai_tools[0]
    assert t["type"] == "function"
    assert t["function"]["name"] == "search_knowledge_base"
    assert "parameters" in t["function"]
    assert "query" in t["function"]["parameters"]["properties"]


def test_inject_knowledge_into_prompt():
    """Verify server-side RAG fallback injects knowledge protocols into prompt."""
    class DummyChunk:
        def __init__(self, title, topic, source_name, content):
            self.title = title
            self.topic = topic
            self.source_name = source_name
            self.content = content

    chunks = [
        DummyChunk(
            title="Box Breathing Protocol",
            topic="stress",
            source_name="NASA Operational Countermeasures",
            content="Inhale 4s, hold 4s, exhale 4s, hold 4s.",
        )
    ]
    base_prompt = "You are an empathetic companion."
    injected = inject_knowledge_into_prompt(base_prompt, chunks)

    assert "RETRIEVED OPERATIONAL PROTOCOLS" in injected
    assert "Box Breathing Protocol" in injected
    assert "NASA Operational Countermeasures" in injected
    assert "Inhale 4s, hold 4s" in injected


def test_clean_json_string():
    """Verify clean_json_string extracts JSON enclosed in markdown code fences."""
    raw_markdown = "```json\n{\"stress\": 2, \"fatigue\": 3}\n```"
    cleaned = clean_json_string(raw_markdown)
    assert cleaned == '{"stress": 2, "fatigue": 3}'


def test_run_analyzer_retry_on_invalid_json():
    """Verify analyzer retries once if first attempt returns invalid JSON."""
    bad_attempt = "I think the astronaut is feeling fine and sleep was okay."
    valid_attempt = json.dumps({
        "scores": {
            "stress": 3,
            "low_mood": 1,
            "anxiety": 2,
            "fatigue": 4,
            "social_isolation": 2,
            "concentration_difficulty": 1,
        },
        "evidence": {
            "stress": "Routine maintenance",
            "fatigue": "Sleep 6 hours",
        },
        "screening_answers": {
            "sleep_quality": 2,
        },
        "confidence": 0.88,
        "risk_flag": False,
        "notes": "Mild fatigue noted.",
    })

    # Mock generate_analyzer_json to return bad output on attempt 1,
    # and mock call_llm_text to return valid output on retry
    with patch("app.services.analyzer_service.generate_analyzer_json", return_value=bad_attempt):
        with patch("app.services.analyzer_service.call_llm_text", return_value=valid_attempt):
            result = run_analyzer_with_retry("Astronaut: Hello\nInterviewer: How are you?")
            assert result is not None
            assert result.scores.stress == 3
            assert result.scores.fatigue == 4
            assert result.risk_flag is False


def test_widget_and_demo_endpoints(client):
    """Verify widget.js and chatbot-demo.html are served with full contract support."""
    # 1. Widget script
    res_widget = client.get("/widget.js")
    assert res_widget.status_code == 200
    assert "astro-chat" in res_widget.text
    assert "astro:task" in res_widget.text
    assert "astro:context" in res_widget.text
    assert "astro:signals-summary" in res_widget.text
    assert "window.AstroChat" in res_widget.text

    # 2. Demo HTML page
    res_demo = client.get("/chatbot-demo.html")
    assert res_demo.status_code == 200
    assert "Astronaut Check-in Assistant" in res_demo.text
    assert "Host-Page Event Bridge" in res_demo.text
    assert "Reaction Time Task" in res_demo.text

    # 3. Chat UI page
    res_ui = client.get("/chat-ui")
    assert res_ui.status_code == 200
