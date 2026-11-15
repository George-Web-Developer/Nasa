"""
Leak-Free, Subject-Disjoint Unified Dataset Builder for Bio Astro Lab.

Combines:
1. Real human NHANES 2017-2018 simultaneous vitals (BP, HR, Fasting Glucose, Sleep, PHQ-9 Mood)
2. Real human PhysioNet CinC 2012 ICU simultaneous multivariate physiology
   (BP, HR, Core Temp, Glucose, SpO2) with held-out SOFA/SAPS-I severity audit columns
3. Real human PhysioNet Balance posturography (strictly 1 row per unique Subject)
4. Real UCI EEG Eye State open/closed prior computed strictly on training slice
5. Real SpaceX Inspiration4 OSDR (OSD-575) astronaut glucose profiles + AI/data/nasa/

Zero leakage guarantees:
- All entity pools (NHANES SEQN, CinC RecordID, Balance Subject, UCI Eye train slice,
  NASA subject_id) are split strictly into 80% Train / 20% Test BEFORE feature assembly.
- No duplicate training subjects are injected; modality availability regimes (Full-13,
  Legacy-9, No-Webcam, Cardiopulmonary-only) are assigned independently across unique
  subjects so missingness never leaks clinical class (no ICU missingness shortcut).
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ingest_nasa import (  # noqa: E402
    EXTENDED_FEATURES,
    FEATURE_COLUMNS,
    METADATA_COLUMNS,
    TARGET_COLUMN,
    assign_spaceflight_risk_label,
    enforce_plausibility_bounds,
    load_nasa_directory,
)

CLEAN_DIR = BASE_DIR / "data" / "cleaned"
NASA_DIR = BASE_DIR / "data" / "nasa"
OSDR_RAW_DIR = PROJECT_ROOT / "database" / "nasa_osdr_raw"
OUTPUT_CSV = BASE_DIR / "data" / "astronaut_health_dataset.csv"
TRAIN_CSV = BASE_DIR / "data" / "train_dataset.csv"
TEST_CSV = BASE_DIR / "data" / "test_dataset.csv"
ICU_AUDIT_CSV = BASE_DIR / "data" / "cinc_outcome_audit_test.csv"

WEBCAM_MODALITIES = ["balance_score", "joint_symmetry_diff", "facial_ear"]


def _compute_fatigue_score(sleep_series: pd.Series, mood_series: pd.Series, rng: np.random.Generator) -> np.ndarray:
    """Computes ocular fatigue propensity with mild sleep/mood physiological correlation."""
    mood_vals = mood_series.fillna(2.0).to_numpy(dtype=float)
    sleep_vals = sleep_series.fillna(7.0).clip(3.0, 10.0).to_numpy(dtype=float)
    mood_term = (mood_vals / 4.0) * 0.25
    sleep_term = ((10.0 - sleep_vals) / 7.0) * 0.25
    return mood_term + sleep_term + rng.uniform(0.0, 0.50, size=len(sleep_vals))


def _apply_modality_regimes(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """
    Assigns realistic, label-independent sensor availability masks across distinct subjects:
    - 46% Full 13-feature telemetry
    - 24% Legacy 9-feature telemetry (heart_rate_bpm, spo2_pct, radiation, co2 = NaN)
    - 15% Step-1 vitals + env only (webcam modalities = NaN)
    - 15% Cardiopulmonary ICU-matched subset (sleep, mood, webcam, rad, co2 = NaN)
    Prevents missingness shortcut leakage when combining NHANES and CinC ICU cohorts.
    """
    rng = np.random.default_rng(seed)
    out = df.copy()
    regime = rng.random(len(out))

    legacy_9_mask = (regime >= 0.46) & (regime < 0.70)
    no_cam_mask = (regime >= 0.70) & (regime < 0.85)
    icu_subset_mask = regime >= 0.85

    for col in EXTENDED_FEATURES:
        out.loc[legacy_9_mask, col] = np.nan

    for col in WEBCAM_MODALITIES:
        out.loc[no_cam_mask, col] = np.nan

    for col in ["sleep_hours", "mood_score"] + WEBCAM_MODALITIES + ["radiation_dose_msv", "cabin_co2_mmhg"]:
        out.loc[icu_subset_mask, col] = np.nan

    return out


def _assemble_nhanes_cohort(
    nh_df: pd.DataFrame,
    bal_df: pd.DataFrame,
    vit_df: pd.DataFrame,
    fatigue_threshold: float,
    split_seed: int,
) -> pd.DataFrame:
    """Assembles spaceflight telemetry for a single split's NHANES subject pool (zero cross-split coupling)."""
    rng = np.random.default_rng(split_seed)
    df = nh_df.copy().reset_index(drop=True)
    n = len(df)

    # Temperature & SpO2 sampled strictly from same-split CinC pool + rare tail coverage
    temp_pool = vit_df["Temp_median"].dropna().to_numpy(dtype=float)
    spo2_pool = vit_df["SaO2_median"].dropna().to_numpy(dtype=float)
    spo2_pool = spo2_pool[(spo2_pool >= 80.0) & (spo2_pool <= 100.0)]

    sampled_temps = rng.choice(temp_pool, size=n, replace=True)
    hypo_t = rng.random(n) < 0.030
    sub_hypo_t = (~hypo_t) & (rng.random(n) < 0.025)
    fever_t = (~hypo_t) & (~sub_hypo_t) & (rng.random(n) < 0.030)
    sampled_temps = np.where(hypo_t, rng.uniform(34.7, 35.39, size=n), sampled_temps)
    sampled_temps = np.where(sub_hypo_t, rng.uniform(35.40, 35.89, size=n), sampled_temps)
    sampled_temps = np.where(fever_t, rng.uniform(38.31, 39.25, size=n), sampled_temps)
    df["body_temp"] = np.round(sampled_temps, 2)

    sampled_spo2 = rng.choice(spo2_pool, size=n, replace=True)
    hypoxia_mask = rng.random(n) < 0.030
    mild_hypoxia = (~hypoxia_mask) & (rng.random(n) < 0.025)
    sampled_spo2 = np.where(hypoxia_mask, rng.uniform(84.0, 89.94, size=n), sampled_spo2)
    sampled_spo2 = np.where(mild_hypoxia, rng.uniform(90.00, 93.94, size=n), sampled_spo2)
    df["spo2_pct"] = np.round(np.clip(sampled_spo2, 82.0, 100.0), 1)

    # Glycemic & hemodynamic threshold-adjacent support on top of real NHANES observations
    hypo_g = rng.random(n) < 0.030
    hyper_g = (~hypo_g) & (rng.random(n) < 0.025)
    glu_vals = df["blood_glucose"].to_numpy(dtype=float)
    glu_mask = ~np.isnan(glu_vals)
    glu_vals = np.where(glu_mask & hypo_g, rng.uniform(45.0, 61.94, size=n), glu_vals)
    glu_vals = np.where(glu_mask & hyper_g, rng.uniform(190.06, 245.0, size=n), glu_vals)
    df["blood_glucose"] = np.round(glu_vals, 1)

    hypo_bp = rng.random(n) < 0.030
    hyper_bp = (~hypo_bp) & (rng.random(n) < 0.020)
    sbp_vals = df["systolic_bp"].to_numpy(dtype=float)
    dbp_vals = df["diastolic_bp"].to_numpy(dtype=float)
    sbp_vals = np.where(hypo_bp, rng.uniform(74.0, 84.94, size=n), sbp_vals)
    dbp_vals = np.where(hypo_bp, np.minimum(dbp_vals, sbp_vals - 18.0).clip(42.0, 51.94), dbp_vals)
    sbp_vals = np.where(hyper_bp, rng.uniform(160.06, 184.0, size=n), sbp_vals)
    dbp_vals = np.where(hyper_bp, rng.uniform(100.06, 114.0, size=n), dbp_vals)
    df["systolic_bp"] = np.round(sbp_vals, 1)
    df["diastolic_bp"] = np.round(dbp_vals, 1)

    # Sensorimotor balance & symmetry sampled strictly from same-split Balance subjects
    bal_idx = rng.integers(0, len(bal_df), size=n)
    bal_s = bal_df.iloc[bal_idx].reset_index(drop=True)
    df["balance_score"] = bal_s["balance_score"].to_numpy(dtype=float)
    base_asym = np.clip(bal_s["asym_raw"].to_numpy(dtype=float) * 3.8 + rng.uniform(0.2, 2.5, size=n), 0.2, 12.98)
    asym_tail = rng.random(n) < 0.045
    df["joint_symmetry_diff"] = np.round(np.where(asym_tail, rng.uniform(13.02, 18.0, size=n), base_asym), 2)

    # Ocular EAR calibrated using training-slice open_ratio quantile (no threshold dead-zone)
    fat_scores = _compute_fatigue_score(df["sleep_hours"], df["mood_score"], rng)
    df["facial_ear"] = np.round(
        np.where(fat_scores >= fatigue_threshold, rng.uniform(0.160, 0.2344, size=n), rng.uniform(0.2356, 0.340, size=n)),
        3,
    )

    # Orbital / Deep-space GCR+SPE & ECLSS CO2 regimes (contiguous across 1.0/2.0/15.0 mSv & 2.2/4.0 mmHg)
    rad_regime = rng.random(n)
    df["radiation_dose_msv"] = np.round(
        np.where(
            rad_regime < 0.70,
            rng.uniform(0.35, 1.00, size=n),
            np.where(
                rad_regime < 0.86,
                rng.uniform(1.01, 2.00, size=n),
                np.where(rad_regime < 0.94, rng.uniform(2.01, 14.98, size=n), rng.uniform(15.00, 22.0, size=n)),
            ),
        ),
        2,
    )

    co2_regime = rng.random(n)
    df["cabin_co2_mmhg"] = np.round(
        np.where(
            co2_regime < 0.76,
            rng.uniform(0.80, 2.20, size=n),
            np.where(co2_regime < 0.93, rng.uniform(2.21, 3.99, size=n), rng.uniform(4.00, 6.20, size=n)),
        ),
        2,
    )

    df["sleep_hours"] = np.round(df["sleep_hours"], 1)
    df["heart_rate_bpm"] = np.round(df["heart_rate_bpm"], 1)
    df["subject_id"] = "nhanes_" + df["SEQN"].astype(int).astype(str)
    df["mission_id"] = "terrestrial_analog"
    df["sol_or_timestamp"] = "baseline"
    df["data_source"] = "nhanes_terrestrial"
    df["label_source"] = "clinical_schema"

    df = _apply_modality_regimes(df, seed=split_seed + 77)
    df = enforce_plausibility_bounds(df)
    df[TARGET_COLUMN] = df[FEATURE_COLUMNS].apply(assign_spaceflight_risk_label, axis=1)
    df = df.dropna(subset=[TARGET_COLUMN]).copy()
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)
    return df[METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]].reset_index(drop=True)


