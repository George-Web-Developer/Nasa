# Bio Astro Lab Multi-Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Bio Astro Lab into a 5-page **Orbital Observatory Photolithograph** (`#0F1114` Smoked Basalt -> `#EAE5DA` Archival Mineral Paper + `#D14D28` Vermilion) NASA Space Apps 2026 physiological & sensorimotor health platform with genuine GSAP/Lenis scroll choreography, NASA data integration, walk-tolerant 3D MediaPipe biomechanics + optical `rPPG` + visor face hologram, and zero fabricated demo telemetry.

**Architecture:** Vanilla ES/modular web app (`index.html`, `scan.html`, `decision.html`, `history.html`, `guide.html`) sharing `styles.css`, generated `nasa-data.js`, `ai-model.js` (`XGBoost v3.0.0`, 13 features), `app-shell.js` (persistent `localStorage`/`sessionStorage` state, cross-page nav, 6-protocol SOS modal, bilingual Bio-Copilot drawer), and `vision.js`. Verified end-to-end via `AI/verify_ai_system.py`, Chromium screenshots, and `impeccable detect`.

**Tech Stack:** HTML5, CSS3 (Custom Properties + Grid), Vanilla JavaScript, GSAP 3 + ScrollTrigger + Lenis Smooth Scroll (CDN on `index.html`), MediaPipe `tasks-vision@0.10.14` (ESM CDN in `vision.js`), Chart.js 4 (CDN on `history.html`), Python 3 (`AI/build_nasa_data.py`, `AI/verify_ai_system.py`).

**Spec:** `docs/superpowers/specs/2026-11-14-bio-astro-lab-redesign-design.md`

## Global Constraints
- **Palette Tokens (`styles.css`):** `--bg-void: #0F1114`, `--bg-elevated-dark: #171A1F`, `--bg-paper: #EAE5DA`, `--bg-paper-card: #F3EFE6`, `--border-dark: #2A2F38`, `--border-paper: #CFC8B8`, `--ink-light: #F2EEE4`, `--ink-dark: #17191E`, `--ink-muted-dark: #A3A097`, `--ink-muted-paper: #50535A`, `--accent-vermilion: #D14D28`, `--accent-nominal: #1C7C54`, `--accent-nominal-dark: #38B07B`, `--accent-amber: #C97A16`, `--accent-critical: #B82924`, `--ghost-slot-dark: #5E6269`.
- **Typography:** Display `Schibsted Grotesk`, Body `B612`, Mono `B612 Mono` (`tabular-nums`), Arabic fallback `Cairo`. Do not use `Inter`, `Space Grotesk`, `Space Mono`, `IBM Plex`, `DM Sans`, `Outfit`, or Tailwind CDN.
- **Anti-AI Craft Guardrails:** No glowing gradients, no heavy SaaS box-shadows, no fake progress rings, no emojis standing in for UI icons (`1.5px` stroke SVGs only), custom scrollbars, `:focus-visible` outlines, and `prefers-reduced-motion` bypass.
- **Data Integrity & `verify_ai_system.py` Invariants:** Never hardcode clinical threshold `if/else` strings (`evaluateClinicalSafetyGate`, `blood_glucose < 62`, `systolic_bp < 85`, `targetP2`, `lower.includes('blood pressure')`, `lower.includes('radiation')`, `Deterministic Clinical Safety Gate`) inside `ai-model.js`, `app-shell.js`, `scan.js`, or `decision.js`. Preserve exact `MODEL_FEATURES` order and `Float32` parity (`max |diff| < 1e-4` across 1,762 rows and 156+ boundary probes).
- **Zero Fabrication & Security:** Unmeasured optional fields remain `NaN`; denied/missing webcam never auto-starts fake data (synthetic demo requires explicit button click); HTML-escape all imported/rendered strings; neutralize CSV formula-injection leading characters (`=`, `+`, `-`, `@`, `\t`, `\r`).

