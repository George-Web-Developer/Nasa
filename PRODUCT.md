# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Multi-page vanilla web application (semantic HTML, Tailwind/custom CSS design tokens, modular ES/vanilla JavaScript) with GSAP 3 + ScrollTrigger + Lenis for homepage scroll choreography, Chart.js for mission telemetry trends, MediaPipe Tasks Vision (`PoseLandmarker` + `FaceLandmarker`) for browser computer vision, and pure-JS physiological triage model (`ai-model.js`) for offline inference—no build bundler required while maintaining E2E parity with `AI/verify_ai_system.py`.

## Users

Astronaut crew members (and flight-surgeon / analog crew researchers) aboard a space station, transit spacecraft, surface rover, or lunar/planetary habitat conducting autonomous physical and sensorimotor health checks under delayed or absent Earth telemetry links.

## Product Purpose

Deliver a truthful, zero-fabrication autonomous health monitoring and triage platform aligned with the NASA Space Apps 2026 Challenge (`Health Monitoring Software`). The product lets crew members choose or track their mission environment (`Space Station` by default, or `Spacecraft`, `Rover`, `Lunar/Planetary Base`), manually enter or upload self-collected physical diagnostics (e.g., glucometer blood glucose, blood pressure, core temperature, sleep, mood, heart rate, SpO2, personal radiation dosimetry, cabin ppCO2, or Inspiration4-compatible CSV/JSON logs), complete a live calibrated webcam movement & ocular scan with an interactive astronaut body-system hologram mapped to their own portrait, review transparent on-device AI readiness triage, persist historical mission logs with real trend charts, query an Arabic/English NASA HRP AI Bio-Copilot, and access field emergency protocols offline.

## Positioning

On-device spaceflight autonomy combining a verifiable 13-feature physiological classifier (calibrated across NHANES, PhysioNet ICU/Balance, OpenML ocular data, and NASA OSDR Inspiration4 CMP crew glucose) with locomotion-aware 3D `worldLandmarks` gait kinematics, honest SQI-gated optical `rPPG` pulse estimation, live portrait-mapped physiological hologram feedback, and strict non-fabrication guarantees when sensors are absent.

## Operating Context

- Dedicated multi-page architecture separated by mission stage:
  1. Homepage (`index.html`): Smooth GSAP + ScrollTrigger + Lenis entry story introducing the system, featuring an astronaut visual starting on the right and gliding left on scroll alongside descriptive copy, project purpose/target cards, and a cleanly partitioned editable footer.
  2. Check-in & Scan (`scan.html` or primary check-in route): Environment selector (`Space Station` default), Stage 1 manual vitals + CSV/JSON upload (13 trained model features + Inspiration4 crew lab panel preview), and Stage 2 live webcam scan supporting both `Static Posture / Squat` and `Dynamic Walk / Locomotion` modes, configurable duration (`15s` / `30s` / `90s`), optical `rPPG` with signal-quality gating, and an interactive astronaut body hologram capturing the user's face portrait.
  3. AI Decision (`decision.html`): Tier triage, readiness score, NASA HRP risk drivers, Live AI Telemetry Inspector (`deltaRisk` per-feature attributions), and interactive body-system status overlay.
  4. Mission History (`history.html`): `localStorage`-persisted mission entries across check-ins, real Chart.js telemetry trend plots, and injection-safe CSV export.
  5. NASA Reference Guide & Emergency Triage (`guide.html` + global SOS modal + floating Bio-Copilot drawer): Searchable NASA HRP 22 risks, 5 RIDGE spaceflight hazards, 5 body systems matrix, 6 complete emergency protocols, and bilingual RAG chatbot over 48 NASA knowledge documents.
- Offline mission requirement: AI inference, RAG lookup, guide data, and history work locally without external cloud APIs during communication blackouts.

## Capabilities and Constraints

