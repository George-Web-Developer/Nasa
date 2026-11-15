# Teammate Integration Guide 🚀
**NASA Space Apps Challenge 2026 — Health Monitoring Software**
**Astronaut Psychological Check-in Assistant & Embedded Chatbot**

Welcome! This guide is written for teammates building the main mission monitoring website (camera/mic analysis, sensor modules, telemetry tabs, flight surgeon dashboard).

---

## 📋 Table of Contents
1. [Two Ways to Integrate (Backend)](#1-two-ways-to-integrate-backend)
   - [Mode A: Standalone Service (Universal HTTP API)](#mode-a-standalone-service-universal-http-api)
   - [Mode B: Modular Python Mount (`create_astro_router`)](#mode-b-modular-python-mount-create_astro_router)
   - [Node.js / Express & Python Flask Integration](#nodejs--express--python-flask-integration)
2. [Security & Authentication (`API_TOKEN`)](#2-security--authentication-api_token)
3. [Frontend Widget Modes & Event Bridge Contract](#3-frontend-widget-modes--event-bridge-contract)
   - [Widget Modes: Floating, Tab, Inline](#widget-modes-floating-tab-inline)
   - [Window Listeners (`astro:*`)](#window-listeners-astro)
   - [Window Dispatched Events](#window-dispatched-events)
   - [Global `window.AstroChat` API](#global-windowastrochat-api)
4. [Complete API Endpoint Reference & Example JSONs](#4-complete-api-endpoint-reference--example-jsons)
   - [1. Start Session (`POST /sessions/start`)](#1-post-sessionsstart)
   - [2. Multi-Turn Task-Aware Chat (`POST /chat`)](#2-post-chat)
   - [3. Log Task Events (`POST /sessions/{id}/events`)](#3-post-sessionsidevents)
   - [4. Get Pending Held Question (`GET /sessions/{id}/pending`)](#4-get-sessionsidpending)
   - [5. Ingest Biometric Telemetry (`POST /sessions/{id}/signals`)](#5-post-sessionsidsignals)
   - [6. Calculate Multimodal Fusion (`POST /sessions/{id}/fuse`)](#6-post-sessionsidfuse)
   - [7. Get Session Fusion Result (`GET /sessions/{id}/fusion`)](#7-get-sessionsidfusion)
   - [8. End Session & Run Analyzer (`POST /sessions/{id}/end`)](#8-post-sessionsidend)
   - [9. Switch to Companion Mode (`POST /sessions/{id}/companion`)](#9-post-sessionsidcompanion)
   - [10. Get Session Detail (`GET /sessions/{id}`)](#10-get-sessionsid)
   - [11. Crew Longitudinal History (`GET /astronauts/{id}/history`)](#11-get-astronautsidhistory)
   - [12. Latest Fused Scores Dashboard (`GET /dashboard/fused-latest`)](#12-get-dashboardfused-latest)
   - [13. Open Alerts Dashboard (`GET /dashboard/alerts`)](#13-get-dashboardalerts)
   - [14. Knowledge Base Usage Dashboard (`GET /dashboard/kb-usage`)](#14-get-dashboardkb-usage)
   - [15. Knowledge Base Search (`GET /kb/search`)](#15-get-kbsearch)
   - [16. Health Check (`GET /health`)](#16-get-health)

---

## 1. Two Ways to Integrate (Backend)

### Mode A: Standalone Service (Universal HTTP API)
Use this mode if your backend is built in **Node.js, Express, Flask, Django, Ruby, Go**, or if you want our service running as a self-contained microservice on port 8000.

1. **Start the API**:
   - Windows: Double click `run.bat` (or run `run.bat` in your terminal).
   - Linux / macOS: Run `./run.sh`.
   - Starts FastAPI on `http://localhost:8000`, automatically applies database migrations, seeds demo profiles, and serves the `web/` directory statically.
2. **CORS Configuration**:
   - If your main website runs on a different port (e.g. `http://localhost:3000` or `http://localhost:5173`), add it to `ALLOWED_ORIGINS` in `.env`:
     ```env
     ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
     ```
3. **Include the Widget**:
   - In your HTML:
     ```html
     <script src="http://localhost:8000/widget.js" defer></script>
     <astro-chat mode="floating" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>
     ```

---

### Mode B: Modular Python Mount (`create_astro_router`)
Use this mode if your website backend is already built with **FastAPI / Python** and you want to mount our entire check-in and fusion engine into your existing app using your database.

```python
from fastapi import FastAPI
from app.astro_router import create_astro_router

app = FastAPI(title="Mission Operations Website")

# Mount astronaut check-in and fusion engine reusing your DB_URL
astro_router = create_astro_router(
    db_url="sqlite:///./mission_operations.db",  # or postgresql://user:pass@host/db
    config={
        "mock_llm": True,                      # Set False when using live LLM keys
        "api_token": "mission-control-secret", # Optional authorization header
    }
)

app.include_router(astro_router, prefix="/api/astro")
```

**Zero Namespace Collisions**: All 11 tables are prefixed with `astro_` (`astro_astronauts`, `astro_sessions`, `astro_signals`, `astro_fusion_results`, etc.), ensuring zero interference with your existing schema.

---

### Node.js / Express & Python Flask Integration

#### Node.js / Express Example:
```javascript
import axios from 'axios';

const ASTRO_API = 'http://localhost:8000';
const HEADERS = {
  'Content-Type': 'application/json',
  // 'Authorization': 'Bearer <YOUR_API_TOKEN>' // if configured
};

// Start Check-in
async function startCrewCheckin(astronautId, missionDay) {
  const res = await axios.post(`${ASTRO_API}/sessions/start`, {
    astronaut_id: astronautId,
    mission_day: missionDay
  }, { headers: HEADERS });
  return res.data; // { session_id, first_message }
}

// Post Camera/Mic Biometrics for Fusion
async function postBiometrics(sessionId, features, quality = 0.95) {
  const res = await axios.post(`${ASTRO_API}/sessions/${sessionId}/signals`, {
    channel: 'multimodal',
    signals: features,
    quality: quality
  }, { headers: HEADERS });
  return res.data;
}

// Calculate Fused Score
async function triggerFusion(sessionId) {
  const res = await axios.post(`${ASTRO_API}/sessions/${sessionId}/fuse`, {}, { headers: HEADERS });
  return res.data; // { composite_score, channel_conflict, z_scores, ... }
}
```

#### Python Flask Example:
```python
import requests

ASTRO_API = "http://localhost:8000"

def get_crew_history(astronaut_id):
    resp = requests.get(f"{ASTRO_API}/astronauts/{astronaut_id}/history")
    return resp.json()

def forward_task_event(session_id, task_name, phase):
    payload = {"task": task_name, "phase": phase, "info": {}}
    resp = requests.post(f"{ASTRO_API}/sessions/{session_id}/events", json=payload)
    return resp.json()
```

---

## 2. Security & Authentication (`API_TOKEN`)

- **Server-Side Key Custody**: LLM credentials (`ANTHROPIC_API_KEY`, `LLM_API_KEY`) and database connection strings are kept strictly on the backend server. No API keys are ever shipped to or exposed in the frontend `<astro-chat>` widget.
- **Optional API Token**: To restrict access so only your frontend or backend server can call check-in endpoints, set `API_TOKEN` in `.env`:
  ```env
  API_TOKEN=your-random-mission-token-here
  ```
  When set, all `/sessions`, `/chat`, `/alerts`, and `/dashboard` API requests must include:
  ```http
  Authorization: Bearer your-random-mission-token-here
  ```
  *(Public static assets such as `/widget.js`, `/chatbot-demo.html`, and `/docs` remain open).*

---

## 3. Frontend Widget Modes & Event Bridge Contract

### Widget Modes: Floating, Tab, Inline

The `<astro-chat>` Web Component provides 3 embedding modes via attribute `mode`:

```html
<!-- Mode 1: Floating Launcher in corner (drawer with badge, Esc key close) -->
<astro-chat mode="floating" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>

<!-- Mode 2: Tab mode (fills 100% of container, ideal inside dashboard tabs) -->
<div style="height: 600px;">
  <astro-chat mode="tab" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>
</div>

<!-- Mode 3: Inline mode (natural document flow) -->
<astro-chat mode="inline" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>
```

#### Element Attributes:
- `mode`: `"floating"` | `"tab"` | `"inline"` (default: `"floating"`)
- `api-base`: Base URL of backend (default: current origin)
- `astronaut-id`: Integer crew ID (default: `1`)
- `mission-day`: Integer mission day (default: `42`)
- `language`: `"en"` | `"ar"` | `"auto"` (supports RTL layout)
- `theme`: `"auto"` | `"dark"` | `"light"`

#### Styling (Futuristic Medical HUD CSS Variables):
Override CSS variables on the host page to customize colors:
```css
:root {
  --astro-bg: #0b1329;
  --astro-panel: rgba(13, 27, 60, 0.95);
  --astro-accent: #00d2ff;
  --astro-text: #e0f2fe;
  --astro-user-bubble: #1e3a8a;
  --astro-bot-bubble: rgba(30, 58, 138, 0.4);
  --astro-border: rgba(0, 210, 255, 0.3);
}
```

---

### Window Listeners (`astro:*`)
Dispatch these custom events on `window` from your host website to notify the check-in assistant:

```javascript
// 1. Notify that a timed task has started or ended
window.dispatchEvent(new CustomEvent('astro:task', {
  detail: {
    task: 'Reaction Time Test',
    phase: 'started', // 'started' | 'ended'
    info: { duration_sec: 120 }
  }
}));

// 2. Notify tab switch or context note
window.dispatchEvent(new CustomEvent('astro:context', {
  detail: {
    current_tab: 'cognitive_battery',
    note: 'Crew is conducting routine EVA readiness test.'
  }
}));

// 3. Send numeric biometrics summary from camera/mic module
window.dispatchEvent(new CustomEvent('astro:signals-summary', {
  detail: {
    recent: {
      voice_stress_index: 0.34,
      face_fatigue_score: 0.28,
      heart_rate_bpm: 72
    }
  }
}));
```

---

### Window Dispatched Events
The widget dispatches the following events on `window` (bubbles: true, composed: true):

```javascript
// Listen for session creation
window.addEventListener('astro:session', (e) => {
  const { session_id, astronaut_id, mode } = e.detail;
  console.log(`Active session: #${session_id} for Astronaut #${astronaut_id}`);
});

// Listen for questions
window.addEventListener('astro:question', (e) => {
  const { session_id, index, text, ts } = e.detail;
  console.log(`Question #${index}: ${text}`);
});

// Listen for all messages
window.addEventListener('astro:message', (e) => {
  const { role, text, ts, escalate } = e.detail;
  console.log(`[${role}] ${text}`);
});

// Listen for check-in completion and analysis readiness
window.addEventListener('astro:session-ended', (e) => {
  const { session_id, analysis_ready } = e.detail;
  console.log(`Session #${session_id} finished. Analysis ready: ${analysis_ready}`);
  // Refresh your dashboard trend charts!
});

// Listen for real-time crisis escalation
window.addEventListener('astro:escalate', (e) => {
  const { session_id, reason } = e.detail;
  console.warn(`🚨 Real-time alert: ${reason}`);
  // Trigger alert banner on Flight Surgeon console!
});
```

---

### Global `window.AstroChat` API
The widget exposes programmatic controls on `window.AstroChat`:
- `window.AstroChat.open()`: Opens the floating chat window.
- `window.AstroChat.close()`: Closes the floating window.
- `window.AstroChat.startSession()`: Begins or restarts a check-in.
- `window.AstroChat.endSession()`: Triggers analysis completion.
- `window.AstroChat.sendSystemNote(text)`: Posts a system notification into the chat.
- `window.AstroChat.getSessionId()`: Returns the active integer `session_id` (or `null`).
- `window.AstroChat.setContext(obj)`: Sets live context dictionary.

---

## 4. Complete API Endpoint Reference & Example JSONs

### 1. `POST /sessions/start`
Starts a check-in and generates Question #1.

**Request**:
```json
{
  "astronaut_id": 1,
  "mission_day": 42
}
```
**Response (`HTTP 201 Created`)**:
```json
{
  "session_id": 14,
  "first_message": "Welcome to today's check-in, Commander. How did you sleep during your rest cycle last night?"
}
```

---

### 2. `POST /chat`
Multi-turn conversational exchange. Accepts live task and biometric context.

**Request**:
```json
{
  "session_id": 14,
  "user_message": "Sleep was broken, about 5 hours. Docking prep is going fine.",
  "context": {
    "task": "Docking Simulation",
    "phase": "started",
    "current_tab": "simulation",
    "signals_summary": { "voice_stress_index": 0.35 }
  }
}
```
**Response (`HTTP 200 OK`)**:
```json
{
  "session_id": 14,
  "reply": "Focus on your Docking Simulation for now; we'll continue our check-in right after.",
  "mode": "session",
  "escalate": false,
  "session_should_end": false,
  "question_count": 1,
  "used_chunk_ids": []
}
```

---

### 3. `POST /sessions/{id}/events`
Logs a crew task start/end event to the session timeline.

**Request**:
```json
{
  "task": "Reaction Time Test",
  "phase": "ended",
  "info": {
    "score": 94,
    "duration_sec": 120
  }
}
```
**Response (`HTTP 200 OK`)**:
```json
{
  "id": 1,
  "session_id": 14,
  "task": "Reaction Time Test",
  "phase": "ended",
  "ts": "2026-11-14T21:40:00",
  "info": { "score": 94, "duration_sec": 120 }
}
```

---

### 4. `GET /sessions/{id}/pending`
Retrieves any queued assistant question held while a timed task was active.

**Response (`HTTP 200 OK`)**:
```json
{
  "session_id": 14,
  "has_pending": true,
  "pending_question": "Glad you completed the Reaction Time Test. On a 0 to 3 scale, how has your energy been today?",
  "question_index": 2
}
```

---

### 5. `POST /sessions/{id}/signals`
Ingests camera, microphone, or wearable biometric telemetry features (strictly numerical, no raw media).

**Request**:
```json
{
  "channel": "multimodal",
  "signals": {
    "voice_stress_index": 0.38,
    "face_fatigue_score": 0.42,
    "heart_rate_bpm": 74
  },
  "quality": 0.95
}
```
**Response (`HTTP 200 OK`)**:
```json
{
  "id": 1,
  "session_id": 14,
  "channel": "multimodal",
  "signals": { "voice_stress_index": 0.38, "face_fatigue_score": 0.42, "heart_rate_bpm": 74 },
  "quality": 0.95,
  "ts": "2026-11-14T21:42:00"
}
```

---

### 6. `POST /sessions/{id}/fuse`
Runs multimodal fusion combining transcript rating and biometric signals, calibrated against personal baseline z-scores.

**Request**: `{}` (Empty JSON body)
**Response (`HTTP 200 OK`)**:
```json
{
  "id": 1,
  "session_id": 14,
  "astronaut_id": 1,
  "composite_score": 3.42,
  "fused_scores": {
    "stress": 3.8,
    "fatigue": 4.5,
    "anxiety": 2.2,
    "low_mood": 1.5,
    "social_isolation": 2.0,
    "concentration_difficulty": 1.8
  },
  "z_scores": {
    "stress": 1.1,
    "fatigue": 1.7,
    "anxiety": -0.3,
    "low_mood": -0.8,
    "social_isolation": -0.5,
    "concentration_difficulty": -0.7
  },
  "channel_conflict": false,
  "conflict_notes": null,
  "baseline_confidence": "high",
  "alert_triggered": false,
  "created_at": "2026-11-14T21:45:00"
}
```

---

### 7. `GET /sessions/{id}/fusion`
Retrieves previously computed fusion result for a session.

---

### 8. `POST /sessions/{id}/end`
Concludes check-in and triggers the evidence-grounded psychological analyzer.

**Response (`HTTP 200 OK`)**:
```json
{
  "session_id": 14,
  "status": "completed",
  "scores": {
    "stress": 4,
    "low_mood": 2,
    "anxiety": 3,
    "fatigue": 5,
    "social_isolation": 2,
    "concentration_difficulty": 2
  },
  "evidence": {
    "fatigue": "Sleep was broken, about 5 hours reported",
    "stress": "Workload manageable with maintenance checklists"
  },
  "screening_answers": {
    "sleep_quality": 2,
    "stress_level": 1
  },
  "confidence": 0.91,
  "risk_flag": false,
  "notes": "Astronaut Sarah displays normal operational functioning with situational mild sleep fatigue."
}
```

---

### 9. `POST /sessions/{id}/companion`
Switches session to open companion mode.

**Response (`HTTP 200 OK`)**:
```json
{
  "session_id": 14,
  "mode": "companion",
  "message": "I'm right here with you, Commander Sarah. The official check-in is complete, and we can just talk freely now."
}
```

---

### 10. `GET /sessions/{id}`
Returns complete session details, full message history, analysis, task events, biometric signals, and fusion result.

---

### 11. `GET /astronauts/{id}/history`
Longitudinal array of all check-in sessions with scores, task events, and composite strain indices for dashboard trend charts.

---

### 12. `GET /dashboard/fused-latest`
Returns latest fused composite strain score for every crew member:
```json
[
  {
    "astronaut_id": 1,
    "name": "Dr. Sarah Al-Mansoor",
    "role": "Commander",
    "language": "en",
    "latest_session_id": 14,
    "composite_score": 3.42,
    "fused_scores": { "stress": 3.8, "fatigue": 4.5, "anxiety": 2.2, "low_mood": 1.5, "social_isolation": 2.0, "concentration_difficulty": 1.8 },
    "channel_conflict": false,
    "baseline_confidence": "high",
    "alert_triggered": false,
    "updated_at": "2026-11-14T21:45:00"
  }
]
```

---

### 13. `GET /dashboard/alerts`
Returns unhandled clinical or fusion alerts across all crew sessions.

---

### 14. `GET /dashboard/kb-usage`
Returns operational protocol chunks cited during companion support sessions.

---

### 15. `GET /kb/search`
Searches approved countermeasures with BM25 SQLite FTS5 ranking:
`GET /kb/search?q=breathing&topic=stress&severity=3.0&language=en`

---

### 16. `GET /health`
Returns system status, active database connection, and mock LLM mode status:
```json
{
  "status": "healthy",
  "database": "sqlite:///./astronaut_checkin.db",
  "mock_llm": true
}
```

---

### 17. `GET /sources`
Returns the complete verified scientific literature, screening instrument licenses, and open-source citations document (`SOURCES.md`):
```bash
curl http://localhost:8000/sources
```

---

## 5. Scientific Grounding, Screening Instruments & Ethics Notice

### Evidence-Based Knowledge Base
All 48 countermeasure protocols in the knowledge base are summarized from verified, peer-reviewed spaceflight literature and public-domain guidance from **NASA HRP/HRR**, the **World Health Organization (WHO)**, **NIMH**, **NHLBI**, and **CDC**.

### Public-Domain Screening Scales
Psychological tracking utilizes public domain clinical instruments:
- **PHQ-2 / PHQ-9** (Kroenke et al. 2001, 2003): Public domain, royalty-free.
- **GAD-2 / GAD-7** (Spitzer et al. 2006, Kroenke et al. 2007): Public domain, royalty-free.
- **PSS-10** (Cohen et al. 1983): Free for educational / non-commercial research use.
- **PVT-B** (Basner & Dinges 2011): Public experimental psychology reaction-time paradigm.

### Non-Diagnostic Clinical Boundary
> **CRITICAL ETHICAL DIRECTIVE**: The assistant is designed strictly as an operational **early-warning decision support tool** for long-duration spaceflight crews and ground medical support. It **never** issues psychiatric diagnoses, clinical labels, or medical/pharmacological prescriptions. At all times, the system provides supportive active listening, evidence-backed self-regulation exercises, and protocols for escalating persistent strain to the mission Flight Surgeon or clinical psychologist.

