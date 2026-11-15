# Bio Astro Lab — AI Chatbot Integration & English Normalization Spec

**Date:** 2026-11-15  
**Scope:** Integrate the standalone FastAPI + Web Component AI Chatbot (`Chat Bot/`) into the Bio Astro Lab web application (`index.html`, `scan.html`, `decision.html`, `history.html`, `guide.html`, plus new `assistant.html`), while ensuring the entire website UI is strictly English (`en`).

---

## 1. User Goals & Requirements
1. **Whole Website in English:** Remove Arabic UI toggles/chips (`#globalLangToggle`, `(EN / AR)` labels, Arabic quick chips) and lock `<astro-chat>` to `language="en"`.
2. **Friendly Mission Naming:** Present the chatbot as **`AI Assistant`** (`assistant.html`) / **`Mission AI Assistant`** instead of clinical-sounding psychological labels.
3. **Dual Placement (Page + Corner Box):**
   - **Dedicated Page (`assistant.html`):** Accessible from the primary navigation bar (`Mission | Scan | Decision | History | NASA Guide | AI Assistant`), rendering `<astro-chat mode="tab">` full-height with live backend status, crew/habitat context, and latest scanned vitals.
   - **Floating Corner Box (Bottom-Right on All Other Pages):** Render `<astro-chat mode="floating">` in the bottom-right corner on `index.html`, `scan.html`, `decision.html`, `history.html`, and `guide.html`, with a one-click expand link to `assistant.html` and offline fallback if the FastAPI server (`http://127.0.0.1:8000`) is stopped.
4. **LLM Mode:** Start configured with `MOCK_LLM=true` in `Chat Bot/.env` (zero API key required), with `ALLOWED_ORIGINS` opened for local static dev ports (`5500`, `8000`, `3000`, `5173`) and easy drop-in support for Gemini/Groq later.
5. **Biometric & Host Event Bridge:** Forward `BioShell` crew profile, habitat, active route, latest vitals (`astro:signals-summary`, `astro:context`), and Stage 2 camera scan lifecycle (`astro:task`) into `<astro-chat>`.

---

## 2. File Changes
- **Created:**
  - `Chat Bot/.env` (from `.env.example`, adding `:5500` origins, `MOCK_LLM=true`)
  - `assistant.html` & `assistant.js` (dedicated full-page AI Assistant interface + backend health check + vitals summary + `<astro-chat mode="tab">`)
- **Modified:**
  - `Chat Bot/web/widget.js` — add optional `title-text` and `full-page-href` attributes so Bio Astro Lab displays `"Mission AI Assistant"` and an `"Expand ↗"` link in floating mode without breaking existing contracts/tests.
  - `app-shell.js` — add `assistant.html` to `NAV_ROUTES`, remove `#globalLangToggle` and visible Arabic copy, mount `<astro-chat mode="floating">` on non-assistant routes (keeping `#copilotToggleBtn`/`#copilotDrawer` cleanly hidden unless offline fallback is triggered or widget script is unavailable), and implement `syncChatbotContext()` + `astro:task` bridge.
  - `styles.css` — theme overrides for `astro-chat` (`--astro-bg`, `--astro-accent`, etc.) and `.assistant-*` layout classes.
  - `scan.js` — dispatch `astro:task` (`started`/`ended`) around Stage 2 camera capture and `syncChatbotContext()` on telemetry updates.
  - `AI/verify_ai_system.py` — update header assertion (no `#globalLangToggle`, verify `AI Assistant` nav item and `<astro-chat>` mounting, plus verify `assistant.html`).