- Verified ML parity: Preserves float parity (`< 1e-4`) and schema escalation integrity tested by `AI/verify_ai_system.py` across Full-13, Legacy-9, and No-Webcam partial vectors.
- Strict non-fabrication: Unmeasured optional/webcam features MUST pass `NaN` rather than guessed defaults; absent or blocked webcam shows honest hardware diagnostics (synthetic replay available only when explicitly selected and labeled as calibration replay); rodent OSDR data (`OSD-435`, `OSD-652`, `OSD-679`) remains quarantined from human clinical inference.
- Locomotion-safe kinematics: `vision.js` MUST use aspect-ratio/3D `worldLandmarks` correction, rolling gait-window ROM symmetry in walking mode, camera-center independence, yaw-turn filtering, and trimmed-median session aggregation rather than latching a single outlier frame.
- Honest optical pulse (`rPPG`): Forehead/cheek skin reflectance pulse estimation MUST compute Signal Quality Index (`SQI`), pause/warn under motion or poor lighting, and clearly disclose optical approximation limits versus a clinical cuff/oximeter.
- Open content slots to preserve for user completion: Footer team credits, mission patch/organization attribution, and external repository/contact links will use clean structured placeholders ready for the user to fill.

## Brand Commitments

- Name: `Bio Astro Lab`
- Rejection of generic AI visuals: Must avoid default AI blue/purple dark-neon SaaS aesthetics; typography, color strategy, layout, and motion must feel authentic, editorial/instrument-grade, and tailored through dedicated craft rather than canned templates.
- Homepage scroll motion: Astronaut figure on the right glides smoothly toward the left on scroll (GSAP ScrollTrigger + Lenis feel) while supporting copy and purpose/target cards unfold below, closing with a well-structured footer.
- Motion & interactivity across workspaces: Live holographic body-system feedback and crisp transitions rather than lifeless static forms.

## Evidence on Hand

- `database/astronaut_health.db` & `database/nasa_knowledge_base.json`: 15 SQLite tables / 12 JSON tables including 12 NASA clinical indicator bands, 22 HRP risks, 5 RIDGE spaceflight hazards, 5 body-system mappings, and 6 emergency protocols (`hypoxia-dcs` and `sans-vision` exist in `database/csv_exports/emergency_protocols.csv` but were missing in the previous HTML UI).
- `AI/data/nasa_training/osdr_inspiration4_crew_matrix.csv`: 28 longitudinal lab rows for SpaceX Inspiration4 crew `C001`–`C004` (`L-92` through `R+194`) covering serum glucose and full CBC/CMP/immune panels.
- `ai-model.js`: Trained physiological triage model (92.57% test accuracy, Macro F1 0.9264) + 48 `NASA_KNOWLEDGE_DOCS` for RAG.
- `AI/verify_ai_system.py`: Automated Chromium V8 + Python parity & E2E audit harness (will require selector/route alignment if tabs split across multiple HTML pages).
- Current implementation absences to replace with working behavior: empty `initChartCanvas()` grid, volatile RAM-only history, `alert()` save popup, hidden 4 extended inputs & missing `envSelect` HTML control, fake silent `Simulated Fallback` camera output, English-only Copilot token splitter, and missing file-upload parser for blood/wearable logs.

## Product Principles

1. **Zero Fabrication**: Every score, chart curve, AI explanation, and optical sensor reading must come from real measurements, explicit `NaN` handling, or clearly labeled calibration tests—never decorative placeholders.
2. **Environment-Aware Autonomy**: Adapt context and baseline guidance to the crew member's active environment (`Space Station` default, switchable anytime) while functioning offline during comms blackouts.
3. **Human-Movement Tolerance**: Computer vision biomechanics must respect natural walking gait and camera perspective rather than penalizing healthy motion.
4. **Live Visceral Feedback**: Surface complex 13-feature physiology through clear visual body-system mapping, real trend charts, and fluid purposeful motion instead of dense wall-of-text tabs.
