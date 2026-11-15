# AI Chatbot Integration & English UI Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- [ ] **Task 1: Configure & Initialize `Chat Bot/` FastAPI Backend**
  - Write `Chat Bot/.env` (`MOCK_LLM=true`, `ALLOWED_ORIGINS` with `:5500`, `:8000`, `:3000`, `:5173`).
  - Create `Chat Bot/venv`, install `requirements.txt`, run `python seed.py`, and run `pytest` in `Chat Bot/`.

- [ ] **Task 2: Add Optional Branding & Full-Page Expand Hook to `Chat Bot/web/widget.js`**
  - Add optional `title-text` and `full-page-href` attributes to `<astro-chat>`, preserving all existing behavior and tests.
  - Enhance offline backend error message inside `<astro-chat>` with clear instructions (`Chat Bot\run.bat`) and an event dispatch (`astro:offline-fallback`) so host pages can offer offline NASA RAG fallback.

- [ ] **Task 3: Update `app-shell.js` & `styles.css` (English-Only + Global Floating Chat + Host Bridge)**
  - Add `assistant.html` (`AI Assistant`) to `NAV_ROUTES`.
  - Remove `#globalLangToggle` and all visible Arabic strings in `app-shell.js`; default `getUiLang()` to `'en'`.
  - Mount `<astro-chat mode="floating" language="en" theme="dark" title-text="Mission AI Assistant" full-page-href="assistant.html" api-base="http://127.0.0.1:8000">` on non-assistant pages after loading `Chat Bot/web/widget.js` dynamically; keep `#copilotDrawer` available as an automatic offline fallback if port `8000` is unreachable (or in headless tests without `widget.js`).
  - Add `syncChatbotContext()` in `BioShell` mapping crew profile (`C001`/`C002`/`C003` -> astronaut IDs `1`/`2`/`3` while keeping `language="en"`), environment, and telemetry into `astro:context` & `astro:signals-summary`, plus forwarding to `POST /sessions/{id}/signals` when online.
  - Add CSS custom property theme overrides for `astro-chat` in `styles.css` + layout classes for `assistant.html`.

- [ ] **Task 4: Create Dedicated `assistant.html` & `assistant.js` + Wire `scan.js` / `decision.js` Events**
  - Create `assistant.html` and `assistant.js` with full-height `<astro-chat mode="tab">`, backend health indicator + retry button, crew & latest vitals card, and quick context actions.
  - Dispatch `astro:task` (`started`/`ended`) in `scan.js` during Stage 2 camera telemetry capture and sync telemetry context in `scan.js` / `decision.js`.

- [ ] **Task 5: End-to-End Verification (Live FastAPI + Chrome V8 + All Suites)**
  - Run `Chat Bot` pytest suite.
  - Run `AI/test_vision_math.py`, `AI/test_nasa_data.py`, `AI/test_bilingual_copilot.py`, `AI/test_app_shell.py`.
  - Update and run `AI/verify_ai_system.py` with live FastAPI backend on `127.0.0.1:8000` + frontend server, testing `assistant.html`, floating `<astro-chat>` across pages, `/sessions/start`, `/chat`, `/signals`, and English-only UI assertions.
