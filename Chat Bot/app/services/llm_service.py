import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session as DBSession

import app.config as config
from app.config import logger
from app.prompts import (
    INTERVIEWER_PROMPT,
    ANALYZER_PROMPT,
    COMPANION_PROMPT,
    get_interviewer_system_prompt,
    get_companion_system_prompt,
)
from app.safety import (
    detect_safety_keywords,
    parse_and_strip_escalate_token,
    get_crisis_support_message,
    ESCALATE_TOKEN,
)
from app.services.kb_service import (
    KB_TOOL_DEFINITION,
    search_knowledge_base,
    log_kb_usage,
)
from app.services.session_service import get_relevant_severity
from app.models import Alert
from app.services.llm_client import (
    call_llm,
    call_llm_text,
    inject_knowledge_into_prompt,
    LLMResponse,
    ToolCall,
)


def is_mock_active() -> bool:
    """Return True if mock mode is explicitly requested or no API key is configured."""
    if getattr(config, "MOCK_LLM", True):
        return True
    api_key = getattr(config, "LLM_API_KEY", "") or getattr(config, "ANTHROPIC_API_KEY", "")
    provider = getattr(config, "LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic" and not api_key:
        return True
    if provider == "openai_compatible" and not api_key:
        base_url = getattr(config, "LLM_BASE_URL", "")
        if "localhost" not in base_url and "127.0.0.1" not in base_url:
            return True
    return False


# =====================================================================
# MOCK LLM SCRIPTS (English & Arabic)
# =====================================================================

MOCK_INTERVIEW_QUESTIONS_EN = [
    "Welcome to today's check-in, Commander. How did you sleep during your rest cycle last night?",
    "Thank you for sharing that. On a 0 to 3 scale (0 being not at all, 3 being nearly all day), how often have you felt down or low in energy today?",
    "Understood. How are you feeling about your workload and the docking and maintenance tasks scheduled for today?",
    "Got it. Over the last 24 hours, on a 0 to 3 scale, how much have you felt nervous, anxious, or on edge?",
    "Thanks for that rating. How have your interactions with your fellow crewmates and your comms with family back on Earth been feeling?",
    "Good to know. Have you noticed any mental fatigue or trouble maintaining sharp focus during your system checklists?",
    "To round out our check-in, what is one moment or achievement today that gave you a sense of calm or satisfaction?",
]

MOCK_CLOSING_MESSAGE_EN = (
    "Thank you for sharing with me today, Commander. It sounds like you're carrying a demanding workload "
    "with steady focus despite some broken sleep, and your crew communication is solid. "
    "One small suggestion: take 5 minutes for guided box-breathing in the cupola before lights out tonight. "
    "That concludes our daily check-in session!"
)

MOCK_INTERVIEW_QUESTIONS_AR = [
    "مرحباً بك يا قائد في جلسة المتابعة اليومية. كيف كانت جودة نومك خلال دورة الراحة الماضية؟",
    "شكراً لمشاركتك. على مقياس من 0 إلى 3 (حيث 0 لا يوجد إطلاقاً و3 طوال اليوم تقريباً)، كم مرة شعرت بانخفاض الطاقة أو تدني المزاج اليوم؟",
    "مفهوم تماماً. كيف تشعر حيال جدول الصيانة وأعباء العمل المقررة لليوم؟ هل شعرت بأي لحظات من التوتر؟",
    "فهمت ذلك. خلال الـ 24 ساعة الماضية، على مقياس من 0 إلى 3، إلى أي مدى شعرت بالقلق أو التحفز العصبي؟",
    "شكراً لتقييمك. كيف تجد تواصلك اليومي مع زملائك في الطاقم واتصالاتك بعائلتك على الأرض؟",
    "أمر مطمئن. هل لاحظت أي تشتت أو صعوبة في الحفاظ على التركيز أثناء تنفيذ قوائم الفحص الفنية؟",
    "ختاماً، ما هو الشيء أو اللحظة التي منحتك شعوراً بالرضا والهدوء خلال يوم المهمة هذا؟",
]

MOCK_CLOSING_MESSAGE_AR = (
    "شكراً جزيلاً لصراحتك ومشاركتك اليوم يا قائد. يبدو أنك تدير مهامك بدقة وثبات بالرغم من قلة النوم وضغط العمل، "
    "وروح الفريق لديك ممتازة. اقتراح بسيط: خصص 5 دقائق لتنفس هادئ وعميق قبل موعد نومك الليلة. "
    "لقد أنهينا جلستنا اليومية بنجاح!"
)


# =====================================================================
# API CALLING HELPER (BACKWARDS COMPATIBILITY)
# =====================================================================

def call_anthropic_api(
    system_prompt: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1000,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Any:
    """Execute call via configured LLM provider (Anthropic or OpenAI-compatible)."""
    return call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
    )


# =====================================================================
# INTERVIEWER LOGIC
# =====================================================================

def generate_first_interview_message(astronaut_name: str, language: str) -> str:
    """Generate question #1 to initiate check-in session."""
    if is_mock_active():
        return MOCK_INTERVIEW_QUESTIONS_AR[0] if language == "ar" else MOCK_INTERVIEW_QUESTIONS_EN[0]

    system_prompt = get_interviewer_system_prompt(astronaut_name, language, current_question_num=1, is_final=False)
    user_prompt = "Start the session now with your first short, warm question."
    return call_llm_text(system_prompt, [{"role": "user", "content": user_prompt}], temperature=0.7)


def generate_interview_reply(
    astronaut_name: str,
    language: str,
    history: List[Dict[str, str]],
    current_question_count: int,
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool, bool]:
    """
    Generate interviewer response.
    Limits to 7 questions total. After 7th, delivers warm closing summary and sets should_end=True.
    Supports task-aware behavior:
    - If a task is currently running (phase 'started'), answers in one short sentence and delays new questions.
    - If a task recently ended (phase 'ended'), gently references it before the next question.
    - Signals summary is strictly private; never quotes raw numbers or labels.
    - Safety layer ([ESCALATE] + keyword check) is active at all times, including during tasks.
    Returns: (reply_text, escalate_flag, should_end_flag)
    """
    # 1. Immediate safety check on user input - ACTIVE AT ALL TIMES INCLUDING DURING TASKS
    safety_hit, kw = detect_safety_keywords(user_message)
    if safety_hit:
        logger.warning(f"Safety keyword detected in user message: '{kw}'")
        crisis_reply = get_crisis_support_message(language)
        return crisis_reply, True, True

    # 2. Check if a timed task is currently running
    phase = context.get("phase") if context else None
    task_name = (context.get("task") if context else "") or "current task"

    if phase == "started":
        if language == "ar":
            reply = f"يرجى التركيز على {task_name} في الوقت الحالي؛ سنستأنف جلستنا فور انتهائك."
        else:
            reply = f"Focus on your {task_name} for now; we'll continue our check-in right after."
        return reply, False, False

    # 3. Check question count: if assistant already asked 7 questions, this must be the closing summary
    is_final_turn = (current_question_count >= 7)

    # 4. Handle Mock Mode
    if is_mock_active():
        if is_final_turn:
            closing = MOCK_CLOSING_MESSAGE_AR if language == "ar" else MOCK_CLOSING_MESSAGE_EN
            return closing, False, True

        q_idx = min(current_question_count, 6)
        next_q = (
            MOCK_INTERVIEW_QUESTIONS_AR[q_idx]
            if language == "ar"
            else MOCK_INTERVIEW_QUESTIONS_EN[q_idx]
        )

        # If a task just ended, gently acknowledge it without judging performance
        if phase == "ended":
            if language == "ar":
                next_q = f"أحسنت بإتمام {task_name}. لنواصل فحصنا: {next_q}"
            else:
                next_q = f"Glad you completed the {task_name}. Returning to our check-in: {next_q}"

        return next_q, False, False

    # 5. Live LLM Provider Call with Live Context
    system_prompt = get_interviewer_system_prompt(
        astronaut_name=astronaut_name,
        language=language,
        current_question_num=current_question_count + 1,
        is_final=is_final_turn,
        context=context,
    )

    api_messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
    api_messages.append({"role": "user", "content": user_message})

    raw_reply = call_llm_text(system_prompt, api_messages, temperature=0.6)
    cleaned_reply, token_escalate = parse_and_strip_escalate_token(raw_reply)
    should_end = is_final_turn or token_escalate

    return cleaned_reply, token_escalate, should_end


# =====================================================================
# ANALYZER LOGIC
# =====================================================================

def generate_analyzer_json(transcript: str, has_crisis_keyword: bool = False) -> str:
    """Run analyzer on full transcript at temperature 0."""
    if is_mock_active():
        if has_crisis_keyword:
            return json.dumps({
                "scores": {
                    "stress": 8,
                    "low_mood": 9,
                    "anxiety": 8,
                    "fatigue": 7,
                    "social_isolation": 7,
                    "concentration_difficulty": 5,
                },
                "evidence": {
                    "stress": "astronaut indicated severe operational or psychological strain",
                    "low_mood": "crisis cue or hopelessness identified in check-in transcript",
                    "anxiety": "high psychological tension",
                    "fatigue": "rest cycle disruption reported",
                    "social_isolation": "feelings of disconnection from mission crew",
                    "concentration_difficulty": "difficulty sustaining focus on checklists",
                },
                "screening_answers": {
                    "phq2_mood": 3,
                    "gad2_anxiety": 3,
                },
                "confidence": 0.95,
                "risk_flag": True,
                "notes": "Critical risk flag raised due to severe distress indicators detected in transcript.",
            })

        return json.dumps({
            "scores": {
                "stress": 4,
                "low_mood": 2,
                "anxiety": 3,
                "fatigue": 5,
                "social_isolation": 2,
                "concentration_difficulty": 2,
            },
            "evidence": {
                "stress": "workload is demanding with maintenance checklists",
                "low_mood": "occasional mood dip during long mission days",
                "anxiety": "moderate nervousness before scheduled EVA",
                "fatigue": "rest cycle was slightly broken last night",
                "social_isolation": "connected with crew and family ground comms",
                "concentration_difficulty": "slight mental fatigue reported on checklists",
            },
            "screening_answers": {
                "sleep_quality": 2,
                "stress_level": 1,
            },
            "confidence": 0.88,
            "risk_flag": False,
            "notes": "Astronaut displays mild situational fatigue and operational stress, with intact coping and stable baseline mood.",
        })

    system_prompt = ANALYZER_PROMPT
    user_prompt = (
        f"Read this complete astronaut check-in transcript:\n\n"
        f"=== TRANSCRIPT ===\n{transcript}\n==================\n\n"
        "Score each dimension from 0 to 10 based ONLY on transcript evidence. "
        "Return ONLY the raw JSON object conforming strictly to the requested schema."
    )

    return call_llm_text(system_prompt, [{"role": "user", "content": user_prompt}], temperature=0.0)


# =====================================================================
# COMPANION LOGIC & KNOWLEDGE BASE TOOL LOOP
# =====================================================================

def generate_companion_opening(
    astronaut_name: str,
    language: str,
    transcript: str,
    analysis_dict: Dict[str, Any],
    past_sessions_summary: str,
) -> str:
    """Generate opening message when transitioning to companion mode."""
    if is_mock_active():
        if language == "ar":
            return (
                f"أهلاً بك يا {astronaut_name}. لقد انتهت جلسة الفحص اليومية، والآن أنا هنا كصديق ورفيق لك "
                "لنتحدث بأريحية ودون أي قيود أو استبيانات. كيف تشعر الآن بعد أن تكلمنا عن نومك وضغط العمل؟"
            )
        return (
            f"I'm right here with you, {astronaut_name}. The official check-in is complete, and we can just talk freely now. "
            "How does your body feel right now after walking through your sleep and today's schedule?"
        )

    analysis_json_str = json.dumps(analysis_dict, indent=2)
    system_prompt = get_companion_system_prompt(
        astronaut_name=astronaut_name,
        language=language,
        transcript=transcript,
        analysis_json_str=analysis_json_str,
        past_sessions_summary=past_sessions_summary,
    )
    init_prompt = (
        "The astronaut has just transitioned into companion mode. Greet them warmly, acknowledge "
        "what they shared earlier gently without repeating questionnaires, and invite them to relax and chat freely."
    )
    return call_llm_text(system_prompt, [{"role": "user", "content": init_prompt}], temperature=0.7)


def generate_direct_companion_opening(
    astronaut_name: str,
    language: str,
    mission_day: int,
) -> str:
    """Generate opening message when starting directly in open discussion (companion) mode."""
    default_msg = (
        f"أهلاً بك يا {astronaut_name} في اليوم {mission_day} من المهمة. أنا هنا في وضع النقاش المفتوح — "
        "يمكننا مراجعة مؤشراتك الحيوية الحالية، التحدث عن النوم أو ضغط العمل، أو استكشاف بروتوكولات ناسا للتركيز والتهدئة. عمّ تود أن نتحدث الآن؟"
        if language == "ar"
        else f"Welcome, {astronaut_name} (Mission Day {mission_day}). We're in Open Discussion mode — no scripted checklist needed. "
        "We can review how your latest scan telemetry looks, talk through workload or sleep recovery, or discuss any topic you'd like. What's on your mind right now?"
    )
    if is_mock_active():
        return default_msg

    system_prompt = get_companion_system_prompt(
        astronaut_name=astronaut_name,
        language=language,
        transcript="",
        analysis_json_str="{}",
        past_sessions_summary="",
    )
    init_prompt = (
        f"The astronaut just opened an Open Discussion chat directly on Mission Day {mission_day} without a scripted questionnaire. "
        "Greet them warmly as Bio Astro Lab's Mission AI Assistant, let them know we can discuss telemetry, NASA protocols, mission science, or anything else openly, and ask what they'd like to explore."
    )
    try:
        text = call_llm_text(system_prompt, [{"role": "user", "content": init_prompt}], temperature=0.7)
        return text.strip() or default_msg
    except Exception as e:
        logger.warning(f"Live LLM opening call failed ({e}). Using default opening greeting.")
        return default_msg


def _clean_kb_title(title: str) -> str:
    """Strip internal placeholder tags from KB titles before showing to users."""
    return re.sub(r"\s*\(PLACEHOLDER\)\s*", "", str(title or ""), flags=re.IGNORECASE).strip()


def _should_query_kb(msg_lower: str, inferred_topic: Optional[str], is_short_followup: bool) -> bool:
    """Return True only when user input touches wellness, spaceflight ops, or protocol guidance."""
    if inferred_topic is not None or is_short_followup:
        return True
    domain_terms = (
        "sleep", "insomnia", "circadian", "light", "breath", "breathing", "box",
        "relax", "calm", "stress", "anxi", "panic", "tense", "pressure", "tired",
        "fatigue", "exhaust", "rest", "nap", "focus", "concentrat", "checklist",
        "isolat", "lonely", "homesick", "mood", "sad", "grounding", "sensory",
        "journal", "protocol", "tip", "tips", "advice", "countermeasure", "cope",
        "coping", "headache", "noise", "caffeine", "recover", "recovery", "burnout",
        "overwhelm", "worried", "worry", "technique", "exercise", "suggest",
        "نوم", "تنفس", "ضغط", "تعب", "قلق", "تركيز", "عزلة", "مزاج", "تهدئة", "نصيحة",
    )
    return any(re.search(rf"\b{re.escape(term)}", msg_lower) for term in domain_terms)


def _extract_telemetry_cues(context: Optional[Dict[str, Any]]) -> Tuple[List[str], Optional[str]]:
    """Summarize telemetry qualitatively from signals_summary without revealing raw scores."""
    signals = (context or {}).get("signals_summary") or {}
    cues: List[str] = []

    def _num(val: Any) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    hr = _num(signals.get("heart_rate_bpm"))
    if hr is not None:
        if hr > 95:
            cues.append("elevated heart rate")
        elif hr < 55:
            cues.append("low resting heart rate")

    spo2 = _num(signals.get("spo2_pct"))
    if spo2 is not None and spo2 < 95:
        cues.append("slightly lower oxygen saturation")

    sleep_h = _num(signals.get("sleep_hours"))
    if sleep_h is not None and sleep_h < 6.5:
        cues.append("shorter sleep duration than optimal")

    co2 = _num(signals.get("cabin_co2_mmhg"))
    if co2 is not None and co2 > 3.5:
        cues.append("elevated cabin CO2 levels")

    glucose = _num(signals.get("blood_glucose"))
    if glucose is not None and (glucose > 140 or glucose < 70):
        cues.append("blood glucose outside the nominal band")

    radiation = _num(signals.get("radiation_msv") if signals.get("radiation_msv") is not None else signals.get("radiation_dose_msv"))
    if radiation is not None and radiation > 1.0:
        cues.append("higher cumulative radiation load")

    decision = str(signals.get("ai_decision") or "").strip() or None
    return cues[:3], decision


def _search_kb_broadly(
    db: DBSession,
    query: str,
    topic: Optional[str],
    severity: float,
    language: str,
) -> List[Dict[str, Any]]:
    """Query FTS5 KB with progressive relaxation so valid topics are never missed in mock mode."""
    results = search_knowledge_base(
        db=db,
        query=query,
        topic=topic,
        severity=severity,
        language=language,
        limit=3,
    )
    if not results and topic:
        results = search_knowledge_base(
            db=db,
            query=query,
            topic=None,
            severity=None,
            language=language,
            limit=3,
        )
    if not results and query:
        results = search_knowledge_base(
            db=db,
            query=query,
            topic=None,
            severity=None,
            language=None,
            limit=3,
        )
    return results


def _build_mock_companion_reply(
    db: DBSession,
    session_id: int,
    astronaut_name: str,
    language: str,
    user_message: str,
    inferred_topic: Optional[str],
    max_severity: float,
    companion_messages: List[Dict[str, str]],
    context: Optional[Dict[str, Any]],
) -> Tuple[str, bool, List[int]]:
    """Build an interactive, telemetry- and KB-aware discussion reply when MOCK_LLM=true."""
    msg_lower = user_message.lower().strip()
    telemetry_cues, decision_status = _extract_telemetry_cues(context)
    tab = str((context or {}).get("current_tab") or "").strip()
    previous_assistant_texts = [
        m.get("content", "") for m in companion_messages if m.get("role") == "assistant"
    ]
    previous_user_texts = [
        m.get("content", "") for m in companion_messages if m.get("role") == "user"
    ]

    greeting_markers = {
        "hi", "hello", "hey", "yo", "good morning", "good evening", "how are you",
        "how r u", "what's up", "whats up", "sup", "who are you", "what can you do",
        "أهلا", "اهلا", "مرحبا", "السلام عليكم", "كيف حالك", "ازيك", "عامل ايه",
    }
    is_greeting = (
        msg_lower in greeting_markers
        or any(msg_lower.startswith(g + " ") for g in ("hi", "hello", "hey", "good morning", "good evening"))
        or "how are you" in msg_lower
        or "what can you do" in msg_lower
    )

    follow_up_markers = {
        "yes", "yeah", "yep", "sure", "ok", "okay", "tell me more", "more",
        "why", "how", "explain", "go on", "continue", "what else", "next",
    }
    is_short_followup = msg_lower.rstrip("?!.") in follow_up_markers

    telemetry_keywords = (
        "telemetry", "vitals", "scan", "status", "heart", "pulse", "spo2", "oxygen",
        "co2", "radiation", "glucose", "blood", "balance", "posture", "reading",
        "caution", "nominal", "alert", "data", "cabin", "how am i", "check my",
    )
    is_telemetry_query = any(kw in msg_lower for kw in telemetry_keywords)

    reciprocal_phrases = (
        "what about you", "how about you", "and you", "how r u", "how are you",
        "who are you", "what can you do", "how do you work",
    )
    casual_state_phrases = (
        "i am fine", "i'm fine", "im fine", "i am good", "i'm good", "im good",
        "doing well", "doing great", "pretty good", "all good", "not bad",
        "thanks", "thank you", "cool", "nice", "awesome", "nothing much", "just chatting",
    )
    has_smalltalk_phrase = (
        any(p in msg_lower for p in reciprocal_phrases)
        or any(p in msg_lower for p in casual_state_phrases)
    )
    wants_kb_guidance = _should_query_kb(msg_lower, inferred_topic, is_short_followup)

    used_chunk_ids: List[int] = []

    if (is_greeting or (has_smalltalk_phrase and not wants_kb_guidance)) and not is_telemetry_query:
        asked_about_assistant = any(p in msg_lower for p in reciprocal_phrases)
        shared_doing_well = any(p in msg_lower for p in casual_state_phrases)

        if language == "ar":
            return (
                f"أهلاً بك يا {astronaut_name}! أنا بخير وجاهز تماماً للدردشة أو مراجعة بيانات المهمة معك — لا توجد أي أسئلة محفوظة."
                f"{(' لاحظت فقط إشارة تستحق المراجعة في قراءات المسح.' if telemetry_cues else '')} "
                "هل تحب أن نراجع مؤشراتك الحيوية الحالية أم نتحدث في موضوع معين اليوم؟",
                False,
                [],
            )

        opener = (
            f"Doing great on my end — mission telemetry monitors are active and ready, {astronaut_name}! "
            if asked_about_assistant
            else f"Glad to hear from you, {astronaut_name}! "
        )
        if shared_doing_well and asked_about_assistant:
            opener = (
                f"Glad to hear you're doing well, {astronaut_name} — I'm running steady over here and ready to talk whenever you like! "
            )
        elif shared_doing_well:
            opener = f"Good to hear things are steady on your end, {astronaut_name}. "

        telemetry_nudge = (
            f"By the way, your latest Scan telemetry notes {', '.join(telemetry_cues)} ({decision_status or 'Active'}) if you ever want to look at that together. "
            if telemetry_cues
            else (
                f"Your latest mission readout shows {decision_status} status. "
                if decision_status
                else ""
            )
        )
        prompts = [
            "What's on your mind right now — want to talk through today's mission plan, spaceflight life, or check any telemetry trends?",
            "Anything you'd like to explore today — crew workload, sleep & recovery, or just general conversation?",
        ]
        follow = prompts[len(previous_assistant_texts) % len(prompts)]
        return f"{opener}{telemetry_nudge}{follow}", False, []

    if is_telemetry_query:
        kb_hits = _search_kb_broadly(
            db, f"{user_message} sleep stress focus breathing", inferred_topic, max_severity, language
        )
        selected_chunk = kb_hits[0] if kb_hits else None
        if selected_chunk:
            used_chunk_ids.append(selected_chunk["id"])

        parts: List[str] = []
        if telemetry_cues:
            status_phrase = f" ({decision_status} readiness)" if decision_status else ""
            parts.append(
                f"From your current mission scan{status_phrase}, the main signals standing out are {', '.join(telemetry_cues)}."
            )
        elif decision_status:
            parts.append(f"Your current mission telemetry shows {decision_status} status with no sharp anomalies flagged.")
        else:
            parts.append(
                "I don't see an active telemetry snapshot synced yet — if you run a quick Scan on the Scan tab (or click Sync Latest Vitals), I can cross-check your live signals here."
            )

        if selected_chunk:
            clean_title = _clean_kb_title(selected_chunk["title"])
            parts.append(
                f"Relevant onboard guidance ({clean_title}): {selected_chunk['content']} [Source: {selected_chunk['source_name']}]"
            )

        parts.append(
            "How does that line up with how your body feels right now — is fatigue, cabin environment, or schedule pressure behind it?"
        )
        return "\n\n".join(parts), False, used_chunk_ids

    # Query KB only when the user actually asks about a wellness/operational/protocol topic
    kb_results: List[Dict[str, Any]] = []
    if wants_kb_guidance:
        effective_query = user_message
        if is_short_followup and previous_user_texts:
            effective_query = f"{previous_user_texts[-1]} {user_message}".strip()
        kb_results = _search_kb_broadly(db, effective_query, inferred_topic, max_severity, language)

    # Avoid repeating the exact same KB chunk back-to-back in companion history
    top_chunk = None
    for candidate in kb_results:
        snippet = candidate["content"][:60]
        if not any(snippet in prev for prev in previous_assistant_texts[-4:]):
            top_chunk = candidate
            break
    if top_chunk is None and kb_results:
        top_chunk = kb_results[0]

    if top_chunk:
        used_chunk_ids.append(top_chunk["id"])
        clean_title = _clean_kb_title(top_chunk["title"])
        citation = f" [Source: {top_chunk['source_name']}]"

        if 4.0 <= max_severity < 7.0:
            alert = Alert(
                session_id=session_id,
                reason=f"Medium severity ({max_severity:.1f}) countermeasure requested: {clean_title}",
                source="chat",
                handled=False,
            )
            db.add(alert)
            db.commit()

            if language == "ar":
                reply = (
                    f"بناءً على بروتوكولاتنا المعتمدة ({clean_title}): {top_chunk['content']}{citation}\n\n"
                    "نظراً لمستوى الإجهاد المرتفع الذي تشعر به، أوصيك بوضوح بالتواصل مع طبيب الرحلة أو الأخصائي النفسي في مركز التحكم للاطمئنان."
                )
            else:
                reply = (
                    f"Based on our onboard protocols ({clean_title}): {top_chunk['content']}{citation}\n\n"
                    "Given the elevated strain you're experiencing, I clearly suggest contacting the flight surgeon or mission psychologist for a brief consult."
                )
            return reply, False, used_chunk_ids

        if language == "ar":
            return (
                f"نقطة مهمة حول «{clean_title}»:\n{top_chunk['content']}{citation}\n\n"
                "كيف ينطبق هذا على جدولك الحالي اليوم، وهل تحب أن نفصّل خطوة معينة معاً؟",
                False,
                used_chunk_ids,
            )

        topic_followups = {
            "sleep": "How close are you to your scheduled lights-out window right now, and would adjusting cabin light or caffeine timing fit today's shift?",
            "stress": "Would you like to walk through a 2-minute paced cycle together right now, or unpack what's driving the workload pressure?",
            "anxiety": "Which part of the upcoming schedule feels heaviest right now — mission tasks, rest, or crew pace?",
            "focus": "Which checklist or procedure is demanding the most focus right now so we can break it into clean blocks?",
            "isolation": "Have you had a chance to connect with the crew or ground comms today, or what helps you feel most grounded in orbit?",
            "fatigue": "Was last night's rest broken by noise, light, or mission tasks, and do you have room for a short recovery block?",
        }
        follow_up = topic_followups.get(
            top_chunk.get("topic") or inferred_topic or "",
            "Does that protocol fit what you're navigating on this shift, or want to explore another angle?"
        )
        telemetry_bridge = (
            f" (Also noting your recent {', '.join(telemetry_cues)} from Scan telemetry.)"
            if telemetry_cues else ""
        )
        reply = (
            f"Regarding {clean_title}:{telemetry_bridge}\n"
            f"{top_chunk['content']}{citation}\n\n"
            f"{follow_up}"
        )
        return reply, False, used_chunk_ids

    # No KB match -> Genuine topic-responsive open discussion instead of one static sentence
    if language == "ar":
        return (
            f"فهمتك يا {astronaut_name}. مشاركتك حول «{user_message[:70]}» مهمة جداً أثناء المهمة. "
            "ما الجزء الأكثر تأثيراً عليك في هذا الموضوع الآن — الجانب البدني، ضغط المهام، أم التركيز؟",
            False,
            [],
        )

    lowered = msg_lower
    telemetry_bridge = (
        f" Meanwhile, your latest telemetry reflects {', '.join(telemetry_cues)}."
        if telemetry_cues else ""
    )
    tab_hint = f" while you're working in {tab}" if tab and tab != "assistant" else ""

    if any(w in lowered for w in ("earth", "home", "family", "trees", "ocean", "miss")):
        reply = (
            f"That longing for Earth's sensory world is one of the most real human experiences in deep transit, {astronaut_name}."
            f"{telemetry_bridge} Taking a few minutes with Earth-view imagery or familiar sounds during off-duty time often helps restore emotional balance. "
            "What memory or place back home has been crossing your mind most lately?"
        )
    elif any(w in lowered for w in ("crew", "team", "commander", "conflict", "communicate", "talk")):
        reply = (
            f"Crew dynamics carry huge weight in confined habitats, {astronaut_name}.{telemetry_bridge} "
            "Even minor friction feels louder after weeks inside the same modules. "
            "Is there a specific crew interaction or expectation you'd like to talk through calmly?"
        )
    elif any(w in lowered for w in ("eva", "task", "work", "workload", "schedule", "checklist", "mission")):
        reply = (
            f"Got it — operational workload{tab_hint} can quietly drain cognitive reserve when tasks stack back-to-back.{telemetry_bridge} "
            "Which part of today's sequence feels tightest right now, and do you want help prioritizing recovery windows around it?"
        )
    else:
        variants = [
            (
                f"I hear what you're bringing up about \"{user_message[:80]}\", {astronaut_name}.{telemetry_bridge} "
                "Looking at it together rather than rushing past it — what's the main thing you want to figure out or ease around that right now?"
            ),
            (
                f"That's a really fair point to unpack, {astronaut_name}.{telemetry_bridge} "
                "Do you see this connecting more to your rest cycle, today's operational pace, or just needing space to think it through?"
            ),
        ]
        reply = variants[len(previous_assistant_texts) % len(variants)]

    return reply, False, []


def generate_companion_reply(
    db: DBSession,
    session_id: int,
    astronaut_name: str,
    language: str,
    transcript: str,
    analysis_dict: Dict[str, Any],
    past_sessions_summary: str,
    companion_messages: List[Dict[str, str]],
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool, List[int]]:
    """
    Generate companion chat reply with server-side RAG tool loop and severity policy enforcement.
    Returns: (reply_text, escalate_flag, used_chunk_ids)
    """
    # 1. Safety keyword check - ACTIVE AT ALL TIMES INCLUDING DURING TASKS
    safety_hit, kw = detect_safety_keywords(user_message)
    if safety_hit:
        logger.warning(f"Safety keyword in companion chat: '{kw}'")
        return get_crisis_support_message(language), True, []

    # Check if a timed task is currently running
    phase = context.get("phase") if context else None
    task_name = (context.get("task") if context else "") or "current task"

    if phase == "started":
        if language == "ar":
            reply = f"يرجى التركيز على {task_name} في الوقت الحالي؛ سنواصل حديثنا فور انتهائك."
        else:
            reply = f"Focus on your {task_name} for now; we'll continue our conversation right after."
        return reply, False, []

    scores = analysis_dict.get("scores", {}) if isinstance(analysis_dict, dict) else {}
    risk_flag = analysis_dict.get("risk_flag", False) if isinstance(analysis_dict, dict) else False

    # Detect inferred topic from message keywords
    topic_keywords = {
        "stress": "stress",
        "breath": "stress",
        "تنفس": "stress",
        "ضغط": "stress",
        "sleep": "sleep",
        "نوم": "sleep",
        "rest": "sleep",
        "anxiety": "anxiety",
        "nervous": "anxiety",
        "قلق": "anxiety",
        "fatigue": "fatigue",
        "tired": "fatigue",
        "تعب": "fatigue",
        "isolation": "isolation",
        "lonely": "isolation",
        "عزلة": "isolation",
        "mood": "mood",
        "مزاج": "mood",
        "focus": "focus",
        "concentration": "focus",
        "checklist": "focus",
        "تركيز": "focus",
    }
    inferred_topic = None
    for kw_token, t_val in topic_keywords.items():
        if kw_token in user_message.lower():
            inferred_topic = t_val
            break

    max_severity = get_relevant_severity(scores, topic=inferred_topic)

    # Severity Policy Enforcement:
    # High (>= 7) or risk_flag -> NO self-help tips, calm support, [ESCALATE]
    if risk_flag or max_severity >= 7.0:
        logger.info(f"High risk/severity detected ({max_severity}). Applying escalation safety policy.")
        crisis_reply = get_crisis_support_message(language)
        return crisis_reply, True, []

    # Windowing: Keep last 10 companion messages in full, summarize older
    older_summary = ""
    recent_messages = companion_messages
    if len(companion_messages) > 10:
        older = companion_messages[:-10]
        recent_messages = companion_messages[-10:]
        older_summary = f"Summary of earlier discussion: astronaut and companion talked about daily routine and coping ({len(older)} turns)."

    analysis_json_str = json.dumps(analysis_dict, indent=2)
    used_chunk_ids: List[int] = []

    # 2. Mock Mode handling
    if is_mock_active():
        return _build_mock_companion_reply(
            db=db,
            session_id=session_id,
            astronaut_name=astronaut_name,
            language=language,
            user_message=user_message,
            inferred_topic=inferred_topic,
            max_severity=max_severity,
            companion_messages=companion_messages,
            context=context,
        )

    # 3. Live LLM Execution (Provider Switch with Tool Calling & Server-Side RAG Fallback)
    system_prompt = get_companion_system_prompt(
        astronaut_name=astronaut_name,
        language=language,
        transcript=transcript,
        analysis_json_str=analysis_json_str,
        past_sessions_summary=past_sessions_summary,
        older_companion_summary=older_summary,
        context=context,
    )

    api_messages: List[Dict[str, Any]] = []
    for msg in recent_messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
    api_messages.append({"role": "user", "content": user_message})

    provider = getattr(config, "LLM_PROVIDER", "anthropic").lower()
    final_text = ""

    if provider == "anthropic":
        try:
            from app.services.llm_client import call_anthropic_provider
            response = call_anthropic_provider(
                system_prompt=system_prompt,
                messages=api_messages,
                temperature=0.7,
                max_tokens=1000,
                tools=[KB_TOOL_DEFINITION],
            )
            while response.tool_calls:
                tc = response.tool_calls[0]
                tool_name = tc.name
                tool_input = tc.arguments or {}
                tool_id = tc.id

                logger.info(f"LLM called tool: {tool_name} with input {tool_input}")
                if tool_name == "search_knowledge_base":
                    kb_results = search_knowledge_base(
                        db=db,
                        query=tool_input.get("query", ""),
                        topic=tool_input.get("topic"),
                        severity=max_severity,
                        language=language,
                        limit=3,
                    )
                    for item in kb_results:
                        used_chunk_ids.append(item["id"])
                    tool_result_str = json.dumps(kb_results, ensure_ascii=False)
                else:
                    tool_result_str = json.dumps({"error": f"Unknown tool {tool_name}"})

                api_messages.append({"role": "assistant", "content": response.raw.content})
                api_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": tool_result_str,
                        }
                    ],
                })
                response = call_anthropic_provider(
                    system_prompt=system_prompt,
                    messages=api_messages,
                    temperature=0.7,
                    max_tokens=1000,
                    tools=[KB_TOOL_DEFINITION],
                )

            final_text = response.content
        except Exception as e:
            logger.warning(f"Anthropic tool calling error: {e}. Falling back to server-side prompt RAG...")
            provider = "fallback_rag"

    if provider != "anthropic":
        # Server-Side Prompt RAG Fallback for OpenAI-compatible providers (Gemini, Groq, etc.)
        kb_results = []
        if _should_query_kb(user_message.lower(), inferred_topic, False):
            kb_results = search_knowledge_base(
                db=db,
                query=user_message,
                topic=inferred_topic,
                severity=max_severity,
                language=language,
                limit=3,
            )
        if kb_results:
            for item in kb_results:
                used_chunk_ids.append(item["id"])

            class ChunkObj:
                def __init__(self, d):
                    self.title = _clean_kb_title(d["title"])
                    self.topic = d["topic"]
                    self.source_name = d["source_name"]
                    self.content = d["content"]

            chunk_objs = [ChunkObj(c) for c in kb_results]
            system_prompt = inject_knowledge_into_prompt(system_prompt, chunk_objs)

        try:
            final_text = call_llm_text(system_prompt, api_messages, temperature=0.7, max_tokens=900)
        except Exception as e:
            logger.warning(f"Live LLM provider call failed ({e}). Falling back to offline companion handler.")
            return _build_mock_companion_reply(
                db=db,
                session_id=session_id,
                astronaut_name=astronaut_name,
                language=language,
                user_message=user_message,
                inferred_topic=inferred_topic,
                max_severity=max_severity,
                companion_messages=companion_messages,
                context=context,
            )

    cleaned_reply, token_escalate = parse_and_strip_escalate_token(final_text)

    # Medium severity check: if 4.0 <= max_severity < 7.0 and KB was used, create alert
    if 4.0 <= max_severity < 7.0 and used_chunk_ids:
        alert = Alert(
            session_id=session_id,
            reason=f"Medium severity ({max_severity:.1f}) countermeasure discussed with companion.",
            source="chat",
            handled=False,
        )
        db.add(alert)
        db.commit()

    return cleaned_reply, token_escalate, used_chunk_ids
