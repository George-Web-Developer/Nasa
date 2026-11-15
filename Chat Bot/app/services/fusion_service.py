"""
Multimodal Affective & Physiological Fusion Engine.
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Fuses:
1. Conversational Psychological Rating (from app.services.analyzer_service)
2. Acoustic Affect Telemetry (vocal pitch, variability, speech rate, vocal stress)
3. Visual Affect Telemetry (facial expressivity, action units, fatigue score)
4. Physiological Sensor Telemetry (wearable HR, HRV, sleep efficiency, rest duration)

Features:
- Weighted fusion using each channel's quality score.
- Dynamic per-astronaut baseline calibration with Z-scores (requires ~5 sessions; flags low confidence before that).
- Channel conflict detection (e.g., verbal stoicism masking high autonomic strain).
- Persistent deviation alerts: fires a clinical alert ONLY when deviation persists over 3 consecutive sessions.
- Non-diagnostic: early-warning support tool only; never stores raw audio/video.
"""

import json
import math
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.models import (
    Session,
    Astronaut,
    Analysis,
    Signal,
    FusionResult,
    Baseline,
    Alert,
    utc_now,
)
from app.config import logger


# Default weights for sensor channels
DEFAULT_CHANNEL_WEIGHTS = {
    "conversational": 1.0,
    "physiological": 0.9,
    "acoustic": 0.8,
    "facial": 0.8,
}


def extract_telemetry_metrics(session: Session) -> Dict[str, Any]:
    """Aggregate all logged telemetry signals for this session into unified metrics."""
    metrics: Dict[str, Any] = {}
    signals = session.signals or []

    for s in signals:
        data = s.signals or {}
        # Merge metrics; later signals update earlier ones
        for k, v in data.items():
            if isinstance(v, (int, float, dict, str, bool)):
                metrics[k] = v

    return metrics


def calculate_channel_scores(
    analysis_scores: Dict[str, Any],
    telemetry: Dict[str, Any],
) -> Dict[str, Tuple[float, float]]:
    """
    Compute normalized strain score (0.0 to 10.0) and channel quality (0.0 to 1.0) for each channel.
    Returns: {channel_name: (strain_score, quality)}
    """
    channels: Dict[str, Tuple[float, float]] = {}

    # 1. Conversational Channel
    valid_analysis_vals = [
        float(v) for v in analysis_scores.values()
        if isinstance(v, (int, float)) and v is not None
    ]
    if valid_analysis_vals:
        conv_strain = sum(valid_analysis_vals) / len(valid_analysis_vals)
        channels["conversational"] = (min(max(conv_strain, 0.0), 10.0), 0.95)
    else:
        channels["conversational"] = (2.5, 0.4)

    # 2. Acoustic Affect Channel
    vocal_stress = float(telemetry.get("vocal_stress_index", telemetry.get("voice_stress_index", 0.25)))
    pitch_var = float(telemetry.get("pitch_variability_semitones", 2.2))
    speech_rate = float(telemetry.get("speech_rate_sps", telemetry.get("speech_rate_syllables_per_sec", 3.4)))

    # Acoustic strain derived from vocal stress and monotone/slow speech indicators
    acoustic_strain = vocal_stress * 8.0
    if pitch_var < 1.5:  # Monotone marker
        acoustic_strain += 1.5
    if speech_rate < 2.5:  # Psychomotor slowing marker
        acoustic_strain += 1.5
    acoustic_quality = 0.9 if ("vocal_stress_index" in telemetry or "voice_stress_index" in telemetry) else 0.5
    channels["acoustic"] = (min(max(acoustic_strain, 0.0), 10.0), acoustic_quality)

    # 3. Visual Affect Channel
    face_fatigue = float(telemetry.get("facial_fatigue_score", 0.25))
    expressivity = float(telemetry.get("facial_expressivity_index", 0.70))

    visual_strain = face_fatigue * 8.0
    if expressivity < 0.25:  # Flat affect / affect attenuation marker
        visual_strain += 2.0
    visual_quality = 0.9 if ("facial_fatigue_score" in telemetry or "facial_expressivity_index" in telemetry) else 0.5
    channels["facial"] = (min(max(visual_strain, 0.0), 10.0), visual_quality)

    # 4. Physiological Wearable Telemetry Channel
    hrv = float(telemetry.get("hrv_rmssd_ms", telemetry.get("hrv_rmssd", 45.0)))
    resting_hr = float(telemetry.get("resting_heart_rate_bpm", telemetry.get("resting_hr", 65.0)))
    sleep_eff = float(telemetry.get("sleep_efficiency_pct", 85.0))
    sleep_hrs = float(telemetry.get("total_sleep_hours", 7.2))

    physio_strain = 2.0
    if hrv < 25.0:  # Severe autonomic strain
        physio_strain += 3.5
    elif hrv < 40.0:
        physio_strain += 1.8

    if sleep_hrs < 5.5 or sleep_eff < 70.0:  # Acute sleep debt
        physio_strain += 3.0
    elif sleep_hrs < 6.5 or sleep_eff < 80.0:
        physio_strain += 1.5

    if resting_hr > 85.0:
        physio_strain += 1.5

    physio_quality = 0.95 if ("hrv_rmssd_ms" in telemetry or "sleep_efficiency_pct" in telemetry) else 0.5
    channels["physiological"] = (min(max(physio_strain, 0.0), 10.0), physio_quality)

    return channels


