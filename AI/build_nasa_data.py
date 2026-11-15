"""Build compact, offline-first NASA telemetry bundle (`nasa-data.js`) from local NASA assets."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "database" / "nasa_knowledge_base.json"
I4_CSV_PATH = ROOT / "AI" / "data" / "nasa_training" / "osdr_inspiration4_crew_matrix.csv"
OUT_JS_PATH = ROOT / "nasa-data.js"

BODY_REGION_IDS = [
    ("Brain, Eyes", "head"),
    ("Cardiovascular", "cardio"),
    ("Musculoskeletal", "musculoskeletal"),
    ("Immune", "immune"),
    ("Renal", "renal"),
]


def _region_slug(label: str) -> str:
    for prefix, slug in BODY_REGION_IDS:
        if prefix.lower() in (label or "").lower():
            return slug
    return "systemic"


def build_bundle() -> dict:
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))

    hazards = [
        {
            "id": h["id"],
            "code": h["hazard_code"],
            "title": h["title"],
            "url": h["url"],
            "summary": " ".join(str(h.get("summary", "")).split())[:520],
        }
        for h in kb.get("spaceflight_hazards", [])
    ]

    hrp_risks = [
        {
            "risk_id": r["risk_id"],
            "short_title": r["short_title"],
            "full_title": r["full_title"],
            "hrp_element": r["hrp_element"],
            "last_published": r.get("last_published", ""),
            "risk_statement": r.get("risk_statement", ""),
            "clinical_context": r.get("clinical_context", ""),
            "hrr_url": r.get("hrr_url", ""),
            "nasa_ref_url": r.get("nasa_ref_url", ""),
        }
        for r in kb.get("nasa_hrp_risks", [])
    ]

    body_systems = [
        {
            "id": _region_slug(b.get("body_region", "")),
            "body_region": b["body_region"],
            "nasa_risk_ids": [x.strip() for x in str(b.get("nasa_risk_ids", "")).split(",") if x.strip()],
            "hazards": b.get("hazards", ""),
            "key_conditions": b.get("key_conditions", ""),
            "measurable_indicators": b.get("measurable_indicators", ""),
            "prevention_and_treatment": b.get("prevention_and_treatment", ""),
        }
        for b in kb.get("body_systems_matrix", [])
    ]

    emergency_protocols = []
    for p in kb.get("emergency_protocols", []):
        steps = p.get("steps")
        if not isinstance(steps, list):
            try:
                steps = json.loads(p.get("steps_json", "[]"))
            except Exception:
                steps = []
        emergency_protocols.append(
            {
                "protocol_id": p["protocol_id"],
                "title": p["title"],
                "badge": p["badge"],
                "nasa_risk_id": str(p.get("nasa_risk_id", "")),
                "trigger_condition": p.get("trigger_condition", ""),
                "steps": steps,
            }
        )

    clinical_indicators = kb.get("clinical_indicators_thresholds", [])

    environments = [
        {
            "id": "Space Station",
            "label": "Space Station (LEO)",
            "gravity": "0 g Microgravity",
            "baselineRadiation": 0.55,
            "baselineCO2": 2.3,
            "pressurePsi": "14.7 psi N2/O2",
            "brief": "Cephalic fluid shift (~1.5-2 L), spinal elongation, circadian drift across 16 orbital day/night cycles.",
        },
        {
            "id": "Spacecraft",
            "label": "Spacecraft (Deep Transit)",
            "gravity": "0 g Transit",
            "baselineRadiation": 1.15,
            "baselineCO2": 2.8,
            "pressurePsi": "14.7 psi Nominal",
            "brief": "GCR/SPE radiation vigilance outside Earth magnetosphere with autonomous onboard clinical triage under comms delay.",
        },
        {
            "id": "Rover",
            "label": "Rover (Surface EVA)",
            "gravity": "0.16-0.38 g Partial-G",
            "baselineRadiation": 0.95,
            "baselineCO2": 3.1,
            "pressurePsi": "8.2 psi Suit/Cab",
            "brief": "Dynamic locomotion torque, suit scrubber ppCO2 excursions, and vestibu-motor stability during surface traversal.",
        },
        {
            "id": "Lunar/Planetary Base",
            "label": "Lunar/Planetary Base",
            "gravity": "0.16-0.38 g Habitat",
            "baselineRadiation": 1.4,
            "baselineCO2": 2.6,
            "pressurePsi": "10.2 psi Exploration Atmo",
            "brief": "Chronic galactic cosmic ray dose accumulation, orthostatic readaptation, and closed-loop habitat fatigue tracking.",
        },
    ]

    def _opt_float(row, *keys, scale=1.0, decimals=2):
        for k in keys:
            raw = row.get(k)
            if raw is not None and str(raw).strip() != "":
                try:
                    val = float(raw) * scale
                    return round(val, decimals) if decimals is not None else val
                except ValueError:
                    continue
        return None

    inspiration4_rows = []
    if I4_CSV_PATH.exists():
        with I4_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                crp_mg_l = _opt_float(row, "crp_concentration_milligram_per_liter")
                if crp_mg_l is None:
                    crp_mg_l = _opt_float(row, "crp_concentration_picogram_per_milliliter", scale=1e-6, decimals=2)
                inspiration4_rows.append(
                    {
                        "subject": (row.get("subject") or row.get("crew_tp") or row.get("Sample Name") or "").strip(),
                        "mission_phase": (row.get("mission_phase") or "").strip(),
                        "glucose_mg_dl": _opt_float(row, "glucose_mg_dl", "glucose_value_milligram_per_deciliter"),
                        "albumin_g_dl": _opt_float(row, "albumin_g_dl", "albumin_value_gram_per_deciliter"),
                        "hemoglobin_g_dl": _opt_float(
                            row,
                            "hemoglobin_g_dl",
                            "hemoglobin_value_gram_per_deciliter",
                            "hemoglobin_value_percent",
                        ),
                        "wbc_10e3_ul": _opt_float(
                            row,
                            "wbc_10e3_ul",
                            "white_blood_cell_count_10_3_per_microliter",
                            "white_blood_cell_count_value_thousand_per_microliter",
                        ),
                        "crp_mg_l": crp_mg_l,
                    }
                )

    mission_presets = [
        {
            "id": "i4-nominal",
            "label": "Inspiration4 C001 Nominal",
            "environment": "Space Station",
            "description": "Balanced crew metabolics and 3D locomotion baseline anchored on OSDR C001 fasting serum panel.",
            "features": {
                "blood_glucose": 92.0,
                "systolic_bp": 116.0,
                "diastolic_bp": 74.0,
                "body_temp": 36.8,
                "sleep_hours": 7.6,
                "mood_score": 1,
                "balance_score": 96.0,
                "joint_symmetry_diff": 1.4,
                "facial_ear": 0.31,
                "heart_rate_bpm": 64.0,
                "radiation_dose_msv": 0.55,
                "cabin_co2_mmhg": 1.5,
                "spo2_pct": 98.5,
            },
        },
        {
            "id": "iss-sleep-debt",
            "label": "ISS Circadian Sleep Debt",
            "environment": "Space Station",
            "description": "Extended orbital shiftwork producing mild cognitive/EAR fatigue without acute cardiopulmonary alarm.",
            "features": {
                "blood_glucose": 106.0,
                "systolic_bp": 124.0,
                "diastolic_bp": 79.0,
                "body_temp": 37.0,
                "sleep_hours": 5.4,
                "mood_score": 2,
                "balance_score": 87.0,
                "joint_symmetry_diff": 3.6,
                "facial_ear": 0.22,
                "heart_rate_bpm": 78.0,
                "radiation_dose_msv": 0.62,
                "cabin_co2_mmhg": 1.9,
                "spo2_pct": 97.6,
            },
        },
        {
            "id": "spe-radiation",
            "label": "Solar Particle Radiation Event",
            "environment": "Spacecraft",
            "description": "Transit capsule elevated solar particle dosimetry exceeding 4.2 mSv/day requiring storm shelter protocol.",
            "features": {
                "blood_glucose": 112.0,
                "systolic_bp": 126.0,
                "diastolic_bp": 80.0,
                "body_temp": 37.2,
                "sleep_hours": 6.8,
                "mood_score": 2,
                "balance_score": 89.0,
                "joint_symmetry_diff": 3.4,
                "facial_ear": 0.25,
                "heart_rate_bpm": 86.0,
                "radiation_dose_msv": 4.85,
                "cabin_co2_mmhg": 2.6,
                "spo2_pct": 96.8,
            },
        },
        {
            "id": "co2-hypoxia",
            "label": "Rover Scrubber CO2 / Hypoxia",
            "environment": "Rover",
            "description": "Elevated cabin ppCO2 (6.4 mmHg) with borderline arterial oxygen saturation requiring scrubber scrub.",
            "features": {
                "blood_glucose": 118.0,
                "systolic_bp": 146.0,
                "diastolic_bp": 94.0,
                "body_temp": 37.8,
                "sleep_hours": 5.5,
                "mood_score": 4,
                "balance_score": 76.0,
                "joint_symmetry_diff": 7.2,
                "facial_ear": 0.20,
                "heart_rate_bpm": 106.0,
                "radiation_dose_msv": 1.10,
                "cabin_co2_mmhg": 6.4,
                "spo2_pct": 91.0,
            },
        },
    ]

    return {
        "sourceChallengeUrl": kb.get("metadata", {}).get("source_challenge_url", ""),
        "hazards": hazards,
        "hrpRisks": hrp_risks,
        "clinicalIndicators": clinical_indicators,
        "bodySystems": body_systems,
        "emergencyProtocols": emergency_protocols,
        "environments": environments,
        "missionPresets": mission_presets,
        "inspiration4Sample": inspiration4_rows,
    }


def main():
    bundle = build_bundle()
    payload = json.dumps(bundle, ensure_ascii=False, indent=2)
    js = (
        "// Auto-generated from database/nasa_knowledge_base.json & osdr_inspiration4_crew_matrix.csv\n"
        "(function (root) {\n"
        f"  const NASA_DATA_BUNDLE = {payload};\n"
        "  if (typeof module !== 'undefined' && module.exports) {\n"
        "    module.exports = NASA_DATA_BUNDLE;\n"
        "  }\n"
        "  if (root) {\n"
        "    root.NASA_DATA_BUNDLE = NASA_DATA_BUNDLE;\n"
        "  }\n"
        "})(typeof window !== 'undefined' ? window : globalThis);\n"
    )
    OUT_JS_PATH.write_text(js, encoding="utf-8")
    print(
        f"Generated {OUT_JS_PATH.name}: hazards={len(bundle['hazards'])}, "
        f"hrpRisks={len(bundle['hrpRisks'])}, systems={len(bundle['bodySystems'])}, "
        f"protocols={len(bundle['emergencyProtocols'])}, presets={len(bundle['missionPresets'])}"
    )


if __name__ == "__main__":
    main()