## Review Focus
1. **Malicious/malformed CSV & OSDR uploads** (quoted fields, formula-injection cells `=CMD()`, missing/non-numeric vitals, wrong column casing) -> Pinned by unit assertions in Task 1 & Task 4 + upload test in Task 7.
2. **Denied or disconnected webcam** (`NotAllowedError` / headless Chromium without camera) -> Must render explicit diagnostic error, preserve `NaN` camera telemetry, and only simulate if user clicks explicit `Calibration Replay Demo (Synthetic)` -> Pinned in Task 5 & Task 7.
3. **Side-on walking turn & initial 2.5s calibration tremor** (`shoulderSpan / torsoLength < 0.24`, first 2.5s erratic frames) -> Must be gated/trimmed out cleanly by `vision.js` math without firing false asymmetric flags -> Pinned by Node/headless biomechanics math tests in Task 5.
4. **Direct navigation to `decision.html` with empty storage or invalid `BP`** -> Must fall back gracefully to editable readiness check / CTA back to `scan.html` without crashing `NaN` inspectors -> Pinned in Task 8 & Task 9.
5. **Cross-page environment persistence (`Lunar/Planetary Base`) & Arabic Bio-Copilot queries** -> Must carry selected habitat across routes and retrieve relevant NASA English docs from Arabic terms cleanly -> Pinned in Task 2, Task 4, and Task 9.

---

### Task 1: Generate Offline NASA Data Bundle (`AI/build_nasa_data.py` -> `nasa-data.js`)

**Files:**
- Create: `AI/build_nasa_data.py`
- Create: `nasa-data.js`
- Test: `AI/test_nasa_data.py`

**Interfaces:**
- Consumes: `database/nasa_knowledge_base.json`, `AI/data/nasa_training/osdr_inspiration4_crew_matrix.csv`
- Produces: `window.NASA_DATA_BUNDLE = { hazards, hrpRisks, bodySystems, emergencyProtocols, environments, missionPresets, inspiration4Sample }` (UMD/browser global + `module.exports` support for Node tests).

- [ ] **Step 1: Write failing test `AI/test_nasa_data.py`**
  Verify `nasa-data.js` executes cleanly via `node`, exposes `5` spaceflight hazards, `22` HRP risks, `5` body systems, `6` emergency protocols (including `hypoxia-dcs` and `sans-vision`), `4` habitat environments (`Space Station`, `Spacecraft`, `Rover`, `Lunar/Planetary Base`), and `>= 4` curated NASA mission test presets with valid numeric/NaN feature mappings.
- [ ] **Step 2: Run test to verify failure**
  Run: `python AI/test_nasa_data.py` — Expected: FAIL (`nasa-data.js` missing).
- [ ] **Step 3: Implement `AI/build_nasa_data.py` and run it to generate `nasa-data.js`**
  Read `database/nasa_knowledge_base.json` and `AI/data/nasa_training/osdr_inspiration4_crew_matrix.csv`; extract clean compact records, define the `4` environment baselines (`Space Station` default: `radiation_msv_day: 0.55`, `cabin_co2_mmhg: 2.3`, gravity `0g`), and emit deterministic `nasa-data.js`.
- [ ] **Step 4: Run test to verify pass**
  Run: `python AI/test_nasa_data.py` — Expected: PASS (`22 HRP, 5 Hazards, 5 Systems, 6 Protocols, 4 Environments, 4 Presets`).

---

### Task 2: Add Bilingual Term Retrieval Helper to `ai-model.js`

**Files:**
- Modify: `ai-model.js:325-372` (`queryBioCopilot` tokenizer only — zero edits to model weights, `predictTreeProbs`, `evaluateAstronautHealth`, or `CLINICAL_BIOMARKER_SCHEMA`)
- Test: `AI/test_bilingual_copilot.mjs`

**Interfaces:**
- Consumes: `window.NASA_KNOWLEDGE_DOCS` inside `ai-model.js`
- Produces: `expandBilingualTokens(queryText: string): string[]` (additive helper mapping Arabic queries via declarative `BILINGUAL_TERM_MAP` object before scoring `NASA_KNOWLEDGE_DOCS`). Zero `if/else` routing strings.

