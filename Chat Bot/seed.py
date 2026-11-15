"""
Seed script for Astronaut Psychological Daily Check-in Assistant.
Initializes the database, seeds demo astronauts, placeholder KB chunks, and sample completed sessions.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal, init_db
from app.models import (
    Astronaut,
    Session,
    Message,
    Analysis,
    Alert,
    KBChunk,
    Baseline,
    TaskEvent,
    SessionSignal,
    FusionResult,
    utc_now,
)
from scripts.kb_load import load_approved_chunks


def seed():
    print("Initializing database tables and FTS5 index...")
    init_db()

    # Seed knowledge base placeholder chunks
    placeholder_file = Path(__file__).resolve().parent / "data" / "kb_seed_placeholder.json"
    if placeholder_file.exists():
        print("Seeding placeholder KB chunks...")
        load_approved_chunks(placeholder_file, force_approve=True)

    db = SessionLocal()
    try:
        # Check if demo astronaut already exists
        demo_astronaut = db.query(Astronaut).filter(Astronaut.id == 1).first()
        if not demo_astronaut:
            print("Creating primary demo astronaut (English)...")
            demo_astronaut = Astronaut(
                id=1,
                name="Dr. Sarah Al-Mansoor",
                language="en",
                role="Commander",
                external_user_id="EXT_CREW_01",
                consent_flag=True,
                is_simulated=True,
            )
            db.add(demo_astronaut)
            db.commit()
            print("Demo astronaut created: Dr. Sarah Al-Mansoor (ID: 1, Role: Commander, Language: en)")
        else:
            demo_astronaut.role = demo_astronaut.role or "Commander"
            demo_astronaut.external_user_id = demo_astronaut.external_user_id or "EXT_CREW_01"
            db.commit()
            print(f"Primary demo astronaut already exists: {demo_astronaut.name} (ID: 1)")

        # Also create an Arabic demo astronaut for multilingual testing
        arabic_astronaut = db.query(Astronaut).filter(Astronaut.id == 2).first()
        if not arabic_astronaut:
            print("Creating second demo astronaut (Arabic)...")
            arabic_astronaut = Astronaut(
                id=2,
                name="رائد الفضاء عمر الفاروق",
                language="ar",
                role="Flight Engineer",
                external_user_id="EXT_CREW_02",
                consent_flag=True,
                is_simulated=True,
            )
            db.add(arabic_astronaut)
            db.commit()
            print("Arabic demo astronaut created: رائد الفضاء عمر الفاروق (ID: 2, Role: Flight Engineer, Language: ar)")
        else:
            arabic_astronaut.role = arabic_astronaut.role or "Flight Engineer"
            arabic_astronaut.external_user_id = arabic_astronaut.external_user_id or "EXT_CREW_02"
            db.commit()

        # Create sample baseline entries for future physiological / psychological baseline comparisons
        dimensions = ["stress", "low_mood", "anxiety", "fatigue", "social_isolation", "concentration_difficulty"]
        for dim in dimensions:
            existing_bl = db.query(Baseline).filter(Baseline.astronaut_id == 1, Baseline.dimension == dim).first()
            if not existing_bl:
                db.add(Baseline(
                    astronaut_id=1,
                    dimension=dim,
                    mean=2.5,
                    std=1.0,
                    n=14,
                ))
        db.commit()

        # Create a sample completed past session for Dr. Sarah (Mission Day 41)
        # to demonstrate longitudinal trend chart data and companion context
        past_session = db.query(Session).filter(Session.astronaut_id == 1, Session.mission_day == 41).first()
        if not past_session:
            print("Creating sample completed past session (Mission Day 41) for trend history...")
            past_time = utc_now() - timedelta(days=1)
            past_session = Session(
                astronaut_id=1,
                mission_day=41,
                mode="companion",
                status="completed",
                question_count=7,
                created_at=past_time,
                ended_at=past_time + timedelta(minutes=15),
            )
            db.add(past_session)
            db.flush()

            # Add sample messages for the past session
            past_messages = [
                Message(
                    session_id=past_session.id,
                    role="assistant",
                    content="Welcome to check-in, Commander. How did you sleep during your rest cycle last night?",
                    mode="session",
                    created_at=past_time,
                ),
                Message(
                    session_id=past_session.id,
                    role="user",
                    content="Sleep was okay, around 6 hours. Had to adjust the ventilation duct sound.",
                    mode="session",
                    created_at=past_time + timedelta(minutes=1),
                ),
                Message(
                    session_id=past_session.id,
                    role="assistant",
                    content="Good that you managed 6 hours. How is your energy and focus feeling today?",
                    mode="session",
                    created_at=past_time + timedelta(minutes=2),
                ),
                Message(
                    session_id=past_session.id,
                    role="user",
                    content="Focus is solid. Ready for the EVA rehearsal.",
                    mode="session",
                    created_at=past_time + timedelta(minutes=3),
                ),
            ]
            db.add_all(past_messages)

            # Add sample analysis
            past_analysis = Analysis(
                session_id=past_session.id,
                scores_json=json.dumps({
                    "stress": 3,
                    "low_mood": 1,
                    "anxiety": 2,
                    "fatigue": 4,
                    "social_isolation": 2,
                    "concentration_difficulty": 1,
                }),
                evidence_json=json.dumps({
                    "stress": "Ready for EVA rehearsal",
                    "fatigue": "Sleep was okay, around 6 hours with ventilation noise",
                    "social_isolation": "Solid teamwork",
                }),
                screening_answers_json=json.dumps({
                    "sleep_rating": 2,
                    "mood_rating": 0,
                }),
                confidence=0.92,
                risk_flag=False,
                notes="Astronaut Sarah displays normal operational readiness with mild acoustic sleep interference.",
                created_at=past_time + timedelta(minutes=15),
            )
            db.add(past_analysis)

            # Add sample task event
            sample_task_event = TaskEvent(
                session_id=past_session.id,
                task="Reaction Time Test",
                phase="ended",
                ts=past_time + timedelta(minutes=5),
                info_json=json.dumps({"score": 95, "duration_sec": 120}),
            )
            db.add(sample_task_event)

            # Add sample biometric signal
            sample_signal = SessionSignal(
                session_id=past_session.id,
                channel="multimodal",
                signals_json=json.dumps({
                    "voice_stress_index": 0.28,
                    "face_fatigue_score": 0.32,
                    "heart_rate_bpm": 66,
                }),
                quality=0.95,
                ts=past_time + timedelta(minutes=6),
            )
            db.add(sample_signal)

            # Add sample fusion result
            sample_fusion = FusionResult(
                session_id=past_session.id,
                astronaut_id=1,
                fused_scores_json=json.dumps({
                    "stress": 3.2,
                    "low_mood": 1.2,
                    "anxiety": 2.0,
                    "fatigue": 4.1,
                    "social_isolation": 2.0,
                    "concentration_difficulty": 1.0,
                }),
                composite_score=2.85,
                z_scores_json=json.dumps({
                    "stress": 0.7,
                    "low_mood": -1.3,
                    "anxiety": -0.5,
                    "fatigue": 1.6,
                    "social_isolation": -0.5,
                    "concentration_difficulty": -1.5,
                }),
                channel_conflict=False,
                conflict_notes=None,
                baseline_confidence="high",
                alert_triggered=False,
                created_at=past_time + timedelta(minutes=16),
            )
            db.add(sample_fusion)

            # Add sample informational alert (handled)
            sample_alert = Alert(
                session_id=past_session.id,
                reason="Routine check-in completed. Mild acoustic sleep interference noted.",
                source="analysis",
                handled=True,
                created_at=past_time + timedelta(minutes=16),
            )
            db.add(sample_alert)

            db.commit()
            print("Sample completed session (Day 41), task events, signals, fusion result, and alert seeded successfully.")
        else:
            # Session exists: ensure sample fusion result exists
            existing_fusion = db.query(FusionResult).filter(FusionResult.session_id == past_session.id).first()
            if not existing_fusion:
                sample_fusion = FusionResult(
                    session_id=past_session.id,
                    astronaut_id=1,
                    fused_scores_json=json.dumps({
                        "stress": 3.2,
                        "low_mood": 1.2,
                        "anxiety": 2.0,
                        "fatigue": 4.1,
                        "social_isolation": 2.0,
                        "concentration_difficulty": 1.0,
                    }),
                    composite_score=2.85,
                    z_scores_json=json.dumps({
                        "stress": 0.7,
                        "low_mood": -1.3,
                        "anxiety": -0.5,
                        "fatigue": 1.6,
                        "social_isolation": -0.5,
                        "concentration_difficulty": -1.5,
                    }),
                    channel_conflict=False,
                    conflict_notes=None,
                    baseline_confidence="high",
                    alert_triggered=False,
                    created_at=utc_now(),
                )
                db.add(sample_fusion)
                db.commit()
                print("Seeded sample FusionResult for existing session.")

            existing_alert = db.query(Alert).filter(Alert.session_id == past_session.id).first()
            if not existing_alert:
                sample_alert = Alert(
                    session_id=past_session.id,
                    reason="Routine check-in completed. Mild acoustic sleep interference noted.",
                    source="analysis",
                    handled=True,
                    created_at=utc_now(),
                )
                db.add(sample_alert)
                db.commit()
                print("Seeded sample Alert for existing session.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()

    print("Seeding completed successfully.")


if __name__ == "__main__":
    seed()
