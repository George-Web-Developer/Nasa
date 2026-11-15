"""
Unit and integration tests for multimodal biometric fusion and calibration layer.
NASA Space Apps Challenge 2026 - Health Monitoring Software.
"""

import json
from datetime import timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, init_db
from app.models import Astronaut, Session, Analysis, Signal, FusionResult, Baseline, Alert, utc_now
from app.services.fusion_service import fuse_session
from scripts.simulate_signals import get_scenario_signals


@pytest.fixture
def fusion_db():
    """Create an isolated in-memory SQLite database for fusion tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Seed demo astronaut
    astronaut = Astronaut(
        id=10,
        name="Test Commander",
        language="en",
        role="Commander",
        consent_flag=True,
        is_simulated=True,
    )
    db.add(astronaut)
    db.commit()

    yield db
    db.close()


def test_fusion_calculation_weighted(fusion_db):
    """Test multi-channel fusion properly weights verbal rating and biometrics."""
    db = fusion_db
    # Create completed session with analysis
    session = Session(
        astronaut_id=10,
        mission_day=50,
        mode="session",
        status="completed",
    )
    db.add(session)
    db.commit()

    analysis = Analysis(
        session_id=session.id,
        scores_json=json.dumps({
            "stress": 3.0,
            "fatigue": 4.0,
            "anxiety": 2.0,
            "low_mood": 1.0,
            "social_isolation": 2.0,
            "concentration_difficulty": 1.0,
        }),
        evidence_json="{}",
        screening_answers_json="{}",
        confidence=0.9,
        risk_flag=False,
        notes="Normal baseline check-in.",
    )
    db.add(analysis)

    # Add multimodal signal
    signal = Signal(
        session_id=session.id,
        channel="multimodal",
        signals_json=json.dumps({
            "voice_stress_index": 0.35,
            "face_fatigue_score": 0.45,
            "heart_rate_bpm": 72,
        }),
        quality=0.9,
    )
    db.add(signal)
    db.commit()

    # Run fusion
    result = fuse_session(db, session.id)

    assert result is not None
    assert isinstance(result.composite_score, float)
    assert 0.0 <= result.composite_score <= 10.0
    fused = result.fused_scores
    assert "stress" in fused
    assert "fatigue" in fused
    assert fused["stress"] > 0
    # Because baseline has <5 sessions, confidence must be low
    assert result.baseline_confidence == "low"


def test_channel_conflict_detection(fusion_db):
    """Test channel conflict is flagged when self-report disagrees with telemetry."""
    db = fusion_db
    session = Session(
        astronaut_id=10,
        mission_day=51,
        mode="session",
        status="completed",
    )
    db.add(session)
    db.commit()

    # Verbal rating claims 0 stress (perfect composure)
    analysis = Analysis(
        session_id=session.id,
        scores_json=json.dumps({
            "stress": 0.0,
            "fatigue": 0.0,
            "anxiety": 0.0,
            "low_mood": 0.0,
            "social_isolation": 0.0,
            "concentration_difficulty": 0.0,
        }),
        evidence_json="{}",
        screening_answers_json="{}",
        confidence=0.9,
        risk_flag=False,
        notes="Astronaut claims zero stress.",
    )
    db.add(analysis)

    # But camera/mic telemetry indicates acute strain (stress index 0.90, HR 105)
    signal = Signal(
        session_id=session.id,
        channel="multimodal",
        signals_json=json.dumps({
            "voice_stress_index": 0.90,
            "face_fatigue_score": 0.85,
            "heart_rate_bpm": 105,
        }),
        quality=0.95,
    )
    db.add(signal)
    db.commit()

    result = fuse_session(db, session.id)

    assert result.channel_conflict is True
    assert result.conflict_notes is not None
    assert "conflict" in result.conflict_notes.lower() or "discrepancy" in result.conflict_notes.lower()


def test_baseline_confidence_and_z_scores(fusion_db):
    """Test baseline calibration: low confidence when <5 sessions, high confidence when >=5 sessions."""
    db = fusion_db

    # Create 5 historical sessions to establish baseline
    for day in range(1, 6):
        s = Session(astronaut_id=10, mission_day=day, mode="session", status="completed")
        db.add(s)
        db.flush()
        a = Analysis(
            session_id=s.id,
            scores_json=json.dumps({"stress": 2.0, "fatigue": 2.0, "anxiety": 1.0, "low_mood": 1.0, "social_isolation": 1.0, "concentration_difficulty": 1.0}),
            evidence_json="{}",
            screening_answers_json="{}",
            confidence=0.9,
            risk_flag=False,
            notes="Historical calibration",
        )
        db.add(a)
        db.commit()
        fuse_session(db, s.id)

    # 6th session with elevated stress
    s6 = Session(astronaut_id=10, mission_day=6, mode="session", status="completed")
    db.add(s6)
    db.flush()
    a6 = Analysis(
        session_id=s6.id,
        scores_json=json.dumps({"stress": 8.0, "fatigue": 7.0, "anxiety": 6.0, "low_mood": 2.0, "social_isolation": 2.0, "concentration_difficulty": 4.0}),
        evidence_json="{}",
        screening_answers_json="{}",
        confidence=0.9,
        risk_flag=False,
        notes="Acute spike",
    )
    db.add(a6)
    # Add matching elevated biometric signals
    db.add(Signal(
        session_id=s6.id,
        channel="multimodal",
        signals_json=json.dumps(get_scenario_signals("stressed")),
        quality=0.95,
    ))
    db.commit()

    result = fuse_session(db, s6.id)
    assert result.baseline_confidence == "high"
    z = result.z_scores
    assert "stress" in z
    # Stress spiked significantly from baseline ~2.0, so z-score must be positive
    assert z["stress"] > 1.0


def test_three_session_persistent_deviation_alert(fusion_db):
    """Test alert triggers when deviation persists over 3 consecutive sessions."""
    db = fusion_db

    # Establish baseline with 5 nominal sessions
    for day in range(1, 6):
        s = Session(astronaut_id=10, mission_day=day, mode="session", status="completed")
        db.add(s)
        db.flush()
        db.add(Analysis(
            session_id=s.id,
            scores_json=json.dumps({"stress": 2.0, "fatigue": 2.0, "anxiety": 1.0, "low_mood": 1.0, "social_isolation": 1.0, "concentration_difficulty": 1.0}),
            evidence_json="{}",
            screening_answers_json="{}",
            confidence=0.9,
            risk_flag=False,
            notes="Nominal",
        ))
        db.commit()
        fuse_session(db, s.id)

    # Now create 3 consecutive elevated sessions (Day 7, 8, 9) with severe strain
    for day in [7, 8, 9]:
        s = Session(astronaut_id=10, mission_day=day, mode="session", status="completed")
        db.add(s)
        db.flush()
        db.add(Analysis(
            session_id=s.id,
            scores_json=json.dumps({"stress": 9.0, "fatigue": 9.0, "anxiety": 8.5, "low_mood": 8.0, "social_isolation": 7.0, "concentration_difficulty": 7.5}),
            evidence_json="{}",
            screening_answers_json="{}",
            confidence=0.9,
            risk_flag=False,
            notes="Sustained strain",
        ))
        db.add(Signal(
            session_id=s.id,
            channel="multimodal",
            signals_json=json.dumps(get_scenario_signals("exhausted")),
            quality=0.95,
        ))
        db.commit()
        res = fuse_session(db, s.id)

    # On the 3rd consecutive high session, alert_triggered must be True
    assert res.alert_triggered is True
    # Verify alert record in astro_alerts table
    alert = db.query(Alert).filter(Alert.session_id == s.id, Alert.source == "fusion").first()
    assert alert is not None
    assert "persistent" in alert.reason.lower() or "deviation" in alert.reason.lower()


def test_simulate_signals_scenarios():
    """Verify simulate_signals generator produces valid telemetry for all scenarios."""
    for scenario_name in ["stable", "stressed", "exhausted"]:
        sig = get_scenario_signals(scenario_name)
        assert "vocal_stress_index" in sig
        assert "facial_fatigue_score" in sig
        assert "resting_heart_rate_bpm" in sig
        assert 0.0 <= sig["vocal_stress_index"] <= 1.0
        assert 0.0 <= sig["facial_fatigue_score"] <= 1.0
        assert 40 <= sig["resting_heart_rate_bpm"] <= 160
