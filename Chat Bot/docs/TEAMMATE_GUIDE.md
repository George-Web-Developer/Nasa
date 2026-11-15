# 🚀 Astronaut Check-in Assistant — Teammate Integration Guide

Welcome! This guide is written for you (the teammate building the main website with camera/microphone affective analysis, dashboard tabs, and mission telemetry).

The chatbot provides structured psychological check-ins, companion support with RAG guidance, crisis detection safeguards, and full task-awareness.

---

## 📋 Table of Contents
1. [How to Run (One-Click Quickstart)](#1-how-to-run-one-click-quickstart)
2. [How to Add the Widget in 2 Lines (3 Modes)](#2-how-to-add-the-widget-in-2-lines-3-modes)
3. [Full Event Bridge Contract (Copy-Paste Examples)](#3-full-event-bridge-contract-copy-paste-examples)
4. [How to Use `session_id` in Your Camera/Mic `POST /sessions/{id}/signals`](#4-how-to-use-session_id-in-your-cameramic-post-sessionsidsignals)
5. [Task-Awareness Contract & How Tasks Pause the Bot](#5-task-awareness-contract--how-tasks-pause-the-bot)
6. [CSS Styling & Futuristic Medical HUD Variables](#6-css-styling--futuristic-medical-hud-variables)
7. [Troubleshooting & FAQ](#7-troubleshooting--faq)

---

## 1. How to Run (One-Click Quickstart)

The server runs out of the box with zero external configuration or paid API keys (`MOCK_LLM=true` is enabled by default).

### On Windows
Double-click `run.bat` in the project root folder (or run it from cmd/powershell):
```cmd
run.bat
```

What `run.bat` does automatically:
1. Detects Python (`python` or `py`).
2. Creates the `venv` virtual environment if not present.
3. Copies `.env.example` to `.env` (safe mock mode, no secrets).
4. Installs/updates dependencies from `requirements.txt`.
5. Initializes SQLite database and seeds demo astronauts and protocol chunks (`python seed.py`).
6. Starts FastAPI backend on **`http://localhost:8000`** with auto-reload.

### On macOS / Linux
```bash
chmod +x run.sh
./run.sh
```

### URLs at a Glance
- **Interactive Contract Demo Page**: [http://localhost:8000/chatbot-demo.html](http://localhost:8000/chatbot-demo.html)
- **Widget JS**: [http://localhost:8000/widget.js](http://localhost:8000/widget.js)
- **Interactive API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

> **Why run on port 8000?**  
> Running your HTML dashboard and the widget on `http://localhost:8000` satisfies modern browser security requirements for accessing user `navigator.mediaDevices.getUserMedia` (webcam and microphone permissions).

---

## 2. How to Add the Widget in 2 Lines (3 Modes)

The widget is an isolated, framework-free Web Component (`<astro-chat>`) styled with Shadow DOM so your host page CSS will never break it.

### Step 1: Include the script in your `<head>` or before `</body>`
```html
<script src="http://localhost:8000/widget.js"></script>
```
*(If your page is hosted on the same server, simply `<script src="/widget.js"></script>`)*.

### Step 2: Drop the `<astro-chat>` tag anywhere in your HTML:

#### A) Tab Mode (Inside your Dashboard Tabs)
Fills 100% of its parent container. Perfect for putting directly inside your dashboard's "Psychological Check-in" tab.
```html
<!-- Inside your tab pane div -->
<div id="checkinTabPane" style="width: 100%; height: 600px;">
  <astro-chat mode="tab" astronaut-id="1" mission-day="42"></astro-chat>
</div>
```

#### B) Floating Mode (Corner Launcher Button)
Adds a fixed round launcher in the bottom corner (bottom-right for English, bottom-left for Arabic RTL).
- Has an unread badge that notifies the astronaut when a new message arrives while minimized or closed.
- Automatically remembers open/closed state for the page session (`sessionStorage`).
- Pressing `Esc` closes the panel.
- Responsive and never blocks mobile navigation controls.
```html
<astro-chat mode="floating" astronaut-id="1" mission-day="42"></astro-chat>
```

#### C) Inline Mode (Regular Box in Document Flow)
A sleek, self-contained box with max-width 480px that flows naturally with your layout.
```html
<astro-chat mode="inline" astronaut-id="1" mission-day="42"></astro-chat>
```

### Supported Tag Attributes
| Attribute | Allowed Values | Default | Description |
|-----------|----------------|---------|-------------|
| `mode` | `"tab"`, `"floating"`, `"inline"` | `"inline"` | Display layout mode |
| `api-base` | URL string | `window.location.origin` | Backend URL (e.g. `http://localhost:8000`) |
| `astronaut-id`| Integer (`1`, `2`, ...) | `1` | `1` = Dr. Sarah (EN), `2` = Omar Al-Farooq (AR) |
| `mission-day` | Integer | `42` | Displays in HUD subtitle and logs session day |
| `language` | `"en"`, `"ar"`, `"auto"` | `"auto"` | Supports full Arabic RTL layout automatically |
| `theme` | `"auto"`, `"dark"`, `"light"` | `"auto"` | Futuristic dark HUD by default, adapts to system |

---

## 3. Full Event Bridge Contract (Copy-Paste Examples)

The widget communicates with your host website through standard browser `window` events (`bubbles: true`, `composed: true`).

### A) Events Your Website Can Send TO the Widget (`window.dispatchEvent`)

#### 1. Task Lifecycle Event (`astro:task`)
Tell the widget when a timed test begins or ends (e.g., reaction-time test, memory checklist, docking sim):
```javascript
// When your cognitive/reaction test STARTS:
window.dispatchEvent(new CustomEvent('astro:task', {
  detail: {
    task: 'Reaction Time Test',
    phase: 'started',
    info: { duration_sec: 90, trials: 30 } // optional extra details
  }
}));

// When your test ENDS:
window.dispatchEvent(new CustomEvent('astro:task', {
  detail: {
    task: 'Reaction Time Test',
    phase: 'ended',
    info: { average_latency_ms: 242, score: 95 }
  }
}));
```

#### 2. Host Context Event (`astro:context`)
Inform the chatbot about which dashboard tab the astronaut is currently looking at, or add situational notes:
```javascript
window.dispatchEvent(new CustomEvent('astro:context', {
  detail: {
    current_tab: 'vitals_dashboard',
    note: 'Astronaut just concluded a 2-hour spacewalk prep checklist.'
  }
}));
```

#### 3. Real-Time Telemetry / Signals Summary (`astro:signals-summary`)
Pass numeric affect summaries from your camera/mic ML analysis into the widget's context:
```javascript
window.dispatchEvent(new CustomEvent('astro:signals-summary', {
  detail: {
    recent: {
      voice_stress_index: 0.35,
      face_fatigue_score: 0.28,
      speech_rate_sps: 3.2,
      heart_rate_bpm: 68
    }
  }
}));
```

---

### B) Events Dispatched BY the Widget to Your Website (`window.addEventListener`)

Listen to these on `window` to coordinate your website's UI, camera recording, or data logging:

```javascript
// 1. Session Initialized
window.addEventListener('astro:session', (e) => {
  const { session_id, astronaut_id, mode } = e.detail;
  console.log(`[Host] Active Session ID: ${session_id} for astronaut ${astronaut_id}`);
  // Store session_id to attach to your camera/mic video recordings or telemetry calls!
  window.currentSessionId = session_id;
});

// 2. Each Assistant Question Asked
window.addEventListener('astro:question', (e) => {
  const { session_id, index, text, ts } = e.detail;
  console.log(`[Host] Question #${index} arrived: "${text}" at ${ts}`);
  // You can highlight a timeline marker in your camera recording graph here!
});

// 3. Every Message (User or Assistant)
window.addEventListener('astro:message', (e) => {
  const { role, text, ts, escalate } = e.detail;
  console.log(`[Host] New ${role} message (Escalate: ${escalate}): "${text}"`);
});

// 4. Session Ended & Analysis Ready
window.addEventListener('astro:session-ended', (e) => {
  const { session_id, analysis_ready } = e.detail;
  console.log(`[Host] Check-in ended for session ${session_id}. Analysis ready: ${analysis_ready}`);
  // You can trigger your dashboard to refresh its psychological trend chart here!
});

// 5. Emergency Safety Escalation Triggered
window.addEventListener('astro:escalate', (e) => {
  const { session_id, reason } = e.detail;
  console.warn(`[Host] ⚠️ CRITICAL ESCALATION in session ${session_id}: ${reason}`);
  // You can sound a calm audio alert or show ground support notification on your UI!
});
```

---

### C) Global JavaScript API (`window.AstroChat`)

The widget also exposes a global control API on `window.AstroChat`:

```javascript
// Open or un-minimize the chat window (floating mode)
window.AstroChat.open();

// Minimize or close the chat window (floating mode)
window.AstroChat.close();

// Start or restart a check-in session
window.AstroChat.startSession();

// End current session and trigger psychological analysis
window.AstroChat.endSession();

// Send an asynchronous note into the live context
window.AstroChat.sendSystemNote("Ground comm window closing in 10 minutes");

// Retrieve current active session ID (or null if not initialized)
const activeId = window.AstroChat.getSessionId();

// Update live context object directly
window.AstroChat.setContext({
  current_tab: "camera_module",
  note: "User calibrating mic gain"
});
```

---

## 4. How to Use `session_id` in Your Camera/Mic `POST /sessions/{id}/signals`

When your camera or microphone analysis module computes affective biomarkers (e.g. fundamental voice frequency, monotone speech index, facial action units, fatigue indices), you can associate them directly with the active session in the database.

### Step 1: Capture `session_id`
Capture it from the `astro:session` window event or call `window.AstroChat.getSessionId()`:
```javascript
const sessionId = window.AstroChat.getSessionId();
```

### Step 2: POST Telemetry to `/sessions/{id}/signals`
```javascript
async function sendBiometricSignals(signalsPayload) {
  const sessionId = window.AstroChat.getSessionId();
  if (!sessionId) {
    console.warn("No active session ID available yet.");
    return;
  }

  const response = await fetch(`http://localhost:8000/sessions/${sessionId}/signals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      signals: {
        voice_pitch_hz: 124.5,
        pitch_variability_semitones: 1.8,
        speech_rate_syllables_per_sec: 3.2,
        facial_action_units: { AU04: 0.2, AU12: 0.5 },
        facial_expressivity_index: 0.65,
        autonomic_heart_rate_bpm: 72
      }
    })
  });

  const result = await response.json();
  console.log("Telemetry signals saved successfully! ID:", result.id);
}
```

You can also fetch past signals for a session with `GET /sessions/{id}/signals`.

### Step 3: Trigger Multimodal Fusion (`POST /sessions/{id}/fuse`)
After check-in completes and your camera/mic signals are posted, trigger multi-channel fusion:
```javascript
const fusionResp = await fetch(`http://localhost:8000/sessions/${sessionId}/fuse`, {
  method: "POST"
});
const fusionData = await fusionResp.json();
console.log("Composite Strain Score:", fusionData.composite_score);
console.log("Channel Conflict Flag:", fusionData.channel_conflict);
console.log("Z-Scores:", fusionData.z_scores);
```
To populate the live crew status cards on your dashboard, simply call:
`GET http://localhost:8000/dashboard/fused-latest`

---

## 5. Task-Awareness Contract & How Tasks Pause the Bot

When an astronaut starts an intensive or timed task (like a reaction-time test or memory exercise):
1. **Host sends `'astro:task'` with `phase: 'started'`**:
   - The chatbot displays a glowing HUD task strip (`Active Task: [task] • Check-in paused`).
   - If the astronaut types anything into the chat, the bot **does not ask new questions**. Instead, it gives a warm 1-sentence reply:
     > *"Focus on your Reaction Time Test for now; we'll continue our check-in right after."*
   - The next scheduled question is **queued** on the server.
2. **Host sends `'astro:task'` with `phase: 'ended'`**:
   - The task banner updates to completed.
   - The widget automatically fetches the queued question from `GET /sessions/{id}/pending`.
   - The bot resumes the check-in and gently acknowledges the completed task without judging performance:
     > *"Glad you completed the Reaction Time Test. Returning to our check-in: [Question]"*
3. **Safety Layer is Never Paused**:
   - Even during an active task, if the astronaut expresses crisis or self-harm keywords, the dual safety safeguards trigger immediately (`escalate=True`, alert logged, and crisis support message delivered).

---

## 6. CSS Styling & Futuristic Medical HUD Variables

The widget is styled according to a **Futuristic Medical HUD** aesthetic (dark navy background, glowing cyan accents, glassmorphic panels with backdrop blur).

You can customize its appearance from your host page stylesheet by overriding CSS variables:

```css
/* Customizing <astro-chat> in your site's CSS */
astro-chat {
  --astro-bg: #050914;                   /* Background color */
  --astro-panel: rgba(14, 23, 42, 0.92); /* Glass panel fill */
  --astro-panel-border: rgba(0, 240, 255, 0.3); /* Border glow */
  --astro-accent: #00f0ff;               /* Cyan accent */
  --astro-accent-hover: #38bdf8;         /* Button hover */
  --astro-text: #f8fafc;                 /* Primary text */
  --astro-text-muted: #94a3b8;           /* Subtitle/timestamps */
  --astro-glow: 0 0 16px rgba(0, 240, 255, 0.25);
}
```

---

## 7. Troubleshooting & FAQ

### Q1: `python -m uvicorn` error or command not found
Make sure Python 3.10+ is installed and "Add Python to PATH" was checked during installation. Run `run.bat` which will automatically detect both `python` and `py`.

### Q2: Port 8000 already in use
If another service is using port 8000, you can run on another port (e.g. 8080):
```cmd
python -m uvicorn app.main:app --port 8080 --reload
```
And specify the base URL on the widget:
```html
<astro-chat api-base="http://localhost:8080" mode="tab"></astro-chat>
```

### Q3: CORS Issues if you run your frontend on Vite / React (port 3000 or 5173)
The backend is pre-configured with CORS for:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://localhost:8000`
- `http://127.0.0.1:*`

If your dev server is on a different port (e.g. 4200), add it to `ALLOWED_ORIGINS` in `.env`:
```ini
ALLOWED_ORIGINS=http://localhost:4200,http://localhost:3000,http://localhost:8000
```

### Q4: Camera / Microphone access blocked by browser
Browsers only allow camera/mic access on `https://` or `http://localhost:*`. Hosting your pages through this FastAPI server (`http://localhost:8000/web/...`) guarantees that camera and mic permissions work cleanly out of the box.

---

## 8. Scientific Sources, Knowledge Base & Non-Diagnostic Notice

For complete scientific citations, screening instrument terms of use, and software licenses, refer to [SOURCES.md](../SOURCES.md) or the live endpoint at `http://localhost:8000/sources`.

### Key Highlights for Your Presentation & NASA Submission:
1. **Verified Knowledge Base**: 48 practical, bilingual (English & Arabic) countermeasure chunks across 8 topics (`sleep`, `stress`, `anxiety`, `fatigue`, `isolation`, `mood`, `focus`, `escalation`) derived exclusively from verified publications from **NASA HRP**, **WHO**, **NIMH**, **NHLBI**, and **CDC**.
2. **Royalty-Free Screening Scales**: Conversational tracking adapts **PHQ-2** (depression screener) and **GAD-2** (anxiety screener), both developed with Pfizer educational grants and placed in the public domain. Reaction-time tracking models the **Brief Psychomotor Vigilance Task (PVT-B)** from Dinges & Basner (2011).
3. **Non-Diagnostic Policy**: This software serves as an operational decision-support tool. It never provides psychiatric diagnoses or pharmacological prescriptions; its role is early detection, evidence-backed self-regulation, and seamless escalation to the mission Flight Surgeon.
4. **Ready-to-Paste Resources Summary**: Available at the top of `SOURCES.md` for instant copy-pasting into the official NASA Space Apps submission form.

---

*NASA Space Apps Challenge 2026 — Astronaut Psychological Daily Check-in Assistant*
