import os
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment flags before importing application modules
os.environ["MOCK_LLM"] = "true"
os.environ["DB_URL"] = "sqlite:///./test_astronaut_checkin.db"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "anthropic"

from app.database import Base, get_db, setup_sqlite_fts, rebuild_fts_index
from app.models import Astronaut, KBChunk, utc_now
from app.main import app

# Test database engine
TEST_DB_FILE = "./test_astronaut_checkin.db"
test_engine = create_engine(f"sqlite:///{TEST_DB_FILE}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test tables, FTS5 virtual table, and seed test data once for the test session."""
    # Ensure fresh start
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with test_engine.connect() as conn:
        setup_sqlite_fts(conn)
        conn.commit()

    # Seed test astronauts and placeholder KB chunks
    db = TestingSessionLocal()
    try:
        a1 = Astronaut(id=1, name="Dr. Sarah Al-Mansoor", language="en")
        a2 = Astronaut(id=2, name="رائد الفضاء عمر الفاروق", language="ar")
        db.add_all([a1, a2])

        # Load placeholder KB chunks
        placeholder_file = Path(__file__).resolve().parent.parent / "data" / "kb_seed_placeholder.json"
        if placeholder_file.exists():
            with open(placeholder_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            for c in chunks:
                chunk = KBChunk(
                    id=c.get("id"),
                    title=c.get("title"),
                    topic=c.get("topic"),
                    severity_min=float(c.get("severity_min", 0.0)),
                    severity_max=float(c.get("severity_max", 10.0)),
                    content=c.get("content"),
                    source_name=c.get("source_name"),
                    source_url=c.get("source_url"),
                    language=c.get("language", "en"),
                    last_reviewed=utc_now(),
                    approved=True,
                )
                db.add(chunk)

        db.commit()
        rebuild_fts_index(db)
    finally:
        db.close()

    yield

    # Teardown
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


@pytest.fixture
def client():
    """FastAPI TestClient with overridden database dependency."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