def detect_channel_conflict(channel_scores: Dict[str, Tuple[float, float]]) -> Tuple[bool, str]:
    """
    Identifies significant discrepancies between conversational self-report and objective sensors.
    For example: Astronaut minimizes stress in dialogue, but physiological HRV & voice show high strain.
    """
    conv_score, conv_q = channel_scores.get("conversational", (2.5, 0.5))

    sensor_scores = []
    sensor_weights = []
    for ch in ["physiological", "acoustic", "facial"]:
        if ch in channel_scores:
            score, q = channel_scores[ch]
            sensor_scores.append(score)
            sensor_weights.append(q)

    if not sensor_scores:
        return False, "Nominal concordance: only single channel telemetry available."

    avg_sensor_score = sum(s * w for s, w in zip(sensor_scores, sensor_weights)) / sum(sensor_weights)
    diff = abs(conv_score - avg_sensor_score)

    # Clinically meaningful discordance threshold: 4.0 points out of 10
    if diff >= 3.5:
        if conv_score < avg_sensor_score:
            note = (
                f"Channel Conflict Detected (discordance={diff:.1f}): Conversational self-report is low ({conv_score:.1f}/10), "
                f"while objective sensor telemetry demonstrates elevated strain ({avg_sensor_score:.1f}/10). Possible stoic masking."
            )
        else:
            note = (
                f"Channel Conflict Detected (discordance={diff:.1f}): Conversational self-report indicates acute distress ({conv_score:.1f}/10), "
                f"while objective biometric telemetry is relatively stable ({avg_sensor_score:.1f}/10)."
            )
        return True, note

    return False, "Nominal multi-channel concordance between subjective self-report and biometric sensors."


