"""
Modular NASA Dataset Ingestion, Declarative Clinical Schema & Canonical Normalization
for Bio Astro Lab.

Design principles:
1. Zero hardcoded feature-by-feature if-elif-else triage chains: all plausibility
   bounds, clinical risk bands, NASA HRP risk mappings, and corrective directives
   live in the declarative CLINICAL_BIOMARKER_SCHEMA registry.
2. Backward-compatible 13-feature layout where indices [0..8] match CORE_9_FEATURES
   and indices [9..12] hold spaceflight/cardiopulmonary expansion features
   (heart_rate_bpm, spo2_pct, radiation_dose_msv, cabin_co2_mmhg). Missing
   modalities remain np.nan so XGBoost routes them natively.
"""

from __future__ import annotations

import fnmatch
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

CORE_9_FEATURES = [
    "blood_glucose",        # 0: mg/dL
    "systolic_bp",          # 1: mmHg
    "diastolic_bp",         # 2: mmHg
    "body_temp",            # 3: deg C
    "sleep_hours",          # 4: hrs / 24h
    "mood_score",           # 5: 1-4 ordinal (1=Optimal, 4=Critical)
    "balance_score",        # 6: 0-100 %
    "joint_symmetry_diff",  # 7: degrees (>= 0)
    "facial_ear",           # 8: Eye Aspect Ratio
]

EXTENDED_FEATURES = [
    "heart_rate_bpm",       # 9: bpm
    "spo2_pct",             # 10: %
    "radiation_dose_msv",   # 11: mSv/day
    "cabin_co2_mmhg",       # 12: mmHg partial pressure
]

FEATURE_COLUMNS = CORE_9_FEATURES + EXTENDED_FEATURES
TARGET_COLUMN = "health_risk_label"  # 0: Optimal, 1: Caution, 2: Critical
RISK_DRIVER_COLUMN = "primary_nasa_risk_id"

METADATA_COLUMNS = [
    "subject_id",
    "mission_id",
    "sol_or_timestamp",
    "data_source",
    "label_source",
]

