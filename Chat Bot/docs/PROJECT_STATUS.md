# 🛰️ Project Status & Architecture Audit
**NASA Space Apps Challenge 2026 — Astronaut Psychological Check-in Assistant**
**Date:** November 2026  
**Document:** `docs/PROJECT_STATUS.md`

This document provides a comprehensive audit of the codebase following the Phase 1 audit specification. It details what already exists, what is functional, what is placeholder, what is missing, and the consolidation plan.

---

## 📊 Executive Summary Checklist

| Component / Subsystem | Status | Details / Implementation Location |
| :--- | :---: | :--- |
| **Adaptive 7-Turn Interviewer** | ✅ COMPLETE | `app/services/llm_service.py`, `app/routers/chat.py` (limits to 7 turns, delivers closing summary, flags `session_should_end: true`) |
| **Evidence-Grounded Analyzer** | ✅ COMPLETE | `app/services/analyzer_service.py` (runs at temp 0, strictly quotes transcript, scores 6 core dimensions, Pydantic validated) |
| **Supportive Companion Mode** | ✅ COMPLETE | `POST /sessions/{id}/companion`, `llm_service.py` (context windowing, private analysis injected without leaking raw scores) |
| **Dual-Layer Crisis Safety Safeguards** | ✅ COMPLETE | `app/safety.py` (bilingual English/Arabic keyword scan + `[ESCALATE]` interception, active at all times) |
| **RAG Knowledge Base with FTS5** | ✅ COMPLETE | `app/services/kb_service.py`, `app/database.py` (SQLite FTS5 BM25 ranked search, severity countermeasure policy, `kb_usage` logging) |
| **`<astro-chat>` Web Component** | ✅ COMPLETE | Framework-free Web Component supporting `mode="floating"`, `mode="tab"`, and `mode="inline"`, unread badge, Esc close, RTL |
| **Host-Page Event Bridge** | ✅ COMPLETE | Listens on `window` for `astro:task`, `astro:context`, `astro:signals-summary`; dispatches `astro:session`, `astro:question`, `astro:message`, `astro:session-ended`, `astro:escalate`; exposes `window.AstroChat` |
| **Task-Aware Backend** | ✅ COMPLETE | `POST /chat` accepts context; pauses questions during `phase: 'started'`, queues next question in `pending_question`, releases on `phase: 'ended'` |
| **Task Events Table & Endpoints** | ✅ COMPLETE | `task_events` table; endpoints `POST /sessions/{id}/events`, `GET /sessions/{id}/events`, `GET /sessions/{id}/pending` |
| **Signals Telemetry Endpoints** | ⚠️ BASIC | `POST /sessions/{id}/signals`, `GET /sessions/{id}/signals` store raw telemetry payloads, but multi-channel fusion is missing |
| **Baselines & Z-Score Calibration** | ⚠️ PARTIAL | `baselines` table exists and is seeded with means/stds, but dynamic z-score calibration and minimum 5-session confidence is missing |
| **Multimodal Affect & Fusion Layer** | ❌ MISSING | `app/modules/physiological.py` and `app/modules/multimodal.py` are only stub dataclasses; `POST /sessions/{id}/fuse`, conflict detection, and 3-session alert logic not yet implemented |
| **Simulated Signals Generator** | ❌ MISSING | `scripts/simulate_signals.py` with stable / stressed / exhausted scenarios needs to be implemented |
| **History & Alerts Endpoints** | ✅ COMPLETE | `GET /astronauts/{id}/history`, `GET /alerts`, `PATCH /alerts/{id}/handle`; Phase 3 dashboard extensions needed |
| **Database Architecture & Migrations** | ⚠️ NEEDS UPGRADE | Single SQLite database with ad-hoc schema migration; needs `astro_` table prefixes and versioned migrations runner |
| **Integration Modes (A & B)** | ⚠️ PARTIAL | Mode A (standalone API on port 8000 serving `web/`) works; Mode B (`app/astro_router.py` with `create_astro_router()`) missing |
| **Multi-LLM Provider Switch** | ❌ MISSING | Currently hardcoded to Anthropic API + offline mock; needs `llm_client.py` supporting `anthropic` and `openai_compatible` (Gemini, Groq, OpenRouter, Ollama) |
| **One-Click Run Scripts** | ✅ COMPLETE | `run.bat` and `run.sh` create venv, install requirements, copy `.env.example`, seed database, run uvicorn on port 8000 |
| **Packaging & Secret Scanner** | ✅ COMPLETE | `scripts/package.py` creates `astro-chatbot.zip` and verifies exclusion of `.env`, `venv`, `*.db`, caches, and secrets |
| **Pytest Test Suite** | ✅ COMPLETE | 35 automated tests currently passing (`test_ingest.py`, `test_kb.py`, `test_main.py`, `test_safety.py`, `test_tasks_and_context.py`) |

---

## 🔍 Detailed Component Audit

### 1. Conversational Engine & Clinical Safeguards
- **Interviewer (`generate_interview_reply`)**:
  - Enforces the 7-question maximum.
  - Automatically incorporates the "Live Context" block into model prompts.
  - While a timed task is running (`phase == 'started'`), outputs a concise 1-sentence acknowledgement and pauses new questions.
  - Releases queued questions when the task completes, gently acknowledging the task without performance judgment.
