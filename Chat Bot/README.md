# Astronaut Daily Psychological Check-in Assistant 🚀🌌
**NASA Space Apps Challenge 2026 — Challenge: Health Monitoring Software**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/pytest-50%20passed-brightgreen.svg)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

A complete, production-grade, clinical-grade psychological check-in chatbot backend, multimodal biometric fusion engine, and embeddable Web Component HUD widget designed for astronauts on long-duration exploration spaceflights (Lunar Gateway, Mars transit). Built with **FastAPI**, **SQLAlchemy + SQLite/Postgres** (with SQLite FTS5 BM25 ranked search), **Pydantic v2**, a multi-provider **LLM Switch** (Anthropic Claude, Gemini, Groq, OpenRouter, Ollama), and an offline **Mock Mode** for rapid frontend development without an API key.

> [!IMPORTANT]
> **Clinical Non-Diagnostic Notice**: This system is designed as an early-warning behavioral health support and operational monitoring countermeasure tool. It **never** provides psychiatric diagnoses, medical prescriptions, or medication dosages. All data and physiological telemetry streams are simulated.

---

## 📋 Table of Contents
1. [Key Features](#-key-features)
2. [Project Architecture](#-project-architecture)
3. [Full Project Tree](#-full-project-tree)
4. [Quickstart (Teammate Setup in 2 Steps)](#-quickstart-teammate-setup-in-2-steps)
5. [Two Integration Modes](#-two-integration-modes)
6. [Embeddable HUD Widget Modes (`<astro-chat>`)](#-embeddable-hud-widget-modes-astro-chat)
7. [Host-Page Event Bridge Contract](#-host-page-event-bridge-contract)
8. [Task-Aware Check-in & Biometric Fusion](#-task-aware-check-in--biometric-fusion)
9. [Running Pytest Tests](#-running-pytest-tests)
10. [Packaging & Distribution](#-packaging--distribution)
11. [Documentation Links](#-documentation-links)

---

## ✨ Key Features
- **Adaptive 7-Turn Check-in Interviewer**: Tracks questions server-side across core operational dimensions (sleep, mood, workload/stress, social connection, focus/energy), weaves in standard 0-3 screening items naturally, delivers a kind closing summary after Question 7, and flags `session_should_end: true`.
- **Evidence-Grounded Psychological Analyzer**: Runs at `temperature: 0` upon session finalization. Ranks 6 core dimensions (`stress`, `low_mood`, `anxiety`, `fatigue`, `social_isolation`, `concentration_difficulty`) from 0 to 10 strictly based on direct transcript evidence quotes. Validated by Pydantic with automated retry logic.
- **Task-Aware Operation & Live Context**:
  - While a timed crew task is active (`phase: 'started'`), the bot answers user inquiries in one short sentence, avoids asking new screening questions, holds the next question in a pending queue, and releases it once `phase: 'ended'` arrives.
  - Gently references completed tasks without judging performance.
  - Strictly preserves privacy: signals summary is private context and never reveals raw numbers or labels like "your stress score is high" to the astronaut.
- **Multimodal Biometric Fusion & Baseline Calibration**:
  - Combines transcript evidence ratings, acoustic affect, facial markers, and wearable physiological telemetry.
  - Dynamically computes personal baseline Z-scores (requires ~5 sessions; flags 'low' confidence before that).
  - Flags channel conflicts when verbal reports diverge from sensor telemetry (e.g. stoic masking).
  - Triggers clinical alerts when composite strain deviation persists across 3 consecutive sessions.
- **RAG Knowledge Base with FTS5 BM25 Ranking**: Server-side tool calling loop (`search_knowledge_base`) querying approved protocols filtered by topic, astronaut language, and clinical severity. Enforces severity-based policy with automatic alerts.
- **Multi-Provider LLM Switch**: Unified client (`app/services/llm_client.py`) supporting Anthropic Claude and OpenAI-compatible providers (Gemini, Groq, OpenRouter, Ollama), with native tool calling and graceful server-side prompt RAG fallback.
- **Dual-Layer Crisis Safety Safeguards**: Active at all times (including during tasks). Scans user inputs in real time for crisis/self-harm keywords in both **English and Arabic**, and intercepts assistant output containing `[ESCALATE]`.
- **Database Namespace Isolation**: All 11 tables prefixed with `astro_` to prevent name collisions in shared databases. Lightweight versioned migrations runner (`astro_migrations`).

---

## 🏛️ Project Architecture
```mermaid
flowchart TD
    A["Frontend HUD Widget (<astro-chat>)"] -->|Window Events / REST| B["FastAPI Backend Router"]
    B --> C{"Crisis Safeguards"}
    C -->|Keyword Hit| D["Alert + Immediate Crisis Support"]
    C -->|Nominal| E{"Task Active?"}
    E -->|Yes (phase=started)| F["Hold Question in Queue + Brief Reply"]
    E -->|No / phase=ended| G{"Check-in or Companion?"}
    G -->|Check-in Mode| H["Interviewer (Turn Tracker <= 7)"]
    H -->|Question 7 Answered| I["Warm Summary + session_should_end=true"]
    I -->|POST /sessions/id/end| J["Analyzer (Temp=0, Strict JSON)"]
    J --> K["Multimodal Fusion & Baseline Calibration"]
    K --> L[("astro_fusion_results & astro_baselines")]
    G -->|Companion Mode| M["Companion Prompt + Context Windowing"]
    M --> N["Knowledge Retrieval (FTS5 BM25 or Server RAG)"]
    N --> O[("astro_kb_chunks & astro_kb_usage")]
```

---

## 📂 Full Project Tree
```text
astronaut-checkin/
├── .env.example                      # Default configuration (MOCK_LLM=true, no secrets)
├── run.bat                           # 1-click Windows runner (venv, install, seed, start)
├── run.sh                            # 1-click Linux/macOS runner
├── requirements.txt                  # Pinned dependencies
├── README.md                         # Project overview and architecture
├── seed.py                           # Seeds demo astronauts, baseline, past sessions, and KB
├── app/
│   ├── config.py                     # LLM Provider switch, DB_URL, CORS, API_TOKEN
│   ├── database.py                   # Engine configuration, SessionLocal, FTS5 triggers
│   ├── models.py                     # All tables prefixed with astro_ (People, Results, Knowledge)
│   ├── schemas.py                    # Pydantic v2 schemas and validation models
│   ├── prompts.py                    # Interviewer, Analyzer, and Companion prompts
│   ├── safety.py                     # Dual-layer safety & crisis keyword detection (EN & AR)
│   ├── main.py                       # Standalone service (Mode A), static file serving
│   ├── astro_router.py               # Modular router factory (Mode B) for FastAPI mounting
│   ├── migrations/
│   │   ├── runner.py                 # Versioned migration runner (astro_migrations)
│   ├── routers/
│   │   ├── sessions.py               # /sessions endpoints (start, end, companion, events, pending, signals, fuse)
│   │   ├── chat.py                   # /chat (task-aware interviewer & companion turns)
│   │   ├── astronauts.py             # /astronauts, /astronauts/{id}/history
│   │   ├── alerts.py                 # /alerts, /alerts/{id}/handle
│   │   ├── kb.py                     # /kb/search (FTS5 BM25 search)
│   │   └── dashboard.py              # /dashboard/fused-latest, /dashboard/alerts, /dashboard/kb-usage
│   └── services/
│       ├── llm_client.py             # LLM provider switch (Anthropic + OpenAI-compatible + Fallback RAG)
│       ├── llm_service.py            # Interviewer and companion conversational logic
│       ├── analyzer_service.py       # Evidence-grounded rater with single retry logic
│       ├── fusion_service.py         # Multi-channel weighted fusion & baseline calibration
│       ├── session_service.py        # Question counter, transcript builder, severity mapper
│       └── kb_service.py             # SQLite FTS5 BM25 search and audit logging
├── data/
│   ├── kb_seed_placeholder.json      # 16 approved placeholder protocols across 8 topics
│   └── resources/                    # NASA source documents
├── web/
│   ├── widget.js                     # Canonical Web Component <astro-chat> (floating/tab/inline)
│   ├── chatbot-demo.html             # Interactive demo page for teammate contract verification
│   └── chat-ui.html                  # Standalone full-page chat interface
├── scripts/
│   ├── simulate_signals.py           # Generates stable / stressed / exhausted telemetry scenarios
│   ├── kb_load.py                    # Loads approved chunks into database
│   └── package.py                    # Builds production-ready zip archive excluding secrets
├── docs/
│   ├── TEAMMATE_GUIDE.md             # Simple instructions for teammate embedding the widget
│   ├── INTEGRATION.md                # Full API endpoint reference with JSON payloads & Mode A/B
│   ├── DATABASE.md                   # Complete database schema documentation and ER diagram
│   └── PROJECT_STATUS.md             # Comprehensive architecture status & audit report
└── tests/
    ├── conftest.py                   # Pytest fixtures and isolated test DB
    ├── test_main.py                  # End-to-end check-in flow tests
    ├── test_safety.py                # Dual-layer safety tests
    ├── test_kb.py                    # Knowledge base FTS5 search tests
    ├── test_ingest.py                # Ingestion and chunk loader tests
    ├── test_tasks_and_context.py     # Task queueing, events, and context tests
    ├── test_fusion.py                # Multimodal fusion, baselines, and conflict tests
    ├── test_migrations.py            # Versioned migration and table prefix tests
    ├── test_router_module.py         # Mode B modular router tests
    └── test_llm_and_events.py        # LLM client abstractions, analyzer retry, widget tests
```

---

## 🚀 Quickstart (Teammate Setup in 2 Steps)

### Step 1: Start the Backend
- **Windows**: Double-click `run.bat` (or execute `run.bat` in Command Prompt / PowerShell).
- **Linux / macOS**:
  ```bash
  chmod +x run.sh && ./run.sh
  ```
The runner creates a virtual environment, installs pinned requirements, creates `.env` with `MOCK_LLM=true`, runs database migrations and seed data, and starts the server on `http://localhost:8000`.

### Step 2: Test the Interactive Demo
Open your browser to:
[http://localhost:8000/chatbot-demo.html](http://localhost:8000/chatbot-demo.html)
You will see:
- The 3 widget modes: **Floating** (corner launcher), **Tab** (embedded in mock dashboard), and **Inline**.
- Buttons to simulate starting and ending tasks (`astro:task`).
- A real-time Event Log panel capturing all dispatched `astro:*` window events.

---

## 🔌 Two Integration Modes

### Mode A: Standalone Service (Universal HTTP API)
Use this if your main website runs on Node.js/Express, Python Flask, React, Vue, or static HTML.
- Starts on port 8000.
- Serves the `web/` folder directly so camera and microphone permissions work over localhost.
- Configure CORS origins in `.env`: `ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173`.
- See [docs/INTEGRATION.md](docs/INTEGRATION.md) for full Axios and fetch code examples.

### Mode B: Modular Python Mount (`create_astro_router`)
Use this if your backend is built with FastAPI and you want to mount our entire engine as an `APIRouter` reusing your database:
```python
from fastapi import FastAPI
from app.astro_router import create_astro_router

app = FastAPI()
astro_router = create_astro_router(
    db_url="sqlite:///./my_mission_db.db",
    config={"mock_llm": True, "api_token": "optional-secret"}
)
app.include_router(astro_router, prefix="/api/astro")
```

---

## 🎨 Embeddable HUD Widget Modes (`<astro-chat>`)

Drop the widget into your webpage in 2 lines:

```html
<!-- Include Web Component -->
<script src="http://localhost:8000/widget.js" defer></script>

<!-- Mode 1: Floating Launcher in corner (remembers state, Esc closes) -->
<astro-chat mode="floating" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>

<!-- Mode 2: Tab Mode (fills 100% of parent container for dashboard tabs) -->
<div style="height: 600px;">
  <astro-chat mode="tab" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>
</div>

<!-- Mode 3: Inline Mode (normal document flow) -->
<astro-chat mode="inline" api-base="http://localhost:8000" astronaut-id="1" mission-day="42"></astro-chat>
```

---

## ⚡ Host-Page Event Bridge Contract

### Window Listeners (Send to Widget):
```javascript
// Timed task started/ended
window.dispatchEvent(new CustomEvent('astro:task', {
  detail: { task: 'Reaction Time Test', phase: 'started' }
}));

// Tab or page context
window.dispatchEvent(new CustomEvent('astro:context', {
  detail: { current_tab: 'vitals', note: 'Crew EVA preparation' }
}));

// Camera/mic numeric affect features
window.dispatchEvent(new CustomEvent('astro:signals-summary', {
  detail: { recent: { voice_stress_index: 0.35, face_fatigue_score: 0.28 } }
}));
```

### Window Dispatched Events (Receive from Widget):
- `'astro:session'`: detail `{ session_id, astronaut_id, mode }`
- `'astro:question'`: detail `{ session_id, index, text, ts }`
- `'astro:message'`: detail `{ role, text, ts, escalate }`
- `'astro:session-ended'`: detail `{ session_id, analysis_ready }`
- `'astro:escalate'`: detail `{ session_id, reason }`

### Global `window.AstroChat` API:
- `open()`, `close()`, `startSession()`, `endSession()`, `sendSystemNote(text)`, `getSessionId()`, `setContext(obj)`

---

## 🧪 Running Pytest Tests

Run the complete test suite (all 50 tests pass in ~2 seconds without requiring an API key):

```bash
pytest
```

---

## 📦 Packaging & Distribution

Build the self-contained `astro-chatbot.zip` shareable archive:

```bash
python scripts/package.py
```
Automatically excludes `.env`, `venv/`, `*.db`, and cache directories, and runs automated security pattern scanning to guarantee zero credentials or tokens are bundled.

---

## 📖 Documentation Links
- **[Teammate Guide](docs/TEAMMATE_GUIDE.md)**: Concise integration instructions for frontend and sensor teammates.
- **[Integration Reference](docs/INTEGRATION.md)**: Full API endpoint specification, request/response JSON schemas, and Node/Flask examples.
- **[Database Architecture](docs/DATABASE.md)**: Complete 3-group database schema, Mermaid ER diagram, and no-raw-media policy.
- **[Project Status Audit](docs/PROJECT_STATUS.md)**: Detailed audit report of components, tests, and capabilities.
