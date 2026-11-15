import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import Session, Message, Alert, TaskEvent, utc_now
from app.schemas import ChatRequest, ChatResponse
from app.safety import detect_safety_keywords, get_crisis_support_message
from app.services.llm_service import (
    generate_interview_reply,
    generate_companion_reply,
    MOCK_INTERVIEW_QUESTIONS_EN,
    MOCK_INTERVIEW_QUESTIONS_AR,
)
from app.services.session_service import get_past_sessions_summary, get_session_transcript_text
from app.services.kb_service import log_kb_usage
from app.config import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def handle_chat(payload: ChatRequest, db: DBSession = Depends(get_db)):
    """
    Handle conversation turns in either 'session' (daily check-in) or 'companion' mode.
    Task-aware capabilities:
    - Accepts context: {task, phase, current_tab, note, signals_summary}.
    - While a timed task is running (phase 'started'), answers in one short sentence, does not advance questions,
      and queues the next question for delivery when phase 'ended' arrives.
    - After task ends, gently refers to the task when resuming questions.
    - Signals summary is strictly confidential private context; never quoted as raw scores.
    - Dual-layer crisis safety safeguards ([ESCALATE] + keywords) remain active at all times, including during tasks.
    """
    session = db.query(Session).filter(Session.id == payload.session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id {payload.session_id} not found."
        )

    astronaut = session.astronaut
    if not astronaut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Astronaut record associated with session not found."
        )

    # Extract normalized context
    context = payload.get_normalized_context()

    # Log task event in task_events table if task and phase are provided
    if context.get("task") and context.get("phase"):
        task_name = context["task"]
        phase_name = context["phase"]
        info_dict = {k: v for k, v in context.items() if k not in ["task", "phase"]}
        task_evt = TaskEvent(
            session_id=session.id,
            task=task_name,
            phase=phase_name,
            ts=utc_now(),
            info_json=json.dumps(info_dict),
        )
        db.add(task_evt)
        db.flush()

    # If session is closed and not in companion mode, require companion transition or new session
    if session.status == "completed" and session.mode == "session":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This check-in session is completed. Please switch to companion mode via POST /sessions/{id}/companion or start a new session."
        )

    user_text = payload.message.strip()

    # 1. First-layer Safety Check on User Message (ACTIVE AT ALL TIMES INCLUDING DURING TASKS)
    safety_hit, matched_kw = detect_safety_keywords(user_text)
    if safety_hit:
        logger.critical(f"Safety crisis detected in session {session.id}! Keyword: '{matched_kw}'")
        # Record user message
        user_msg = Message(
            session_id=session.id,
            role="user",
            content=user_text,
            mode=session.mode,
            created_at=utc_now(),
        )
        db.add(user_msg)

        # Trigger real-time alert with source="keyword"
        alert = Alert(
            session_id=session.id,
            reason=f"Emergency safety keyword detected in user message: '{matched_kw}'",
            source="keyword",
            handled=False,
            created_at=utc_now(),
        )
        db.add(alert)

        # Crisis support reply
        crisis_reply = get_crisis_support_message(astronaut.language)
        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content=crisis_reply,
            mode=session.mode,
            created_at=utc_now(),
        )
        db.add(assistant_msg)
        db.commit()

        return ChatResponse(
            reply=crisis_reply,
            mode=session.mode,
            escalate=True,
            session_should_end=True,
            should_end=True,
        )

    # 2. Record standard user message
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=user_text,
        mode=session.mode,
        created_at=utc_now(),
    )
    db.add(user_msg)
    db.flush()

    escalate_flag = False
    task_phase = context.get("phase")
    task_name = context.get("task", "task")

    # 3. Branch by Mode
    if session.mode == "session":
        # Count how many questions assistant has already asked in this check-in session
        assistant_q_count = (
            db.query(Message)
            .filter(
                Message.session_id == session.id,
                Message.role == "assistant",
                Message.mode == "session",
            )
            .count()
        )

        # Handle task running: phase == 'started'
        if task_phase == "started":
            # Bot answers in one short sentence acknowledging the astronaut and pausing check-in
            reply_text, token_escalate, should_end = generate_interview_reply(
                astronaut_name=astronaut.name,
                language=astronaut.language,
                history=[],
                current_question_count=assistant_q_count,
                user_message=user_text,
                context=context,
            )

            # Queue next question if not already queued
            if not session.pending_question and assistant_q_count < 7:
                q_idx = min(assistant_q_count, 6)
                queued_q = (
                    MOCK_INTERVIEW_QUESTIONS_AR[q_idx]
                    if astronaut.language == "ar"
                    else MOCK_INTERVIEW_QUESTIONS_EN[q_idx]
                )
                session.pending_question = queued_q
                session.pending_question_index = assistant_q_count + 1

            assistant_msg = Message(
                session_id=session.id,
                role="assistant",
                content=reply_text,
                mode="session",
                created_at=utc_now(),
            )
            db.add(assistant_msg)
            db.commit()

            return ChatResponse(
                reply=reply_text,
                mode="session",
                escalate=False,
                session_should_end=False,
                should_end=False,
                pending_question=session.pending_question,
                task_active=True,
            )

        # Handle task ended: phase == 'ended'
        if task_phase == "ended" and session.pending_question:
            # Release pending question with gentle reference to completed task
            base_q = session.pending_question
            session.pending_question = None
            session.pending_question_index = None

            if astronaut.language == "ar":
                reply_text = f"أحسنت بإتمام {task_name}. لنواصل فحصنا اليومي: {base_q}"
            else:
                reply_text = f"Glad you completed the {task_name}. Returning to our check-in: {base_q}"

            assistant_msg = Message(
                session_id=session.id,
                role="assistant",
                content=reply_text,
                mode="session",
                created_at=utc_now(),
            )
            db.add(assistant_msg)
            session.question_count = assistant_q_count + 1
            db.commit()

            return ChatResponse(
                reply=reply_text,
                mode="session",
                escalate=False,
                session_should_end=False,
                should_end=False,
                task_active=False,
            )

        # Standard Interview turn
        session_messages = (
            db.query(Message)
            .filter(Message.session_id == session.id, Message.mode == "session")
            .order_by(Message.created_at.asc())
            .all()
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in session_messages[:-1]  # exclude newly added user message
        ]

        reply_text, token_escalate, should_end = generate_interview_reply(
            astronaut_name=astronaut.name,
            language=astronaut.language,
            history=history,
            current_question_count=assistant_q_count,
            user_message=user_text,
            context=context,
        )

        if token_escalate:
            escalate_flag = True
            alert = Alert(
                session_id=session.id,
                reason="Interviewer LLM generated [ESCALATE] token",
                source="chat",
                handled=False,
                created_at=utc_now(),
            )
            db.add(alert)
            logger.warning(f"[ESCALATE] token triggered alert in session {session.id}")

        if not should_end:
            session.question_count = assistant_q_count + 1

        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content=reply_text,
            mode="session",
            created_at=utc_now(),
        )
        db.add(assistant_msg)
        db.commit()

        return ChatResponse(
            reply=reply_text,
            mode="session",
            escalate=escalate_flag,
            session_should_end=should_end,
            should_end=should_end,
            task_active=False,
        )

    else:
        # Companion Mode
        transcript = get_session_transcript_text(db, session.id)
        analysis_dict = {
            "scores": session.analysis.scores if session.analysis else {},
            "notes": session.analysis.notes if session.analysis else "",
            "risk_flag": session.analysis.risk_flag if session.analysis else False,
        }
        past_sessions_summary = get_past_sessions_summary(db, astronaut.id, session.id)

        companion_msgs = (
            db.query(Message)
            .filter(Message.session_id == session.id, Message.mode == "companion")
            .order_by(Message.created_at.asc())
            .all()
        )
        companion_history = [
            {"role": m.role, "content": m.content}
            for m in companion_msgs[:-1]
        ]

        reply_text, token_escalate, used_chunk_ids = generate_companion_reply(
            db=db,
            session_id=session.id,
            astronaut_name=astronaut.name,
            language=astronaut.language,
            transcript=transcript,
            analysis_dict=analysis_dict,
            past_sessions_summary=past_sessions_summary,
            companion_messages=companion_history,
            user_message=user_text,
            context=context,
        )

        if token_escalate:
            escalate_flag = True
            alert = Alert(
                session_id=session.id,
                reason="Companion LLM generated [ESCALATE] token",
                source="chat",
                handled=False,
                created_at=utc_now(),
            )
            db.add(alert)
            logger.warning(f"[ESCALATE] token triggered alert in companion session {session.id}")

        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content=reply_text,
            mode="companion",
            created_at=utc_now(),
        )
        db.add(assistant_msg)
        db.flush()

        if used_chunk_ids:
            log_kb_usage(db, assistant_msg.id, used_chunk_ids)

        db.commit()

        return ChatResponse(
            reply=reply_text,
            mode="companion",
            escalate=escalate_flag,
            session_should_end=False,
            should_end=False,
            task_active=(task_phase == "started"),
        )
