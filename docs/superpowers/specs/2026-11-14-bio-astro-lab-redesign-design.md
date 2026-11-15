# Bio Astro Lab — Architectural & Visual Redesign Specification

**Date:** 2026-11-14
**Scope:** Multi-page web application (`index.html`, `scan.html`, `decision.html`, `history.html`, `guide.html`), visual design system (**Orbital Observatory Photolithograph — Comp 1**, user-selected `seed:0758ff23015f1428`), NASA Space Apps 2026 data integration, real client-side working capabilities (no fabricated demo metrics), and `vision.js` locomotion/rPPG/hologram overhaul.
**Related Specs/Records:** `PRODUCT.md`, `.impeccable/config.json`, `.impeccable/surfaces/index-html.md` (`seed:0758ff23015f1428`), `.impeccable/mocks/decision/assigned.png`, Chromium proof `orbital_basalt_comp.png`.

---

## 1. Visual World & Anti-AI Design System

**Direction:** *Orbital Observatory Photolithograph* (Code-first anchored directly on approved reference `.impeccable/mocks/decision/assigned.png` and verified Chromium preview `orbital_basalt_comp.png`).
Rejects generic dark-navy/indigo neon SaaS styling in favor of archival NASA/JPL photolithographic contrast and aerospace instrument legibility:

- **Color Palette (Tokens in `styles.css`):**
  - `--bg-void`: `#0F1114` (Smoked basalt opening Hero plate, `.hud-stage` optical camera viewport, calibration frames)
  - `--bg-elevated-dark`: `#171A1F` (Dark basalt panels, hairline border `#2A2F38`)
  - `--bg-paper`: `#EAE5DA` (Warm archival mineral paper across Editorial body below fold & interior data workspaces)
  - `--bg-paper-card`: `#F3EFE6` (Muted elevated mineral surface on paper workspaces, hairline border `#CFC8B8`)
  - `--bg-pill-dark`: `#181B20` (Basalt header selector pill, border `#363C46`) | `--bg-pill-paper`: `#E2DDD0`
  - `--grid-dark`: `rgba(255, 255, 255, 0.03)` | `--grid-paper`: `rgba(23, 25, 30, 0.055)` (`36px` precision vernier hairline ruling)
  - `--ink-dark`: `#17191E` (High-contrast carbon ink on paper surfaces, >= 12:1 contrast)
  - `--ink-light`: `#F2EEE4` (Primary bone ink on basalt surfaces)
  - `--ink-muted-paper`: `#50535A` | `--ink-muted-dark`: `#A3A097`
  - `--accent-vermilion`: `#D14D28` (Oxide safety vermilion — primary CTAs, active nav underline, SOS triggers, acute attention; hover `#B63E1C`)
  - `--accent-amber`: `#C97A16` (Cautionary clinical monitoring state — Tier 2)
  - `--accent-nominal`: `#1C7C54` on paper / `#38B07B` on dark (Chlorophyll telemetry green — Nominal readiness state / `SCAN READY` — Tier 1)
  - `--accent-critical`: `#B82924` (Emergency hazard state — Tier 3)
  - `--ghost-slot-dark`: `#5E6269` / `--ghost-slot-paper`: `rgba(23, 25, 30, 0.35)` (Deliberate subtle placeholder ticks for `NaN` / unmeasured metrics)
- **Typography (Google Fonts aerospace voices + local fallbacks):**
  - **Display & UI Sans:** `Schibsted Grotesk` (sharp architectural grotesque, weights `600/700/800`) paired with `B612` (avionics cockpit legibility designed with Intactile Design for Airbus)
  - **Numeric & Coordinate Mono:** `B612 Mono` (strictly for measurements, dates, clinical coordinates, units, `tabular-nums`) — paired with `Cairo` fallback for Arabic UI copy & Bio-Copilot responses.
- **Anti-Pattern Guardrails (`craft-floor.md`):**
  - Zero glowing gradient text, zero frosted glassmorphic bloat cards, zero fake progress rings, zero heavy SaaS drop-shadows, and zero emojis standing in for icons (consistent `1.5px` vector SVG iconography only).
  - Custom themed scrollbars, `:focus-visible` outlines (`--accent-vermilion`), text selection styling, and reduced-motion fallbacks (`prefers-reduced-motion`).

---

## 2. Multi-Page Architecture (5 Dedicated Routes)

Instead of cramming all consoles inside hidden CSS tabs on one screen, the application splits cleanly by mission stage while preserving zero-build vanilla deployment and shared cross-page `localStorage` state:

