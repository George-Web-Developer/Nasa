from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


# =====================================================================
# ANALYZER OUTPUT SCHEMAS
# =====================================================================

class DimensionScores(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stress: Optional[int] = Field(None, ge=0, le=10, description="Stress level 0 (none) - 10 (severe)")
    low_mood: Optional[int] = Field(None, ge=0, le=10, description="Depressed or low mood 0-10")
    anxiety: Optional[int] = Field(None, ge=0, le=10, description="Anxiety / worry / panic 0-10")
    fatigue: Optional[int] = Field(None, ge=0, le=10, description="Fatigue / sleep disruption 0-10")
    social_isolation: Optional[int] = Field(None, ge=0, le=10, description="Sense of isolation / friction 0-10")
    concentration_difficulty: Optional[int] = Field(None, ge=0, le=10, description="Cognitive difficulty 0-10")


class DimensionEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stress: Optional[str] = Field(None, description="Short direct quote from transcript")
    low_mood: Optional[str] = Field(None, description="Short direct quote from transcript")
    anxiety: Optional[str] = Field(None, description="Short direct quote from transcript")
    fatigue: Optional[str] = Field(None, description="Short direct quote from transcript")
    social_isolation: Optional[str] = Field(None, description="Short direct quote from transcript")
    concentration_difficulty: Optional[str] = Field(None, description="Short direct quote from transcript")


class AnalyzerOutput(BaseModel):
    """Strict schema required from the LLM psychological analyzer."""
    model_config = ConfigDict(extra="ignore")

    scores: DimensionScores
    evidence: DimensionEvidence
    screening_answers: Dict[str, Optional[int]] = Field(
        default_factory=dict,
        description="Screening items answered on 0-3 scale, e.g. {'sleep_quality': 2, 'mood_drop': 1}"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in assessment 0.0-1.0")
    risk_flag: bool = Field(False, description="True if self-harm, severe crisis, or extreme scores present")
    notes: str = Field(..., description="One sentence summary explanation of assessment")


# =====================================================================
# API REQUEST & RESPONSE SCHEMAS
# =====================================================================

class SessionStartRequest(BaseModel):
    astronaut_id: int = Field(..., description="ID of the astronaut")
    mission_day: int = Field(..., ge=1, description="Current mission day (e.g. 42)")
    mode: Optional[str] = Field("session", description="Initial session mode: 'session' or 'companion'")


class SessionStartResponse(BaseModel):
    session_id: int
    first_message: str
    mode: str = "session"


class ChatContext(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task: Optional[str] = None
    phase: Optional[str] = None  # "started" | "ended"
    current_tab: Optional[str] = None
    note: Optional[str] = None
    signals_summary: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: int = Field(..., description="Active session ID")
    message: str = Field(..., min_length=1, description="Message from the astronaut")
    context: Optional[ChatContext] = None
    task: Optional[str] = None
    phase: Optional[str] = None
    current_tab: Optional[str] = None
    note: Optional[str] = None
    signals_summary: Optional[Dict[str, Any]] = None

    def get_normalized_context(self) -> Dict[str, Any]:
        ctx = self.context.model_dump() if self.context else {}
        if self.task and not ctx.get("task"):
            ctx["task"] = self.task
        if self.phase and not ctx.get("phase"):
            ctx["phase"] = self.phase
        if self.current_tab and not ctx.get("current_tab"):
            ctx["current_tab"] = self.current_tab
        if self.note and not ctx.get("note"):
            ctx["note"] = self.note
        if self.signals_summary and not ctx.get("signals_summary"):
            ctx["signals_summary"] = self.signals_summary
        return {k: v for k, v in ctx.items() if v is not None}


class ChatResponse(BaseModel):
    reply: str
    mode: str
    escalate: bool
    session_should_end: bool = Field(
        False,
        description="True when max interview turns reached; frontend should notify astronaut or trigger /end"
    )
    should_end: bool = Field(
        False,
        description="Backward-compatible alias for session_should_end"
    )
    pending_question: Optional[str] = None
    task_active: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def sync_should_end_flags(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Keep session_should_end and should_end synced
            if "session_should_end" in data and "should_end" not in data:
                data["should_end"] = data["session_should_end"]
            elif "should_end" in data and "session_should_end" not in data:
                data["session_should_end"] = data["should_end"]
        return data


class CompanionStartResponse(BaseModel):
    session_id: int
    mode: str
    opening_message: str


class MessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    mode: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisRead(BaseModel):
    id: int
    session_id: int
    scores: Dict[str, Optional[int]]
    evidence: Dict[str, Optional[str]]
    screening_answers: Dict[str, Optional[int]]
    confidence: float
    risk_flag: bool
    notes: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertRead(BaseModel):
    id: int
    session_id: int
    reason: str
    source: str
    handled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(BaseModel):
    id: int
    astronaut_id: int
    astronaut_name: Optional[str] = None
    astronaut_language: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    mission_day: int
    mode: str
    status: str
    question_count: int = 0
    messages: List[MessageRead]
    analysis: Optional[AnalysisRead] = None
    alerts: List[AlertRead] = []

    model_config = ConfigDict(from_attributes=True)


class SessionHistoryItem(BaseModel):
    session_id: int
    created_at: datetime
    ended_at: Optional[datetime] = None
    mission_day: int
    status: str
    mode: str
    scores: Optional[Dict[str, Optional[int]]] = None
    risk_flag: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class AlertHandleResponse(BaseModel):
    id: int
    session_id: int
    reason: str
    source: str
    handled: bool
    message: str


class KBChunkRead(BaseModel):
    id: int
    title: str
    topic: str
    severity_min: float
    severity_max: float
    content: str
    source_name: str
    source_url: str
    language: str

    model_config = ConfigDict(from_attributes=True)


class BaselineRead(BaseModel):
    astronaut_id: int
    dimension: str
    mean: float
    std: float
    n: int

    model_config = ConfigDict(from_attributes=True)


class TaskEventCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task: str = Field(..., description="Name/ID of the task (e.g. reaction_time, memory_test)")
    phase: str = Field(..., description="'started' | 'ended'")
    info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional extra details/scores")
    ts: Optional[datetime] = None


class TaskEventRead(BaseModel):
    id: int
    session_id: int
    task: str
    phase: str
    ts: datetime
    info: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class SignalsCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    signals: Optional[Dict[str, Any]] = None
    recent: Optional[Dict[str, Any]] = None


class SignalsRead(BaseModel):
    id: int
    session_id: int
    signals: Dict[str, Any]
    ts: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingQuestionResponse(BaseModel):
    session_id: int
    has_pending: bool
    pending: bool
    question: Optional[str] = None
    question_index: Optional[int] = None


class FusionResultRead(BaseModel):
    id: int
    session_id: int
    astronaut_id: int
    fused_scores: Dict[str, float]
    composite_score: float
    z_scores: Dict[str, float]
    channel_conflict: bool
    conflict_notes: Optional[str] = None
    baseline_confidence: str
    alert_triggered: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LatestFusedScoreItem(BaseModel):
    astronaut_id: int
    astronaut_name: str
    session_id: int
    mission_day: int
    composite_score: float
    fused_scores: Dict[str, float]
    z_scores: Dict[str, float]
    channel_conflict: bool
    baseline_confidence: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBUsageRead(BaseModel):
    id: int
    message_id: int
    chunk_id: int
    chunk_title: Optional[str] = None
    chunk_topic: Optional[str] = None
    source_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AstronautRead(BaseModel):
    id: int
    name: str
    language: str
    role: str
    created_at: datetime
    external_user_id: Optional[str] = None
    consent_flag: bool
    is_simulated: bool

    model_config = ConfigDict(from_attributes=True)
