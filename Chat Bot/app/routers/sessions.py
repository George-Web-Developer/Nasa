import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import (
    Astronaut,
    Session,
    Message,
    Analysis,
    Alert,
    TaskEvent,
    SessionSignal,
    Signal,
    FusionResult,
    utc_now,
)
from app.schemas import (
    SessionStartRequest,
    SessionStartResponse,
    CompanionStartResponse,
    SessionDetailResponse,
    AnalysisRead,
    MessageRead,
    AlertRead,
    TaskEventCreate,
    TaskEventRead,
    SignalsCreate,
    SignalsRead,
    PendingQuestionResponse,
    FusionResultRead,
)
from app.services.fusion_service import fuse_session
from app.services.llm_service import (
    generate_first_interview_message,
    generate_companion_opening,
    generate_direct_companion_opening,
)
from app.services.analyzer_service import analyze_and_save_session
from app.services.session_service import (
    get_past_sessions_summary,
    get_session_transcript_text,
)
from app.config import logger

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("/start", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_session(payload: SessionStartRequest, db: DBSession = Depends(get_db)):
    """
    Start a new daily check-in session for an astronaut.
    Initializes session in 'session' mode and returns the opening question (Question #1).
    """
    astronaut = db.query(Astronaut).filter(Astronaut.id == payload.astronaut_id).first()
    if not astronaut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Astronaut with id {payload.astronaut_id} not found."
        )

    # 1. Create new session in requested mode ('session' check-in or 'companion' open discussion)
    session_mode = "companion" if (payload.mode or "").strip().lower() == "companion" else "session"
    session = Session(
        astronaut_id=astronaut.id,
        mission_day=payload.mission_day,
        mode=session_mode,
        status="active",
        question_count=0 if session_mode == "companion" else 1,
        created_at=utc_now(),
    )
    db.add(session)
    db.flush()

    # 2. Generate opening message in astronaut's preferred language
    try:
        if session_mode == "companion":
            first_message_content = generate_direct_companion_opening(
                astronaut_name=astronaut.name,
                language=astronaut.language,
                mission_day=payload.mission_day,
            )
        else:
            first_message_content = generate_first_interview_message(
                astronaut_name=astronaut.name,
                language=astronaut.language,
            )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate first message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate first message: {str(e)}"
        )

    # 3. Store first message in messages table
    first_msg = Message(
        session_id=session.id,
        role="assistant",
        content=first_message_content,
        mode=session_mode,
        created_at=utc_now(),
    )
    db.add(first_msg)
    db.commit()
    db.refresh(session)

    logger.info(f"Started {session_mode} session {session.id} for astronaut {astronaut.id} ({astronaut.name})")
    return SessionStartResponse(
        session_id=session.id,
        first_message=first_message_content,
        mode=session_mode,
    )


@router.post("/{id}/end", response_model=AnalysisRead)
def end_session(id: int, db: DBSession = Depends(get_db)):
    """
    Mark check-in session as completed, execute the psychological analyzer at temperature 0,
    save the structured analysis, and flag any medical/psychological risk alerts.
    """
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    # Update session status
    session.status = "completed"
    if not session.ended_at:
        session.ended_at = utc_now()
    db.commit()

    # Run analyzer and save analysis
    try:
        analysis = analyze_and_save_session(db, session)
    except Exception as e:
        logger.error(f"Error running analyzer for session {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing psychological analysis: {str(e)}"
        )

    return AnalysisRead(
        id=analysis.id,
        session_id=analysis.session_id,
        scores=analysis.scores,
        evidence=analysis.evidence,
        screening_answers=analysis.screening_answers,
        confidence=analysis.confidence,
        risk_flag=analysis.risk_flag,
        notes=analysis.notes,
        created_at=analysis.created_at,
    )