1. **`index.html` — Mission Overview & Editorial Landing (`experience` mode)**
   - **Slim Top Avionics Rail (`#0F1114` Smoked Basalt):** `BIO ASTRO LAB` mark, 5 route links (`Overview`, `Health Scan`, `AI Triage`, `History`, `NASA Guide`) with `#D14D28` vermilion active rule, global **Mission Environment Selector** (`Space Station` default, `Spacecraft`, `Rover`, `Lunar/Planetary Base`), and `#D14D28` `SOS` button.
   - **Hero Plate (`#0F1114` Smoked Basalt):**
     - Left Zone: Oversized `BIO ASTRO LAB` bone masthead (`#F2EEE4`), autonomous mission overview copy, primary `Enter Health Scan` vermilion CTA (`#D14D28` -> `scan.html`) + `Upload CSV / JSON Panel ->` shortcut, and live telemetry readout strip displaying either saved station metrics or deliberate unmeasured `NaN` ghost slots (`#5E6269`, never fabricated).
     - Right Zone: **NASA Public-Domain EVA Spacesuit Asset** (`assets/astronaut-eva.png`, `637x1415` alpha cutout of NASA Artemis III asset `axemu-prada-spacesuit-mockup-20241007-423`, metadata stored in `assets/astronaut-eva.png.json`) hovering inside subtle orbital trajectory hairlines over a horizontal vernier track (`SCROLL X -> 0.00`).
   - **GSAP 3 + ScrollTrigger + Lenis Smooth Scroll Choreography:**
     - `Lenis` raf synced cleanly with `gsap.ticker` and `ScrollTrigger.update` (`prefers-reduced-motion` skips motion cleanly keeping legible static layout).
     - Scrolling past Hero seamlessly glides the astronaut horizontally leftward across the briefing threshold into the mineral editorial band (`Physiological mission`) while capability cards settle underneath.
   - **Mineral Archival Body (`#EAE5DA`) & Structured Multi-Column Footer:**
     - Column-ruled Purpose & Target Audience blocks (`NASA Dataset Telemetry`, `Kinematic & Visor Scan`, `Offline Clinical Decision`, `Target Crew & Habitats`) plus direct launch strip to `scan.html`.
     - Partitioned multi-column footer containing Navigation Links, NASA Grounded Sources (`HRP Risks`, `OSDR Inspiration4`, `CSA Radiobiology`), and cleanly marked **editable user slots** (`Crew / Team Name`, `Mission Cohort / Institution`, `Repository / Contact URL`) persisted in `localStorage`.

2. **`scan.html` — Stage 1 Diagnostics/Upload + Stage 2 Live Camera & Hologram (`operate` mode)**
   - **Mission Environment Selector & Context Strip (`#EAE5DA` Paper Workspace with compact `#0F1114` stage header):** Lets astronaut switch `Space Station` (default — microgravity, ~0.55 mSv/d LEO baseline), `Spacecraft`, `Rover`, or `Lunar/Planetary Base` (partial-g, ~1.4 mSv/d GCR baseline), showing environment-aware baseline context cleanly without mutating user inputs.
   - **Stage 1 — Vitals Inputs + File Upload + NASA Mission Presets:**
     - **All 13 `MODEL_FEATURES` directly exposed and logically grouped:** Blood Glucose (`mg/dL`), Blood Pressure (`Sys/Dia mmHg`), Core Temp (`°C`), Heart Rate (`bpm`), SpO2 (`%`), Sleep (`hrs`), Mood State (`1-5` discrete scale), Radiation Dose (`mSv/day`), Cabin `ppCO2` (`mmHg`). Unmeasured optional fields stay `""` -> true `NaN`.
     - **Real File Uploader (`CSV / JSON`)**: Reads glucometer, wearable, or **NASA OSDR Inspiration4 CSV (`osdr_inspiration4_crew_matrix.csv` format)** files locally via `FileReader`, populates mapped vitals (`glucose_value_milligram_per_deciliter`), and renders additional serum panels (`Albumin`, `CRP`, `WBC`, `Hemoglobin`) in an expandable table.
     - **NASA Mission Test Presets:** One-click buttons for `Inspiration4 C001 Post-Flight (Nominal)`, `ISS Sleep/Stress Fatigue`, `SPE Solar Radiation Event`, `Elevated Cabin CO2 / Hypoxia`.
   - **Stage 2 — Re-Engineered Live Camera Scan + Experimental Optical `rPPG` + Astronaut Body Hologram:**
     - **Scan Mode Selector:** `Dynamic Walk / Locomotion` (3.0s rolling bilateral gait ROM symmetry + 3D `worldLandmarks` + yaw exclusion) vs `Static Posture / Squat` (static alignment + squat counter).
     - **Duration Selector:** `15s` (Quick Check) / `30s` (Standard) / `90s` (NASA Full).
     - **Split Live Scan Canvas (`#0F1114` Basalt HUD) + Interactive Hologram (`#F3EFE6` Card / Dark Visor Frame):**
       - Left/Main: Webcam `<video>` + crisp bone/ocular overlay `<canvas>` + optical `rPPG` live pulse wave + **SQI % badge** (`Experimental Optical Heart Rate — Hold Steady 8s` with manual `"Apply Optical HR"` button).
       - Right/Interactive: **Astronaut Body-System Hologram SVG** reacting dynamically to joint angles, balance sway, cranial alertness, and embedding the user's **live cropped face portrait inside the helmet visor slot** upon calibration lock.
     - **Zero-Fabrication Hardware Fallback:** If webcam access is denied/unavailable, surfaces explicit error reason, keeps camera metrics `NaN` on skip, or requires clicking an explicitly labeled **`Calibration Replay Demo (Synthetic)`** button—never silently spoofing green fake lockouts.

