"""
build_nasa_database.py
Builds the normalized SQLite database (database/astronaut_health.db),
JSON knowledge base (database/nasa_knowledge_base.json), and CSV exports
(database/csv_exports/) from all scraped NASA Space Apps 2026 Challenge
resources (NASA HRP, Human Research Roadmap, CSA, and NASA OSDR datasets).
"""
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_SCRAPED = BASE_DIR / "raw_scraped"
OSDR_RAW = BASE_DIR / "nasa_osdr_raw"
CSV_EXPORTS = BASE_DIR / "csv_exports"
CSV_EXPORTS.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "astronaut_health.db"
JSON_KB_PATH = BASE_DIR / "nasa_knowledge_base.json"


# Curated structured clinical indicator & countermeasure reference mapped directly
# to NASA HRP Risks, 5 Hazards (RIDGE), and Bio Astro Lab telemetry features.
CLINICAL_INDICATORS = [
    {
        "indicator_code": "BLOOD_GLUCOSE",
        "name": "Blood Glucose (Fasting / Pre-Post Exercise)",
        "unit": "mg/dL",
        "app_feature_key": "blood_glucose",
        "nominal_range": "70 - 99",
        "caution_range": "62 - 69 or 100 - 189",
        "critical_threshold": "< 62 or > 190",
        "microgravity_effect": "Unloading of postural muscles (soleus/quadriceps) reduces GLUT4-mediated glucose uptake and induces spaceflight-associated insulin resistance.",
        "measurement_in_space": "Finger-prick micro-glucometer or wearable continuous interstitial glucose sensor; verified via Inspiration4 CMP (OSD-575).",
        "primary_hazard": "Gravity Fields",
        "linked_risk_ids": "176,180,95",
        "countermeasure": "Daily high-intensity ergometer + ARED resistance workouts; balanced low-glycemic spaceflight nutrition; hydration check.",
    },
    {
        "indicator_code": "BLOOD_PRESSURE",
        "name": "Arterial Blood Pressure (Systolic / Diastolic)",
        "unit": "mmHg",
        "app_feature_key": "systolic_bp,diastolic_bp",
        "nominal_range": "95-120 / 60-80",
        "caution_range": "85-94 or 121-159 / 52-59 or 81-99",
        "critical_threshold": "SBP < 85 or > 160; DBP < 52 or > 100",
        "microgravity_effect": "Cephalad fluid shift (1.5-2 L from legs to thorax/head) raises upper-body vascular pressure in orbit and causes post-flight orthostatic intolerance.",
        "measurement_in_space": "Oscillometric arm cuff held strictly at heart level while stationary for 60s; Doppler ultrasound for jugular flow.",
        "primary_hazard": "Gravity Fields",
        "linked_risk_ids": "179,105,95",
        "countermeasure": "Lower Body Negative Pressure (LBNP) device, fluid-loading electrolyte protocol before re-entry, aerobic cycling.",
    },
    {
        "indicator_code": "HEART_RATE",
        "name": "Resting Heart Rate",
        "unit": "bpm",
        "app_feature_key": "heart_rate_bpm",
        "nominal_range": "55 - 90",
        "caution_range": "45-54 or 91-115",
        "critical_threshold": "< 45 or > 120 (at rest)",
        "microgravity_effect": "Cardiac remodeling, reduced plasma volume (10-15%), and altered autonomic baroreflex sensitivity increase arrhythmia/tachycardia risk.",
        "measurement_in_space": "12-lead ECG, chest-strap telemetry, or optical PPG wearable; linked to radiation cardiac studies (OSD-435).",
        "primary_hazard": "Gravity Fields",
        "linked_risk_ids": "179,180,168",
        "countermeasure": "Daily cardiovascular ergometer conditioning, electrolyte balance, 12-lead ECG uplink during chest pain/palpitations.",
    },
    {
        "indicator_code": "CORE_TEMP",
        "name": "Core Body Temperature",
        "unit": "°C",
        "app_feature_key": "body_temp",
        "nominal_range": "36.2 - 37.3",
        "caution_range": "35.5-36.1 or 37.4-38.2",
        "critical_threshold": "< 35.4 or > 38.3",
        "microgravity_effect": "Absence of convective cooling and sweat pooling causes 'Space Fever' (+0.5 to +1.0°C baseline elevation during exercise/rest).",
        "measurement_in_space": "Temporal artery forehead thermometer or ingestible telemetry pill.",
        "primary_hazard": "Hostile/Closed Environments",
        "linked_risk_ids": "85,80,175",
        "countermeasure": "Increase cabin airflow fans, liquid-cooling ventilation garment (LCVG) during EVA, check infection/latent viral reactivation.",
    },
    {
        "indicator_code": "SPO2",
        "name": "Blood Oxygen Saturation (SpO2)",
        "unit": "%",
        "app_feature_key": "spo2_pct",
        "nominal_range": "95 - 100",
        "caution_range": "91 - 94",
        "critical_threshold": "< 90",
        "microgravity_effect": "Mild hypoxemia risks during EVA prebreathe, decompression events, or Lunar/Mars reduced-pressure habitat atmospheres (8.2 psi / 34% O2).",
        "measurement_in_space": "Fingertip pulse oximetry + cabin PPO2/CO2 ECLSS telemetry.",
        "primary_hazard": "Hostile/Closed Environments",
        "linked_risk_ids": "173,168,84",
        "countermeasure": "Immediate supplemental O2 (4 L/min), verify cabin O2/CO2 scrubbers, screen for decompression sickness (DCS) symptoms.",
    },
    {
        "indicator_code": "SLEEP_DURATION",
        "name": "Daily Sleep Duration & Circadian Alignment",
        "unit": "hours/day",
        "app_feature_key": "sleep_hours",
        "nominal_range": "6.5 - 8.5",
        "caution_range": "4.5 - 6.4",
        "critical_threshold": "< 4.5",
        "microgravity_effect": "16 orbital sunrises/sunsets per 24h, cabin noise, CO2 pockets, and workload shifts cause chronic sleep debt and circadian desynchronization.",
        "measurement_in_space": "Wrist actigraphy, sleep logs, and PVT cognitive reaction testing.",
        "primary_hazard": "Isolation and Confinement",
        "linked_risk_ids": "100,99,101",
        "countermeasure": "Blue-enriched morning / amber evening solid-state lighting, sleep-station airflow fans, CBT-I & scheduled wind-down.",
    },
    {
        "indicator_code": "BEHAVIORAL_MOOD",
        "name": "Behavioral Health & Mood Score (PHQ-9 / Stress Scale)",
        "unit": "1-4 scale (1=Optimal, 4=Severe)",
        "app_feature_key": "mood_score",
        "nominal_range": "1",
        "caution_range": "2 - 3",
        "critical_threshold": "4",
        "microgravity_effect": "Prolonged isolation, confinement, crew friction, and communication delay (>22 min one-way to Mars) elevate anxiety, depression, and cognitive fatigue.",
        "measurement_in_space": "Self-report mood check-ins, speech/facial affect biomarkers, and computerized cognitive batteries.",
        "primary_hazard": "Isolation and Confinement",
        "linked_risk_ids": "99,101,175",
        "countermeasure": "Private family audio/video conferences, autonomous psychological support tools, workload balancing, structured recreation.",
    },
    {
        "indicator_code": "SENSORIMOTOR_BALANCE",
        "name": "Postural Stability & Sensorimotor Balance Score",
        "unit": "% (0-100)",
        "app_feature_key": "balance_score",
        "nominal_range": "82 - 100",
        "caution_range": "62 - 81.9",
        "critical_threshold": "< 62",
        "microgravity_effect": "Otolith unloading and proprioceptive reweighting cause space motion sickness in orbit and severe postural ataxia upon gravity transitions (Moon/Mars/Earth).",
        "measurement_in_space": "Computerized MediaPipe Pose sway kinematics, tandem walk, and sit-to-stand balance tests.",
        "primary_hazard": "Gravity Fields",
        "linked_risk_ids": "88,167,84",
        "countermeasure": "Vestibular adaptation exercises, handrail anchoring, Promethazine for acute SMS, sensorimotor reconditioning before EVA.",
    },
    {
        "indicator_code": "JOINT_SYMMETRY",
        "name": "Bilateral Joint Kinematics Symmetry Difference",
        "unit": "degrees",
        "app_feature_key": "joint_symmetry_diff",
        "nominal_range": "0.0 - 4.5",
        "caution_range": "4.6 - 13.0",
        "critical_threshold": "> 13.0",
        "microgravity_effect": "Asymmetric musculoskeletal deconditioning, EVA suit shoulder/hand strain, or intervertebral disc swelling (spinal elongation) causes kinematic asymmetry.",
        "measurement_in_space": "Real-time pose landmark joint angle symmetry (left vs right shoulder, hip, knee) via onboard camera.",
        "primary_hazard": "Gravity Fields",
        "linked_risk_ids": "180,78,77,84",
        "countermeasure": "Balanced ARED resistance loading, spinal decompression stretching, EVA suit fit verification.",
    },
    {
        "indicator_code": "OCULAR_EAR_SANS",
        "name": "Ocular Fatigue (EAR) & SANS Neuro-Ocular Status",
        "unit": "EAR ratio / IOP mmHg",
        "app_feature_key": "facial_ear",
        "nominal_range": "EAR >= 0.235 | IOP 10-21 mmHg",
        "caution_range": "EAR 0.195 - 0.234",
        "critical_threshold": "EAR < 0.195 or IOP > 22 mmHg / acute visual acuity drop",
        "microgravity_effect": "Headward fluid shift elevates intracranial/choroidal pressure, causing optic disc edema, globe flattening, choroidal folds, and hyperopic shift (SANS).",
        "measurement_in_space": "FaceMesh Eye Aspect Ratio (EAR) for fatigue + In-flight OCT, Fundoscopy, Tonometry IOP, and ocular ultrasound (OSD-583/679).",
        "primary_hazard": "Gravity Fields",
        "linked_risk_ids": "105,100",
        "countermeasure": "LBNP fluid redistribution, B-vitamin/one-carbon metabolic supplementation, corrective Space Anticipation Glasses, OCT tracking.",
    },
    {
        "indicator_code": "RADIATION_EXPOSURE",
        "name": "Space Radiation Dose Rate & Cumulative Exposure (GCR / SPE / Neutrons)",
        "unit": "mSv / day (or mSv cumulative)",
        "app_feature_key": "radiation_dose_msv",
        "nominal_range": "< 1.0 mSv/day (LEO ~0.4-0.8 mSv/day)",
        "caution_range": "1.0 - 10.0 mSv/day (Deep space GCR ~1.5-2.0 mSv/day)",
        "critical_threshold": "> 50 mSv/hr (SPE Solar Particle Event) or > 600 mSv career limit",
        "microgravity_effect": "GCR high-Z/energy ions and secondary neutrons (~30% of ISS dose per CSA CANS) damage DNA, elevate lifetime cancer risk, and injure CNS/cardiovascular tissue.",
        "measurement_in_space": "Active dosimeters (RAD), CSA Canadian Active Neutron Spectrometer (CANS), Radi-N2 bubble detectors, crew personal badges.",
        "primary_hazard": "Space Radiation",
        "linked_risk_ids": "96,179,105",
        "countermeasure": "Retreat to Aft Water Wall / polyethylene storm shelter during SPE, abort EVA within 8 min, log personal dosimeter rates.",
    },
    {
        "indicator_code": "CABIN_CO2",
        "name": "Cabin CO2 Partial Pressure (ppCO2)",
        "unit": "mmHg",
        "app_feature_key": "cabin_co2_mmhg",
        "nominal_range": "< 2.0",
        "caution_range": "2.0 - 3.9",
        "critical_threshold": ">= 4.0",
        "microgravity_effect": "Closed ECLSS habitats accumulate CO2 pockets around crew without airflow, causing headaches, cognitive impairment, hypercapnia, and exacerbating SANS.",
        "measurement_in_space": "Continuous ECLSS CO2 infrared analyzers + transcutaneous pCO2 monitoring.",
        "primary_hazard": "Hostile/Closed Environments",
        "linked_risk_ids": "82,105,173,99",
        "countermeasure": "Verify CDRA/amine scrubber status, maximize sleep-station ventilation fans, inspect filters for lunar/martian dust.",
    },
]