- [ ] **Step 1: Write failing test `AI/test_bilingual_copilot.mjs`**
  Assert `queryBioCopilot('مستوى الاشعاع في المحطة', nominalInput).matchedDocs.length > 0` matches radiation docs, and `queryBioCopilot('صداع و ضغط الدم', nominalInput).matchedDocs[0].text` relates to blood pressure / cephalic shift.
- [ ] **Step 2: Run test to verify failure**
  Run: `node AI/test_bilingual_copilot.mjs` — Expected: FAIL (Arabic query returns 0 keyword matches).
- [ ] **Step 3: Implement `BILINGUAL_TERM_MAP` and `expandBilingualTokens(queryText)` inside `ai-model.js`**
  Preserve Unicode Arabic tokens alongside `/[a-z0-9\u0600-\u06FF]+/` splitting and augment query tokens via declarative `Object.entries(BILINGUAL_TERM_MAP)` lookup.
- [ ] **Step 4: Run tests to verify pass + XGBoost parity check**
  Run: `node AI/test_bilingual_copilot.mjs` and verify `ai-model.js` remains parity-safe — Expected: PASS.

---

### Task 3: Author Orbital Observatory Photolithograph Design System (`styles.css`)

**Files:**
- Replace: `styles.css`
- Test: `impeccable detect styles.css --json` + CSS syntax/token validation

**Interfaces:**
- Produces: Shared CSS classes & CSS custom properties (`--bg-void`, `--bg-elevated-dark`, `--bg-paper`, `--bg-paper-card`, `--ink-light`, `--ink-dark`, `--accent-vermilion`, `--accent-nominal`, `--accent-nominal-dark`, `--accent-amber`, `--accent-critical`, `.basalt-hero`, `.paper-workspace`, `.topbar`, `.env-pill`, `.sos-btn`, `.mission-band`, `.vernier-track`, `.hud-stage`, `.toast-banner`, `.copilot-drawer`, `@media (prefers-reduced-motion)`).

- [ ] **Step 1: Write `styles.css`**
  Include Google Fonts import (`Schibsted Grotesk`, `B612`, `B612 Mono`, `Cairo`) with aerospace fallbacks, smoked basalt hero + camera HUD tokens (`#0F1114`), warm archival mineral paper workspace tokens (`#EAE5DA` / `#F3EFE6`), vernier 36px hairlines, responsive 5-page header & mobile menu, hologram SVG zone states (`nominal`, `caution`, `critical`), non-blocking toast styles, and `prefers-reduced-motion` rules.
- [ ] **Step 2: Validate anti-pattern & token audit**
  Run: `C:\Users\Dell\.gemini\config\skills\impeccable\scripts\impeccable.cmd detect styles.css --json` — Expected: zero anti-pattern flags (`Inter`/`glassmorphic`/`neon`).

---

### Task 4: Build Shared Shell, State Store, 6-Protocol SOS, CSV Safe Parser & Bilingual Copilot Drawer (`app-shell.js`)

**Files:**
- Create: `app-shell.js`
- Test: `AI/test_app_shell.mjs`

**Interfaces:**
- Consumes: `window.NASA_DATA_BUNDLE`, `window.evaluateAstronautHealth`, `window.queryBioCopilot`
- Produces: `window.BioShell = { getSession, saveSession, getHistory, appendHistory, resetHistoryToSeed, getEnvironment, setEnvironment, showToast, escapeHtml, sanitizeCsvCell, parseCsvTable, renderShellChrome, openEmergencyModal, selectEmergencySymptom }` synced via `localStorage` (`bioAstroLab.session.v1`, `bioAstroLab.history.v1`, `bioAstroLab.env.v1`, `bioAstroLab.footerCredits.v1`) and `sessionStorage['bioAstroLab.facePortrait']`.