3. **`decision.html` — AI Triage, Body-System Hologram & Live Telemetry Inspector (`operate` mode)**
   - **Verdict Header & Readiness Score (`0-100`):** Driven exclusively by `window.evaluateAstronautHealth()` (`XGBoost v3.0.0`, `13` features).
   - **Captured Face Astronaut Body-System Hologram:** Mounts Stage 2 cranial visor portrait (or neutral wireframe avatar if camera skipped) onto anatomical body map displaying real statuses across NASA's **5 Body Systems (`body_systems_matrix.csv`)**; clicking any zone highlights linked risk factors.
   - **Live AI Telemetry Inspector:** Real-time waterfall bars showing each feature's `deltaRisk` contribution + interactive tuning sliders right on `decision.html` to test how shifting any of the 13 inputs shifts `XGBoost` probabilities & clinical safety gates without mutating stored check-ins unless saved.
   - **Save to Mission History:** Appends entry persistently into `localStorage` (`bioAstroLab.history.v1`), shows non-blocking status toast (no `alert()`), and links directly to `history.html`.

4. **`history.html` — Persistent Mission Telemetry & Real `Chart.js` Analytics (`operate` mode)**
   - Replaces empty `initChartCanvas()` grid with real multi-series **Chart.js** charts plotted in Archival Mineral & Vermilion/Emerald/Cobalt ink across 4 selectable metrics (`Readiness Score`, `Glucose & Blood Pressure`, `Radiation & CO2`, `Balance & Sleep`).
   - Full HTML-escaped telemetry table, formula-injection-safe `"Export CSV"`, `"Import CSV"`, and `"Reset to NASA Reference Seed"`.

5. **`guide.html` — Grounded NASA Knowledge Base & All 6 Emergency Protocols (`operate/read` mode)**
   - Backed by generated `nasa-data.js` exported directly from `database/nasa_knowledge_base.json`.
   - Live search & category filter across NASA's **22 HRP Risks**, **5 RIDGE Spaceflight Hazards**, **5 Body Systems**, and **all 6 Emergency Protocols** (`chest-pain`, `dizziness`, `balance-loss`, `radiation`, `hypoxia-dcs`, `sans-vision`), mirrored cleanly inside the global `#D14D28` `SOS` modal.
   - **Global Persistent Bio-Copilot Drawer** available on workspace routes: enhanced `queryBioCopilot()` adds declarative bilingual Arabic-to-English lookup dictionary (`BILINGUAL_TERM_MAP`) before scoring the 48 `NASA_KNOWLEDGE_DOCS` (zero hardcoded `if/else` chains, keeping `verify_ai_system.py` green!).

---

## 3. Biomechanics & Computer Vision Overhaul (`vision.js`)

Replaces all 6 root causes of false abnormal flags during walking/movement:

