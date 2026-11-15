import json
import re
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session as DBSession
from app.models import Session, Message, Analysis, Alert
from app.schemas import AnalyzerOutput, DimensionScores, DimensionEvidence
from app.services.llm_service import generate_analyzer_json
from app.services.llm_client import call_llm_text
from app.prompts import ANALYZER_PROMPT
from app.safety import detect_safety_keywords
from app.config import logger


def clean_json_string(raw: str) -> str:
    """Extract raw JSON text if enclosed in markdown code fences or conversational text."""
    if not raw:
        return ""
    # Strip markdown code fences if present
    code_fence_pattern = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if code_fence_pattern:
        return code_fence_pattern.group(1).strip()
    return raw.strip()


def build_transcript_string(messages: List[Message]) -> str:
    """Format messages list into a clean text transcript."""
    lines = []
    for msg in messages:
        sender = "Astronaut" if msg.role == "user" else "Interviewer"
        lines.append(f"[{msg.created_at.strftime('%H:%M:%S')}] {sender}: {msg.content}")
    return "\n".join(lines)


def run_analyzer_with_retry(transcript: str, has_crisis_keyword: bool = False) -> AnalyzerOutput:
    """
    Execute analyzer LLM call. Validate with Pydantic AnalyzerOutput.
    If parsing fails, retry ONCE as required.
    """
    # Attempt 1
    raw_output = generate_analyzer_json(transcript, has_crisis_keyword=has_crisis_keyword)
    cleaned = clean_json_string(raw_output)

    try:
        data = json.loads(cleaned)
        validated = AnalyzerOutput.model_validate(data)
        logger.info("Analyzer output successfully validated on attempt 1.")
        return validated
    except Exception as e1:
        logger.warning(f"Analyzer attempt 1 failed validation: {e1}. Retrying once...")

    # Retry Attempt (Attempt 2)
    try:
        retry_prompt = (
            f"The previous output was not valid JSON matching the schema. "
            f"Please re-rate the following transcript strictly and return ONLY a valid JSON object matching the schema:\n\n"
            f"=== TRANSCRIPT ===\n{transcript}\n==================\n\n"
            "Dimensions: stress, low_mood, anxiety, fatigue, social_isolation, concentration_difficulty (0-10 or null)."
        )
        retry_raw = call_llm_text(ANALYZER_PROMPT, [{"role": "user", "content": retry_prompt}], temperature=0.0)
        retry_cleaned = clean_json_string(retry_raw)
        retry_data = json.loads(retry_cleaned)
        validated_retry = AnalyzerOutput.model_validate(retry_data)
        logger.info("Analyzer output successfully validated on retry attempt.")
        return validated_retry
    except Exception as e2:
        logger.error(f"Analyzer retry also failed: {e2}. Falling back to safe conservative analysis.")
        # Safe fallback
        return AnalyzerOutput(
            scores=DimensionScores(
                stress=None,
                low_mood=None,
                anxiety=None,
                fatigue=None,
                social_isolation=None,
                concentration_difficulty=None,
            ),
            evidence=DimensionEvidence(),
            screening_answers={},
            confidence=0.5,
            risk_flag=has_crisis_keyword,
            notes=f"Automatic analysis parsing was inconclusive. Manual clinical review recommended. (Error: {str(e2)})",
        )


def analyze_and_save_session(db: DBSession, session_obj: Session) -> Analysis:
    """
    Run the psychological analyzer for a completed session, persist to database,
    and trigger risk alert if risk_flag is True.
    """
    # Check if analysis already exists
    if session_obj.analysis:
        logger.info(f"Analysis for session {session_obj.id} already exists. Returning existing.")
        return session_obj.analysis

    # 1. Fetch all session messages
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_obj.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    transcript = build_transcript_string(messages)

    # 2. Check if any message contained critical safety keywords
    has_crisis_keyword = False
    for msg in messages:
        if msg.role == "user":
            hit, _ = detect_safety_keywords(msg.content)
            if hit:
                has_crisis_keyword = True
                break

    # 3. Run analyzer with retry
    analyzer_result = run_analyzer_with_retry(transcript, has_crisis_keyword=has_crisis_keyword)

    # 4. Save analysis to database
    analysis_record = Analysis(
        session_id=session_obj.id,
        scores_json=json.dumps(analyzer_result.scores.model_dump()),
        evidence_json=json.dumps(analyzer_result.evidence.model_dump()),
        screening_answers_json=json.dumps(analyzer_result.screening_answers),
        confidence=analyzer_result.confidence,
        risk_flag=analyzer_result.risk_flag,
        notes=analyzer_result.notes,
    )
    db.add(analysis_record)
    db.flush()

    # 5. If risk_flag is true, create an alert
    if analyzer_result.risk_flag:
        alert = Alert(
            session_id=session_obj.id,
            reason=f"Analyzer flagged psychological risk: {analyzer_result.notes}",
            source="analysis",
            handled=False,
        )
        db.add(alert)
        logger.warning(f"High risk alert created for session {session_obj.id}")

    db.commit()
    db.refresh(analysis_record)
    return analysis_record