- [ ] **Step 1: Write failing test `AI/test_app_shell.mjs`**
  Test XSS `escapeHtml`, CSV formula-injection `sanitizeCsvCell('=HYPERLINK("http://evil")')`, `parseCsvTable` quoted commas + Inspiration4 headers, plus history & environment round-trip persistence.
- [ ] **Step 2: Run test to verify failure**
  Run: `node AI/test_app_shell.mjs` — Expected: FAIL (`app-shell.js` not found).
- [ ] **Step 3: Implement `app-shell.js`**
  Implement unified basalt/paper header renderer, environment pill synced across routes, all **6 Emergency Protocols** sourced from `window.NASA_DATA_BUNDLE.emergencyProtocols`, non-blocking `#toastRegion`, persistent Bio-Copilot drawer styled in Orbital Observatory tokens with safe DOM rendering, and editable footer credit storage.
- [ ] **Step 4: Run test to verify pass**
  Run: `node AI/test_app_shell.mjs` — Expected: ALL assertions PASS.

---

### Task 5: Overhaul Computer Vision, Walking Gait Math, Optical `rPPG` & Visor Capture (`vision.js`)

**Files:**
- Replace/Refactor: `vision.js`
- Test: `AI/test_vision_math.mjs`

**Interfaces:**
- Consumes: Scan UI DOM IDs (`webcam`, `visionCanvas`, `startCameraBtn`, `stopCameraBtn`, `finishAnalyzeBtn`, `replayDemoBtn`, `scanModeWalkBtn`, `scanModeStaticBtn`, `scanDurationSelect`, `valPosture`, `badgePosture`, `valCoronalTilt`, `valSway`, `valJoint`, `badgeJoint`, `valJointDelta`, `valRepsCount`, `valFatigue`, `badgeFatigue`, `valEar`, `valBlinkStatus`, `valOpticalHr`, `badgeOpticalSqi`, `rppgWaveCanvas`, `applyOpticalHrBtn`, `hologramVisorImg`)
- Produces: Pure testable exports (`calculateAngle3D`, `RollingROMSymmetryTracker`, `isYawAngleGated`, `trimmedMean`, `computeChromBpm`, `captureFacePortraitDataUrl`) + `window.visionLab = { initVisionModels, startCamera, stopCameraStream, finishAndAnalyzeMotion, startCalibrationReplayDemo, setScanMode, setDuration, resetSessionMetrics, resetVisionUI }`.

- [ ] **Step 1: Write failing unit tests `AI/test_vision_math.mjs`**
  Assert: 3D angle invariance, zero lateral room-offset penalty, alternating walking gait bilateral ROM symmetry (`|ROM_L - ROM_R| < 2°` -> `'Balanced'`), side-on yaw turn exclusion (`< 0.24`), `trimmedMean` outlier rejection, and CHROM `72 BPM` sinusoidal signal recovery (`SQI >= 60%`).
- [ ] **Step 2: Run test to verify failure**
  Run: `node AI/test_vision_math.mjs` — Expected: FAIL.
- [ ] **Step 3: Refactor `vision.js` implementing all 6 CV fixes + optical `rPPG` + visor face crop**
  Implement real `worldLandmarks`, rolling `3.0s` bilateral ROM window, yaw exclusion gate, `2.5s` warmup discard + `trimmedMean`, pitch-aware EAR, `CHROM` pulse waveform + `SQI %` + `"Apply Optical HR"`, cranial `faceLandmarker` canvas capture into `sessionStorage['bioAstroLab.facePortrait']`, AND honest denied-webcam error state leaving metrics `NaN` unless user explicitly clicks `Calibration Replay Demo (Synthetic)`.
- [ ] **Step 4: Run test to verify pass**
  Run: `node AI/test_vision_math.mjs` — Expected: ALL assertions PASS.

---

### Task 6: Implement Editorial Homepage (`index.html`, `landing.js`)

**Files:**
- Rewrite: `index.html`
- Create: `landing.js`
- Verify Asset: `assets/astronaut-eva.png` + `assets/astronaut-eva.png.json`