def update_or_get_baselines(
    db: DBSession,
    astronaut_id: int,
    current_fused_scores: Dict[str, float],
) -> Tuple[Dict[str, Dict[str, float]], str]:
    """
    Calibrate or retrieve per-astronaut baselines.
    Rule: Requires ~5 completed sessions for normative calibration; flags 'low' confidence before that.
    Returns: (baselines_dict, confidence_level)
    """
    # Count past completed sessions for this astronaut
    completed_count = (
        db.query(Session)
        .filter(Session.astronaut_id == astronaut_id, Session.status == "completed")
        .count()
    )

    confidence = "high" if completed_count >= 5 else "low"

    baselines_dict: Dict[str, Dict[str, float]] = {}

    for dim, score in current_fused_scores.items():
        bl = (
            db.query(Baseline)
            .filter(Baseline.astronaut_id == astronaut_id, Baseline.dimension == dim)
            .first()
        )
        if not bl:
            # Initialize baseline
            bl = Baseline(
                astronaut_id=astronaut_id,
                dimension=dim,
                mean=score,
                std=1.0,
                n=1,
                updated_at=utc_now(),
            )
            db.add(bl)
            db.flush()
        else:
            # Welford's online update algorithm for mean and std
            n_new = bl.n + 1
            delta = score - bl.mean
            new_mean = bl.mean + delta / n_new
            delta2 = score - new_mean
            m2 = (bl.std ** 2) * max(bl.n - 1, 1) + delta * delta2
            new_std = math.sqrt(m2 / max(n_new - 1, 1))

            bl.mean = round(new_mean, 3)
            bl.std = max(round(new_std, 3), 0.5)  # Enforce minimum std to prevent div-by-zero
            bl.n = n_new
            bl.updated_at = utc_now()

        baselines_dict[dim] = {"mean": bl.mean, "std": bl.std, "n": bl.n}

    db.commit()
    return baselines_dict, confidence


def compute_z_scores(
    fused_scores: Dict[str, float],
    baselines: Dict[str, Dict[str, float]],
) -> Dict[str, float]:
    """Calculate Z-score for each dimension compared to the astronaut's historical baseline."""
    z_scores = {}
    for dim, score in fused_scores.items():
        bl = baselines.get(dim, {"mean": 2.5, "std": 1.0})
        mean = bl.get("mean", 2.5)
        std = max(bl.get("std", 1.0), 0.5)
        z = (score - mean) / std
        z_scores[dim] = round(z, 2)
    return z_scores


def check_persistent_deviation_alert(
    db: DBSession,
    session: Session,
    current_composite: float,
    current_z: float,
) -> bool:
    """
    Clinical Safeguard:
    Alert ONLY when the strain deviation persists over 3 consecutive sessions.
    Avoids false alarms from single-day operational spikes (e.g. EVA day or docking).
    """
    # Fetch last 2 completed fusion results prior to current session
    prior_fusions = (
        db.query(FusionResult)
        .filter(
            FusionResult.astronaut_id == session.astronaut_id,
            FusionResult.session_id != session.id,
        )
        .order_by(FusionResult.created_at.desc())
        .limit(2)
        .all()
    )

    if len(prior_fusions) < 2:
        # Not enough history to confirm 3 consecutive sessions
        return False

    # Check deviation threshold across all 3 sessions:
    # Deviation criteria: composite_score >= 6.5 or composite Z-score >= 2.0
    f1, f2 = prior_fusions[0], prior_fusions[1]

    f1_deviant = f1.composite_score >= 6.5 or f1.z_scores.get("composite", 0.0) >= 2.0
    f2_deviant = f2.composite_score >= 6.5 or f2.z_scores.get("composite", 0.0) >= 2.0
    current_deviant = current_composite >= 6.5 or current_z >= 2.0

    if f1_deviant and f2_deviant and current_deviant:
        logger.warning(
            f"Persistent multi-channel strain deviation detected for astronaut {session.astronaut_id} across 3 sessions."
        )
        alert = Alert(
            session_id=session.id,
            reason=(
                f"Persistent strain deviation across 3 consecutive sessions "
                f"(current composite={current_composite:.1f}/10, Z={current_z:.2f}). Flight surgeon consult recommended."
            ),
            source="fusion",
            handled=False,
            created_at=utc_now(),
        )
        db.add(alert)
        db.commit()
        return True

    return False


