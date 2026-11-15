"""
Multimodal Biometric & Affect Signal Simulator.
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Generates realistic simulated sensor telemetry across three operational spaceflight scenarios:
1. 'stable': Nominal circadian rest, parasympathetic dominance, energetic speech, high facial expressivity.
2. 'stressed': Autonomic sympathetic arousal, low HRV, elevated heart rate, vocal strain, brow tension.
3. 'exhausted': Severe cumulative sleep debt, psychomotor slowing, monotone acoustics, eyelid fatigue.

Can be run via CLI or imported into automated tests and seed scripts.
NEVER creates or stores raw video/audio files - strictly non-diagnostic numeric affect metrics.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any

# Ensure project root in python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_scenario_signals(scenario: str) -> Dict[str, Any]:
    """Returns realistic simulated telemetry dictionary for specified operational scenario."""
    sc = (scenario or "stable").lower()

    if sc == "stressed":
        return {
            # Acoustic Affect Features
            "mean_pitch_f0_hz": 142.5,
            "pitch_variability_semitones": 1.4,       # Monotone pitch indicator
            "speech_rate_sps": 3.1,
            "vocal_stress_index": 0.72,               # High vocal acoustic strain
            
            # Visual Facial Action Units (FAU)
            "facial_expressivity_index": 0.42,
            "facial_fatigue_score": 0.55,
            "brow_furrow_au04": 0.68,                 # Corrugator supercilii tension
            "lip_corner_depressor_au15": 0.45,

            # Autonomic & Physiological Telemetry
            "resting_heart_rate_bpm": 86.0,
            "hrv_rmssd_ms": 22.5,                     # Low HRV = sympathetic dominance
            "sleep_efficiency_pct": 74.0,
            "total_sleep_hours": 5.6,
            "skin_temp_deviation_c": +0.45,
            "quality": 0.95,
            "scenario": "stressed",
        }

    elif sc == "exhausted":
        return {
            # Acoustic Affect Features
            "mean_pitch_f0_hz": 108.0,
            "pitch_variability_semitones": 1.05,      # Severely monotone speech
            "speech_rate_sps": 2.1,                   # Psychomotor slowing (< 2.5)
            "vocal_stress_index": 0.84,

            # Visual Facial Action Units (FAU)
            "facial_expressivity_index": 0.18,        # Flat affect / affect attenuation
            "facial_fatigue_score": 0.91,             # Eyelid drooping / slow blinks
            "eyelid_droop_au43": 0.88,
            "yawns_per_10min": 4,

            # Autonomic & Physiological Telemetry
            "resting_heart_rate_bpm": 78.0,
            "hrv_rmssd_ms": 17.0,                     # Severe autonomic fatigue
            "sleep_efficiency_pct": 58.0,             # Disturbed sleep cycle
            "total_sleep_hours": 4.1,                 # Acute sleep deficit
            "skin_temp_deviation_c": -0.60,
            "quality": 0.95,
            "scenario": "exhausted",
        }

    else:  # "stable" (default)
        return {
            # Acoustic Affect Features
            "mean_pitch_f0_hz": 122.0,
            "pitch_variability_semitones": 2.6,       # Natural, expressive intonation
            "speech_rate_sps": 3.8,
            "vocal_stress_index": 0.16,               # Nominal vocal strain

            # Visual Facial Action Units (FAU)
            "facial_expressivity_index": 0.76,        # High, animated facial engagement
            "facial_fatigue_score": 0.18,
            "zygomatic_smile_au12": 0.65,

            # Autonomic & Physiological Telemetry
            "resting_heart_rate_bpm": 64.0,           # Healthy resting baseline
            "hrv_rmssd_ms": 54.0,                     # Robust parasympathetic recovery
            "sleep_efficiency_pct": 89.5,             # Restorative sleep
            "total_sleep_hours": 7.6,
            "skin_temp_deviation_c": 0.0,
            "quality": 0.98,
            "scenario": "stable",
        }


def simulate(session_id: int, scenario: str, api_base: str = None, direct_db: bool = False):
    signals_data = get_scenario_signals(scenario)

    if direct_db or not api_base:
        # Save directly to local database
        from app.database import SessionLocal, init_db
        from app.models import Signal, Session, utc_now

        init_db()
        db = SessionLocal()
        try:
            sess = db.query(Session).filter(Session.id == session_id).first()
            if not sess:
                print(f"[ERROR] Session with id {session_id} not found in database.")
                return False

            sig = Signal(
                session_id=session_id,
                channel="multimodal",
                signals_json=json.dumps(signals_data),
                quality=signals_data.get("quality", 1.0),
                ts=utc_now(),
            )
            db.add(sig)
            db.commit()
            print(f"[SUCCESS] Injected simulated '{scenario}' telemetry for Session #{session_id} (Signal ID: {sig.id})")
            return True
        finally:
            db.close()
    else:
        # POST via HTTP API
        import urllib.request
        import urllib.error

        url = f"{api_base.rstrip('/')}/sessions/{session_id}/signals"
        payload = json.dumps({"signals": signals_data}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"[SUCCESS] POSTed '{scenario}' telemetry to {url}: Record ID {data.get('id')}")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to POST signals to {url}: {e}")
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate astronaut camera/mic/physiological signals.")
    parser.add_argument("--session-id", type=int, default=1, help="Target session ID (default: 1)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="stable",
        choices=["stable", "stressed", "exhausted"],
        help="Telemetry profile (stable, stressed, exhausted)",
    )
    parser.add_argument("--api-base", type=str, default="", help="Backend URL (e.g. http://localhost:8000)")
    parser.add_argument("--direct-db", action="store_true", help="Write directly to SQLite database")

    args = parser.parse_args()
    simulate(
        session_id=args.session_id,
        scenario=args.scenario,
        api_base=args.api_base,
        direct_db=args.direct_db or not args.api_base,
    )