**Interfaces:**
- Consumes: `assets/astronaut-eva.png`, `styles.css`, `nasa-data.js`, `app-shell.js`, CDN `gsap@3.12.5` + `ScrollTrigger` + `lenis@1.1.14`
- Produces: Orbital Observatory landing page anchored on `orbital_basalt_comp.png` / Comp 1 (`#0F1114` Smoked Basalt Hero transitioning cleanly on scroll to `#EAE5DA` Archival Mineral Paper `Physiological mission` section, live ghost telemetry slots reading real session data or explicit `NaN` dashes, `Enter Health Scan` vermilion CTA -> `scan.html`, GSAP/ScrollTrigger/Lenis horizontal right-to-left astronaut glide, project purpose & target crew cards, and editable multi-column footer).

- [ ] **Step 1: Write `index.html` matching Orbital Observatory Comp 1 geometry**
  Include basalt top rail, hero stage (`BIO ASTRO LAB`, concise briefing copy, `Enter Health Scan` `#D14D28` CTA, upload shortcut `scan.html?upload=1`, real telemetry + ghost `NaN` slots), `<img id="heroAstronaut" src="assets/astronaut-eva.png">` over `.vernier-track` (`SCROLL X -> 0.00`), `#EAE5DA` below-fold narrative band where the astronaut glides left beside `Physiological mission` capability cards, and editable `<footer>` persisted in `localStorage`.
- [ ] **Step 2: Write `landing.js`**
  Hydrate hero telemetry strictly from `BioShell.getSession()`/`getHistory()`, sync `Lenis` raf with `gsap.ticker` + `ScrollTrigger.update`, drive horizontal right-to-left glide choreography + `SCROLL X` vernier readout, handle `prefers-reduced-motion`, and persist footer credits.
- [ ] **Step 3: Capture Chromium screenshots (`scroll=0`, `scroll=550`, mobile `375x812`) and inspect via `read_file`**
  Expected: zero overlapping copy, crisp astronaut contrast over basalt & paper threshold, clean leftward glide motion.

---

### Task 7: Implement Multi-Stage Health Scan Workspace (`scan.html`, `scan.js`)

**Files:**
- Create: `scan.html`
- Create: `scan.js`

**Interfaces:**
- Consumes: `styles.css`, `nasa-data.js`, `ai-model.js`, `app-shell.js`, `vision.js`
- Produces: Complete Stage 1 (`13` inputs visible & grouped, habitat context banner, CSV/JSON/OSDR `FileReader` uploader + serum panel readout, 4 NASA presets) + Stage 2 (`Walk`/`Static` mode selector, `15s/30s/90s` duration, `#0F1114` basalt camera HUD, optical `rPPG` card + `Apply Optical HR`, live interactive Astronaut Body-System Hologram with cranial face crop, explicit `Calibration Replay Demo (Synthetic)` fallback) + navigation to `decision.html`. Exposes `window.app` compatibility hooks (`extractModelFeatures`, `parseBloodPressure`, `mapMoodToScore`, `runModelInference`, `goToStep`, `startNewCheckin`).

- [ ] **Step 1: Build `scan.html` semantic workspace**
  Retain every required verifier ID (`inputGlucose`, `inputBP`, `bpValidationError`, `inputTemp`, `inputSleep`, `inputHeartRate`, `inputRadiation`, `inputCO2`, `inputSpO2`, `sumPosture`, `valPosture`, `valJoint`, `valJointDelta`, `valFatigue`, `valEar`, `#telemetryFileInput`, NASA presets, `#0F1114` camera HUD, inline Hologram SVG w/ `#hologramVisorClip`).
- [ ] **Step 2: Implement `scan.js`**
  Implement real-time BP validation, `FileReader` handler using `BioShell.parseCsvTable` + JSON parsing for standard & Inspiration4 OSDR panels, NASA preset loader, Step 1 <-> Step 2 transition cleanly compatible with `?verify=1`, optical HR transfer (`#applyOpticalHrBtn`), visor face listener updating Hologram SVG, and Stage 2 -> `decision.html` handoff saving session into `BioShell.saveSession()`.