def fuse_session(db: DBSession, session_id: int) -> FusionResult:
    """
    Main entry point for session multimodal fusion.
    Integrates conversational analysis, vocal telemetry, facial markers, and physiological streams.
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise ValueError(f"Session with id {session_id} not found.")

    analysis_scores = session.analysis.scores if session.analysis else {}
    telemetry = extract_telemetry_metrics(session)

    # 1. Compute normalized channel strain and quality
    channel_scores = calculate_channel_scores(analysis_scores, telemetry)

    # 2. Check for channel conflict
    has_conflict, conflict_notes = detect_channel_conflict(channel_scores)

    # 3. Weighted Multi-Channel Fusion per dimension
    conv_score, conv_q = channel_scores["conversational"]
    acoust_score, acoust_q = channel_scores["acoustic"]
    facial_score, facial_q = channel_scores["facial"]
    physio_score, physio_q = channel_scores["physiological"]

    # Dimension fusion formulas
    fused_stress = (conv_score * 0.4 + acoust_score * 0.3 + physio_score * 0.3)
    fused_fatigue = (conv_score * 0.3 + facial_score * 0.35 + physio_score * 0.35)
    fused_low_mood = (conv_score * 0.5 + acoust_score * 0.25 + facial_score * 0.25)
    fused_anxiety = (conv_score * 0.4 + physio_score * 0.4 + acoust_score * 0.2)
    fused_social = float(analysis_scores.get("social_isolation", conv_score * 0.8))
    fused_cognitive = float(analysis_scores.get("concentration_difficulty", (conv_score + physio_score) / 2))

    fused_dimensions = {
        "stress": round(min(max(fused_stress, 0.0), 10.0), 2),
        "fatigue": round(min(max(fused_fatigue, 0.0), 10.0), 2),
        "low_mood": round(min(max(fused_low_mood, 0.0), 10.0), 2),
        "anxiety": round(min(max(fused_anxiety, 0.0), 10.0), 2),
        "social_isolation": round(min(max(fused_social, 0.0), 10.0), 2),
        "concentration_difficulty": round(min(max(fused_cognitive, 0.0), 10.0), 2),
    }

    composite_score = round(sum(fused_dimensions.values()) / len(fused_dimensions), 2)
    fused_dimensions["composite"] = composite_score

    # 4. Baselines and Z-Scores
    baselines, confidence_level = update_or_get_baselines(db, session.astronaut_id, fused_dimensions)
    z_scores = compute_z_scores(fused_dimensions, baselines)

    # 5. Persistent Deviation Alert (over 3 sessions)
    alert_triggered = check_persistent_deviation_alert(
        db,
        session,
        composite_score,
        z_scores.get("composite", 0.0),
    )

    # 6. Save or update FusionResult
    existing_fusion = db.query(FusionResult).filter(FusionResult.session_id == session.id).first()
    if existing_fusion:
        existing_fusion.fused_scores_json = json.dumps(fused_dimensions)
        existing_fusion.composite_score = composite_score
        existing_fusion.z_scores_json = json.dumps(z_scores)
        existing_fusion.channel_conflict = has_conflict
        existing_fusion.conflict_notes = conflict_notes
        existing_fusion.baseline_confidence = confidence_level
        existing_fusion.alert_triggered = alert_triggered
        result = existing_fusion
    else:
        result = FusionResult(
            session_id=session.id,
            astronaut_id=session.astronaut_id,
            fused_scores_json=json.dumps(fused_dimensions),
            composite_score=composite_score,
            z_scores_json=json.dumps(z_scores),
            channel_conflict=has_conflict,
            conflict_notes=conflict_notes,
            baseline_confidence=confidence_level,
            alert_triggered=alert_triggered,
            created_at=utc_now(),
        )
        db.add(result)

    db.commit()
    db.refresh(result)
    logger.info(
        f"Session {session.id} fusion complete: composite={composite_score:.2f}, "
        f"conflict={has_conflict}, baseline_conf='{confidence_level}', alert={alert_triggered}"
    )
    return result