@router.post("/{id}/companion", response_model=CompanionStartResponse)
def switch_to_companion(id: int, db: DBSession = Depends(get_db)):
    """
    Switch a session to Companion mode.
    Ensures analysis exists (auto-analyzing if necessary), builds companion system context
    with transcript + confidential analysis + past 3 sessions summary, and returns an opening message.
    """
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    astronaut = session.astronaut
    if not astronaut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Astronaut record associated with session not found."
        )

    # If session is active, complete it and analyze
    if session.status == "active":
        session.status = "completed"
        if not session.ended_at:
            session.ended_at = utc_now()
        db.commit()

    # Ensure analysis exists
    if not session.analysis:
        analyze_and_save_session(db, session)
        db.refresh(session)

    # Switch session mode to companion
    session.mode = "companion"
    db.commit()

    # Build context for companion opening
    transcript = get_session_transcript_text(db, session.id)
    analysis_dict = {
        "scores": session.analysis.scores if session.analysis else {},
        "notes": session.analysis.notes if session.analysis else "",
        "risk_flag": session.analysis.risk_flag if session.analysis else False,
    }
    past_sessions_summary = get_past_sessions_summary(db, astronaut.id, session.id)

    # Generate companion opening message
    try:
        opening_content = generate_companion_opening(
            astronaut_name=astronaut.name,
            language=astronaut.language,
            transcript=transcript,
            analysis_dict=analysis_dict,
            past_sessions_summary=past_sessions_summary,
        )
    except Exception as e:
        logger.error(f"Error generating companion opening for session {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate companion opening: {str(e)}"
        )

    # Save companion opening message
    opening_msg = Message(
        session_id=session.id,
        role="assistant",
        content=opening_content,
        mode="companion",
        created_at=utc_now(),
    )
    db.add(opening_msg)
    db.commit()

    logger.info(f"Session {session.id} switched to companion mode.")
    return CompanionStartResponse(
        session_id=session.id,
        mode="companion",
        opening_message=opening_content,
    )