# Declarative clinical specification exported identically to Python labeling & JS UI/model.
# Each band: {min, max, points, critical, status, tag, directiveTitle, directiveDetail}
# Unbounded sides use None (serialized to JSON null and handled as -Infinity/+Infinity).
CLINICAL_BIOMARKER_SCHEMA: list[dict[str, Any]] = [
    {
        "key": "blood_glucose",
        "label": "Blood Glucose",
        "unit": "mg/dL",
        "group": "metabolic",
        "plausible": [35.0, 500.0],
        "nominalBaseline": 92.0,
        "nasaRiskId": 176,
        "nasaRiskTitle": "Inadequate Nutrition & Metabolic Homeostasis",
        "bands": [
            {
                "min": None, "max": 62.0, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Severe Hypoglycemia",
                "directiveTitle": "Severe Hypoglycemic Protocol",
                "directiveDetail": "Administer 15-20g rapid glucose gel immediately, halt EVA/ARED, and repeat glucometry in 15 min.",
            },
            {
                "min": 62.0, "max": 70.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Hypoglycemic Drift",
                "directiveTitle": "Hypoglycemic Drift Intervention",
                "directiveDetail": "Borderline low fasting glucose; consume complex carbohydrate snack and re-check in 30 minutes.",
            },
            {
                "min": 70.0, "max": 115.0, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Optimal Fasting",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 115.0, "max": 135.0, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Glycemic Elevation",
                "directiveTitle": "Glycemic & GLUT4 Activity Check",
                "directiveDetail": "Mildly elevated fasting glucose; log carbohydrate intake and schedule daily ergometer session.",
            },
            {
                "min": 135.0, "max": 190.0, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Hyperglycemic Strain",
                "directiveTitle": "Metabolic & Glycemic Balance",
                "directiveDetail": "Elevated blood glucose under microgravity insulin resistance; review diet and perform ARED/cycle load.",
            },
            {
                "min": 190.0, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Acute Hyperglycemia",
                "directiveTitle": "Acute Hyperglycemic Escalation",
                "directiveDetail": "Critical hyperglycemia detected; verify repeat fingerstick, hydrate orally, and escalate to Flight Surgeon.",
            },
        ],
    },
    {
        "key": "systolic_bp",
        "label": "Systolic Blood Pressure",
        "unit": "mmHg",
        "group": "cardiovascular",
        "plausible": [60.0, 260.0],
        "nominalBaseline": 116.0,
        "nasaRiskId": 179,
        "nasaRiskTitle": "Cardiovascular Alterations & Orthostatic Intolerance",
        "bands": [
            {
                "min": None, "max": 85.0, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Critical Hypotension",
                "directiveTitle": "Acute Hypotension / Presyncope Alert",
                "directiveDetail": "Place crew supine with legs elevated, initiate oral/IV electrolyte bolus, and notify Flight Surgeon.",
            },
            {
                "min": 85.0, "max": 92.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Low BP Borderline",
                "directiveTitle": "Orthostatic & Hypotensive Hydration",
                "directiveDetail": "Borderline low systolic BP; administer electrolyte solution and perform LBNP check before EVA.",
            },
            {
                "min": 92.0, "max": 128.0, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Normotensive",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 128.0, "max": 138.0, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Vascular Load",
                "directiveTitle": "Resting Vascular Re-Check",
                "directiveDetail": "Slightly elevated systolic pressure; confirm cuff held at heart level after 5 min stationary rest.",
            },
            {
                "min": 138.0, "max": 160.0, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Elevated Vascular Load",
                "directiveTitle": "Hypertensive Vascular Strain Monitoring",
                "directiveDetail": "Elevated systolic pressure (cephalad fluid shift); restrict caffeine/sodium and re-measure.",
            },
            {
                "min": 160.0, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Hypertensive Crisis Risk",
                "directiveTitle": "Acute Hypertensive Escalation",
                "directiveDetail": "Critical systolic hypertension; cease resistive ARED exercise immediately and uplink ECG to Flight Surgeon.",
            },
        ],
    },
    {
        "key": "diastolic_bp",
        "label": "Diastolic Blood Pressure",
        "unit": "mmHg",
        "group": "cardiovascular",
        "plausible": [35.0, 160.0],
        "nominalBaseline": 76.0,
        "nasaRiskId": 179,
        "nasaRiskTitle": "Cardiovascular Alterations & Orthostatic Intolerance",
        "bands": [
            {
                "min": None, "max": 52.0, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Critical Low Diastolic",
                "directiveTitle": "Diastolic Hypoperfusion Alert",
                "directiveDetail": "Critically low diastolic perfusion pressure; hydrate immediately and evaluate orthostatic stability.",
            },
            {
                "min": 52.0, "max": 58.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Low Diastolic Borderline",
                "directiveTitle": "Volume & Electrolyte Support",
                "directiveDetail": "Borderline low diastolic BP; increase electrolyte fluids and defer rapid postural transitions.",
            },
            {
                "min": 58.0, "max": 83.0, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Normotensive",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 83.0, "max": 88.0, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Diastolic Elevation",
                "directiveTitle": "Diastolic Pressure Watch",
                "directiveDetail": "Mild diastolic elevation; repeat oscillometric reading after 5 minutes seated rest.",
            },
            {
                "min": 88.0, "max": 100.0, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Elevated Diastolic Load",
                "directiveTitle": "Elevated Diastolic Strain",
                "directiveDetail": "Sustained diastolic elevation; reduce sodium intake and schedule medical check before heavy EVA.",
            },
            {
                "min": 100.0, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Critical Diastolic Hypertension",
                "directiveTitle": "Critical Diastolic Escalation",
                "directiveDetail": "Severe diastolic hypertension; suspend strenuous ops and initiate Flight Surgeon consultation.",
            },
        ],
    },
    {
        "key": "body_temp",
        "label": "Core Body Temperature",
        "unit": "deg C",
        "group": "thermoregulatory",
        "plausible": [33.0, 42.0],
        "nominalBaseline": 36.8,
        "nasaRiskId": 85,
        "nasaRiskTitle": "Immune Dysregulation & Infectious Disease Risk",
        "bands": [
            {
                "min": None, "max": 35.4, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Hypothermia Alert",
                "directiveTitle": "Critical Hypothermia Intervention",
                "directiveDetail": "Core temperature critically low; warm habitat/LCG suit loop immediately and check thyroid/metabolic state.",
            },
            {
                "min": 35.4, "max": 35.9, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Sub-Nominal Thermal Shift",
                "directiveTitle": "Thermal Envelope Warming",
                "directiveDetail": "Core temperature trending low; adjust thermal garment loop and monitor core stability.",
            },
            {
                "min": 35.9, "max": 37.3, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Core Balanced",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 37.3, "max": 37.6, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Thermal Elevation",
                "directiveTitle": "Thermal & Hydration Check",
                "directiveDetail": "Mild core temp rise (common post-exercise in microgravity); hydrate and re-verify in 60 min.",
            },
            {
                "min": 37.6, "max": 38.3, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Thermal Strain / Low Pyrexia",
                "directiveTitle": "Thermal Strain & Pyrexia Watch",
                "directiveDetail": "Verify LCG cooling flow, increase fluids, and monitor immune symptom markers every 2 hours.",
            },
            {
                "min": 38.3, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Acute Pyrexia / Fever",
                "directiveTitle": "Acute Fever & Immune Escalation",
                "directiveDetail": "Significant pyrexia; stand down EVA, inspect microbial cabin alerts, and initiate Flight Surgeon review.",
            },
        ],
    },
    {
        "key": "sleep_hours",
        "label": "Sleep Duration",
        "unit": "hrs",
        "group": "circadian",
        "plausible": [0.0, 20.0],
        "nominalBaseline": 7.5,
        "nasaRiskId": 100,
        "nasaRiskTitle": "Circadian Desynchronization & Sleep Loss",
        "bands": [
            {
                "min": None, "max": 4.5, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Severe Sleep Deprivation",
                "directiveTitle": "Severe Sleep Debt Stand-Down",
                "directiveDetail": "Less than 4.5h sleep sharply increases human error risk; defer critical piloting/EVA and enforce recovery rest.",
            },
            {
                "min": 4.5, "max": 6.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Circadian Sleep Deficit",
                "directiveTitle": "Circadian Rest Recovery",
                "directiveDetail": "Sub-nominal sleep duration; shift crew quarter lighting to warm spectrum pre-sleep and extend rest window.",
            },
            {
                "min": 6.0, "max": 6.5, "maxInclusive": False,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Sleep Restriction",
                "directiveTitle": "Sleep Hygiene Optimization",
                "directiveDetail": "Slightly reduced sleep; apply 480nm morning circadian light protocol and limit late caffeine.",
            },
            {
                "min": 6.5, "max": 9.5, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Circadian Aligned",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 9.5, "max": None, "minInclusive": False,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Extended Hypersomnia",
                "directiveTitle": "Hypersomnia & Fatigue Review",
                "directiveDetail": "Extended sleep logged (> 9.5h); screen for fatigue/illness and verify morning blue-enriched light compliance.",
            },
        ],
    },
    {
        "key": "mood_score",
        "label": "Behavioral Mood Index",
        "unit": "1-4 scale",
        "group": "behavioral",
        "plausible": [1.0, 4.0],
        "nominalBaseline": 1.0,
        "nasaRiskId": 99,
        "nasaRiskTitle": "Behavioral Health & Psychiatric Performance",
        "bands": [
            {
                "min": None, "max": 1.5, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Alert & Resilient",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 1.5, "max": 2.5, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Calm / Mild Load",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 2.5, "max": 3.5, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Fatigued / High Strain",
                "directiveTitle": "Behavioral Workload Offload",
                "directiveDetail": "Crew reports significant strain/fatigue (Mood 3/4); reduce non-essential tasking and schedule BHP check.",
            },
            {
                "min": 3.5, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Acute Stress Overload",
                "directiveTitle": "Acute Behavioral Stress Escalation",
                "directiveDetail": "Critical psychological strain (Mood 4/4); suspend hazardous EVA and initiate private Flight Surgeon conference.",
            },
        ],
    },
    {
        "key": "balance_score",
        "label": "Postural Stability",
        "unit": "%",
        "group": "sensorimotor",
        "plausible": [0.0, 100.0],
        "nominalBaseline": 95.0,
        "nasaRiskId": 88,
        "nasaRiskTitle": "Sensorimotor & Vestibular Alterations",
        "bands": [
            {
                "min": None, "max": 62.0, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Critical Vestibular Deficit",
                "directiveTitle": "Severe Sensorimotor / Ataxia Alert",
                "directiveDetail": "Postural stability < 62%; anchor crew member via handrails, halt EVA/locomotion, and assess vestibular drift.",
            },
            {
                "min": 62.0, "max": 78.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Moderate Sway Drift",
                "directiveTitle": "Vestibular Adaptation Countermeasure",
                "directiveDetail": "Reduced sensorimotor score; run neuro-vestibular stabilization drill before heavy tasks.",
            },
            {
                "min": 78.0, "max": 85.0, "maxInclusive": False,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Postural Drift",
                "directiveTitle": "Balance Baseline Re-Check",
                "directiveDetail": "Minor postural instability; re-capture 30s vision pose check before transitioning environments.",
            },
            {
                "min": 85.0, "max": None,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Steady Control",
                "directiveTitle": None, "directiveDetail": None,
            },
        ],
    },
    {
        "key": "joint_symmetry_diff",
        "label": "Bilateral Joint Asymmetry",
        "unit": "deg",
        "group": "sensorimotor",
        "plausible": [0.0, 45.0],
        "nominalBaseline": 1.5,
        "nasaRiskId": 88,
        "nasaRiskTitle": "Sensorimotor & Musculoskeletal Unloading",
        "bands": [
            {
                "min": None, "max": 4.5, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Symmetric Alignment",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 4.5, "max": 6.5, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Load Asymmetry",
                "directiveTitle": "ARED Calibration Review",
                "directiveDetail": "Mild bilateral angle asymmetry; inspect ARED footplate/shoulder alignment during resistive training.",
            },
            {
                "min": 6.5, "max": 13.0, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Moderate Joint Shift",
                "directiveTitle": "Musculoskeletal Symmetry Countermeasure",
                "directiveDetail": "Moderate bilateral asymmetry; offload unilateral load and verify neuromotor coordination.",
            },
            {
                "min": 13.0, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Severe Joint Asymmetry",
                "directiveTitle": "Acute Musculoskeletal / Ataxia Escalation",
                "directiveDetail": "Severe bilateral delta (> 13 deg); halt ARED/EVA to prevent ligament/muscle injury and notify Flight Surgeon.",
            },
        ],
    },
    {
        "key": "facial_ear",
        "label": "Ocular Eye Aspect Ratio (EAR)",
        "unit": "ratio",
        "group": "ocular",
        "plausible": [0.10, 0.45],
        "nominalBaseline": 0.285,
        "nasaRiskId": 105,
        "nasaRiskTitle": "Spaceflight Associated Neuro-ocular Syndrome (SANS) & Fatigue",
        "bands": [
            {
                "min": None, "max": 0.195, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Critical Microsleep / Ptosis",
                "directiveTitle": "Critical Ocular Fatigue Stand-Down",
                "directiveDetail": "Sustained EAR < 0.195 indicates severe microsleep/fatigue or ocular strain; pause console ops immediately.",
            },
            {
                "min": 0.195, "max": 0.235, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Ocular Fatigue",
                "directiveTitle": "Ocular Fatigue Mitigation",
                "directiveDetail": "EAR in fatigued zone; implement 15-minute visual rest and evaluate SANS ocular checklist.",
            },
            {
                "min": 0.235, "max": None,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Alert Gaze",
                "directiveTitle": None, "directiveDetail": None,
            },
        ],
    },
    {
        "key": "heart_rate_bpm",
        "label": "Resting Heart Rate",
        "unit": "bpm",
        "group": "cardiovascular",
        "plausible": [28.0, 220.0],
        "nominalBaseline": 72.0,
        "nasaRiskId": 179,
        "nasaRiskTitle": "Cardiovascular Alterations & Arrhythmia Risk",
        "bands": [
            {
                "min": None, "max": 45.0, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Severe Bradycardia",
                "directiveTitle": "Critical Bradycardia Escalation",
                "directiveDetail": "Heart rate < 45 bpm; deploy 12-lead ECG telemetry and initiate Flight Surgeon evaluation.",
            },
            {
                "min": 45.0, "max": 52.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Low Resting Heart Rate",
                "directiveTitle": "Autonomic & ECG Review",
                "directiveDetail": "Heart rate mildly bradycardic; assess vagal tone and review Holter/ECG trend.",
            },
            {
                "min": 52.0, "max": 92.0, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Normal Sinus",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 92.0, "max": 100.0, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Mild Sinus Elevation",
                "directiveTitle": "Hydration & Resting HR Check",
                "directiveDetail": "Heart rate mildly elevated; ensure hydration after exercise and repeat resting pulse in 15 min.",
            },
            {
                "min": 100.0, "max": 120.0, "minInclusive": False, "maxInclusive": True,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Sinus Tachycardia",
                "directiveTitle": "Tachycardia & Plasma Volume Countermeasure",
                "directiveDetail": "Resting HR > 100 bpm; verify hydration/electrolytes, rest, and check ECG rhythm.",
            },
            {
                "min": 120.0, "max": None, "minInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Acute Tachycardia",
                "directiveTitle": "Acute Tachycardia / Arrhythmia Protocol",
                "directiveDetail": "Resting HR > 120 bpm; cease activity, deploy 12-lead ECG uplink, and consult Flight Surgeon immediately.",
            },
        ],
    },
    {
        "key": "spo2_pct",
        "label": "Oxygen Saturation (SpO2)",
        "unit": "%",
        "group": "respiratory",
        "plausible": [50.0, 100.0],
        "nominalBaseline": 98.0,
        "nasaRiskId": 173,
        "nasaRiskTitle": "Hypoxia, Cabin Atmosphere & Ebullism Risk",
        "bands": [
            {
                "min": None, "max": 90.0, "maxInclusive": False,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Acute Hypoxemia",
                "directiveTitle": "Acute Hypoxia & O2 Mask Protocol",
                "directiveDetail": "SpO2 < 90%; administer supplemental O2 at 4 L/min immediately and check ECLSS cabin pO2/pressure.",
            },
            {
                "min": 90.0, "max": 94.0, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Mild Desaturation",
                "directiveTitle": "ECLSS pO2 & Pulse Ox Verification",
                "directiveDetail": "SpO2 between 90-94%; warm finger/re-seat pulse oximeter and inspect habitat O2 partial pressure.",
            },
            {
                "min": 94.0, "max": 95.5, "maxInclusive": False,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Borderline Saturation",
                "directiveTitle": "Ventilation & Airflow Check",
                "directiveDetail": "SpO2 borderline; confirm cabin ventilation fan airflow to clear localized CO2 pockets.",
            },
            {
                "min": 95.5, "max": None,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Normoxic",
                "directiveTitle": None, "directiveDetail": None,
            },
        ],
    },
    {
        "key": "radiation_dose_msv",
        "label": "Space Radiation Dose Rate",
        "unit": "mSv/day",
        "group": "radiation",
        "plausible": [0.0, 100.0],
        "nominalBaseline": 0.6,
        "nasaRiskId": 96,
        "nasaRiskTitle": "Space Radiation Carcinogenesis & Acute SPE Hazard",
        "bands": [
            {
                "min": None, "max": 1.0, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "LEO Nominal GCR",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 1.0, "max": 2.0, "minInclusive": False, "maxInclusive": True,
                "points": 1, "critical": False, "status": "MONITOR", "tag": "Deep Space GCR Flux",
                "directiveTitle": "Dosimeter Cumulative Budget Check",
                "directiveDetail": "Elevated deep-space GCR flux; log personal RAD/CANS neutron dosimetry against career limit.",
            },
            {
                "min": 2.0, "max": 15.0, "minInclusive": False, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Elevated Solar Flux",
                "directiveTitle": "EVA Deferral & Storm Watch",
                "directiveDetail": "Elevated particle flux (>= 2 mSv/d); defer EVA and prepare aft shielding blankets.",
            },
            {
                "min": 15.0, "max": None, "minInclusive": True,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Solar Particle Event (SPE)",
                "directiveTitle": "SPE Storm Shelter Retreat",
                "directiveDetail": "High radiation surge (>= 15 mSv/d); terminate EVA immediately and retreat to Water Wall Storm Shelter.",
            },
        ],
    },
    {
        "key": "cabin_co2_mmhg",
        "label": "Cabin ppCO2 (ECLSS)",
        "unit": "mmHg",
        "group": "environment",
        "plausible": [0.1, 15.0],
        "nominalBaseline": 1.5,
        "nasaRiskId": 173,
        "nasaRiskTitle": "CO2 Hypercapnia, Headache & ECLSS Scrubbing",
        "bands": [
            {
                "min": None, "max": 2.2, "maxInclusive": True,
                "points": 0, "critical": False, "status": "OPTIMAL", "tag": "Clean ECLSS Air",
                "directiveTitle": None, "directiveDetail": None,
            },
            {
                "min": 2.2, "max": 4.0, "minInclusive": False, "maxInclusive": False,
                "points": 2, "critical": False, "status": "CAUTION", "tag": "Moderate Hypercapnia Risk",
                "directiveTitle": "CDRA Scrubber & Airflow Increase",
                "directiveDetail": "Cabin ppCO2 elevated (2.2-4.0 mmHg); boost CDRA scrubber cadence and cabin fan mixing to prevent headache/SANS.",
            },
            {
                "min": 4.0, "max": None, "minInclusive": True,
                "points": 3, "critical": True, "status": "CRITICAL", "tag": "Critical Hypercapnia Alert",
                "directiveTitle": "Critical Cabin CO2 Contingency",
                "directiveDetail": "Cabin ppCO2 >= 4.0 mmHg; don O2 masks, activate backup LiOH/CDRA canisters, and alert Mission Control.",
            },
        ],
    },
]