BODY_SYSTEMS_MATRIX = [
    {
        "body_region": "Brain, Eyes & Vestibular (Head)",
        "nasa_risk_ids": "105,88,99,100,173",
        "hazards": "Gravity Fields, Space Radiation, Isolation and Confinement, Hostile/Closed Environments",
        "key_conditions": "Spaceflight-Associated Neuro-ocular Syndrome (SANS), Vestibular Ataxia / Space Motion Sickness, Cognitive/Sleep Decrement, Hypercapnia",
        "measurable_indicators": "Eye Aspect Ratio (EAR), Intraocular Pressure (IOP), OCT Retinal/Choroidal Thickness, Sleep Hours, Mood Score, Balance Score",
        "prevention_and_treatment": "In-flight OCT & tonometry, LBNP fluid shift countermeasures, circadian lighting, Promethazine for acute SMS, CO2 scrubbing.",
    },
    {
        "body_region": "Cardiovascular & Circulatory (Chest)",
        "nasa_risk_ids": "179,168,173,96",
        "hazards": "Gravity Fields, Space Radiation, Hostile/Closed Environments",
        "key_conditions": "Orthostatic Intolerance, Cardiac Remodeling, Venous Thromboembolism (Jugular Stasis), Radiation-Induced CVD, Decompression Sickness",
        "measurable_indicators": "Systolic/Diastolic BP, Resting Heart Rate, 12-Lead ECG, SpO2, Echocardiography, Serum CRP/Fibrinogen",
        "prevention_and_treatment": "Daily aerobic ergometer + resistance exercise, pre-landing fluid loading, LBNP, Doppler jugular ultrasound, O2 prebreathe before EVA.",
    },
    {
        "body_region": "Musculoskeletal & Spine (Torso & Limbs)",
        "nasa_risk_ids": "77,180,78,84,167",
        "hazards": "Gravity Fields, Distance from Earth",
        "key_conditions": "Bone Mineral Density Loss (1-1.5%/month), Muscle Atrophy, Intervertebral Disc Herniation/Back Pain, EVA Joint Injury",
        "measurable_indicators": "Bilateral Joint Symmetry Diff, Posture Balance Score, Grip/Muscle Force, Vitamin D & Calcium, Serum ALP",
        "prevention_and_treatment": "ARED high-load resistive exercise (2+ hrs/day), bisphosphonates/Vitamin D, balanced protein nutrition, spinal unloading stretches.",
    },
    {
        "body_region": "Immune, Blood & Metabolic (Systemic)",
        "nasa_risk_ids": "85,80,176,96,177",
        "hazards": "Space Radiation, Isolation and Confinement, Hostile/Closed Environments, Distance from Earth",
        "key_conditions": "Immune Dysregulation & Latent Viral Reactivation, Insulin Resistance, Altered Drug Pharmacokinetics, Radiation Carcinogenesis",
        "measurable_indicators": "Blood Glucose, Body Temp ('Space Fever'), WBC/Lymphocyte/Neutrophil CBC, Metabolic Panel (CMP), Cytokines, Radiation mSv",
        "prevention_and_treatment": "In-flight CBC/CMP blood/saliva/urine assays, radiation shielding/storm shelters, microbiome hygiene, stability-tested medical formulary.",
    },
    {
        "body_region": "Renal & Hydration (Abdomen)",
        "nasa_risk_ids": "81,176",
        "hazards": "Gravity Fields, Hostile/Closed Environments",
        "key_conditions": "Renal Stone Formation (Hypercalciuria from bone resorption + dehydration)",
        "measurable_indicators": "BUN, Creatinine, eGFR, Serum/Urine Calcium, Daily Hydration Volume",
        "prevention_and_treatment": "Potassium citrate prophylaxis, >= 2.5 L/day fluid intake, renal ultrasound monitoring.",
    },
]