@router.get("/{id}", response_model=SessionDetailResponse)
def get_session_detail(id: int, db: DBSession = Depends(get_db)):
    """
    Get full session record including all conversation messages, psychological analysis,
    and associated safety alerts.
    """
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    analysis_read = None
    if session.analysis:
        analysis_read = AnalysisRead(
            id=session.analysis.id,
            session_id=session.analysis.session_id,
            scores=session.analysis.scores,
            evidence=session.analysis.evidence,
            screening_answers=session.analysis.screening_answers,
            confidence=session.analysis.confidence,
            risk_flag=session.analysis.risk_flag,
            notes=session.analysis.notes,
            created_at=session.analysis.created_at,
        )

    messages_read = [
        MessageRead(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            mode=m.mode,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    alerts_read = [
        AlertRead(
            id=a.id,
            session_id=a.session_id,
            reason=a.reason,
            source=a.source,
            handled=a.handled,
            created_at=a.created_at,
        )
        for a in session.alerts
    ]

    return SessionDetailResponse(
        id=session.id,
        astronaut_id=session.astronaut_id,
        astronaut_name=session.astronaut.name if session.astronaut else None,
        astronaut_language=session.astronaut.language if session.astronaut else None,
        created_at=session.created_at,
        ended_at=session.ended_at,
        mission_day=session.mission_day,
        mode=session.mode,
        status=session.status,
        question_count=session.question_count,
        messages=messages_read,
        analysis=analysis_read,
        alerts=alerts_read,
    )


@router.post("/{id}/events", response_model=TaskEventRead, status_code=status.HTTP_201_CREATED)
def log_task_event(id: int, payload: TaskEventCreate, db: DBSession = Depends(get_db)):
    """
    Log a task lifecycle event (e.g. reaction_time test started or ended) from host page or server.
    Stores event in task_events table and associates with session.
    """
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    info_dict = payload.info if payload.info is not None else {}
    ts_val = payload.ts or utc_now()

    event = TaskEvent(
        session_id=session.id,
        task=payload.task,
        phase=payload.phase,
        ts=ts_val,
        info_json=json.dumps(info_dict),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return TaskEventRead(
        id=event.id,
        session_id=event.session_id,
        task=event.task,
        phase=event.phase,
        ts=event.ts,
        info=event.info,
    )


@router.get("/{id}/events", response_model=List[TaskEventRead])
def get_session_events(id: int, db: DBSession = Depends(get_db)):
    """Retrieve all task events recorded during this session."""
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    events = db.query(TaskEvent).filter(TaskEvent.session_id == id).order_by(TaskEvent.ts.asc()).all()
    return [
        TaskEventRead(
            id=e.id,
            session_id=e.session_id,
            task=e.task,
            phase=e.phase,
            ts=e.ts,
            info=e.info,
        )
        for e in events
    ]


@router.get("/{id}/pending", response_model=PendingQuestionResponse)
def get_pending_question(id: int, deliver: bool = True, db: DBSession = Depends(get_db)):
    """
    Poll for queued questions held while a timed task was running.
    When deliver=True, commits the queued question as an assistant message and advances question count.
    """
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    if not session.pending_question:
        return PendingQuestionResponse(
            session_id=session.id,
            has_pending=False,
            pending=False,
            question=None,
            question_index=None,
        )

    q_text = session.pending_question
    q_index = session.pending_question_index or (session.question_count + 1)

    if deliver:
        last_event = (
            db.query(TaskEvent)
            .filter(TaskEvent.session_id == id)
            .order_by(TaskEvent.ts.desc())
            .first()
        )
        delivered_text = q_text
        if last_event and last_event.phase == "ended":
            task_name = last_event.task
            lang = session.astronaut.language if session.astronaut else "en"
            if lang == "ar":
                delivered_text = f"أحسنت بإتمام {task_name}. لنواصل فحصنا اليومي: {q_text}"
            else:
                delivered_text = f"Glad you completed the {task_name}. Returning to our check-in: {q_text}"

        asst_msg = Message(
            session_id=session.id,
            role="assistant",
            content=delivered_text,
            mode=session.mode,
            created_at=utc_now(),
        )
        db.add(asst_msg)
        session.question_count = q_index
        session.pending_question = None
        session.pending_question_index = None
        db.commit()

        return PendingQuestionResponse(
            session_id=session.id,
            has_pending=True,
            pending=True,
            question=delivered_text,
            question_index=q_index,
        )

    return PendingQuestionResponse(
        session_id=session.id,
        has_pending=True,
        pending=True,
        question=q_text,
        question_index=q_index,
    )


@router.post("/{id}/signals", response_model=SignalsRead, status_code=status.HTTP_201_CREATED)
def log_signals(id: int, payload: SignalsCreate, db: DBSession = Depends(get_db)):
    """
    Log acoustic, facial, or physiological telemetry from the teammate's camera/mic module.
    """
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    signals_data = payload.signals if payload.signals is not None else (payload.recent or {})
    signal_record = SessionSignal(
        session_id=session.id,
        signals_json=json.dumps(signals_data),
        ts=utc_now(),
    )
    db.add(signal_record)
    db.commit()
    db.refresh(signal_record)

    return SignalsRead(
        id=signal_record.id,
        session_id=signal_record.session_id,
        signals=signal_record.signals,
        ts=signal_record.ts,
    )


@router.get("/{id}/signals", response_model=List[SignalsRead])
def get_session_signals(id: int, db: DBSession = Depends(get_db)):
    """Retrieve telemetry signals logged for this session."""
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {id} not found."
        )

    signals = (
        db.query(SessionSignal)
        .filter(SessionSignal.session_id == id)
        .order_by(SessionSignal.ts.desc())
        .limit(50)
        .all()
    )
    return [
        SignalsRead(
            id=s.id,
            session_id=s.session_id,
            signals=s.signals,
            ts=s.ts,
        )
        for s in signals
    ]


@router.post("/{id}/fuse", response_model=FusionResultRead)
def run_session_fusion(id: int, db: DBSession = Depends(get_db)):
    """
    Execute multimodal fusion for the session.
    Combines conversational rating (analyzer), acoustic affect, facial markers, and physiological metrics.
    Computes per-astronaut z-score baseline deviation and flags channel conflicts.
    """
    try:
        fusion_record = fuse_session(db, id)
        return FusionResultRead(
            id=fusion_record.id,
            session_id=fusion_record.session_id,
            astronaut_id=fusion_record.astronaut_id,
            fused_scores=fusion_record.fused_scores,
            composite_score=fusion_record.composite_score,
            z_scores=fusion_record.z_scores,
            channel_conflict=fusion_record.channel_conflict,
            conflict_notes=fusion_record.conflict_notes,
            baseline_confidence=fusion_record.baseline_confidence,
            alert_triggered=fusion_record.alert_triggered,
            created_at=fusion_record.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Fusion error for session {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multimodal fusion calculation failed: {str(e)}"
        )


@router.get("/{id}/fusion", response_model=FusionResultRead)
def get_session_fusion(id: int, db: DBSession = Depends(get_db)):
    """Retrieve existing multimodal fusion results for this session."""
    session = db.query(Session).filter(Session.id == id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session with id {id} not found.")

    fusion_record = db.query(FusionResult).filter(FusionResult.session_id == id).first()
    if not fusion_record:
        # Run fusion on-the-fly if analysis exists
        if session.analysis or session.signals:
            fusion_record = fuse_session(db, id)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No fusion result found for session {id}. Run POST /sessions/{id}/fuse first."
            )

    return FusionResultRead(
        id=fusion_record.id,
        session_id=fusion_record.session_id,
        astronaut_id=fusion_record.astronaut_id,
        fused_scores=fusion_record.fused_scores,
        composite_score=fusion_record.composite_score,
        z_scores=fusion_record.z_scores,
        channel_conflict=fusion_record.channel_conflict,
        conflict_notes=fusion_record.conflict_notes,
        baseline_confidence=fusion_record.baseline_confidence,
        alert_triggered=fusion_record.alert_triggered,
        created_at=fusion_record.created_at,
    )