BIOMARKER_BY_KEY: dict[str, dict[str, Any]] = {spec["key"]: spec for spec in CLINICAL_BIOMARKER_SCHEMA}
PLAUSIBILITY_BOUNDS: dict[str, tuple[float, float]] = {
    spec["key"]: (float(spec["plausible"][0]), float(spec["plausible"][1]))
    for spec in CLINICAL_BIOMARKER_SCHEMA
}

DEFAULT_COLUMN_ALIASES: dict[str, list[str]] = {
    "subject_id": ["subject_id", "astronaut_id", "crew_id", "participant_id", "seqn", "subject", "recordid"],
    "mission_id": ["mission_id", "mission", "expedition", "campaign", "cohort"],
    "sol_or_timestamp": ["sol_or_timestamp", "sol", "mission_day", "timestamp", "timestamp_utc", "date", "day", "timepoint"],
    "blood_glucose": ["blood_glucose", "glucose", "fasting_glucose", "glucose_mg_dl", "glucose_mmol_l", "glucose_mmol", "lbxglu", "glucose_median"],
    "systolic_bp": ["systolic_bp", "sbp", "systolic", "sys_bp", "bp_sys", "sbp_kpa", "sysabp", "sysabp_median"],
    "diastolic_bp": ["diastolic_bp", "dbp", "diastolic", "dia_bp", "bp_dia", "dbp_kpa", "diasabp", "diasabp_median"],
    "body_temp": ["body_temp", "core_temp", "core_temp_c", "core_temp_f", "temp_c", "temp_f", "temperature", "temp", "temp_median"],
    "sleep_hours": ["sleep_hours", "sleep_duration", "sleep_hrs", "sleep_minutes", "sleep_min", "sleep"],
    "mood_score": ["mood_score", "stress_score", "mood", "fatigue_mood", "psych_score"],
    "balance_score": ["balance_score", "posture_score", "stability_score", "balance"],
    "joint_symmetry_diff": ["joint_symmetry_diff", "joint_asymmetry", "joint_delta_rad", "symmetry_diff_deg", "gait_asymmetry"],
    "facial_ear": ["facial_ear", "ear", "eye_aspect_ratio", "avg_ear"],
    "heart_rate_bpm": ["heart_rate_bpm", "heart_rate", "hr", "hr_bpm", "bpxpls", "hr_median", "pulse"],
    "spo2_pct": ["spo2_pct", "spo2", "sao2", "sao2_median", "oxygen_saturation"],
    "radiation_dose_msv": ["radiation_dose_msv", "radiation_msv", "dose_msv", "rad_dose", "dosimeter_msv"],
    "cabin_co2_mmhg": ["cabin_co2_mmhg", "co2_mmhg", "ppco2", "cabin_co2"],
    TARGET_COLUMN: [TARGET_COLUMN, "risk_label", "clinical_risk", "label", "triage_tier"],
}


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _match_band(value: float, bands: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Evaluates declarative range bounds cleanly without per-feature branching."""
    for band in bands:
        lo = band.get("min")
        hi = band.get("max")
        lo_ok = True if lo is None else (value >= lo if band.get("minInclusive", True) else value > lo)
        hi_ok = True if hi is None else (value <= hi if band.get("maxInclusive", False) else value < hi)
        if lo_ok and hi_ok:
            return band
    return None


def assign_spaceflight_label_and_driver(row: Mapping[str, Any]) -> tuple[float, int]:
    """
    Table-driven, NaN-safe evaluation against CLINICAL_BIOMARKER_SCHEMA.
    Missing (NaN) modalities are ignored cleanly so partial-sensor rows never score falsely.
    Returns (risk_label [0, 1, 2 or NaN], primary_nasa_risk_id [int]).
    """
    observed = 0
    critical_flags = 0
    risk_points = 0
    driver_scores: dict[int, int] = {}

    for spec in CLINICAL_BIOMARKER_SCHEMA:
        raw = row.get(spec["key"], np.nan)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isnan(val):
            continue

        observed += 1
        band = _match_band(val, spec["bands"])
        if band is None:
            continue

        pts = int(band["points"])
        crit = bool(band["critical"])
        if crit:
            critical_flags += 1
        else:
            risk_points += pts

        if pts > 0 or crit:
            rid = int(spec["nasaRiskId"])
            driver_scores[rid] = driver_scores.get(rid, 0) + pts + (10 if crit else 0)

    if observed == 0:
        return np.nan, 0

    primary_risk = max(driver_scores, key=driver_scores.get) if driver_scores else 0
    if critical_flags >= 1 or risk_points >= 6:
        return 2, primary_risk
    if risk_points >= 3:
        return 1, primary_risk
    return 0, primary_risk


def assign_spaceflight_risk_label(row: Mapping[str, Any]) -> float:
    """Compatibility helper returning only the integer triage label (0, 1, 2, or NaN)."""
    label, _ = assign_spaceflight_label_and_driver(row)
    return label


def _clean_unit_token(unit: Optional[str]) -> str:
    if unit is None or (isinstance(unit, float) and math.isnan(unit)):
        return ""
    return str(unit).strip().lower().replace("μ", "u").replace("µ", "u").replace(" ", "")


def normalize_glucose_to_mgdl(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    factor = 18.0182 if (u in {"mmol/l", "mmol", "mmol_l", "mm"} or (not u and float(valid.quantile(0.95)) < 30.0)) else 1.0
    return s * factor


def normalize_bp_to_mmhg(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    factor = 7.50062 if (u == "kpa" or (not u and float(valid.median()) < 30.0)) else 1.0
    return s * factor


def normalize_temp_to_celsius(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    med = float(valid.median())
    if u in {"k", "kelvin", "degk"} or (not u and med > 200.0):
        return s - 273.15
    if u in {"f", "degf", "fahrenheit", "°f"} or (not u and med > 45.0):
        return (s - 32.0) * (5.0 / 9.0)
    return s


def normalize_sleep_to_hours(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    med = float(valid.median())
    if u in {"s", "sec", "secs", "second", "seconds"} or (not u and med > 1440.0):
        return s / 3600.0
    if u in {"m", "min", "mins", "minute", "minutes"} or (not u and med > 24.0):
        return s / 60.0
    return s


def normalize_angle_to_degrees(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series).abs()
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    factor = (180.0 / np.pi) if (u in {"rad", "radian", "radians"} or (not u and float(valid.max()) < 1.5 and float(valid.quantile(0.95)) < 1.0)) else 1.0
    return s * factor


def normalize_balance_to_pct(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    factor = 100.0 if (u in {"ratio", "0-1", "fraction"} or (not u and float(valid.max()) <= 1.0)) else 1.0
    return s * factor


def normalize_spo2_to_pct(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    factor = 100.0 if (u in {"ratio", "0-1", "fraction"} or (not u and float(valid.max()) <= 1.01)) else 1.0
    return s * factor


def normalize_radiation_to_msv(series: pd.Series, unit: Optional[str] = None) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    unit_factors = {
        "gy": 1000.0,
        "gray": 1000.0,
        "cgy": 10.0,
        "mgy": 1.0,
        "msv": 1.0,
        "msv/d": 1.0,
        "msv/day": 1.0,
        "msv/24h": 1.0,
        "sv": 1000.0,
        "rem": 10.0,
        "mrem": 0.01,
        "usv/h": 0.024,
        "usv/hr": 0.024,
        "usv_hr": 0.024,
        "ugy/h": 0.024,
        "ugy/hr": 0.024,
        "msv/h": 24.0,
        "msv/hr": 24.0,
        "usv": 0.001,
        "usv/d": 0.001,
        "usv/day": 0.001,
    }
    return s * unit_factors.get(u, 1.0)


def normalize_co2_to_mmhg(
    series: pd.Series,
    unit: Optional[str] = None,
    cabin_pressure_mmhg: float = 760.0,
) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    u = _clean_unit_token(unit)
    if u == "ppm" or (not u and float(valid.median()) > 50.0):
        return (s * 1e-6) * float(cabin_pressure_mmhg)
    if u in {"%", "pct", "percent"}:
        return (s / 100.0) * float(cabin_pressure_mmhg)
    if u == "kpa":
        return s * 7.50062
    if u in {"hpa", "mbar"}:
        return s * 0.750062
    return s


def normalize_mood_to_ordinal(
    series: pd.Series,
    scale_min: Optional[float] = None,
    scale_max: Optional[float] = None,
    higher_is_worse: bool = True,
) -> pd.Series:
    s = _to_numeric(series)
    valid = s.dropna()
    if valid.empty:
        return s
    lo = float(valid.min()) if scale_min is None else float(scale_min)
    hi = float(valid.max()) if scale_max is None else float(scale_max)
    if lo >= 1.0 and hi <= 4.0 and np.all(np.isclose(valid, np.round(valid))):
        out = s if higher_is_worse else (5.0 - s)
        return out.clip(1.0, 4.0)
    span = max(1e-6, hi - lo)
    norm01 = ((s - lo) / span).clip(0.0, 1.0)
    if not higher_is_worse:
        norm01 = 1.0 - norm01
    mapped = np.floor(norm01 * 3.999999) + 1.0
    return pd.Series(np.where(s.isna(), np.nan, mapped), index=series.index, dtype=float)


def enforce_plausibility_bounds(df: pd.DataFrame) -> pd.DataFrame:
    """Replaces physically impossible sensor artifacts with NaN without dropping partial rows."""
    out = df.copy()
    for col, (lo, hi) in PLAUSIBILITY_BOUNDS.items():
        if col in out.columns:
            vals = _to_numeric(out[col])
            out[col] = vals.where((vals >= lo) & (vals <= hi), np.nan)
    if "systolic_bp" in out.columns and "diastolic_bp" in out.columns:
        bad_pp = out["systolic_bp"].notna() & out["diastolic_bp"].notna() & (out["systolic_bp"] <= out["diastolic_bp"] + 10.0)
        out.loc[bad_pp, ["systolic_bp", "diastolic_bp"]] = np.nan
    return out


def _resolve_column(df: pd.DataFrame, canonical_name: str, explicit_map: Optional[Mapping[str, str]]) -> Optional[str]:
    if explicit_map and canonical_name in explicit_map and explicit_map[canonical_name] in df.columns:
        return explicit_map[canonical_name]
    lower_lookup = {str(c).strip().lower(): c for c in df.columns}
    for alias in DEFAULT_COLUMN_ALIASES.get(canonical_name, [canonical_name]):
        if alias in lower_lookup:
            return lower_lookup[alias]
    return None


_COL_UNIT_SUFFIX_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"_(mmol_l|mmol)$"), "mmol/l"),
    (re.compile(r"_kpa$"), "kpa"),
    (re.compile(r"_(hpa|mbar)$"), "hpa"),
    (re.compile(r"_(degf|fahrenheit|f)$"), "f"),
    (re.compile(r"_(kelvin|degk|k)$"), "k"),
    (re.compile(r"_(min|mins|minute|minutes)$"), "minutes"),
    (re.compile(r"_(sec|secs|second|seconds)$"), "seconds"),
    (re.compile(r"_(rad|radian|radians)$"), "rad"),
    (re.compile(r"_(usv_hr|usv_h|ugy_hr|ugy_h)$"), "usv/hr"),
    (re.compile(r"_cgy$"), "cgy"),
    (re.compile(r"_mgy$"), "mgy"),
    (re.compile(r"_gy$"), "gy"),
    (re.compile(r"_(msv_day|msv_d|msv)$"), "msv/day"),
    (re.compile(r"_(usv_day|usv_d|usv)$"), "usv/day"),
    (re.compile(r"_ppm$"), "ppm"),
    (re.compile(r"_(percent|pct)$"), "percent"),
    (re.compile(r"_(mmhg|torr)$"), "mmhg"),
]


def infer_unit_from_column_name(col_name: str) -> Optional[str]:
    """Extracts an explicit unit hint using strict unit-suffix patterns (never unsafe substrings)."""
    low = str(col_name).strip().lower()
    for pattern, unit_hint in _COL_UNIT_SUFFIX_PATTERNS:
        if pattern.search(low):
            return unit_hint
    return None


def _apply_rowwise_or_scalar_normalizer(
    series: pd.Series,
    normalizer_fn,
    scalar_unit: Optional[str],
    row_units: Optional[pd.Series],
) -> pd.Series:
    """Applies row-level UNITS conversion when a unit column exists, else batch conversion."""
    if scalar_unit or row_units is None:
        return normalizer_fn(series, scalar_unit)

    result = pd.Series(np.nan, index=series.index, dtype=float)
    unit_tokens = row_units.fillna("").astype(str).map(_clean_unit_token)
    for token in unit_tokens.unique():
        mask = unit_tokens == token
        result.loc[mask] = normalizer_fn(series.loc[mask], token or None)
    return result


def ingest_nasa_dataframe(
    raw_df: pd.DataFrame,
    mission_id: str = "nasa_challenge",
    column_mapping: Optional[Mapping[str, str]] = None,
    unit_hints: Optional[Mapping[str, str]] = None,
    unit_column: Optional[str] = None,
    mood_higher_is_worse: bool = True,
    cabin_pressure_mmhg: float = 760.0,
    approve_source_target: bool = False,
    strict_species_check: bool = True,
) -> pd.DataFrame:
    """Converts a raw human NASA dataset DataFrame into the canonical Bio Astro Lab 13-feature contract."""
    unit_hints = unit_hints or {}
    out = pd.DataFrame(index=raw_df.index)

    subj_col = _resolve_column(raw_df, "subject_id", column_mapping)
    out["subject_id"] = (
        "nasa_" + raw_df[subj_col].astype(str).str.strip()
        if subj_col is not None
        else [f"nasa_{mission_id}_row_{i}" for i in range(len(raw_df))]
    )

    mis_col = _resolve_column(raw_df, "mission_id", column_mapping)
    out["mission_id"] = raw_df[mis_col].astype(str) if mis_col is not None else mission_id

    ts_col = _resolve_column(raw_df, "sol_or_timestamp", column_mapping)
    out["sol_or_timestamp"] = raw_df[ts_col].astype(str) if ts_col is not None else [f"row_{i}" for i in range(len(raw_df))]
    out["data_source"] = "nasa_mission"

    row_units: Optional[pd.Series] = None
    if unit_column and unit_column in raw_df.columns:
        row_units = raw_df[unit_column]
    else:
        for cand in ["UNITS", "UNIT", "units", "unit"]:
            if cand in raw_df.columns:
                row_units = raw_df[cand]
                break

    normalizers = {
        "blood_glucose": lambda s, u: normalize_glucose_to_mgdl(s, u),
        "systolic_bp": lambda s, u: normalize_bp_to_mmhg(s, u),
        "diastolic_bp": lambda s, u: normalize_bp_to_mmhg(s, u),
        "body_temp": lambda s, u: normalize_temp_to_celsius(s, u),
        "sleep_hours": lambda s, u: normalize_sleep_to_hours(s, u),
        "mood_score": lambda s, _u: normalize_mood_to_ordinal(s, higher_is_worse=mood_higher_is_worse),
        "balance_score": lambda s, u: normalize_balance_to_pct(s, u),
        "joint_symmetry_diff": lambda s, u: normalize_angle_to_degrees(s, u),
        "facial_ear": lambda s, _u: _to_numeric(s),
        "heart_rate_bpm": lambda s, _u: _to_numeric(s),
        "spo2_pct": lambda s, u: normalize_spo2_to_pct(s, u),
        "radiation_dose_msv": lambda s, u: normalize_radiation_to_msv(s, u),
        "cabin_co2_mmhg": lambda s, u: normalize_co2_to_mmhg(s, u, cabin_pressure_mmhg=cabin_pressure_mmhg),
    }

    for feat in FEATURE_COLUMNS:
        src_col = _resolve_column(raw_df, feat, column_mapping)
        if src_col is not None:
            explicit_unit = unit_hints.get(feat) or infer_unit_from_column_name(src_col)
            out[feat] = _apply_rowwise_or_scalar_normalizer(
                raw_df[src_col], normalizers[feat], explicit_unit, row_units
            )
        else:
            out[feat] = np.nan

    if strict_species_check:
        for vital_col in ["heart_rate_bpm", "body_temp", "systolic_bp", "diastolic_bp"]:
            vals = _to_numeric(out[vital_col]).dropna()
            if len(vals) >= 10:
                lo, hi = PLAUSIBILITY_BOUNDS[vital_col]
                oob_rate = float(((vals < lo) | (vals > hi)).mean())
                if oob_rate > 0.20:
                    raise ValueError(
                        f"Species/Unit plausibility violation in '{vital_col}' for mission '{mission_id}': "
                        f"{oob_rate * 100:.1f}% of values fall outside human bounds [{lo}, {hi}]."
                    )

    out = enforce_plausibility_bounds(out)

    tgt_col = _resolve_column(raw_df, TARGET_COLUMN, column_mapping)
    if approve_source_target and tgt_col is not None and raw_df[tgt_col].notna().any():
        parsed_tgt = pd.to_numeric(raw_df[tgt_col], errors="coerce")
        valid_tgt = parsed_tgt.dropna()
        invalid_vals = set(valid_tgt.unique().tolist()) - {0, 1, 2, 0.0, 1.0, 2.0}
        if invalid_vals:
            raise ValueError(
                f"Invalid source target labels {sorted(invalid_vals)} in '{tgt_col}' for mission '{mission_id}'. "
                f"Manifest-approved targets must strictly be integers in {{0, 1, 2}}."
            )
        out[TARGET_COLUMN] = parsed_tgt
        out["label_source"] = "nasa_ground_truth"
        missing_lbl = out[TARGET_COLUMN].isna()
        if missing_lbl.any():
            out.loc[missing_lbl, TARGET_COLUMN] = out.loc[missing_lbl].apply(assign_spaceflight_risk_label, axis=1)
            out.loc[missing_lbl, "label_source"] = "clinical_schema"
    else:
        out[TARGET_COLUMN] = out.apply(assign_spaceflight_risk_label, axis=1)
        out["label_source"] = "clinical_schema"

    out = out.dropna(subset=[TARGET_COLUMN]).copy()
    out[TARGET_COLUMN] = out[TARGET_COLUMN].astype(int)
    return out[METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]].reset_index(drop=True)


def load_osdr_inspiration4_records(osdr_raw_dir: Path) -> pd.DataFrame:
    """
    Loads real SpaceX Inspiration4 crew glucose draws (OSD-575) grouped strictly by
    crew member (C001-C004) in canonical 13-feature partial-modality format (only
    blood_glucose observed, remaining modalities natively NaN), applying row-level UNITS conversion.
    """
    cmp_path = osdr_raw_dir / "OSD-575_CMP_SUBMITTED.csv"
    if not cmp_path.exists():
        return pd.DataFrame(columns=METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN])

    cmp = pd.read_csv(cmp_path)
    glu = cmp[cmp["ANALYTE"].astype(str).str.upper() == "GLUCOSE"].copy()
    if glu.empty:
        return pd.DataFrame(columns=METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN])

    out = pd.DataFrame(index=glu.index)
    out["subject_id"] = "nasa_i4_" + glu["SUBJECT_ID"].astype(str).str.strip()
    out["mission_id"] = "inspiration4_osd575"
    out["sol_or_timestamp"] = glu["timepoint"].astype(str).str.strip()
    out["data_source"] = "nasa_inspiration4"
    out["label_source"] = "clinical_schema"

    for feat in FEATURE_COLUMNS:
        out[feat] = np.nan
    row_units = glu["UNITS"] if "UNITS" in glu.columns else None
    out["blood_glucose"] = _apply_rowwise_or_scalar_normalizer(
        glu["VALUE"], normalize_glucose_to_mgdl, scalar_unit=None, row_units=row_units
    )
    out = enforce_plausibility_bounds(out)
    out[TARGET_COLUMN] = out.apply(assign_spaceflight_risk_label, axis=1)
    out = out.dropna(subset=[TARGET_COLUMN]).copy()
    out[TARGET_COLUMN] = out[TARGET_COLUMN].astype(int)
    return out[METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]].reset_index(drop=True)


DEFAULT_FORBIDDEN_PATTERNS = [
    "*_TRANSFORMED.csv",
    "spaceflight_clinical_triage_*.csv",
    "*DATADICTIONARY*.csv",
]


def load_nasa_directory(
    nasa_dir: Path,
    osdr_raw_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    return_report: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, Any]]:
    """
    Manifest-driven NASA ingestion loader:
    - Never blindly globs arbitrary CSVs in AI/data/nasa/.
    - Enforces species == 'human' and dataset_role == 'human_clinical'.
    - Quarantines non-human/animal OSDR sets (OSD-435, OSD-652, OSD-679), derived tables,
      and *_TRANSFORMED.csv duplicates.
    """
    frames = []
    report: dict[str, Any] = {"ingested": [], "quarantined": [], "unregistered": []}

    resolved_manifest = manifest_path or (nasa_dir / "manifest.json")
    manifest_data: dict[str, Any] = {}
    if resolved_manifest.exists():
        manifest_data = json.loads(resolved_manifest.read_text(encoding="utf-8"))

    allowed_species = {str(s).strip().lower() for s in manifest_data.get("allowed_species", ["human"])}
    allowed_roles = {str(r).strip().lower() for r in manifest_data.get("allowed_dataset_roles", ["human_clinical"])}
    forbidden_patterns = list(manifest_data.get("forbidden_filename_patterns", DEFAULT_FORBIDDEN_PATTERNS))

    registered_names: set[str] = set()
    for entry in manifest_data.get("datasets", []):
        rel_name = str(entry.get("filename", "")).strip()
        if not rel_name:
            continue
        registered_names.add(Path(rel_name).name)
        file_path = Path(rel_name) if Path(rel_name).is_absolute() else (nasa_dir / rel_name)
        species = str(entry.get("species", "")).strip().lower()
        role = str(entry.get("dataset_role", "")).strip().lower()
        fname = file_path.name

        if any(fnmatch.fnmatch(fname, pat) for pat in forbidden_patterns):
            report["quarantined"].append({"filename": fname, "reason": "Matches forbidden derived/transformed filename pattern"})
            continue
        if species not in allowed_species or role not in allowed_roles:
            report["quarantined"].append({
                "filename": fname,
                "reason": f"Quarantined: species='{species}' role='{role}' (requires species in {sorted(allowed_species)} and role in {sorted(allowed_roles)})",
            })
            continue
        if not file_path.exists():
            raise FileNotFoundError(f"Manifest dataset '{file_path}' declared in {resolved_manifest} was not found on disk.")

        raw_df = pd.read_parquet(file_path) if file_path.suffix.lower() == ".parquet" else pd.read_csv(file_path)
        norm_df = ingest_nasa_dataframe(
            raw_df,
            mission_id=str(entry.get("mission_id") or file_path.stem),
            column_mapping=entry.get("column_mapping"),
            unit_hints=entry.get("unit_hints"),
            unit_column=entry.get("unit_column"),
            mood_higher_is_worse=bool(entry.get("mood_higher_is_worse", True)),
            cabin_pressure_mmhg=float(entry.get("cabin_pressure_mmhg", 760.0)),
            approve_source_target=bool(entry.get("approved_target_column", False)),
            strict_species_check=True,
        )
        if not norm_df.empty:
            frames.append(norm_df)
            report["ingested"].append({"filename": fname, "rows": len(norm_df), "subjects": int(norm_df["subject_id"].nunique())})

    if nasa_dir.exists():
        for data_file in sorted(list(nasa_dir.glob("*.csv")) + list(nasa_dir.glob("*.parquet"))):
            if data_file.name not in registered_names:
                report["unregistered"].append({
                    "filename": data_file.name,
                    "reason": "Ignored unregistered file; must be explicitly declared in manifest.json with species='human' and dataset_role='human_clinical'.",
                })

    if osdr_raw_dir is not None and osdr_raw_dir.exists():
        i4_df = load_osdr_inspiration4_records(osdr_raw_dir)
        if not i4_df.empty:
            frames.append(i4_df)
            report["ingested"].append({"filename": "OSD-575_CMP_SUBMITTED.csv", "rows": len(i4_df), "subjects": int(i4_df["subject_id"].nunique())})

    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN])
    )
    return (combined, report) if return_report else combined
