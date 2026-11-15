"""
Unit tests for Mode B Modular Router integration (app/astro_router.py).
NASA Space Apps Challenge 2026 - Health Monitoring Software.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.astro_router import create_astro_router
from app.models import Astronaut
from app.database import SessionLocal


def test_modular_router_mount_and_endpoints(tmp_path):
    """Test mounting create_astro_router inside a teammate's FastAPI app."""
    test_db = f"sqlite:///{tmp_path}/modular_test.db"
    host_app = FastAPI(title="Teammate Host App")

    # Mount astro router at /subsystem
    astro_router = create_astro_router(
        db_url=test_db,
        config={"mock_llm": True},
    )
    host_app.include_router(astro_router, prefix="/subsystem")

    # Seed an astronaut in the modular database
    db = SessionLocal()
    astro = Astronaut(id=99, name="Modular Pilot", language="en", role="Pilot")
    db.add(astro)
    db.commit()
    db.close()

    client = TestClient(host_app)

    # 1. Health check
    res_health = client.get("/subsystem/astro-health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # 2. Widget asset access
    res_widget = client.get("/subsystem/widget.js")
    assert res_widget.status_code == 200
    assert "astro-chat" in res_widget.text

    # 3. Start check-in session via mounted route
    res_start = client.post(
        "/subsystem/sessions/start",
        json={"astronaut_id": 99, "mission_day": 10},
    )
    assert res_start.status_code == 201
    data = res_start.json()
    assert "session_id" in data
    assert "first_message" in data


def test_modular_router_api_token_protection(tmp_path):
    """Test that optional API_TOKEN enforces authorization when configured."""
    test_db = f"sqlite:///{tmp_path}/auth_test.db"
    host_app = FastAPI()

    secret = "classified-mission-key-2026"
    astro_router = create_astro_router(
        db_url=test_db,
        config={"mock_llm": True, "api_token": secret},
    )
    host_app.include_router(astro_router, prefix="/secured")

    # Seed astronaut
    db = SessionLocal()
    db.add(Astronaut(id=101, name="Secure Astronaut", language="en"))
    db.commit()
    db.close()

    client = TestClient(host_app)

    # Calling without token must fail with 401
    res_unauth = client.post(
        "/secured/sessions/start",
        json={"astronaut_id": 101, "mission_day": 1},
    )
    assert res_unauth.status_code == 401

    # Calling with valid Bearer token must succeed
    res_auth = client.post(
        "/secured/sessions/start",
        json={"astronaut_id": 101, "mission_day": 1},
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert res_auth.status_code == 201
    assert "session_id" in res_auth.json()
