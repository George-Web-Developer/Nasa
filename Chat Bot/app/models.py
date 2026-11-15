import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-naive for SQLite compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# =====================================================================
# GROUP A: PEOPLE
# =====================================================================

class Astronaut(Base):
    __tablename__ = "astro_astronauts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    language = Column(String(10), default="en", nullable=False)  # "en" or "ar"
    role = Column(String(80), default="Mission Specialist", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    external_user_id = Column(String(120), nullable=True, index=True)  # Mapped to teammate's user table
    consent_flag = Column(Boolean, default=True, nullable=False)
    is_simulated = Column(Boolean, default=True, nullable=False)

    sessions = relationship("Session", back_populates="astronaut", cascade="all, delete-orphan")
    baselines = relationship("Baseline", back_populates="astronaut", cascade="all, delete-orphan")
    fusion_results = relationship("FusionResult", back_populates="astronaut", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Astronaut(id={self.id}, name='{self.name}', role='{self.role}', lang='{self.language}')>"


# =====================================================================
# GROUP B: RESULTS
# =====================================================================

class Session(Base):
    __tablename__ = "astro_sessions"

    id = Column(Integer, primary_key=True, index=True)
    astronaut_id = Column(Integer, ForeignKey("astro_astronauts.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    mission_day = Column(Integer, nullable=False)
    mode = Column(String(20), default="session", nullable=False)  # "session" | "companion"
    status = Column(String(20), default="active", nullable=False)  # "active" | "completed"
    question_count = Column(Integer, default=0, nullable=False)
    pending_question = Column(Text, nullable=True)
    pending_question_index = Column(Integer, nullable=True)

    astronaut = relationship("Astronaut", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    analysis = relationship("Analysis", back_populates="session", uselist=False, cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="session", cascade="all, delete-orphan", order_by="Alert.created_at.desc()")
    task_events = relationship("TaskEvent", back_populates="session", cascade="all, delete-orphan", order_by="TaskEvent.ts.asc()")
    signals = relationship("Signal", back_populates="session", cascade="all, delete-orphan", order_by="Signal.ts.asc()")
    fusion_result = relationship("FusionResult", back_populates="session", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, astronaut_id={self.astronaut_id}, mode='{self.mode}', status='{self.status}')>"


class Message(Base):
    __tablename__ = "astro_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("astro_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    mode = Column(String(20), default="session", nullable=False)  # "session" | "companion"
    created_at = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("Session", back_populates="messages")
    kb_usages = relationship("KBUsage", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, session_id={self.session_id}, role='{self.role}', mode='{self.mode}')>"


class TaskEvent(Base):
    __tablename__ = "astro_task_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("astro_sessions.id"), nullable=False, index=True)
    task = Column(String(100), nullable=False)
    phase = Column(String(50), nullable=False)  # "started" | "ended"
    ts = Column(DateTime, default=utc_now, nullable=False)
    info_json = Column(Text, nullable=True, default="{}")

    session = relationship("Session", back_populates="task_events")

    @property
    def info(self) -> Dict[str, Any]:
        try:
            return json.loads(self.info_json) if self.info_json else {}
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<TaskEvent(id={self.id}, session_id={self.session_id}, task='{self.task}', phase='{self.phase}')>"


class Signal(Base):
    """
    Stores non-invasive affect & physiological features from teammate camera/mic/sensor modules.
    NEVER stores raw audio or video files - strictly numerical features and action units.
    """
    __tablename__ = "astro_signals"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("astro_sessions.id"), nullable=False, index=True)
    channel = Column(String(50), default="multimodal", nullable=False)  # acoustic, facial, physiological, multimodal
    signals_json = Column(Text, nullable=False, default="{}")
    quality = Column(Float, default=1.0, nullable=False)  # Quality / confidence score 0.0 - 1.0
    ts = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("Session", back_populates="signals")

    @property
    def signals(self) -> Dict[str, Any]:
        try:
            return json.loads(self.signals_json) if self.signals_json else {}
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<Signal(id={self.id}, session_id={self.session_id}, channel='{self.channel}', quality={self.quality})>"


# Backwards-compatible alias for Signal
SessionSignal = Signal


class Analysis(Base):
    __tablename__ = "astro_analyses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("astro_sessions.id"), unique=True, nullable=False, index=True)
    scores_json = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=False)
    screening_answers_json = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    risk_flag = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("Session", back_populates="analysis")

    @property
    def scores(self) -> Dict[str, Any]:
        try:
            return json.loads(self.scores_json)
        except Exception:
            return {}

    @property
    def evidence(self) -> Dict[str, Any]:
        try:
            return json.loads(self.evidence_json)
        except Exception:
            return {}

    @property
    def screening_answers(self) -> Dict[str, Any]:
        try:
            return json.loads(self.screening_answers_json)
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<Analysis(id={self.id}, session_id={self.session_id}, risk_flag={self.risk_flag})>"


class FusionResult(Base):
    """
    Multimodal fusion integrating conversational rating, acoustic affect, facial markers,
    and physiological telemetry with dynamic z-score baseline calibration.
    """
    __tablename__ = "astro_fusion_results"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("astro_sessions.id"), unique=True, nullable=False, index=True)
    astronaut_id = Column(Integer, ForeignKey("astro_astronauts.id"), nullable=False, index=True)
    fused_scores_json = Column(Text, nullable=False)  # JSON dict of fused dimension scores (0-10)
    composite_score = Column(Float, nullable=False)  # Weighted composite strain score (0.0-10.0)
    z_scores_json = Column(Text, nullable=False)  # JSON dict of z-scores vs baseline
    channel_conflict = Column(Boolean, default=False, nullable=False)  # True if discrepancy between channels
    conflict_notes = Column(Text, nullable=True)
    baseline_confidence = Column(String(20), default="low", nullable=False)  # "low" (<5 sessions) or "high" (>=5)
    alert_triggered = Column(Boolean, default=False, nullable=False)  # Persistent deviation alert flag
    created_at = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("Session", back_populates="fusion_result")
    astronaut = relationship("Astronaut", back_populates="fusion_results")

    @property
    def fused_scores(self) -> Dict[str, Any]:
        try:
            return json.loads(self.fused_scores_json)
        except Exception:
            return {}

    @property
    def z_scores(self) -> Dict[str, Any]:
        try:
            return json.loads(self.z_scores_json)
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<FusionResult(id={self.id}, session_id={self.session_id}, composite={self.composite_score:.2f}, conflict={self.channel_conflict})>"


class Baseline(Base):
    __tablename__ = "astro_baselines"

    id = Column(Integer, primary_key=True, index=True)
    astronaut_id = Column(Integer, ForeignKey("astro_astronauts.id"), nullable=False, index=True)
    dimension = Column(String(50), nullable=False)  # stress, low_mood, anxiety, fatigue, etc.
    mean = Column(Float, nullable=False, default=0.0)
    std = Column(Float, nullable=False, default=1.0)
    n = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=utc_now, nullable=False)

    astronaut = relationship("Astronaut", back_populates="baselines")

    __table_args__ = (
        UniqueConstraint("astronaut_id", "dimension", name="uq_astro_astronaut_dimension"),
    )

    def __repr__(self) -> str:
        return f"<Baseline(astronaut_id={self.astronaut_id}, dim='{self.dimension}', mean={self.mean:.2f}, n={self.n})>"


class Alert(Base):
    __tablename__ = "astro_alerts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("astro_sessions.id"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)  # "chat" | "analysis" | "keyword" | "fusion"
    handled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    session = relationship("Session", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, session_id={self.session_id}, source='{self.source}', handled={self.handled})>"


# =====================================================================
# GROUP C: KNOWLEDGE
# =====================================================================

class KBChunk(Base):
    __tablename__ = "astro_kb_chunks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    topic = Column(String(50), nullable=False, index=True)
    severity_min = Column(Float, default=0.0, nullable=False)
    severity_max = Column(Float, default=10.0, nullable=False)
    content = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(String(512), nullable=False)
    language = Column(String(10), default="en", nullable=False)  # "en" or "ar"
    last_reviewed = Column(DateTime, default=utc_now, nullable=False)
    approved = Column(Boolean, default=False, nullable=False, index=True)

    kb_usages = relationship("KBUsage", back_populates="chunk", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<KBChunk(id={self.id}, topic='{self.topic}', title='{self.title[:30]}', approved={self.approved})>"


class KBUsage(Base):
    __tablename__ = "astro_kb_usage"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("astro_messages.id"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("astro_kb_chunks.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    message = relationship("Message", back_populates="kb_usages")
    chunk = relationship("KBChunk", back_populates="kb_usages")

    def __repr__(self) -> str:
        return f"<KBUsage(message_id={self.message_id}, chunk_id={self.chunk_id})>"