EMERGENCY_PROTOCOLS = [
    {
        "protocol_id": "chest-pain",
        "title": "Acute Protocol: Coronary & Angina Triage",
        "badge": "CODE RED - CRITICAL",
        "nasa_risk_id": "179",
        "trigger_condition": "Acute chest pain, resting HR > 120 bpm, SBP > 180 or < 85 mmHg",
        "steps_json": json.dumps([
            "Halt all physical exercise (ergometer/ARED) immediately and secure crew member in sleep station harness.",
            "Deploy Clinical Medical Pack Alpha: Initiate 12-lead ECG telemetry stream to Flight Surgeon console.",
            "Administer supplemental oxygen via oral-nasal mask at 4 L/min.",
            "Verify astronaut has not consumed sildenafil or PDE-5 inhibitors; prepare chewable Aspirin 325 mg.",
            "Maintain direct voice link with Houston Flight Surgeon on Air-to-Ground 1 (or autonomous protocol if Mars comms delay > 5 min).",
        ]),
    },
    {
        "protocol_id": "dizziness",
        "title": "Acute Protocol: Presyncope & Orthostatic Instability",
        "badge": "URGENT - TIER 2",
        "nasa_risk_id": "179",
        "trigger_condition": "Presyncope, SBP < 90 mmHg, post-landing/gravity transition dizziness",
        "steps_json": json.dumps([
            "Secure astronaut in supine position with feet elevated to alleviate cephalic hypoperfusion.",
            "Administer 1.0 L oral electrolyte rehydration solution within 60 minutes.",
            "Check continuous blood pressure cuff every 5 minutes for postural hypotension.",
            "Verify cabin CO2 levels on ECLSS sensor (ensure < 2.5 mmHg partial pressure).",
            "Activate lower-body compression garment / LBNP countermeasure if transitioning gravity fields.",
        ]),
    },
    {
        "protocol_id": "balance-loss",
        "title": "Acute Protocol: Vestibular Ataxia & Otolith Decompensation",
        "badge": "OBSERVATION",
        "nasa_risk_id": "88",
        "trigger_condition": "Balance score < 62%, joint asymmetry > 13°, acute vertigo/nausea",
        "steps_json": json.dumps([
            "Anchor crew member to primary handrails to prevent rotational tumble and head impact.",
            "Restrict rapid head movements in pitch and yaw axes (mitigate Coriolis effect).",
            "Administer Promethazine 25mg IM or oral if accompanied by active space motion sickness (SMS).",
            "Inspect cabin air intake filters for particulate, Lunar/Mars dust, or chemical irritants.",
        ]),
    },
    {
        "protocol_id": "radiation",
        "title": "Acute Protocol: Solar Particle Event (SPE) Alert",
        "badge": "RADIATION SHELTER",
        "nasa_risk_id": "96",
        "trigger_condition": "SPE flux > 50 mSv/hr or CANS/RAD dosimeter surge alert",
        "steps_json": json.dumps([
            "Immediately sound habitat klaxon: all crew retreat to Aft Water Wall / polyethylene storm shelter.",
            "Terminate ongoing Extravehicular Activities (EVA) within 8-minute airlock contingency window.",
            "Record active personal dosimeter (RAD) and CSA CANS neutron spectrometer readings immediately.",
            "Deploy auxiliary polyethylene shielding blankets over crew bunk positions.",
            "Await Space Radiation Analysis Group (SRAG) real-time flux clearance before resuming EVA.",
        ]),
    },
    {
        "protocol_id": "hypoxia-dcs",
        "title": "Acute Protocol: Hypoxia / Decompression Sickness (DCS) Triage",
        "badge": "CODE RED - EVA / CABIN",
        "nasa_risk_id": "173",
        "trigger_condition": "SpO2 < 90%, cabin depressurization, joint pain ('bends') post-EVA",
        "steps_json": json.dumps([
            "Don emergency 100% O2 mask or seal EVA suit pressure loop immediately.",
            "Verify cabin total pressure, PPO2, and ppCO2 on ECLSS console.",
            "If DCS suspected post-EVA, initiate hyperbaric treatment protocol (suit/airlock repressurization + 100% O2).",
            "Log neurological exam, pulse oximetry, and vital signs every 5 minutes.",
        ]),
    },
    {
        "protocol_id": "sans-vision",
        "title": "Acute Protocol: SANS Visual Acuity & Intracranial Pressure Shift",
        "badge": "CLINICAL ALERT",
        "nasa_risk_id": "105",
        "trigger_condition": "Acute hyperopic shift, scotoma, IOP > 22 mmHg, or sustained EAR < 0.195",
        "steps_json": json.dumps([
            "Perform in-flight Optical Coherence Tomography (OCT), Fundoscopy, and Tonometry IOP check.",
            "Measure visual acuity using onboard Amsler grid and Space Anticipation Glasses calibration.",
            "Check cabin ppCO2 (< 2.0 mmHg target, as elevated CO2 worsens cerebral vasodilation).",
            "Schedule LBNP session and review one-carbon / B-complex nutritional status.",
        ]),
    },
]