1. **3D Metric Coordinates (`worldLandmarks`):** Prefer `PoseLandmarker`'s `worldLandmarks[0]` (metric 3D meters) for shoulder tilt, hip tilt, and knee/elbow joint flexion/extension (`calculateAngle3D`), eliminating 2D aspect-ratio foreshortening distortion. Scale 2D fallback horizontal coordinates by `videoWidth / videoHeight`.
2. **No Camera-Center Offset Penalty:** Remove `Math.abs(midShoulderX - 0.5) * 80` so shifting laterally across the room never lowers posture score. Normalize postural sway strictly as mid-shoulder relative to mid-hip horizontal offset normalized by shoulder width.
3. **Walking Gait Tolerance (`Rolling Bilateral ROM Symmetry`):**
   - In `Dynamic Walk / Locomotion` mode, keep a `3.0s` sliding buffer of left/right knee & elbow angles.
   - Compute bilateral peak-to-valley Range of Motion (`ROM_L = max(L) - min(L)`, `ROM_R = max(R) - min(R)`). Healthy alternating gait produces high instantaneous phase delta (`25-45°`) but near-zero **ROM amplitude difference (`|ROM_L - ROM_R| < 6°`)**, eliminating false `Asymmetric` walking alerts.
   - Smooth minor step-phase tilt variation via 1.5s EMA baseline.
4. **Yaw / Turn Exclusion Gate:** Compute apparent shoulder width normalized by torso height (`shoulderSpan / torsoLength`). Frames where the subject rotates near side-on (`ratio < 0.24`) or landmark visibility `< 0.55` are tagged `angleGated = true` and excluded from final asymmetry aggregation instead of exploding `atan2`.
5. **Trimmed-Median Session Finalization:** Discard initial `2.5s` calibration warmup samples, strip outlier top/bottom 10% transient spikes (`trimmedMean`), and grade overall `balanceScore`, `jointSymmetryDiff`, `avgEAR`, and tier flags strictly from the trimmed distribution — never allowing a single transient frame (`includes('Asymmetric')`) to invalidate the entire session.
6. **Pitch-Aware EAR + Experimental Optical `rPPG` + Face Visor Capture:**
   - Gate fatigue `EAR` drops only when forward face alignment pitch is within nominal bounds.
   - Compute experimental forehead/cheek skin ROI `CHROM` bandpass (`0.75-3.0 Hz`) BPM + spectral SNR `SQI %`, pausing cleanly under locomotion (`SQI < 55%`).
   - Extract centered high-clarity canvas face crop into `sessionStorage['bioAstroLab.facePortrait']` when landmarks lock cleanly.

---

## 4. Shared Architecture, Files & Verification Contract

- **Files Planned:**
  - `assets/astronaut-eva.png` + `assets/astronaut-eva.png.json` (NASA PD Artemis III image `axemu-prada-spacesuit-mockup-20241007-423`, alpha cutout)
  - `styles.css` (Orbital Observatory Photolithograph tokens: `#0F1114` Smoked Basalt, `#EAE5DA` Archival Mineral Paper, `#D14D28` Vermilion, `#1C7C54`/`#38B07B` Nominal, `B612`/`Schibsted Grotesk`/`B612 Mono`/`Cairo`)
  - `nasa-data.js` + generator script `AI/build_nasa_data.py`
  - `app-shell.js` (shared `localStorage`/`sessionStorage` state, cross-page nav rail, environment selector, 6-protocol SOS modal, bilingual Bio-Copilot drawer, toast system, CSV/XSS security helpers)
  - `index.html` + `landing.js` (GSAP 3 + ScrollTrigger + Lenis Smooth Scroll astronaut right-to-left glide choreography, editorial purpose cards, editable multi-column footer)
  - `scan.html` + `scan.js` (Stage 1 all-13 inputs + CSV/JSON/OSDR file parser + NASA presets + Stage 2 Camera/Walk/Static/Duration controls + Hologram HUD + `window.app` compatibility hooks)
  - `decision.html` + `decision.js` (AI evaluation UI, 5-system Astronaut Hologram w/ visor portrait, Live Telemetry Inspector `deltaRisk` sliders)
  - `history.html` + `history.js` (Real `Chart.js` multi-metric trends + persisted table + CSV import/export + NASA seed reset)
  - `guide.html` + `guide.js` (Live filterable NASA 22 HRP risks / 5 RIDGE hazards / 5 Body Systems / 6 Protocols explorer)
  - `vision.js` (3D `worldLandmarks`, Rolling Gait ROM, Yaw gating, Trimmed-Median finalization, CHROM `rPPG` w/ `SQI`, cranial portrait capture, honest no-camera state)
  - `ai-model.js` (Add declarative `BILINGUAL_TERM_MAP` helper inside `queryBioCopilot` — preserving 100% XGBoost v3.0.0 weights, schemas, and `Float32` parity `< 1e-4`)
  - `AI/verify_ai_system.py` (Update static scan & Step 5 E2E harness for multi-page routes preserving all 1,762 parity checks, 156+ boundary probes, leakage checks, and zero-if-else rules; retire legacy monolithic `app.js`)