- [ ] **Step 3: Test Stage 1 file upload, presets, NaN preservation, and denied-webcam state in headless Chromium**
  Expected: OSDR CSV populates Glucose & reveals serum table; denied webcam surfaces explicit error leaving camera fields `NaN` unless user explicitly clicks synthetic demo button.

---

### Task 8: Build Decision/Inspector (`decision.html`, `decision.js`), History/Charts (`history.html`, `history.js`), & Explorer Guide (`guide.html`, `guide.js`)

**Files:**
- Create: `decision.html`, `decision.js`, `history.html`, `history.js`, `guide.html`, `guide.js`

**Interfaces:**
- Consumes: `styles.css`, `nasa-data.js`, `ai-model.js`, `app-shell.js`, CDN `chart.js@4.4.3` (in `history.html`)
- Produces:
  - `decision.html` + `decision.js`: Real `XGBoost` verdict (`#step3StatusBadge`), `#decisionRiskBadges`, 5-system Astronaut Hologram displaying captured stage-2 visor photo + bidirectional zone click inspector, SHAP `deltaRisk` waterfall bars + interactive what-if telemetry sliders (`reset to scanned baseline`), and `"Save to Mission History"` + toast feedback.
  - `history.html` + `history.js`: Real multi-series **Chart.js** canvas (`#vitalsChart`, plotted in Archival Carbon, Vermilion `#D14D28`, Emerald `#1C7C54`, Cobalt `#2B6CA3`) across 4 metric toggles, HTML-escaped `#historyTableBody`, formula-safe CSV Export/Import, and `"Reset to NASA Seed"`.
  - `guide.html` + `guide.js`: Live filter/search across 22 HRP risks, 5 RIDGE hazards, 5 Body Systems, and all 6 Emergency Protocols.

- [ ] **Step 1: Author `decision.html` and `decision.js` (with graceful empty-session handling)**
- [ ] **Step 2: Author `history.html` and `history.js` (with real Chart.js & CSV Export/Import)**
- [ ] **Step 3: Author `guide.html` and `guide.js` (with live search across 22 HRP / 5 RIDGE / 5 Systems / 6 Protocols)**
- [ ] **Step 4: Capture & inspect desktop + mobile Chromium renders for `decision.html`, `history.html`, and `guide.html`**
  Expected: Chart.js plots real curves cleanly, Hologram visor renders cleanly, zero console errors.

---

### Task 9: Update Verification Harness (`AI/verify_ai_system.py`), Retire Legacy `app.js`, Full End-to-End Audit & Final Gate

**Files:**
- Modify: `AI/verify_ai_system.py` (update static scan targets `[ai-model.js, app-shell.js, scan.js, decision.js, history.js]` and multi-page Step 5 E2E flow across `/index.html`, `/scan.html?verify=1`, `/decision.html?verify=1`, `/history.html?verify=1`, `/guide.html`, keeping 100% of parity, `NaN`, leakage, and boundary assertions intact)
- Remove: `app.js` (dead legacy monolithic file)

- [ ] **Step 1: Update `AI/verify_ai_system.py` static scan list and multi-page Chrome verification flow, and remove obsolete `app.js`**
- [ ] **Step 2: Run complete verification suite (`python AI/verify_ai_system.py`, `python AI/test_nasa_data.py`, `node AI/test_bilingual_copilot.mjs`, `node AI/test_app_shell.mjs`, `node AI/test_vision_math.mjs`)**
  Expected: ZERO failures across all 5 `verify_ai_system.py` passes + all unit tests.
- [ ] **Step 3: Run `impeccable detect` across HTML/CSS pages & inspect final screenshots of all 5 routes at desktop (`1440px`) and mobile (`375px`)**
- [ ] **Step 4: Dispatch fresh Final Code Review subagent (`superpowers:requesting-code-review`) over full Review Focus + ledger rulings, resolve any Critical/Important items in one TDD pass, re-verify suite green, and mark finish.**
