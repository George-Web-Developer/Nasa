"""
prepare_nasa_extended_dataset.py
Generates expanded, subject-disjoint, NASA-grounded ML & AI training datasets in AI/data/nasa_training/:
1. spaceflight_clinical_triage_{train,test,dataset}.csv (~6,717 subjects, 13 physiological & spaceflight features,
   combining all NHANES BP+HR, Glucose, Sleep/Mood + PhysioNet ICU Vitals/SpO2 + Balance + UCI Eye State
   + NASA OSDR Inspiration4 CMP Glucose baselines + NASA/CSA Radiation & ECLSS CO2 parameters).
2. osdr_inspiration4_clinical_labs.csv & osdr_inspiration4_crew_matrix.csv (real SpaceX Inspiration4 crew biomarkers).
3. osdr_radiation_cardio_ml.csv (1,152 real OSD-435 radiation echocardiography records).
4. osdr_sans_ocular_ml.csv (real OSD-583 & OSD-679 IOP/OCT SANS ocular records).
5. osdr_muscle_grip_ml.csv (595 real OSD-652 grip strength & bodyweight unloading records).
6. nasa_hrp_copilot_rag_corpus.jsonl (structured Q&A / RAG corpus from all 22 NASA HRP Risks, 5 Hazards, 327 Gaps, CSA CANS).
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

AI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AI_DIR.parent
CLEAN_DIR = AI_DIR / "data" / "cleaned"
DB_PATH = PROJECT_ROOT / "database" / "astronaut_health.db"
OSDR_RAW = PROJECT_ROOT / "database" / "nasa_osdr_raw"
KB_JSON = PROJECT_ROOT / "database" / "nasa_knowledge_base.json"
OUT_DIR = AI_DIR / "data" / "nasa_training"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXTENDED_FEATURES = [
    "blood_glucose",
    "systolic_bp",
    "diastolic_bp",
    "heart_rate_bpm",
    "body_temp",
    "spo2_pct",
    "sleep_hours",
    "mood_score",
    "balance_score",
    "joint_symmetry_diff",
    "facial_ear",
    "radiation_dose_msv",
    "cabin_co2_mmhg",
]


def assign_spaceflight_multi_hazard_label(row: pd.Series) -> tuple[int, int]:
    """
    Assigns (health_risk_label, primary_nasa_risk_id) grounded in NASA HRP medical standards:
    Labels: 0 = Optimal, 1 = Caution, 2 = Critical.
    """
    critical_flags = []
    risk_points = 0
    risk_drivers = {}

    def add_driver(rid: int, pts: int, is_crit: bool = False):
        risk_drivers[rid] = risk_drivers.get(rid, 0) + pts + (10 if is_crit else 0)

    # 1. Blood Glucose (NASA Risk 176/180)
    glu = row["blood_glucose"]
    if glu < 62 or glu > 190:
        critical_flags.append(176)
        add_driver(176, 3, True)
    elif glu < 70 or glu > 135:
        risk_points += 2
        add_driver(176, 2)
    elif glu > 115:
        risk_points += 1
        add_driver(176, 1)

    # 2. Blood Pressure & Heart Rate (NASA Risk 179 - Cardiovascular)
    sbp, dbp, hr = row["systolic_bp"], row["diastolic_bp"], row["heart_rate_bpm"]
    if sbp < 85 or sbp > 160 or dbp < 52 or dbp > 100 or hr < 45 or hr > 120:
        critical_flags.append(179)
        add_driver(179, 3, True)
    elif sbp < 92 or sbp > 138 or dbp < 58 or dbp > 88 or hr < 52 or hr > 100:
        risk_points += 2
        add_driver(179, 2)
    elif sbp > 128 or dbp > 83 or hr > 92:
        risk_points += 1
        add_driver(179, 1)

    # 3. Body Temperature (NASA Risk 85 - Immune / Fever)
    temp = row["body_temp"]
    if temp < 35.4 or temp > 38.3:
        critical_flags.append(85)
        add_driver(85, 3, True)
    elif temp < 35.9 or temp > 37.6:
        risk_points += 2
        add_driver(85, 2)
    elif temp > 37.3:
        risk_points += 1
        add_driver(85, 1)

    # 4. SpO2 & Cabin CO2 (NASA Risk 173 - Hypoxia & ECLSS)
    spo2, co2 = row["spo2_pct"], row["cabin_co2_mmhg"]
    if spo2 < 90.0 or co2 >= 4.0:
        critical_flags.append(173)
        add_driver(173, 3, True)
    elif spo2 < 94.0 or co2 >= 2.2:
        risk_points += 2
        add_driver(173, 2)

    # 5. Sleep & Behavioral Mood (NASA Risk 100 / 99)
    slp, mood = row["sleep_hours"], row["mood_score"]
    if slp < 4.5 or mood == 4:
        rid = 99 if mood == 4 else 100
        critical_flags.append(rid)
        add_driver(rid, 3, True)
    elif slp < 6.0 or mood == 3:
        rid = 99 if mood == 3 else 100
        risk_points += 2
        add_driver(rid, 2)
    elif slp < 6.5 or mood == 2:
        risk_points += 1
        add_driver(100, 1)

    # 6. Sensorimotor Balance & Joint Symmetry (NASA Risk 88 / 180)
    bal, asym = row["balance_score"], row["joint_symmetry_diff"]
    if bal < 62 or asym > 13.0:
        critical_flags.append(88)
        add_driver(88, 3, True)
    elif bal < 78 or asym > 6.5:
        risk_points += 2
        add_driver(88, 2)
    elif bal < 85 or asym > 4.5:
        risk_points += 1
        add_driver(88, 1)

    # 7. Ocular Fatigue / SANS indicator (NASA Risk 105)
    ear = row["facial_ear"]
    if ear < 0.195:
        critical_flags.append(105)
        add_driver(105, 3, True)
    elif ear < 0.235:
        risk_points += 2
        add_driver(105, 2)

    # 8. Space Radiation Exposure mSv/day (NASA Risk 96)
    rad = row["radiation_dose_msv"]
    if rad >= 15.0:
        critical_flags.append(96)
        add_driver(96, 3, True)
    elif rad >= 2.0:
        risk_points += 2
        add_driver(96, 2)
    elif rad >= 1.0:
        risk_points += 1
        add_driver(96, 1)

    primary_risk = max(risk_drivers, key=risk_drivers.get) if risk_drivers else 0
    if len(critical_flags) >= 1 or risk_points >= 6:
        return 2, primary_risk
    elif risk_points >= 3:
        return 1, primary_risk
    return 0, 0


def assemble_extended_split(bp_pool, glu_pool, slp_pool, vit_pool, bal_pool, i4_glu_vals, open_ratio, seed):
    rng = np.random.default_rng(seed)
    df = bp_pool[["SEQN", "systolic_bp", "diastolic_bp", "heart_rate_bpm"]].copy().reset_index(drop=True)
    n = len(df)

    # Attach real glucose & sleep/mood by SEQN where present; sample strictly from same-split pool otherwise
    df = df.merge(glu_pool[["SEQN", "blood_glucose"]], on="SEQN", how="left")
    df = df.merge(slp_pool[["SEQN", "sleep_hours", "mood_score"]], on="SEQN", how="left")

    # Combine NHANES + ICU + NASA OSDR Inspiration4 CMP glucose pools for missing glucose rows
    glu_combined_pool = np.concatenate([
        glu_pool["blood_glucose"].to_numpy(dtype=float),
        vit_pool["Glucose_median"].dropna().to_numpy(dtype=float),
        i4_glu_vals,
    ])
    miss_glu = df["blood_glucose"].isna()
    df.loc[miss_glu, "blood_glucose"] = rng.choice(glu_combined_pool, size=int(miss_glu.sum()), replace=True)

    # Hypo/hyperglycemic physiological tail support
    glu_vals = df["blood_glucose"].to_numpy(dtype=float)
    hypo_g = rng.random(n) < 0.02
    hyper_g = (~hypo_g) & (rng.random(n) < 0.02)
    glu_vals = np.where(hypo_g, rng.uniform(46.0, 61.5, size=n), glu_vals)
    glu_vals = np.where(hyper_g, rng.uniform(192.0, 245.0, size=n), glu_vals)
    df["blood_glucose"] = np.round(glu_vals, 1)

    # Fill missing sleep/mood strictly from same-split NHANES SLQ/DPQ pool
    miss_slp = df["sleep_hours"].isna() | df["mood_score"].isna()
    if miss_slp.sum() > 0:
        slp_idx = rng.integers(0, len(slp_pool), size=int(miss_slp.sum()))
        df.loc[miss_slp, "sleep_hours"] = slp_pool.iloc[slp_idx]["sleep_hours"].to_numpy()
        df.loc[miss_slp, "mood_score"] = slp_pool.iloc[slp_idx]["mood_score"].to_numpy()

    # Sample body_temp and SpO2 from same-split PhysioNet ICU Vitals pool
    temp_pool = vit_pool["Temp_median"].dropna().to_numpy(dtype=float)
    spo2_pool = vit_pool["SaO2_median"].dropna().to_numpy(dtype=float)
    spo2_pool = spo2_pool[(spo2_pool >= 80.0) & (spo2_pool <= 100.0)]

    sampled_temps = rng.choice(temp_pool, size=n, replace=True)
    hypo_t = rng.random(n) < 0.025
    fever_t = (~hypo_t) & (rng.random(n) < 0.03)
    sampled_temps = np.where(hypo_t, rng.uniform(34.8, 35.35, size=n), sampled_temps)
    sampled_temps = np.where(fever_t, rng.uniform(38.35, 39.2, size=n), sampled_temps)
    df["body_temp"] = np.round(sampled_temps, 2)

    sampled_spo2 = rng.choice(spo2_pool, size=n, replace=True)
    hypoxia_mask = rng.random(n) < 0.025
    sampled_spo2 = np.where(hypoxia_mask, rng.uniform(84.0, 89.8, size=n), sampled_spo2)
    df["spo2_pct"] = np.round(np.clip(sampled_spo2, 82.0, 100.0), 1)

    # Sample Balance & Joint Symmetry from same-split PhysioNet Balance pool
    bal_idx = rng.integers(0, len(bal_pool), size=n)
    bal_s = bal_pool.iloc[bal_idx].reset_index(drop=True)
    df["balance_score"] = bal_s["balance_score"].to_numpy(dtype=float)
    base_asym = np.clip(bal_s["asym_raw"].to_numpy(dtype=float) * 3.8 + rng.uniform(0.2, 2.5, size=n), 0.2, 12.8)
    asym_tail = rng.random(n) < 0.045
    df["joint_symmetry_diff"] = np.round(np.where(asym_tail, rng.uniform(13.2, 18.0, size=n), base_asym), 2)

    # Sample Ocular EAR calibrated by OpenML eye open_ratio + mild sleep/mood propensity
    mood_term = (df["mood_score"].to_numpy(dtype=float) / 4.0) * 0.25
    sleep_term = ((10.0 - df["sleep_hours"].clip(3.0, 10.0).to_numpy(dtype=float)) / 7.0) * 0.25
    fat_score = mood_term + sleep_term + rng.uniform(0.0, 0.50, size=n)
    thresh = float(np.quantile(fat_score, open_ratio))
    df["facial_ear"] = np.round(
        np.where(fat_score >= thresh, rng.uniform(0.165, 0.235, size=n), rng.uniform(0.240, 0.340, size=n)),
        3,
    )

    # NASA Spaceflight Environment Parameters (Radiation mSv/day + Cabin ppCO2 mmHg)
    # 70% LEO nominal (0.4-0.8 mSv/d), 22% Deep space/Lunar/Mars GCR (1.1-2.3 mSv/d), 8% SPE/elevated (3.0-22.0 mSv/d)
    rad_regime = rng.random(n)
    rad_vals = np.where(
        rad_regime < 0.70,
        rng.uniform(0.35, 0.85, size=n),
        np.where(rad_regime < 0.92, rng.uniform(1.10, 2.35, size=n), rng.uniform(2.50, 22.0, size=n)),
    )
    df["radiation_dose_msv"] = np.round(rad_vals, 2)

    co2_regime = rng.random(n)
    co2_vals = np.where(
        co2_regime < 0.78,
        rng.uniform(0.8, 1.9, size=n),
        np.where(co2_regime < 0.95, rng.uniform(2.0, 3.6, size=n), rng.uniform(4.0, 6.2, size=n)),
    )
    df["cabin_co2_mmhg"] = np.round(co2_vals, 2)

    df["sleep_hours"] = np.round(df["sleep_hours"], 1)
    df["mood_score"] = df["mood_score"].astype(int)
    df["systolic_bp"] = np.round(df["systolic_bp"], 1)
    df["diastolic_bp"] = np.round(df["diastolic_bp"], 1)
    df["heart_rate_bpm"] = np.round(df["heart_rate_bpm"], 1)

    labels_and_risks = df[EXTENDED_FEATURES].apply(assign_spaceflight_multi_hazard_label, axis=1)
    df["health_risk_label"] = [x[0] for x in labels_and_risks]
    df["primary_nasa_risk_id"] = [x[1] for x in labels_and_risks]

    return df[EXTENDED_FEATURES + ["health_risk_label", "primary_nasa_risk_id"]]


def build_extended_clinical_dataset():
    bp = pd.read_csv(CLEAN_DIR / "clean_nhanes_bp.csv")
    glu = pd.read_csv(CLEAN_DIR / "clean_nhanes_glucose.csv")
    slp = pd.read_csv(CLEAN_DIR / "clean_sleep_stress_data.csv")
    vit = pd.read_csv(CLEAN_DIR / "clean_vitals_temp_data.csv")
    bal = pd.read_csv(CLEAN_DIR / "clean_balance_data.csv")
    eye = pd.read_csv(CLEAN_DIR / "clean_eye_fatigue_data.csv")

    # Clean BP + HR
    bp["systolic_bp"] = bp[["BPXSY1", "BPXSY2", "BPXSY3"]].mean(axis=1)
    bp["diastolic_bp"] = bp[["BPXDI1", "BPXDI2", "BPXDI3"]].mean(axis=1)
    bp["heart_rate_bpm"] = bp["BPXPLS"]
    bp_clean = bp[["SEQN", "systolic_bp", "diastolic_bp", "heart_rate_bpm"]].dropna()
    bp_clean = bp_clean[(bp_clean["diastolic_bp"] >= 40.0) & (bp_clean["systolic_bp"] >= 70.0)].drop_duplicates("SEQN")

    glu_clean = glu[["SEQN", "LBXGLU"]].rename(columns={"LBXGLU": "blood_glucose"}).dropna().drop_duplicates("SEQN")

    for col in ["SLD012", "SLD013"]:
        slp.loc[slp[col] > 24, col] = np.nan
    slp["sleep_hours"] = slp[["SLD012", "SLD013"]].mean(axis=1)
    dpq_cols = [f"DPQ0{i}0" for i in range(1, 10) if f"DPQ0{i}0" in slp.columns]
    for col in dpq_cols:
        slp.loc[slp[col] > 3, col] = np.nan
    slp["phq_total"] = slp[dpq_cols].sum(axis=1, min_count=3)
    slp["mood_score"] = pd.cut(slp["phq_total"], bins=[-1, 3, 8, 14, 30], labels=[1, 2, 3, 4]).astype(float)
    slp_clean = slp[["SEQN", "sleep_hours", "mood_score"]].dropna().drop_duplicates("SEQN")

    bal_subj = (
        bal[["Subject", "Best_T", "Best_3l", "Best_3r", "Best_6l", "Best_6r"]]
        .dropna()
        .groupby("Subject", as_index=False)
        .first()
    )
    bal_subj["balance_score"] = np.round((bal_subj["Best_T"] / 28.0) * 100.0, 2)
    bal_subj["asym_raw"] = (bal_subj["Best_3l"] - bal_subj["Best_3r"]).abs() + (bal_subj["Best_6l"] - bal_subj["Best_6r"]).abs()

    vit_subj = vit[["RecordID", "Temp_median", "Glucose_median", "SaO2_median"]].dropna(subset=["Temp_median"]).drop_duplicates("RecordID")
    vit_subj = vit_subj[(vit_subj["Temp_median"] >= 34.8) & (vit_subj["Temp_median"] <= 39.5)]

    open_ratio = float((eye["Class"].dropna().astype(int) == 1).mean())

    # Real NASA OSDR Inspiration4 Crew Glucose values
    cmp = pd.read_csv(OSDR_RAW / "OSD-575_CMP_SUBMITTED.csv")
    i4_glu_vals = cmp[cmp["ANALYTE"] == "GLUCOSE"]["VALUE"].dropna().to_numpy(dtype=float)

    # Subject-disjoint 80/20 split BEFORE feature assembly
    bp_tr, bp_te = train_test_split(bp_clean, test_size=0.20, random_state=42)
    glu_tr, glu_te = train_test_split(glu_clean, test_size=0.20, random_state=42)
    slp_tr, slp_te = train_test_split(slp_clean, test_size=0.20, random_state=42)
    vit_tr, vit_te = train_test_split(vit_subj, test_size=0.20, random_state=42)
    bal_tr, bal_te = train_test_split(bal_subj, test_size=0.20, random_state=42)

    assert set(bp_tr["SEQN"]).isdisjoint(set(bp_te["SEQN"]))

    train_df = assemble_extended_split(bp_tr, glu_tr, slp_tr, vit_tr, bal_tr, i4_glu_vals, open_ratio, seed=101)
    test_df = assemble_extended_split(bp_te, glu_te, slp_te, vit_te, bal_te, i4_glu_vals, open_ratio, seed=202)

    train_df.to_csv(OUT_DIR / "spaceflight_clinical_triage_train.csv", index=False)
    test_df.to_csv(OUT_DIR / "spaceflight_clinical_triage_test.csv", index=False)
    pd.concat([train_df.assign(split="train"), test_df.assign(split="test")], ignore_index=True).to_csv(
        OUT_DIR / "spaceflight_clinical_triage_dataset.csv", index=False
    )
    print(f"Extended Triage Dataset: train={len(train_df)}, test={len(test_df)}, total={len(train_df)+len(test_df)}")
    print("  Train label dist:", train_df["health_risk_label"].value_counts().sort_index().to_dict())


def build_osdr_ml_datasets():
    # 1. Inspiration4 Clinical Labs (1,084 rows)
    conn = sqlite3.connect(DB_PATH)
    labs = pd.read_sql_query("SELECT * FROM osdr_inspiration4_labs", conn)
    labs["mission_phase"] = np.where(labs["timepoint"].str.startswith("L-"), "Pre-flight", "Post-flight")
    labs.to_csv(OUT_DIR / "osdr_inspiration4_clinical_labs.csv", index=False)

    # 2. Inspiration4 Wide Crew Matrix (CBC + CMP + Cardiovascular)
    cbc_w = pd.read_csv(OSDR_RAW / "OSD-569_CBC_TRANSFORMED.csv")
    cmp_w = pd.read_csv(OSDR_RAW / "OSD-575_CMP_TRANSFORMED.csv")
    cv_w = pd.read_csv(OSDR_RAW / "OSD-575_Cardiovascular_TRANSFORMED.csv")

    cbc_w["crew_tp"] = cbc_w["Sample Name"].str.replace("_whole-blood", "", regex=False).str.replace("_cbc", "", regex=False)
    cmp_w["crew_tp"] = cmp_w["Sample Name"].str.replace("_serum", "", regex=False)
    cv_w["crew_tp"] = cv_w["Sample Name"].str.replace("_serum", "", regex=False)

    wide = cmp_w.merge(cbc_w, on="crew_tp", how="outer", suffixes=("", "_cbc")).merge(
        cv_w, on="crew_tp", how="outer", suffixes=("", "_cv")
    )
    wide["mission_phase"] = np.where(wide["crew_tp"].str.contains("_L-"), "Pre-flight", "Post-flight")
    wide.to_csv(OUT_DIR / "osdr_inspiration4_crew_matrix.csv", index=False)

    # 3. Radiation & Cardiovascular Echocardiography ML Dataset (OSD-435: 1,152 rows)
    rad_df = pd.read_sql_query("SELECT * FROM osdr_radiation_cardio_metrics", conn)
    rad_df["radiation_exposed"] = (rad_df["dose_gy"].fillna(0) > 0).astype(int)
    rad_df.to_csv(OUT_DIR / "osdr_radiation_cardio_ml.csv", index=False)

    # 4. SANS Ocular IOP & OCT Retinal Thickness ML Datasets (OSD-583 + OSD-679)
    sans_iop = pd.read_sql_query("SELECT * FROM osdr_sans_ocular_metrics", conn)
    sans_iop.to_csv(OUT_DIR / "osdr_sans_ocular_ml.csv", index=False)

    oct679 = pd.read_csv(OSDR_RAW / "OSD-679_LSDS-81_Ophthalmologic Diagnostic Technique_Fuller_OCT_TRANSFORMED.csv").dropna(how="all")
    oct679.to_csv(OUT_DIR / "osdr_sans_oct_retinal_ml.csv", index=False)

    # 5. Muscle Grip Strength & Bodyweight Unloading ML Dataset (OSD-652: 595 rows)
    grip = pd.read_csv(OSDR_RAW / "OSD-652_LSDS-76_Force Transducer_Grip_Strength_Transformed.csv")
    bw = pd.read_csv(OSDR_RAW / "OSD-652_LSDS-76_Force Transducer_Bodyweight_Transformed.csv")
    muscle = grip.merge(bw, on="Sample Name", how="left")
    muscle.to_csv(OUT_DIR / "osdr_muscle_grip_ml.csv", index=False)

    conn.close()
    print(f"OSDR ML datasets saved: labs={len(labs)}, wide={len(wide)}, rad_cardio={len(rad_df)}, sans_iop={len(sans_iop)}, sans_oct={len(oct679)}, muscle={len(muscle)}")


def build_rag_copilot_corpus():
    with open(KB_JSON, encoding="utf-8") as f:
        kb = json.load(f)

    records = []
    # Hazards
    for h in kb["spaceflight_hazards"]:
        records.append({
            "id": f"hazard_{h['hazard_code']}",
            "category": "Spaceflight Hazard",
            "source_url": h["url"],
            "title": h["title"],
            "prompt": f"What are the physiological and mission impacts of the NASA spaceflight hazard: {h['title']}?",
            "response": h["full_text"][:2200],
        })

    # 22 HRP Risks
    drm_by_risk = {}
    for d in kb["risk_drm_ratings"]:
        drm_by_risk.setdefault(d["risk_id"], []).append(d)

    for r in kb["nasa_hrp_risks"]:
        rid = r["risk_id"]
        drms = drm_by_risk.get(rid, [])
        drm_str = "; ".join(
            f"{d['drm_category']} ({d['mission_type_duration']}): Ops {d['ops_lxc']} [{d['ops_disposition']}], Long-Term {d['lth_lxc']} [{d['lth_disposition']}]"
            for d in drms
        )
        records.append({
            "id": f"hrp_risk_{rid}",
            "category": "NASA HRP Risk",
            "source_url": r["hrr_url"],
            "title": r["full_title"],
            "prompt": f"Explain NASA HRP Risk #{rid} ({r['short_title']}): {r['full_title']}, its mission ratings, and clinical context.",
            "response": f"HRP Element: {r['hrp_element']}. Risk Statement: {r['risk_statement']}\n\nContext: {r['clinical_context'][:1400]}\n\nMission Ratings (DRM): {drm_str}",
        })

    # Clinical Indicators & Thresholds
    for ind in kb["clinical_indicators_thresholds"]:
        records.append({
            "id": f"indicator_{ind['indicator_code']}",
            "category": "Clinical Indicator",
            "source_url": "https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources",
            "title": ind["name"],
            "prompt": f"How is {ind['name']} measured in space, what are nominal vs critical thresholds, and what countermeasures apply?",
            "response": (
                f"Unit: {ind['unit']}. Nominal: {ind['nominal_range']}. Caution: {ind['caution_range']}. "
                f"Critical: {ind['critical_threshold']}. Microgravity Effect: {ind['microgravity_effect']} "
                f"Space Measurement: {ind['measurement_in_space']} Countermeasure: {ind['countermeasure']}"
            ),
        })

    # CSA Radiation & ISS
    for c in kb["csa_resources"]:
        records.append({
            "id": f"csa_{len(records)}",
            "category": "CSA Space Health & Radiation",
            "source_url": c["url"],
            "title": c["title"],
            "prompt": f"Summarize Canadian Space Agency (CSA) insights on: {c['title']}",
            "response": c["full_text"][:2200],
        })

    # Research Gaps (327 records)
    for g in kb["research_gaps"]:
        records.append({
            "id": f"gap_{g['gap_id']}",
            "category": "NASA HRP Research Gap",
            "source_url": g["url"],
            "title": g["gap_code"],
            "prompt": f"What is NASA HRP Research Gap {g['gap_code']}?",
            "response": g["title"],
        })

    # Emergency Protocols
    for ep in kb["emergency_protocols"]:
        records.append({
            "id": f"protocol_{ep['protocol_id']}",
            "category": "Emergency Protocol",
            "source_url": f"https://humanresearchroadmap.nasa.gov/Risks/?i={ep['nasa_risk_id']}",
            "title": ep["title"],
            "prompt": f"What is the spaceflight emergency protocol for {ep['protocol_id']} (trigger: {ep['trigger_condition']})?",
            "response": f"[{ep['badge']}] {ep['title']}:\n- " + "\n- ".join(ep["steps"]),
        })

    out_jsonl = OUT_DIR / "nasa_hrp_copilot_rag_corpus.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"RAG/LLM Copilot corpus saved: {len(records)} structured records -> {out_jsonl}")


if __name__ == "__main__":
    build_extended_clinical_dataset()
    build_osdr_ml_datasets()
    build_rag_copilot_corpus()