def parse_risk_statement_and_context(text: str):
    stmt = ""
    ctx = ""
    if not text:
        return stmt, ctx
    m_stmt = re.search(r"Risk Statement\s*\n+(.*?)(?:\n+Context|\n+Risk Master Logic|\Z)", text, re.S | re.I)
    if m_stmt:
        stmt = re.sub(r"\s+", " ", m_stmt.group(1)).strip()
    m_ctx = re.search(r"Context\s*\n+(.*?)(?:\n+Risk Ratings|\n+Gaps|\n+Evidence|\Z)", text, re.S | re.I)
    if m_ctx:
        ctx = re.sub(r"\s+", " ", m_ctx.group(1)).strip()[:3000]
    return stmt, ctx


def main():
    with open(RAW_SCRAPED / "nasa_hrp_pages.json", encoding="utf-8") as f:
        hrp_pages = json.load(f)
    with open(RAW_SCRAPED / "nasa_hrr_roadmap.json", encoding="utf-8") as f:
        hrr = json.load(f)
    with open(RAW_SCRAPED / "csa_pages.json", encoding="utf-8") as f:
        csa_pages = json.load(f)

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create schema
    cur.executescript("""
    CREATE TABLE challenge_spec (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_title TEXT,
        event_name TEXT,
        difficulty TEXT,
        source_url TEXT,
        core_goal TEXT,
        recommended_indicators TEXT,
        supported_environments TEXT
    );

    CREATE TABLE spaceflight_hazards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hazard_code TEXT UNIQUE,
        title TEXT,
        url TEXT,
        summary TEXT,
        full_text TEXT
    );

    CREATE TABLE nasa_hrp_elements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        url TEXT,
        full_text TEXT
    );

    CREATE TABLE nasa_hrp_risks (
        risk_id INTEGER PRIMARY KEY,
        short_title TEXT,
        full_title TEXT,
        hrp_element TEXT,
        last_published TEXT,
        risk_statement TEXT,
        clinical_context TEXT,
        hrr_url TEXT,
        nasa_ref_url TEXT,
        nasa_ref_summary TEXT
    );

    CREATE TABLE risk_drm_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_id INTEGER,
        drm_category TEXT,
        mission_type_duration TEXT,
        ops_lxc TEXT,
        ops_disposition TEXT,
        lth_lxc TEXT,
        lth_disposition TEXT,
        FOREIGN KEY (risk_id) REFERENCES nasa_hrp_risks(risk_id)
    );

    CREATE TABLE research_gaps (
        gap_id INTEGER PRIMARY KEY,
        gap_code TEXT,
        title TEXT,
        risk_id INTEGER,
        url TEXT
    );

    CREATE TABLE research_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        risk_id INTEGER,
        short_title TEXT,
        principal_investigator TEXT,
        responsible_element TEXT,
        description TEXT,
        url TEXT
    );

    CREATE TABLE evidence_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        risk_id INTEGER,
        pdf_url TEXT UNIQUE
    );

    CREATE TABLE csa_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        url TEXT,
        full_text TEXT
    );

    CREATE TABLE clinical_indicators_thresholds (
        indicator_code TEXT PRIMARY KEY,
        name TEXT,
        unit TEXT,
        app_feature_key TEXT,
        nominal_range TEXT,
        caution_range TEXT,
        critical_threshold TEXT,
        microgravity_effect TEXT,
        measurement_in_space TEXT,
        primary_hazard TEXT,
        linked_risk_ids TEXT,
        countermeasure TEXT
    );

    CREATE TABLE body_systems_matrix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        body_region TEXT,
        nasa_risk_ids TEXT,
        hazards TEXT,
        key_conditions TEXT,
        measurable_indicators TEXT,
        prevention_and_treatment TEXT
    );

    CREATE TABLE emergency_protocols (
        protocol_id TEXT PRIMARY KEY,
        title TEXT,
        badge TEXT,
        nasa_risk_id TEXT,
        trigger_condition TEXT,
        steps_json TEXT
    );

    CREATE TABLE osdr_inspiration4_labs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        study_accession TEXT,
        panel_type TEXT,
        subject_id TEXT,
        sex TEXT,
        timepoint TEXT,
        analyte TEXT,
        value REAL,
        range_min REAL,
        range_max REAL,
        units TEXT,
        out_of_range INTEGER
    );

    CREATE TABLE osdr_sans_ocular_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        study_accession TEXT,
        measurement_type TEXT,
        sample_name TEXT,
        timepoint TEXT,
        metric_name TEXT,
        metric_value REAL,
        unit TEXT
    );

    CREATE TABLE osdr_radiation_cardio_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        study_accession TEXT,
        subject_id TEXT,
        rad_type REAL,
        dose_gy REAL,
        cohort TEXT,
        month INTEGER,
        heart_rate_bpm REAL,
        lvaw_d REAL,
        lvid_d REAL,
        lvpw_d REAL,
        ef_pct REAL,
        fs_pct REAL,
        aorta_peak_vel REAL
    );
    """)

    # 1. Challenge Spec
    cur.execute(
        """INSERT INTO challenge_spec (challenge_title, event_name, difficulty, source_url, core_goal, recommended_indicators, supported_environments)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "Create Health Monitoring Software for Astronauts on Space Missions",
            "2026 NASA Space Apps Challenge",
            "Intermediate",
            "https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources",
            "Build a visual tool enabling astronauts to gather health indicators, assess their own physical and mental health in space, and receive preventive and treatment guidance.",
            "blood_pressure, heart_rate, blood_sugar, body_temperature, sleep_hours, mood, ocular_ear, balance, radiation_dosimetry",
            "Spacecraft, Space Station, Rover, Lunar/Planetary Base",
        ),
    )

    # 2. Hazards
    hazard_codes = ["R", "I", "D", "G", "E"]
    for idx, h in enumerate(hrp_pages.get("hazards", [])):
        code = hazard_codes[idx] if idx < len(hazard_codes) else f"H{idx}"
        txt = h["sections_text"]
        summary = txt[:600]
        cur.execute(
            "INSERT INTO spaceflight_hazards (hazard_code, title, url, summary, full_text) VALUES (?, ?, ?, ?, ?)",
            (code, h["title"], h["url"], summary, txt),
        )

    # 3. HRP Elements
    for el in hrp_pages.get("elements", []):
        cur.execute(
            "INSERT INTO nasa_hrp_elements (title, url, full_text) VALUES (?, ?, ?)",
            (el["title"], el["url"], el["sections_text"]),
        )

    # Map NASA Reference pages to HRR Risk IDs by keyword matching
    ref_pages = hrp_pages.get("risk_references", [])

    def match_ref_page(risk_title: str):
        rt = risk_title.lower()
        keywords = [
            ("sans", "sans"),
            ("neuro-ocular", "sans"),
            ("bone", "bone"),
            ("cardiovascular", "cardiovascular"),
            ("immune", "immune"),
            ("sensorimotor", "sensorimotor"),
            ("vestibular", "sensorimotor"),
            ("decompression", "decompression"),
            ("hypoxia", "hypoxia"),
            ("food", "food"),
            ("nutrition", "nutrition"),
            ("sleep", "sleep"),
            ("behavioral", "behavioral"),
            ("psychiatric", "behavioral"),
            ("team", "teamwork"),
            ("radiation", "radiation"),
            ("carcinogenesis", "radiation"),
            ("host", "microorganism"),
            ("microhost", "microorganism"),
            ("eva", "extravehicular"),
            ("dynamic", "dynamic"),
            ("aerobic", "cardiorespiratory"),
            ("muscle", "cardiorespiratory"),
            ("eihso", "systems-operations"),
            ("earth independent", "systems-operations"),
        ]
        for k1, k2 in keywords:
            if k1 in rt:
                for rp in ref_pages:
                    if k2 in rp["url"].lower() or k2 in rp["title"].lower():
                        return rp
        return None

    # 4. 22 HRR Risks + DRM Ratings + Tasks + Evidence PDFs
    evidence_seen = set()
    for r in hrr.get("risks_detailed", []):
        rid = int(r["risk_id"])
        stmt, ctx = parse_risk_statement_and_context(r.get("risk_content_text", ""))
        rp = match_ref_page(r["title"] + " " + r.get("short_title", ""))
        cur.execute(
            """INSERT INTO nasa_hrp_risks
            (risk_id, short_title, full_title, hrp_element, last_published, risk_statement, clinical_context, hrr_url, nasa_ref_url, nasa_ref_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rid,
                r.get("short_title", ""),
                r.get("title", ""),
                r.get("element", ""),
                r.get("last_published", ""),
                stmt,
                ctx,
                r.get("url", ""),
                rp["url"] if rp else "",
                rp["sections_text"][:2500] if rp else "",
            ),
        )
        for drm in r.get("drm_ratings", []):
            cur.execute(
                """INSERT INTO risk_drm_ratings
                (risk_id, drm_category, mission_type_duration, ops_lxc, ops_disposition, lth_lxc, lth_disposition)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid,
                    drm.get("drm_category", ""),
                    drm.get("mission_type_duration", ""),
                    drm.get("ops_lxc", ""),
                    drm.get("ops_disposition", ""),
                    drm.get("lth_lxc", ""),
                    drm.get("lth_disposition", ""),
                ),
            )
        for t in r.get("tasks_detailed", []):
            cur.execute(
                """INSERT INTO research_tasks
                (task_id, risk_id, short_title, principal_investigator, responsible_element, description, url)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    t.get("task_id", ""),
                    rid,
                    t.get("short_title", ""),
                    t.get("principal_investigator", ""),
                    t.get("responsible_element", ""),
                    t.get("description", ""),
                    t.get("url", ""),
                ),
            )
        for pdf in r.get("evidence_pdfs", []):
            u = pdf.get("url", "")
            if u and u not in evidence_seen:
                evidence_seen.add(u)
                cur.execute(
                    "INSERT INTO evidence_reports (title, risk_id, pdf_url) VALUES (?, ?, ?)",
                    (pdf.get("label", "Evidence Report"), rid, u),
                )

    for pdf in hrr.get("evidence_pdfs", []):
        u = pdf.get("url", "")
        if u and u not in evidence_seen:
            evidence_seen.add(u)
            cur.execute(
                "INSERT INTO evidence_reports (title, risk_id, pdf_url) VALUES (?, ?, ?)",
                (pdf.get("label", "Evidence Report"), None, u),
            )

    # 5. Research Gaps (327+)
    for g in hrr.get("gaps", []):
        gid = int(g["gap_id"])
        title = g.get("title", "")
        code_m = re.match(r"^([A-Za-z0-9\-]+)\s*:", title)
        gcode = code_m.group(1) if code_m else f"GAP-{gid}"
        rid = int(g["risk_id"]) if g.get("risk_id") else None
        cur.execute(
            "INSERT OR REPLACE INTO research_gaps (gap_id, gap_code, title, risk_id, url) VALUES (?, ?, ?, ?, ?)",
            (gid, gcode, title, rid, g.get("url", "")),
        )

    # 6. CSA Resources
    for c in csa_pages:
        cur.execute(
            "INSERT INTO csa_resources (title, url, full_text) VALUES (?, ?, ?)",
            (c["title"], c["url"], c["sections_text"]),
        )

    # 7. Curated Clinical Indicators, Body Systems Matrix, Emergency Protocols
    for ind in CLINICAL_INDICATORS:
        cur.execute(
            """INSERT INTO clinical_indicators_thresholds VALUES
            (:indicator_code, :name, :unit, :app_feature_key, :nominal_range, :caution_range,
             :critical_threshold, :microgravity_effect, :measurement_in_space, :primary_hazard,
             :linked_risk_ids, :countermeasure)""",
            ind,
        )

    for bs in BODY_SYSTEMS_MATRIX:
        cur.execute(
            """INSERT INTO body_systems_matrix
            (body_region, nasa_risk_ids, hazards, key_conditions, measurable_indicators, prevention_and_treatment)
            VALUES (:body_region, :nasa_risk_ids, :hazards, :key_conditions, :measurable_indicators, :prevention_and_treatment)""",
            bs,
        )

    for ep in EMERGENCY_PROTOCOLS:
        cur.execute(
            """INSERT INTO emergency_protocols
            (protocol_id, title, badge, nasa_risk_id, trigger_condition, steps_json)
            VALUES (:protocol_id, :title, :badge, :nasa_risk_id, :trigger_condition, :steps_json)""",
            ep,
        )

    # 8. NASA OSDR Real Spaceflight Data: Inspiration4 Labs (OSD-569 CBC + OSD-575 CMP)
    cbc = pd.read_csv(OSDR_RAW / "OSD-569_CBC_SUBMITTED.csv")
    for _, row in cbc.iterrows():
        val = pd.to_numeric(row["VALUE"], errors="coerce")
        rmin = pd.to_numeric(row["RANGE_MIN"], errors="coerce")
        rmax = pd.to_numeric(row["RANGE_MAX"], errors="coerce")
        oor = int((pd.notna(val) and pd.notna(rmin) and val < rmin) or (pd.notna(val) and pd.notna(rmax) and val > rmax))
        cur.execute(
            """INSERT INTO osdr_inspiration4_labs
            (study_accession, panel_type, subject_id, sex, timepoint, analyte, value, range_min, range_max, units, out_of_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("OSD-569", "CBC", str(row["SUBJECT_ID"]), str(row["SEX"]), str(row["TEST_DATE"]),
             str(row["ANALYTE"]), None if pd.isna(val) else float(val),
             None if pd.isna(rmin) else float(rmin), None if pd.isna(rmax) else float(rmax),
             str(row["UNITS"]), oor),
        )

    cmp = pd.read_csv(OSDR_RAW / "OSD-575_CMP_SUBMITTED.csv")
    for _, row in cmp.iterrows():
        val = pd.to_numeric(row["VALUE"], errors="coerce")
        rmin = pd.to_numeric(row["RANGE_MIN"], errors="coerce")
        rmax = pd.to_numeric(row["RANGE_MAX"], errors="coerce")
        oor = int((pd.notna(val) and pd.notna(rmin) and val < rmin) or (pd.notna(val) and pd.notna(rmax) and val > rmax))
        cur.execute(
            """INSERT INTO osdr_inspiration4_labs
            (study_accession, panel_type, subject_id, sex, timepoint, analyte, value, range_min, range_max, units, out_of_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("OSD-575", "CMP", str(row["SUBJECT_ID"]), str(row["SEX"]), str(row["timepoint"]),
             str(row["ANALYTE"]), None if pd.isna(val) else float(val),
             None if pd.isna(rmin) else float(rmin), None if pd.isna(rmax) else float(rmax),
             str(row["UNITS"]), oor),
        )

    # 9. OSDR SANS Ocular Metrics (OSD-583 + OSD-679 IOP)
    iop583 = pd.read_csv(OSDR_RAW / "OSD-583_LSDS-16_tonometry_Transformed_Files.csv")
    for _, row in iop583.iterrows():
        for eye_col in ["Left_Eye_IOP_Measurement_Average_mmHg", "Right_IOP_Measurement_Average_mmHg"]:
            v = pd.to_numeric(row.get(eye_col), errors="coerce")
            if pd.notna(v):
                cur.execute(
                    """INSERT INTO osdr_sans_ocular_metrics
                    (study_accession, measurement_type, sample_name, timepoint, metric_name, metric_value, unit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    ("OSD-583", "Spaceflight Tonometry IOP", str(row["Sample Name"]), "Post-flight", eye_col, float(v), "mmHg"),
                )

    iop679 = pd.read_csv(OSDR_RAW / "OSD-679_LSDS-81_tonometry_Fuller_TonometryIOP_TRANSFORMED.csv")
    day_cols = [c for c in iop679.columns if c.startswith("Day_")]
    for _, row in iop679.iterrows():
        for dc in day_cols:
            v = pd.to_numeric(row.get(dc), errors="coerce")
            if pd.notna(v):
                tp = dc.replace("_Intraocular_Pressure_torr", "")
                cur.execute(
                    """INSERT INTO osdr_sans_ocular_metrics
                    (study_accession, measurement_type, sample_name, timepoint, metric_name, metric_value, unit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    ("OSD-679", "Hindlimb Unloading Tonometry IOP", str(row["Sample Name"]), tp, "Intraocular Pressure", float(v), "torr"),
                )

    # 10. OSDR Radiation Cardio Metrics (OSD-435 Heart + Aorta merged)
    heart = pd.read_csv(OSDR_RAW / "OSD-435_LSDS-22_Echocardiography_heart_SUBMITTED.csv")
    aorta = pd.read_csv(OSDR_RAW / "OSD-435_LSDS-22_Echocardiography_aorta_SUBMITTED.csv")
    aorta_map = aorta.groupby(["SID", "MONTH"], as_index=False)["PEAKVEL"].mean()
    rad_merged = heart.merge(aorta_map, on=["SID", "MONTH"], how="left")
    for _, row in rad_merged.iterrows():
        cur.execute(
            """INSERT INTO osdr_radiation_cardio_metrics
            (study_accession, subject_id, rad_type, dose_gy, cohort, month, heart_rate_bpm, lvaw_d, lvid_d, lvpw_d, ef_pct, fs_pct, aorta_peak_vel)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "OSD-435",
                str(row.get("SID", "")),
                None if pd.isna(row.get("RADTYPE")) else float(row["RADTYPE"]),
                None if pd.isna(row.get("DOSE")) else float(row["DOSE"]),
                str(row.get("COHORT", "")),
                None if pd.isna(row.get("MONTH")) else int(row["MONTH"]),
                None if pd.isna(row.get("HR")) else float(row["HR"]),
                None if pd.isna(row.get("LVAW_d")) else float(row["LVAW_d"]),
                None if pd.isna(row.get("LVID_d")) else float(row["LVID_d"]),
                None if pd.isna(row.get("LVPW_d")) else float(row["LVPW_d"]),
                None if pd.isna(row.get("EF")) else float(row["EF"]),
                None if pd.isna(row.get("FS")) else float(row["FS"]),
                None if pd.isna(row.get("PEAKVEL")) else float(row["PEAKVEL"]),
            ),
        )

    conn.commit()

    # Export all tables to database/csv_exports/ and build JSON knowledge base
    tables = [
        "challenge_spec",
        "spaceflight_hazards",
        "nasa_hrp_elements",
        "nasa_hrp_risks",
        "risk_drm_ratings",
        "research_gaps",
        "research_tasks",
        "evidence_reports",
        "csa_resources",
        "clinical_indicators_thresholds",
        "body_systems_matrix",
        "emergency_protocols",
        "osdr_inspiration4_labs",
        "osdr_sans_ocular_metrics",
        "osdr_radiation_cardio_metrics",
    ]
    counts = {}
    for tbl in tables:
        df = pd.read_sql_query(f"SELECT * FROM {tbl}", conn)
        df.to_csv(CSV_EXPORTS / f"{tbl}.csv", index=False)
        counts[tbl] = len(df)

    # Build nasa_knowledge_base.json (ready for Bio-Copilot, UI Body Map, and Backend)
    kb = {
        "metadata": {
            "source_challenge_url": "https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources",
            "table_counts": counts,
        },
        "challenge_spec": pd.read_sql_query("SELECT * FROM challenge_spec", conn).to_dict(orient="records"),
        "spaceflight_hazards": pd.read_sql_query("SELECT * FROM spaceflight_hazards", conn).to_dict(orient="records"),
        "nasa_hrp_elements": pd.read_sql_query("SELECT * FROM nasa_hrp_elements", conn).to_dict(orient="records"),
        "nasa_hrp_risks": pd.read_sql_query("SELECT * FROM nasa_hrp_risks", conn).to_dict(orient="records"),
        "risk_drm_ratings": pd.read_sql_query("SELECT * FROM risk_drm_ratings", conn).to_dict(orient="records"),
        "research_gaps": pd.read_sql_query("SELECT * FROM research_gaps", conn).to_dict(orient="records"),
        "evidence_reports": pd.read_sql_query("SELECT * FROM evidence_reports", conn).to_dict(orient="records"),
        "csa_resources": pd.read_sql_query("SELECT * FROM csa_resources", conn).to_dict(orient="records"),
        "clinical_indicators_thresholds": CLINICAL_INDICATORS,
        "body_systems_matrix": BODY_SYSTEMS_MATRIX,
        "emergency_protocols": [
            {**ep, "steps": json.loads(ep["steps_json"])} for ep in EMERGENCY_PROTOCOLS
        ],
    }
    with open(JSON_KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)

    conn.close()
    print("=== DATABASE BUILD COMPLETE ===")
    for k, v in counts.items():
        print(f"  {k}: {v} rows")
    print(f"SQLite DB: {DB_PATH}")
    print(f"JSON KB:   {JSON_KB_PATH}")


if __name__ == "__main__":
    main()