def _assemble_cinc_icu_cohort(vit_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Converts real PhysioNet CinC 2012 ICU multivariate records (same-patient BP, HR,
    Temp, Glucose, SpO2) into partial-modality canonical format, while returning held-out
    clinical outcome columns (SOFA, SAPS-I, In-hospital_death) for external validation.
    """
    out = pd.DataFrame(index=vit_df.index)
    out["subject_id"] = "cinc_" + vit_df["RecordID"].astype(int).astype(str)
    out["mission_id"] = "physionet_cinc_icu"
    out["sol_or_timestamp"] = "icu_median"
    out["data_source"] = "physionet_icu"
    out["label_source"] = "clinical_schema"

    inv_sbp = pd.to_numeric(vit_df["SysABP_median"], errors="coerce")
    inv_dbp = pd.to_numeric(vit_df["DiasABP_median"], errors="coerce")
    ni_sbp = pd.to_numeric(vit_df["NISysABP_median"], errors="coerce")
    ni_dbp = pd.to_numeric(vit_df["NIDiasABP_median"], errors="coerce")

    # Enforce paired arterial vs oscillometric NIBP validity so a zeroed/damped
    # arterial line cleanly falls back to valid NIBP as a (SBP, DBP) pair and
    # invalid cuffs never leak unilateral SBP-without-DBP artifacts.
    inv_ok = inv_sbp.between(60.0, 260.0) & inv_dbp.between(35.0, 160.0) & (inv_sbp > inv_dbp + 10.0)
    ni_ok = ni_sbp.between(60.0, 260.0) & ni_dbp.between(35.0, 160.0) & (ni_sbp > ni_dbp + 10.0)
    pair_ok = inv_ok | ni_ok

    old_sbp = inv_sbp.fillna(ni_sbp)
    old_dbp = inv_dbp.fillna(ni_dbp)
    old_pair_ok = old_sbp.between(60.0, 260.0) & old_dbp.between(35.0, 160.0) & (old_sbp > old_dbp + 10.0)
    old_unilat = (
        (old_sbp.between(60.0, 260.0) & ~old_dbp.between(35.0, 160.0))
        | (~old_sbp.between(60.0, 260.0) & old_dbp.between(35.0, 160.0))
    )
    recovered_bp_pairs = int(pair_ok.sum() - old_pair_ok.sum())
    cleared_unilat_bp = int((old_unilat & ~pair_ok).sum())

    sbp = pd.Series(np.where(inv_ok, inv_sbp, np.where(ni_ok, ni_sbp, np.nan)), index=vit_df.index, dtype=float)
    dbp = pd.Series(np.where(inv_ok, inv_dbp, np.where(ni_ok, ni_dbp, np.nan)), index=vit_df.index, dtype=float)

    out["blood_glucose"] = np.round(vit_df["Glucose_median"].to_numpy(dtype=float), 1)
    out["systolic_bp"] = np.round(sbp.to_numpy(dtype=float), 1)
    out["diastolic_bp"] = np.round(dbp.to_numpy(dtype=float), 1)
    out["body_temp"] = np.round(vit_df["Temp_median"].to_numpy(dtype=float), 2)
    out["sleep_hours"] = np.nan
    out["mood_score"] = np.nan
    out["balance_score"] = np.nan
    out["joint_symmetry_diff"] = np.nan
    out["facial_ear"] = np.nan
    out["heart_rate_bpm"] = np.round(vit_df["HR_median"].to_numpy(dtype=float), 1)
    out["spo2_pct"] = np.round(vit_df["SaO2_median"].to_numpy(dtype=float), 1)
    out["radiation_dose_msv"] = np.nan
    out["cabin_co2_mmhg"] = np.nan

    out = enforce_plausibility_bounds(out)
    out[TARGET_COLUMN] = out[FEATURE_COLUMNS].apply(assign_spaceflight_risk_label, axis=1)
    keep_mask = out[TARGET_COLUMN].notna()
    dropped_unlabeled = int((~keep_mask).sum())
    out = out.loc[keep_mask].copy()
    out[TARGET_COLUMN] = out[TARGET_COLUMN].astype(int)

    audit = vit_df.loc[keep_mask, ["RecordID", "SAPS-I", "SOFA", "In-hospital_death"]].copy()
    audit_sentinels = 0
    for scol in ("SAPS-I", "SOFA"):
        vals = pd.to_numeric(audit[scol], errors="coerce")
        neg_mask = vals < 0
        audit_sentinels += int(neg_mask.sum())
        audit[scol] = vals.where(~neg_mask, np.nan)
    audit["subject_id"] = out["subject_id"].to_numpy()
    print(
        f"[Hygiene CinC ICU] rows={len(vit_df)}->{len(out)} (dropped_unlabeled={dropped_unlabeled}, "
        f"recovered_nibp_pairs={recovered_bp_pairs}, cleared_unilateral_bp={cleared_unilat_bp}, "
        f"audit_neg_sentinels_nulled={audit_sentinels})"
    )
    return (
        out[METADATA_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]].reset_index(drop=True),
        audit.reset_index(drop=True),
    )


def split_nasa_by_subject(nasa_df: pd.DataFrame, random_state: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splits longitudinal/multi-mission NASA records by canonical subject_id with zero overlap."""
    if nasa_df.empty:
        return nasa_df.copy(), nasa_df.iloc[0:0].copy()

    unique_subjects = int(nasa_df["subject_id"].nunique())
    if unique_subjects < 2:
        # Single-subject cohorts stay in train to avoid fabricating synthetic split targets
        return nasa_df.copy(), nasa_df.iloc[0:0].copy()

    strat_key = nasa_df["mission_id"].astype(str) + "__" + nasa_df[TARGET_COLUMN].astype(str)
    mission_class_groups = strat_key.groupby(nasa_df["subject_id"]).first().value_counts()
    if len(mission_class_groups) >= 2 and int(mission_class_groups.min()) >= 2:
        y_strat = strat_key
        min_groups = int(mission_class_groups.min())
    else:
        y_strat = nasa_df[TARGET_COLUMN]
        class_group_counts = nasa_df.groupby(TARGET_COLUMN)["subject_id"].nunique()
        min_groups = int(class_group_counts.min()) if not class_group_counts.empty else 0

    n_splits = min(5, unique_subjects, min_groups)
    if n_splits >= 2:
        sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        tr_idx, te_idx = next(sgkf.split(nasa_df[FEATURE_COLUMNS], y_strat, nasa_df["subject_id"]))
        tr_out = nasa_df.iloc[tr_idx].copy()
        te_out = nasa_df.iloc[te_idx].copy()
    else:
        subj_list = nasa_df["subject_id"].unique()
        rng_nasa = np.random.default_rng(random_state)
        test_subjs = set(rng_nasa.choice(subj_list, size=max(1, len(subj_list) // 4), replace=False))
        tr_out = nasa_df[~nasa_df["subject_id"].isin(test_subjs)].copy()
        te_out = nasa_df[nasa_df["subject_id"].isin(test_subjs)].copy()

    assert set(tr_out["subject_id"]).isdisjoint(set(te_out["subject_id"])), "NASA subject_id overlap!"
    return tr_out, te_out


def _feature_signature_series(df: pd.DataFrame, cols: list[str] = FEATURE_COLUMNS) -> pd.Series:
    """Stable hashable 13-feature tuple key preserving NaNs via sentinel strings."""
    rounded = df[cols].round(4)
    return rounded.astype(object).where(rounded.notna(), "__NAN__").apply(tuple, axis=1)


def deduplicate_splits_zero_collision(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    max_sparse_observed: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Removes redundant single/dual-analyte repeats (e.g. identical glucose-only readings
    where all other telemetry is NaN) within each split and guarantees ZERO exact
    13-feature row collisions between train_df and test_df.
    """
    tr = train_df.copy().reset_index(drop=True)
    te = test_df.copy().reset_index(drop=True)

    tr_obs = tr[FEATURE_COLUMNS].notna().sum(axis=1)
    tr_sig = _feature_signature_series(tr)
    # Within train: collapse identical sparse (<=2 feature) tuples while preserving dense subjects
    sparse_seen: set[tuple] = set()
    tr_keep_mask = []
    for is_sparse, sig in zip(tr_obs <= max_sparse_observed, tr_sig):
        if not is_sparse:
            tr_keep_mask.append(True)
        elif sig not in sparse_seen:
            sparse_seen.add(sig)
            tr_keep_mask.append(True)
        else:
            tr_keep_mask.append(False)
    tr = tr.loc[tr_keep_mask].reset_index(drop=True)

    train_sigs_all = set(_feature_signature_series(tr).tolist())
    te_obs = te[FEATURE_COLUMNS].notna().sum(axis=1)
    te_sig = _feature_signature_series(te)
    te_sparse_seen: set[tuple] = set()
    te_keep_mask = []
    for is_sparse, sig in zip(te_obs <= max_sparse_observed, te_sig):
        if sig in train_sigs_all:
            te_keep_mask.append(False)
        elif is_sparse:
            if sig not in te_sparse_seen:
                te_sparse_seen.add(sig)
                te_keep_mask.append(True)
            else:
                te_keep_mask.append(False)
        else:
            te_keep_mask.append(True)
    te = te.loc[te_keep_mask].reset_index(drop=True)
    return tr, te


def build_unified_dataset():
    bp = pd.read_csv(CLEAN_DIR / "clean_nhanes_bp.csv")
    glu = pd.read_csv(CLEAN_DIR / "clean_nhanes_glucose.csv")
    slp = pd.read_csv(CLEAN_DIR / "clean_sleep_stress_data.csv")
    vit = pd.read_csv(CLEAN_DIR / "clean_vitals_temp_data.csv")
    bal = pd.read_csv(CLEAN_DIR / "clean_balance_data.csv")
    eye = pd.read_csv(CLEAN_DIR / "clean_eye_fatigue_data.csv")

    # 1. Clean NHANES BP + Heart Rate per cuff BEFORE averaging
    # SAS XPORT zero readings (5.398e-79) and corrupted cuff values (<35 mmHg DBP,
    # >160 DBP, <60 or >260 SBP, pulse pressure <= 10) must be masked per cuff before
    # averaging; otherwise a single zero cuff pulls a normotensive subject's mean DBP < 52.
    legacy_sy = bp[["BPXSY1", "BPXSY2", "BPXSY3"]].mean(axis=1)
    legacy_di = bp[["BPXDI1", "BPXDI2", "BPXDI3"]].mean(axis=1)
    legacy_ok = (
        legacy_sy.notna() & legacy_di.notna() & bp["BPXPLS"].notna()
        & (legacy_di >= 40.0) & (legacy_sy >= 70.0)
    )

    cuff_denorm_masked = 0
    cuff_oob_masked = 0
    for idx_c in (1, 2, 3, 4):
        sy_col, di_col = f"BPXSY{idx_c}", f"BPXDI{idx_c}"
        sy_raw = pd.to_numeric(bp[sy_col], errors="coerce")
        di_raw = pd.to_numeric(bp[di_col], errors="coerce")
        denorm_mask = (sy_raw.abs() < 1e-30) | (di_raw.abs() < 1e-30)
        cuff_denorm_masked += int(denorm_mask.sum())
        sy_val = sy_raw.where(sy_raw >= 1e-30, np.nan)
        di_val = di_raw.where(di_raw >= 1e-30, np.nan)
        pair_present = sy_val.notna() & di_val.notna()
        pair_valid = sy_val.between(60.0, 260.0) & di_val.between(35.0, 160.0) & (sy_val > di_val + 10.0)
        cuff_oob_masked += int((pair_present & ~pair_valid).sum())
        bp[f"_cuff_sy{idx_c}"] = sy_val.where(pair_valid, np.nan)
        bp[f"_cuff_di{idx_c}"] = di_val.where(pair_valid, np.nan)

    bp["systolic_bp"] = bp[["_cuff_sy1", "_cuff_sy2", "_cuff_sy3"]].mean(axis=1).fillna(bp["_cuff_sy4"])
    bp["diastolic_bp"] = bp[["_cuff_di1", "_cuff_di2", "_cuff_di3"]].mean(axis=1).fillna(bp["_cuff_di4"])
    bp["heart_rate_bpm"] = pd.to_numeric(bp["BPXPLS"], errors="coerce")
    bp_valid_mask = (
        bp["systolic_bp"].between(60.0, 260.0)
        & bp["diastolic_bp"].between(35.0, 160.0)
        & (bp["systolic_bp"] > bp["diastolic_bp"] + 10.0)
        & bp["heart_rate_bpm"].between(28.0, 220.0)
    )
    repaired_cuff_corrupted = int((legacy_ok & bp_valid_mask & ((bp["diastolic_bp"] - legacy_di).abs() > 0.5)).sum())
    recovered_bp_subjects = int((bp_valid_mask & ~legacy_ok).sum())
    bp_clean = bp.loc[bp_valid_mask, ["SEQN", "systolic_bp", "diastolic_bp", "heart_rate_bpm"]].drop_duplicates("SEQN").copy()
    print(
        f"[Hygiene NHANES BP] raw={len(bp)} -> clean={len(bp_clean)} | "
        f"cuff_denorm_zeros_masked={cuff_denorm_masked}, cuff_oob_masked={cuff_oob_masked}, "
        f"zero_deflated_subjects_repaired={repaired_cuff_corrupted}, valid_subjects_recovered={recovered_bp_subjects}"
    )

    # 2. Clean NHANES Glucose
    glu["LBXGLU"] = pd.to_numeric(glu["LBXGLU"], errors="coerce")
    glu_clean = glu.loc[glu["LBXGLU"].between(35.0, 500.0), ["SEQN", "LBXGLU"]].rename(columns={"LBXGLU": "blood_glucose"}).drop_duplicates("SEQN")

    # 3. Clean NHANES Sleep & PHQ-9 Mood
    sleep_oob = 0
    for col in ["SLD012", "SLD013"]:
        oob = slp[col] > 24
        sleep_oob += int(oob.sum())
        slp.loc[oob, col] = np.nan
    slp["sleep_hours"] = slp[["SLD012", "SLD013"]].mean(axis=1)
    dpq_cols = [f"DPQ0{i}0" for i in range(1, 10) if f"DPQ0{i}0" in slp.columns]
    dpq_refusal_masked = 0
    for col in dpq_cols:
        # Normalize SAS XPORT zero encoding (5.398e-79 -> exact 0.0 "Not at all")
        slp[col] = pd.to_numeric(slp[col], errors="coerce").where(lambda x: x.isna() | (x >= 1e-30), 0.0)
        bad_dpq = slp[col] > 3
        dpq_refusal_masked += int(bad_dpq.sum())
        slp.loc[bad_dpq, col] = np.nan
    slp["phq_total"] = slp[dpq_cols].sum(axis=1, min_count=3)
    slp["mood_score"] = pd.cut(slp["phq_total"], bins=[-1, 3, 8, 14, 30], labels=[1, 2, 3, 4]).astype(float)
    slp_clean = slp[["SEQN", "sleep_hours", "mood_score"]].dropna().drop_duplicates("SEQN")
    print(f"[Hygiene NHANES Sleep/PHQ9] raw={len(slp)} -> clean={len(slp_clean)} | sleep_gt24_masked={sleep_oob}, dpq_refusal_gt3_masked={dpq_refusal_masked}")

    # Left-join glucose so NHANES keeps both fasted-lab subjects AND non-lab BP/HR/sleep/mood subjects
    nhanes_all = (
        bp_clean.merge(slp_clean, on="SEQN", how="inner")
        .merge(glu_clean, on="SEQN", how="left")
        .drop_duplicates(subset=["SEQN"])
        .reset_index(drop=True)
    )

    # 4. Deduplicate Balance dataset strictly to 1 row per unique Subject
    bal_subj = (
        bal[["Subject", "Best_T", "Best_3l", "Best_3r", "Best_6l", "Best_6r"]]
        .dropna()
        .groupby("Subject", as_index=False)
        .first()
    )
    bal_subj["balance_score"] = np.round((bal_subj["Best_T"] / 28.0) * 100.0, 2)
    bal_subj["asym_raw"] = (bal_subj["Best_3l"] - bal_subj["Best_3r"]).abs() + (bal_subj["Best_6l"] - bal_subj["Best_6r"]).abs()

    # 5. Deduplicate CinC ICU patients strictly by RecordID
    vit_subj = vit.dropna(subset=["Temp_median"]).drop_duplicates(subset=["RecordID"]).reset_index(drop=True)

    # 6. Compute UCI Eye open_ratio strictly on the training 80% slice (zero test eye distribution leak)
    eye_tr, _ = train_test_split(eye["Class"].dropna().astype(int), test_size=0.20, random_state=42)
    open_ratio = float((eye_tr.to_numpy() == 1).mean())

    # 7. Split ALL source entity pools 80% Train / 20% Test BEFORE ANY feature pairing or threshold math
    nh_train, nh_test = train_test_split(
        nhanes_all, test_size=0.20, random_state=42, stratify=nhanes_all["mood_score"].astype(int)
    )
    bal_train, bal_test = train_test_split(bal_subj, test_size=0.20, random_state=42)
    vit_train, vit_test = train_test_split(vit_subj, test_size=0.20, random_state=42)

    assert set(nh_train["SEQN"]).isdisjoint(set(nh_test["SEQN"])), "NHANES SEQN overlap!"
    assert set(bal_train["Subject"]).isdisjoint(set(bal_test["Subject"])), "Balance Subject overlap!"
    assert set(vit_train["RecordID"]).isdisjoint(set(vit_test["RecordID"])), "CinC RecordID overlap!"

    # 8. Compute fatigue quantile threshold strictly on Training pool only
    rng_thresh = np.random.default_rng(42)
    train_fatigue_scores = _compute_fatigue_score(nh_train["sleep_hours"], nh_train["mood_score"], rng_thresh)
    train_fatigue_threshold = float(np.quantile(train_fatigue_scores, open_ratio))

    # 9. Assemble NHANES cohorts independently per split
    nh_tr_assembled = _assemble_nhanes_cohort(nh_train, bal_train, vit_train, train_fatigue_threshold, split_seed=1042)
    nh_te_assembled = _assemble_nhanes_cohort(nh_test, bal_test, vit_test, train_fatigue_threshold, split_seed=2042)

    # 10. Assemble real PhysioNet CinC multivariate ICU cohorts independently per split
    icu_tr_df, _ = _assemble_cinc_icu_cohort(vit_train)
    icu_te_df, icu_te_audit = _assemble_cinc_icu_cohort(vit_test)

    train_frames = [nh_tr_assembled, icu_tr_df]
    test_frames = [nh_te_assembled, icu_te_df]

    # 11. Ingest manifest-verified NASA OSDR human datasets from AI/data/nasa/manifest.json
    nasa_df, nasa_report = load_nasa_directory(NASA_DIR, osdr_raw_dir=OSDR_RAW_DIR, return_report=True)
    if not nasa_df.empty:
        nasa_train, nasa_test = split_nasa_by_subject(nasa_df, random_state=42)
        train_frames.append(nasa_train)
        if not nasa_test.empty:
            test_frames.append(nasa_test)

    train_df = pd.concat(train_frames, ignore_index=True)
    test_df = pd.concat(test_frames, ignore_index=True)

    pre_dedup_tr, pre_dedup_te = len(train_df), len(test_df)
    train_df, test_df = deduplicate_splits_zero_collision(train_df, test_df, max_sparse_observed=2)
    cross_split_exact_dups = len(
        set(_feature_signature_series(train_df).tolist()) & set(_feature_signature_series(test_df).tolist())
    )

    # Final leak-proof assertions
    assert set(train_df["subject_id"]).isdisjoint(set(test_df["subject_id"])), (
        "CRITICAL: subject_id overlap detected between train and test!"
    )
    assert cross_split_exact_dups == 0, (
        f"CRITICAL: {cross_split_exact_dups} exact 13-feature row collisions detected across train/test!"
    )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(TRAIN_CSV, index=False)
    test_df.to_csv(TEST_CSV, index=False)
    icu_te_audit.to_csv(ICU_AUDIT_CSV, index=False)

    combined_df = pd.concat([train_df.assign(split="train"), test_df.assign(split="test")], ignore_index=True)
    combined_df.to_csv(OUTPUT_CSV, index=False)

    print("=== LEAK-FREE, SUBJECT-DISJOINT 13-FEATURE DATASETS READY ===")
    print(f"OpenML Eye train-slice open_ratio : {open_ratio:.4f}")
    print(f"Manifest NASA report: ingested={len(nasa_report['ingested'])}, quarantined={len(nasa_report['quarantined'])}, unregistered={len(nasa_report['unregistered'])}")
    print(f"Deduplication: train {pre_dedup_tr}->{len(train_df)}, test {pre_dedup_te}->{len(test_df)}, cross-split exact collisions={cross_split_exact_dups}")
    print(f"Train Rows: {len(train_df)} (Unique subjects: {train_df['subject_id'].nunique()}) | sources: {train_df['data_source'].value_counts().to_dict()}")
    print(f"Test  Rows: {len(test_df)}  (Unique subjects: {test_df['subject_id'].nunique()}) | sources: {test_df['data_source'].value_counts().to_dict()}")
    print("Train Class Distribution:", train_df[TARGET_COLUMN].value_counts().sort_index().to_dict())
    print("Test  Class Distribution:", test_df[TARGET_COLUMN].value_counts().sort_index().to_dict())


if __name__ == "__main__":
    build_unified_dataset()
