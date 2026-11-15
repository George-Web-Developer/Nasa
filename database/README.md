# NASA Space Apps 2026 — Astronaut Health Monitoring Database & Training Data

Collected and structured from the official **2026 NASA Space Apps Challenge** resources page:
- Challenge Page: https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources
- NASA HRP 5 Hazards: https://www.nasa.gov/hrp/hazards/
- NASA HRP Risks of Human Spaceflight: https://www.nasa.gov/hrp/risks/
- NASA Ongoing HRP Research: https://www.nasa.gov/hrp/ongoing-hrp-research/
- NASA Human Research Roadmap (HRR): https://humanresearchroadmap.nasa.gov/
- Canadian Space Agency (CSA) — Monitoring Radiation for Astronaut Health (CANS): https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp
- Canadian Space Agency (CSA) — Why Conduct Science Experiments in Space & Human Body Effects: https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp
- NASA Open Science Data Repository (OSDR): https://osdr.nasa.gov/

---

## 1. Relational Database (`database/astronaut_health.db`) & Exports (`database/csv_exports/`)

Rebuilt reproducibly via `python database/build_nasa_database.py`.

| Table Name | Rows | Description |
| :--- | ---: | :--- |
| `challenge_spec` | 1 | Official challenge overview, objectives, indicators, and supported environments |
| `spaceflight_hazards` | 5 | NASA RIDGE 5 Hazards (`R` Radiation, `I` Isolation, `D` Distance, `G` Gravity, `E` Environments) |
| `nasa_hrp_elements` | 4 | NASA HRP research elements (HFBP, HHC, Space Radiation, ROI) |
| `nasa_hrp_risks` | 22 | All 22 official NASA HRP Spaceflight Risks with Risk Statements, Context, and Reference Summaries |
| `risk_drm_ratings` | 198 | Official Design Reference Mission (DRM) Likelihood x Consequence (LxC) ratings across LEO, Lunar, and Mars |
| `research_gaps` | 327 | NASA HRP Research Gaps (`GAP-ID`, code, title, URL) |
| `research_tasks` | 2,374 | NASA HRP Research Tasks (PI, HRP element, description, Task Book link) |
| `evidence_reports` | 71 | Direct links to official NASA HRP Evidence Report PDFs |
| `csa_resources` | 3 | CSA CANS neutron spectrometer & ISS human body effects articles |
| `clinical_indicators_thresholds` | 12 | Spaceflight vital/biomarker reference ranges, microgravity measurement protocols, and countermeasures |
| `body_systems_matrix` | 5 | Anatomical body regions mapped to NASA HRP Risks, indicators, and treatments |
| `emergency_protocols` | 6 | Acute spaceflight emergency checklists (`chest-pain`, `dizziness`, `balance-loss`, `radiation`, `hypoxia-dcs`, `sans-vision`) |
| `osdr_inspiration4_labs` | 1,084 | Real SpaceX Inspiration4 Crew CBC (`OSD-569`) & Comprehensive Metabolic Panel (`OSD-575`) lab results |
| `osdr_sans_ocular_metrics` | 1,830 | Real NASA OSDR Tonometry IOP (`OSD-583`, `OSD-679`) measurements for SANS research |
| `osdr_radiation_cardio_metrics` | 1,152 | Real NASA OSDR Radiation Echocardiography & Aorta Doppler (`OSD-435`) measurements |

Also exported as a unified JSON bundle for frontend / API / RAG consumption:
- `database/nasa_knowledge_base.json`

---

## 2. ML & AI Training Datasets (`AI/data/nasa_training/`)

Rebuilt reproducibly via `python AI/prepare_nasa_extended_dataset.py` and verified via `python AI/train_nasa_extended.py`.

| File | Rows | Purpose |
| :--- | ---: | :--- |
| `spaceflight_clinical_triage_train.csv` | 5,180 | 13-feature subject-disjoint training split (NHANES BP/HR/Glucose/Sleep + PhysioNet ICU/Balance + UCI Eye + OSDR Inspiration4 Glucose + NASA/CSA Radiation & CO2) |
| `spaceflight_clinical_triage_test.csv` | 1,296 | 13-feature subject-disjoint holdout test split (Verified Model: **91.44% accuracy, 0.8630 Macro F1**; Primary NASA Risk-Driver: **98.45% accuracy**) |
| `spaceflight_clinical_triage_dataset.csv` | 6,476 | Combined train+test dataset with `split` column |
| `osdr_inspiration4_clinical_labs.csv` | 1,084 | Real SpaceX Inspiration4 CBC + CMP lab dataset (`out_of_range`, `mission_phase`) |
| `osdr_inspiration4_crew_matrix.csv` | 28 | Wide joined CBC + CMP + Cardiovascular biomarker vectors per crew timepoint (`L-92` to `R+82`) |
| `osdr_radiation_cardio_ml.csv` | 1,152 | Real NASA OSDR `OSD-435` Radiation Type/Dose + Heart Rate + Echocardiography dataset |
| `osdr_sans_ocular_ml.csv` | 1,830 | Real NASA OSDR `OSD-583` + `OSD-679` Intraocular Pressure dataset |
| `osdr_sans_oct_retinal_ml.csv` | 599 | Real NASA OSDR `OSD-679` OCT Retinal & Choroidal Thickness dataset |
| `osdr_muscle_grip_ml.csv` | 595 | Real NASA OSDR `OSD-652` Grip Strength & Bodyweight unloading dataset |
| `nasa_hrp_copilot_rag_corpus.jsonl` | 375 | Structured Q&A / RAG knowledge corpus for Bio-Copilot & LLM grounding |
