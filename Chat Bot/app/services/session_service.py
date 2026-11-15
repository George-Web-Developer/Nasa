from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from app.models import Session, Astronaut, Message, Analysis, TaskEvent, utc_now


def get_past_sessions_summary(db: DBSession, astronaut_id: int, current_session_id: int) -> str:
    """
    Fetch up to 3 previous completed sessions for this astronaut and format a brief summary
    to provide longitudinal context for the companion prompt.
    """
    past_sessions = (
        db.query(Session)
        .filter(
            Session.astronaut_id == astronaut_id,
            Session.id != current_session_id,
            Session.status == "completed",
        )
        .order_by(Session.created_at.desc())
        .limit(3)
        .all()
    )

    if not past_sessions:
        return "No prior completed sessions recorded for this astronaut. This is an early mission check-in."

    summaries = []
    for s in past_sessions:
        created_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else "N/A"
        if s.analysis:
            scores_dict = s.analysis.scores
            scores_str = ", ".join([f"{k}: {v}/10" for k, v in scores_dict.items() if v is not None]) or "No scores"
            notes = s.analysis.notes
            summaries.append(
                f"- Mission Day {s.mission_day} ({created_str}): Scores ({scores_str}). Assessment: {notes}"
            )
        else:
            summaries.append(f"- Mission Day {s.mission_day} ({created_str}): Session completed (no formal analysis).")

    return "\n".join(summaries)


def get_session_transcript_text(
    db: DBSession,
    session_id: int,
    mode_filter: Optional[str] = "session",
    include_task_events: bool = True,
) -> str:
    """
    Get formatted transcript of messages and task events for analyzer or companion context.
    Interleaves task events chronologically so the analyzer knows when each task happened.
    """
    q = db.query(Message).filter(Message.session_id == session_id)
    if mode_filter:
        q = q.filter(Message.mode == mode_filter)
    messages = q.order_by(Message.created_at.asc()).all()

    items = []
    for m in messages:
        items.append({
            "type": "message",
            "ts": m.created_at,
            "role": m.role,
            "content": m.content,
        })

    if include_task_events:
        task_events = (
            db.query(TaskEvent)
            .filter(TaskEvent.session_id == session_id)
            .order_by(TaskEvent.ts.asc())
            .all()
        )
        for t in task_events:
            items.append({
                "type": "task_event",
                "ts": t.ts,
                "task": t.task,
                "phase": t.phase,
                "info": t.info,
            })

    # Sort all items chronologically
    items.sort(key=lambda x: x["ts"] or utc_now())

    lines = []
    for item in items:
        if item["type"] == "message":
            sender = "Astronaut" if item["role"] == "user" else "Assistant"
            lines.append(f"{sender}: {item['content']}")
        elif item["type"] == "task_event":
            ts_str = item["ts"].strftime("%H:%M:%S") if item["ts"] else "N/A"
            info_str = f" details={item['info']}" if item["info"] else ""
            lines.append(f"[Task Event: '{item['task']}' phase={item['phase']} at {ts_str}{info_str}]")

    return "\n".join(lines)


def get_relevant_severity(analysis_scores: Dict[str, Any], topic: Optional[str] = None) -> float:
    """
    Calculate relevant severity score from analysis scores.
    If topic maps to a specific dimension, prioritize that dimension score;
    otherwise use the maximum score across all evaluated dimensions.
    """
    if not analysis_scores:
        return 2.0  # nominal default baseline

    topic_dim_map = {
        "sleep": "fatigue",
        "fatigue": "fatigue",
        "stress": "stress",
        "anxiety": "anxiety",
        "isolation": "social_isolation",
        "mood": "low_mood",
        "focus": "concentration_difficulty",
        "escalation": "stress",
    }

    if topic and topic.lower() in topic_dim_map:
        target_dim = topic_dim_map[topic.lower()]
        val = analysis_scores.get(target_dim)
        if isinstance(val, (int, float)):
            return float(val)

    numeric_scores = [v for v in analysis_scores.values() if isinstance(v, (int, float))]
    return float(max(numeric_scores)) if numeric_scores else 2.0