- **Evidence-Grounded Analyzer (`analyze_and_save_session`)**:
  - Scores 6 dimensions strictly on transcript evidence quotes: `stress`, `low_mood`, `anxiety`, `fatigue`, `social_isolation`, `concentration_difficulty`.
  - Sets confidence (0.0 to 1.0) and boolean `risk_flag`.
- **Companion Mode (`generate_companion_reply`)**:
  - Injects transcript, confidential analysis (never disclosing raw scores to the astronaut), and longitudinal summary of up to 3 past sessions.
  - Executes tool loop calling `search_knowledge_base`.
- **Safety Safeguards (`app/safety.py`)**:
  - Detects critical keywords in English (`suicide`, `self-harm`, `hopeless`, `emergency`, `end my life`, `end it all`...) and Arabic (`انتحار`, `إيذاء النفس`, `لا أمل`, `طوارئ`...).
  - Scans user inputs before turn logic; triggers immediate crisis alert and calming support message.
  - Intercepts assistant `[ESCALATE]` tokens, strips them before rendering, and logs safety alerts.

### 2. Frontend Widget (`<astro-chat>`)
- Web Component using native browser Shadow DOM.
- Three display modes:
  - `mode="floating"`: launcher button, unread count badge, minimizes, closes on `Esc`, remembers state via `sessionStorage`.
  - `mode="tab"`: fills container 100% with no launcher (designed for dashboard tabs).
  - `mode="inline"`: standard document-flow box.
- Binds to host page events on `window`:
  - Listens to `astro:task`, `astro:context`, `astro:signals-summary`.
  - Dispatches `astro:session`, `astro:question`, `astro:message`, `astro:session-ended`, `astro:escalate`.
  - Global `window.AstroChat` API (`open`, `close`, `startSession`, `endSession`, `sendSystemNote`, `getSessionId`, `setContext`).

### 3. File Duplication & Inconsistencies Report
- **Duplicate Widget Script**:
  - `static/widget.js` (606 lines)
  - `web/widget.js` (606 lines)
  - *Consolidation action:* Remove duplicate from `static/`, keep a single canonical source of truth at `web/widget.js`, and serve it at both `/widget.js` and `/web/widget.js`.
- **Documentation Overlap**:
  - `docs/TEAMMATE_GUIDE.md` and `docs/INTEGRATION.md` have overlapping content.
  - *Consolidation action:* Maintain `docs/TEAMMATE_GUIDE.md` as the quickstart / widget integration guide, and update `docs/INTEGRATION.md` to document Mode A (standalone HTTP API) and Mode B (`create_astro_router` FastAPI module) with complete JSON contracts.

### 4. Placeholder & Stub Inventory
- **`data/kb_seed_placeholder.json`**:
  - 16 chunks marked with `(PLACEHOLDER)` in titles. Approved flag is enabled for testing.
  - Keep placeholders clearly marked; loader script must only load approved chunks.
- **`app/modules/multimodal.py`**:
  - Contains dataclass `MultimodalObservation` and static method `analyze_affect()`. Only returns simulated flags; not plugged into an active fusion endpoint.
- **`app/modules/physiological.py`**:
  - Contains dataclass `PhysiologicalTelemetry` and method `evaluate_telemetry()`. Stub only; needs integration with `POST /sessions/{id}/fuse`.

---

## 🎯 Gap Analysis: What Must Be Built

1. **Phase 2: Fusion & Calibration Layer**:
   - Create tables `signals` and `fusion_results`.
   - Endpoint `POST /sessions/{id}/fuse`:
     - Combines conversational rating (analyzer), vocal/acoustic telemetry, facial action units, and physiological wearable metrics.
     - Weights channels by confidence/quality.
     - Checks channel conflicts (e.g. conversational rating calm vs biometric high strain).
     - Computes z-scores against baseline (needs >= 5 sessions for high confidence).
     - Generates alert only when deviation persists over 3 sessions.
   - Script `scripts/simulate_signals.py` generating realistic telemetry for `stable`, `stressed`, and `exhausted` scenarios.
2. **Phase 3: Database Consolidation & Table Prefixing**:
   - Prefix all tables with `astro_` to prevent collisions in host databases:
     - People: `astro_astronauts` (with `role`, `created_at`, `external_user_id`, `consent_flag`, `is_simulated`).
     - Results: `astro_sessions`, `astro_messages`, `astro_task_events`, `astro_signals`, `astro_analyses`, `astro_fusion_results`, `astro_baselines`, `astro_alerts`, `astro_kb_usage`.
     - Knowledge: `astro_kb_chunks` (+ `astro_kb_chunks_fts`).
   - Versioned migration runner (pure Python versioned runner or Alembic).
   - Document architecture and ER diagram in `docs/DATABASE.md`.
   - Add dashboard query endpoints for history, latest fused scores, open alerts, and used KB chunks.
3. **Phase 4: Two Integration Modes**:
   - Mode A (Standalone Service on port 8000).
   - Mode B (Module): `app/astro_router.py` with `create_astro_router(db_url, config)`.
   - Comprehensive `docs/INTEGRATION.md`.
4. **Phase 5: Multi-LLM Provider Switch**:
   - `app/services/llm_client.py` supporting `anthropic` and `openai_compatible` (Gemini, Groq, OpenRouter, Ollama) via standard endpoint calls with retry on invalid JSON.
5. **Phase 6: Verification & Packaging**:
   - Update `run.bat`, `.env.example`, `requirements.txt`, `scripts/package.py`, and comprehensive test suite.
