import os
import subprocess
import sys
from pathlib import Path


CHATBOT_ROOT = Path(__file__).resolve().parents[1]


def test_sqlite_parent_dir_and_auto_seed_on_lifespan_startup(tmp_path):
    """Fresh SQLite DB path in non-existent directory auto-creates parent dir and auto-seeds crew on FastAPI startup."""
    db_file = tmp_path / "nested" / "cloud_data" / "astronaut_checkin.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    script = f"""
import sqlite3
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    chat_check = client.get("/astronauts")
    assert chat_check.status_code == 200, chat_check.text
    crew = chat_check.json()
    assert len(crew) >= 1, f"Expected auto-seeded crew, got {{crew}}"

# Restart lifespan against same populated DB to confirm idempotency
with TestClient(app) as client2:
    crew2 = client2.get("/astronauts").json()
    assert len(crew2) == len(crew), f"Expected idempotent startup seed: {{len(crew)}} vs {{len(crew2)}}"
"""

    env = os.environ.copy()
    env["DB_URL"] = db_url
    env["MOCK_LLM"] = "true"
    env["PYTHONPATH"] = str(CHATBOT_ROOT)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(CHATBOT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert db_file.exists(), "Expected SQLite DB file to be created inside missing nested directory"
