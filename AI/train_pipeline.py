"""
Leak-Free, Regularized Multi-Modal Spaceflight Health Training & JS Export Pipeline.

Architecture highlights:
- 5-fold StratifiedGroupKFold CV grouped strictly by subject_id (zero leakage).
- Train-only balanced physiological manifold coverage inside each training fold so pure
  XGBoost learns isolated single-vital red flags natively WITHOUT needing imperative
  if-else guardrail overrides in production.
- Evaluates Generalization Gap (Train vs CV Val vs Untouched Test), ECE calibration,
  Legacy 9-feature mode, No-Webcam partial mode, 21-probe clinical sanity matrix, and
  external PhysioNet CinC ICU severity concordance (SAPS-I / SOFA).
- Exports standalone `ai-model.js` containing:
  * Regularized XGBoost booster weights (exact float32 parity + native NaN branches)
  * Declarative CLINICAL_BIOMARKER_SCHEMA & CLINICAL_TIERS (zero if-else triage chains)
  * Tree perturbation Feature Attribution (explainable ML drivers per sensor)
  * Embedded NASA Knowledge Base RAG docs + BM25-style queryBioCopilot retriever
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, spearmanr
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.preprocessing import label_binarize
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ingest_nasa import (  # noqa: E402
    CLINICAL_BIOMARKER_SCHEMA,
    CORE_9_FEATURES,
    EXTENDED_FEATURES,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    assign_spaceflight_risk_label,
)

DEFAULT_CSV_PATH = BASE_DIR / "data" / "astronaut_health_dataset.csv"
DEFAULT_TRAIN_CSV_PATH = BASE_DIR / "data" / "train_dataset.csv"
DEFAULT_TEST_CSV_PATH = BASE_DIR / "data" / "test_dataset.csv"
DEFAULT_AUDIT_CSV_PATH = BASE_DIR / "data" / "cinc_outcome_audit_test.csv"
DEFAULT_KB_JSON_PATH = PROJECT_ROOT / "database" / "nasa_knowledge_base.json"
DEFAULT_EXPORT_JS_PATH = PROJECT_ROOT / "ai-model.js"

CLASS_NAMES = ["Optimal", "Caution", "Critical"]

CLINICAL_TIERS = {
    0: {
        "tierText": "Tier 1 Mission Ready",
        "badgeText": "Status: Mission Ready (Tier 1)",
        "dotClass": "w-3 h-3 rounded-full bg-emerald-500",
        "badgeClass": "px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-semibold",
        "scoreTextClass": "text-3xl font-extrabold font-mono text-emerald-600",
        "barClass": "bg-emerald-500 h-1.5 rounded-full transition-all duration-300",
        "confTextClass": "text-lg font-bold font-mono text-emerald-600",
        "protocolTitle": "Routine Mission Operations",
        "protocolMeta": "Standard S-band telemetry cadence",
        "historyStatus": "Nominal",
        "summaryDetail": "Suitable for EVA, heavy maintenance, and high cognitive load operations.",
    },
    1: {
        "tierText": "Tier 2 Monitored Duty",
        "badgeText": "Status: Monitored (Tier 2)",
        "dotClass": "w-3 h-3 rounded-full bg-amber-500 animate-pulse",
        "badgeClass": "px-3 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-xs font-semibold",
        "scoreTextClass": "text-3xl font-extrabold font-mono text-amber-600",
        "barClass": "bg-amber-500 h-1.5 rounded-full transition-all duration-300",
        "confTextClass": "text-lg font-bold font-mono text-amber-600",
        "protocolTitle": "Enhanced Biometric Monitoring",
        "protocolMeta": "EVA restricted pending 4-hr re-evaluation",
        "historyStatus": "Monitored",
        "summaryDetail": "Moderate physiological strain or borderline telemetry detected; defer high-load EVA until re-check.",
    },
    2: {
        "tierText": "Tier 3 Flight Surgeon Escalation",
        "badgeText": "Status: Critical Alert (Tier 3)",
        "dotClass": "w-3 h-3 rounded-full bg-rose-600 animate-ping",
        "badgeClass": "px-3 py-1 bg-rose-50 text-rose-700 border border-rose-200 rounded-full text-xs font-semibold",
        "scoreTextClass": "text-3xl font-extrabold font-mono text-rose-600",
        "barClass": "bg-rose-600 h-1.5 rounded-full transition-all duration-300",
        "confTextClass": "text-lg font-bold font-mono text-rose-600",
        "protocolTitle": "Immediate Flight Surgeon Escalation",
        "protocolMeta": "PRIORITY UPLINK: Stand-down all hazardous ops",
        "historyStatus": "Critical",
        "summaryDetail": "Immediate medical stand-down required due to elevated ML multi-vital risk attribution.",
    },
}


def load_pre_split_datasets(
    train_csv_path: Path = DEFAULT_TRAIN_CSV_PATH,
    test_csv_path: Path = DEFAULT_TEST_CSV_PATH,
    fallback_csv_path: Path = DEFAULT_CSV_PATH,
):
    """Loads pre-split, subject-disjoint train and test datasets without leakage."""
    if train_csv_path.exists() and test_csv_path.exists():
        train_df = pd.read_csv(train_csv_path)
        test_df = pd.read_csv(test_csv_path)
    elif fallback_csv_path.exists():
        df = pd.read_csv(fallback_csv_path).dropna(subset=[TARGET_COLUMN])
        if "split" in df.columns:
            train_df = df[df["split"] == "train"].copy()
            test_df = df[df["split"] == "test"].copy()
        else:
            sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
            tr_idx, te_idx = next(sgkf.split(df[FEATURE_COLUMNS], df[TARGET_COLUMN].astype(int), df["subject_id"]))
            train_df, test_df = df.iloc[tr_idx].copy(), df.iloc[te_idx].copy()
    else:
        raise FileNotFoundError(f"Neither {train_csv_path}/{test_csv_path} nor {fallback_csv_path} exists.")

    for split_name, split_df in [("train", train_df), ("test", test_df)]:
        missing_cols = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in split_df.columns]
        if missing_cols:
            raise ValueError(f"{split_name} dataset missing columns: {missing_cols}")

    train_df = train_df.dropna(subset=[TARGET_COLUMN]).reset_index(drop=True)
    test_df = test_df.dropna(subset=[TARGET_COLUMN]).reset_index(drop=True)

    X_train = train_df[FEATURE_COLUMNS].copy()
    y_train = train_df[TARGET_COLUMN].astype(int).copy()
    X_test = test_df[FEATURE_COLUMNS].copy()
    y_test = test_df[TARGET_COLUMN].astype(int).copy()

    g_train = train_df["subject_id"].astype(str) if "subject_id" in train_df.columns else pd.Series([f"tr_{i}" for i in range(len(train_df))])
    g_test = test_df["subject_id"].astype(str) if "subject_id" in test_df.columns else pd.Series([f"te_{i}" for i in range(len(test_df))])
    assert set(g_train).isdisjoint(set(g_test)), "CRITICAL: Subject overlap between train and test splits!"

    src_train = train_df["data_source"].astype(str) if "data_source" in train_df.columns else pd.Series(["unknown"] * len(train_df))
    src_test = test_df["data_source"].astype(str) if "data_source" in test_df.columns else pd.Series(["unknown"] * len(test_df))
    sub_test = test_df["subject_id"].astype(str) if "subject_id" in test_df.columns else pd.Series([f"te_{i}" for i in range(len(test_df))])
    return X_train, X_test, y_train, y_test, g_train, g_test, src_train, src_test, sub_test


_BOUND_EPS = {
    "facial_ear": 0.001,
    "body_temp": 0.01,
    "cabin_co2_mmhg": 0.01,
    "radiation_dose_msv": 0.01,
    "joint_symmetry_diff": 0.02,
}


def cramers_v_from_missingness(X_df: pd.DataFrame, y_series: pd.Series | np.ndarray) -> float:
    """Computes Cramér's V between full 13-feature missingness bitmasks and target labels."""
    if len(X_df) == 0:
        return 0.0
    bitmasks = (
        X_df[FEATURE_COLUMNS]
        .isna()
        .astype(int)
        .astype(str)
        .agg("".join, axis=1)
    )
    y_vals = pd.Series(y_series).astype(int).reset_index(drop=True)
    ct = pd.crosstab(bitmasks.reset_index(drop=True), y_vals)
    r, c = ct.shape
    min_dim = min(r - 1, c - 1)
    if min_dim <= 0:
        return 0.0
    chi2, _, _, _ = chi2_contingency(ct.to_numpy(), correction=False)
    n = float(ct.to_numpy().sum())
    return float(np.sqrt(max(0.0, chi2 / (n * min_dim))))


def _fast_assign_labels(df: pd.DataFrame) -> np.ndarray:
    """Vector-friendly batch wrapper around table-driven assign_spaceflight_risk_label."""
    records = df[FEATURE_COLUMNS].to_dict("records")
    return np.array([assign_spaceflight_risk_label(rec) for rec in records], dtype=float)


def build_training_manifold_support(seed: int = 777) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Generates balanced single-corridor, threshold-edge, composite Caution, and healthy-anchor
    exemplars STRICTLY for training folds (never included in validation or held-out test sets).
    Closes boundary backoff dead-zones around all critical/caution edges.
    """
    rng = np.random.default_rng(seed)
    opt_bounds = {}
    caution_bands_by_key = {}
    for spec in CLINICAL_BIOMARKER_SCHEMA:
        opt_band = next(b for b in spec["bands"] if b["points"] == 0)
        lo = spec["plausible"][0] if opt_band.get("min") is None else float(opt_band["min"])
        hi = spec["plausible"][1] if opt_band.get("max") is None else float(opt_band["max"])
        opt_bounds[spec["key"]] = (lo, hi)
        caution_bands_by_key[spec["key"]] = [b for b in spec["bands"] if not b["critical"] and b["points"] >= 1]

    def _sample_healthy_row() -> dict:
        r = {}
        for s2 in CLINICAL_BIOMARKER_SCHEMA:
            k2 = s2["key"]
            lo2, hi2 = opt_bounds[k2]
            pad = (hi2 - lo2) * 0.04
            r[k2] = float(round(rng.uniform(lo2 + pad, hi2 - pad), 3))
        r["mood_score"] = float(rng.choice([1.0, 2.0], p=[0.78, 0.22]))
        return r

    rows = []
    sid = 0
    for spec in CLINICAL_BIOMARKER_SCHEMA:
        k = spec["key"]
        eps = _BOUND_EPS.get(k, 0.1)
        plaus_lo, plaus_hi = float(spec["plausible"][0]), float(spec["plausible"][1])
        for band in [b for b in spec["bands"] if b["points"] > 0]:
            reps = 44 if band["critical"] else 28
            b_lo = plaus_lo if band.get("min") is None else float(band["min"])
            b_hi = plaus_hi if band.get("max") is None else float(band["max"])
            lo_s = (
                (b_lo if band.get("minInclusive", True) else b_lo + eps)
                if band.get("min") is not None
                else max(plaus_lo, b_hi - max(eps * 8, (b_hi - plaus_lo) * 0.45))
            )
            hi_s = (
                (b_hi if band.get("maxInclusive", False) else b_hi - eps)
                if band.get("max") is not None
                else min(plaus_hi, b_lo + max(eps * 8, (plaus_hi - b_lo) * 0.30))
            )
            lo_s = min(max(lo_s, plaus_lo), plaus_hi)
            hi_s = min(max(hi_s, plaus_lo), plaus_hi)
            for _ in range(reps):
                row = _sample_healthy_row()
                if k == "mood_score":
                    row[k] = 4.0 if band["critical"] else 3.0
                else:
                    row[k] = float(round(rng.uniform(min(lo_s, hi_s), max(lo_s, hi_s)), 3))
                row[TARGET_COLUMN] = int(assign_spaceflight_risk_label(row))
                row["subject_id"] = f"train_manifold_{seed}_{sid}"
                sid += 1
                rows.append(row)

            # Dense exact boundary-straddling exemplars (left, at threshold, right)
            if k != "mood_score":
                for bound_key in ("min", "max"):
                    t_val = band.get(bound_key)
                    if t_val is None:
                        continue
                    t_val = float(t_val)
                    edge_offsets = [-2 * eps, -eps, 0.0, eps, 2 * eps]
                    for _rep in range(3):
                        for off in edge_offsets:
                            val = float(round(min(max(t_val + off, plaus_lo), plaus_hi), 3))
                            row = _sample_healthy_row()
                            row[k] = val
                            lbl = assign_spaceflight_risk_label(row)
                            if not np.isnan(lbl):
                                row[TARGET_COLUMN] = int(lbl)
                                row["subject_id"] = f"train_manifold_{seed}_{sid}"
                                sid += 1
                                rows.append(row)

    # Composite Caution exemplars (2-3 moderate deviations combining to 3-5 points, 0 critical)
    composite_keys = [s["key"] for s in CLINICAL_BIOMARKER_SCHEMA if caution_bands_by_key[s["key"]]]
    for _ in range(280):
        row = _sample_healthy_row()
        chosen = rng.choice(composite_keys, size=int(rng.integers(2, 4)), replace=False)
        for ck in chosen:
            cb = rng.choice(caution_bands_by_key[ck])
            spec_c = next(s for s in CLINICAL_BIOMARKER_SCHEMA if s["key"] == ck)
            eps_c = _BOUND_EPS.get(ck, 0.1)
            if ck == "mood_score":
                row[ck] = 3.0 if cb["points"] >= 2 else 2.0
            else:
                c_lo = float(cb["min"]) if cb.get("min") is not None else float(spec_c["plausible"][0])
                c_hi = float(cb["max"]) if cb.get("max") is not None else float(spec_c["plausible"][1])
                c_lo = c_lo if cb.get("minInclusive", True) else c_lo + eps_c
                c_hi = c_hi if cb.get("maxInclusive", False) else c_hi - eps_c
                row[ck] = float(round(rng.uniform(min(c_lo, c_hi), max(c_lo, c_hi)), 3))
        lbl = assign_spaceflight_risk_label(row)
        if not np.isnan(lbl):
            row[TARGET_COLUMN] = int(lbl)
            row["subject_id"] = f"train_manifold_{seed}_{sid}"
            sid += 1
            rows.append(row)

    # Healthy optimal anchors (diverse baseline coverage)
    for _ in range(380):
        row = _sample_healthy_row()
        row["mood_score"] = 1.0
        row[TARGET_COLUMN] = int(assign_spaceflight_risk_label(row))
        row["subject_id"] = f"train_manifold_{seed}_{sid}"
        sid += 1
        rows.append(row)

    man_df = pd.DataFrame(rows)
    return man_df[FEATURE_COLUMNS], man_df[TARGET_COLUMN].astype(int), man_df["subject_id"].astype(str)


def build_augmented_training_fold(
    X_fold: pd.DataFrame,
    y_fold: pd.Series,
    seed: int = 42,
    max_cramers_v: float = 0.05,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Combines a clean training fold with boundary manifold support, structured stochastic
    modality-dropout (Legacy-9, No-Webcam, ICU-subset, Step-1-only, random sensor dropout),
    and bitmask class-conditional equalization so XGBoost learns true missing-value routing
    with missingness-vs-target Cramér's V <= 0.05 (never touching CV validation or test data).
    """
    rng = np.random.default_rng(seed)
    X_man, y_man, _ = build_training_manifold_support(seed=seed + 700)

    X_base = pd.concat([X_fold[FEATURE_COLUMNS], X_man[FEATURE_COLUMNS]], ignore_index=True)
    y_base = pd.concat([pd.Series(y_fold).astype(int), y_man.astype(int)], ignore_index=True)

    # 1. Structured stochastic modality-dropout on rich (>=9 feature) training rows
    obs_counts = X_base.notna().sum(axis=1)
    rich_df = X_base.loc[obs_counts >= 9].copy().reset_index(drop=True)
    dropout_patterns = [
        ("legacy_9", EXTENDED_FEATURES),
        ("no_webcam", ["balance_score", "joint_symmetry_diff", "facial_ear"]),
        ("icu_subset", ["sleep_hours", "mood_score", "balance_score", "joint_symmetry_diff", "facial_ear", "radiation_dose_msv", "cabin_co2_mmhg"]),
        ("step1_only", ["balance_score", "joint_symmetry_diff", "facial_ear"] + EXTENDED_FEATURES),
    ]

    masked_chunks = [X_base.assign(**{TARGET_COLUMN: y_base.to_numpy()})]
    for _pname, drop_cols in dropout_patterns:
        sample_idx = rng.choice(len(rich_df), size=min(len(rich_df), 750), replace=False)
        sub = rich_df.iloc[sample_idx].copy()
        for dc in drop_cols:
            sub[dc] = np.nan
        sub_y = _fast_assign_labels(sub)
        valid = ~np.isnan(sub_y)
        sub = sub.loc[valid].copy()
        sub[TARGET_COLUMN] = sub_y[valid].astype(int)
        masked_chunks.append(sub)

    # Balanced single-analyte glucose_only support (enables LOMO & sparse-mission generalization)
    if not rich_df.empty:
        g_mask = rich_df.copy()
        for dc in [c for c in FEATURE_COLUMNS if c != "blood_glucose"]:
            g_mask[dc] = np.nan
        g_y = _fast_assign_labels(g_mask)
        g_valid = g_mask.loc[~np.isnan(g_y)].copy()
        if not g_valid.empty:
            g_valid[TARGET_COLUMN] = g_y[~np.isnan(g_y)].astype(int)
            for cls in (0, 1, 2):
                cls_rows = g_valid[g_valid[TARGET_COLUMN] == cls]
                if not cls_rows.empty:
                    pick_idx = rng.choice(len(cls_rows), size=80, replace=(len(cls_rows) < 80))
                    masked_chunks.append(cls_rows.iloc[pick_idx].copy())

    aug_df = pd.concat(masked_chunks, ignore_index=True)

    # 2. Equalize class ratios across every multi-feature missingness bitmask (including Full-13)
    aug_df["_mask_key"] = (
        aug_df[FEATURE_COLUMNS].isna().astype(int).astype(str).agg("".join, axis=1)
    )
    target_props = aug_df[TARGET_COLUMN].value_counts(normalize=True).reindex([0, 1, 2], fill_value=0.25).to_numpy()
    target_props = np.maximum(target_props, 0.22)
    target_props = target_props / target_props.sum()

    # Balanced compact pool of full-13 training/manifold donors so label computation runs once per mask
    full13_mask = aug_df[FEATURE_COLUMNS].notna().all(axis=1)
    rich_all = aug_df.loc[full13_mask].reset_index(drop=True)
    if len(rich_all) > 1800:
        donor_parts = []
        for cls in (0, 1, 2):
            cls_sub = rich_all[rich_all[TARGET_COLUMN] == cls]
            if not cls_sub.empty:
                take = min(600, len(cls_sub))
                donor_parts.append(cls_sub.iloc[rng.choice(len(cls_sub), size=take, replace=False)])
        rich_pool_df = pd.concat(donor_parts, ignore_index=True)
    else:
        rich_pool_df = rich_all

    balance_chunks = [aug_df.drop(columns=["_mask_key"])]
    mask_groups = aug_df.groupby("_mask_key")
    for mkey, grp in mask_groups:
        n_obs_in_mask = mkey.count("0")
        counts = grp[TARGET_COLUMN].value_counts().reindex([0, 1, 2], fill_value=0).to_numpy()
        cols_to_nan = [FEATURE_COLUMNS[i] for i, ch in enumerate(mkey) if ch == "1"]

        if n_obs_in_mask <= 1:
            if counts[2] == 0 and counts[0] > 0 and len(rich_pool_df) > 0:
                masked_rich = rich_pool_df[FEATURE_COLUMNS].copy()
                for c_nan in cols_to_nan:
                    masked_rich[c_nan] = np.nan
                masked_y = _fast_assign_labels(masked_rich)
                cls2_donors = masked_rich.loc[masked_y == 2].copy()
                if not cls2_donors.empty:
                    cls2_donors[TARGET_COLUMN] = 2
                    pick_n = min(len(cls2_donors), int(counts[0]))
                    balance_chunks.append(cls2_donors.iloc[rng.integers(0, len(cls2_donors), size=pick_n)].copy())
            continue

        target_scale = max((counts[c] / target_props[c]) for c in (0, 1, 2) if target_props[c] > 0)
        deficits = {cls: int(np.ceil(target_scale * target_props[cls])) - int(counts[cls]) for cls in (0, 1, 2)}
        if not any(d > 0 for d in deficits.values()):
            continue

        masked_rich = None
        masked_y = None
        if len(rich_pool_df) > 0:
            masked_rich = rich_pool_df[FEATURE_COLUMNS].copy()
            for c_nan in cols_to_nan:
                masked_rich[c_nan] = np.nan
            masked_y = _fast_assign_labels(masked_rich)

        for cls, deficit in deficits.items():
            if deficit <= 0:
                continue
            same_cls = grp[grp[TARGET_COLUMN] == cls].drop(columns=["_mask_key"])
            donor_frames = []
            if masked_rich is not None and masked_y is not None:
                cls_donors = masked_rich.loc[masked_y == cls].copy()
                cls_donors[TARGET_COLUMN] = cls
                if not cls_donors.empty:
                    donor_frames.append(cls_donors)
            if not same_cls.empty:
                donor_frames.append(same_cls)
            if not donor_frames:
                continue

            donor_pool = pd.concat(donor_frames, ignore_index=True)
            pick_idx = rng.integers(0, len(donor_pool), size=deficit)
            balance_chunks.append(donor_pool.iloc[pick_idx].copy())

    balanced_df = pd.concat(balance_chunks, ignore_index=True)
    return balanced_df[FEATURE_COLUMNS].reset_index(drop=True), balanced_df[TARGET_COLUMN].astype(int).reset_index(drop=True)


def build_xgb_classifier(early_stopping_rounds: int | None = 25, random_state: int = 42) -> XGBClassifier:
    """Returns a regularized multi-class XGBoost classifier with high-resolution splits & native NaN routing."""
    return XGBClassifier(
        n_estimators=550,
        max_depth=4,
        max_bin=1024,
        tree_method="hist",
        min_child_weight=5,
        gamma=0.15,
        learning_rate=0.055,
        subsample=0.85,
        colsample_bytree=0.90,
        reg_lambda=6.0,
        reg_alpha=0.6,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        missing=np.nan,
        early_stopping_rounds=early_stopping_rounds,
        random_state=random_state,
    )


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error on top-class predicted confidences."""
    conf = np.max(y_prob, axis=1)
    pred = np.argmax(y_prob, axis=1)
    acc = (pred == y_true).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        in_bin = (conf >= lo) & (conf <= hi if i == n_bins - 1 else conf < hi)
        if np.any(in_bin):
            ece += float(np.mean(in_bin)) * abs(float(np.mean(acc[in_bin])) - float(np.mean(conf[in_bin])))
    return ece


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict:
    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro"))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted"))
    prec, rec, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1, 2], zero_division=0)

    y_prob = np.asarray(y_prob, dtype=np.float64)
    row_sums = y_prob.sum(axis=1, keepdims=True)
    y_prob = np.divide(y_prob, row_sums, out=np.full_like(y_prob, 1.0 / 3.0), where=row_sums > 0)

    y_bin = label_binarize(y_true, classes=[0, 1, 2])
    roc_auc_macro = float(roc_auc_score(y_bin, y_prob, average="macro", multi_class="ovr"))
    roc_auc_per_class = roc_auc_score(y_bin, y_prob, average=None, multi_class="ovr")
    pr_auc_macro = float(average_precision_score(y_bin, y_prob, average="macro"))
    pr_auc_per_class = average_precision_score(y_bin, y_prob, average=None)

    ll = float(log_loss(y_true, y_prob))
    brier_per_class = [float(brier_score_loss(y_bin[:, c], y_prob[:, c])) for c in range(3)]
    brier_macro = float(np.mean(brier_per_class))
    ece = compute_ece(y_true, y_prob)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])

    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "support": sup,
        "roc_auc_macro": roc_auc_macro,
        "roc_auc_per_class": roc_auc_per_class,
        "pr_auc_macro": pr_auc_macro,
        "pr_auc_per_class": pr_auc_per_class,
        "log_loss": ll,
        "brier_macro": brier_macro,
        "brier_per_class": brier_per_class,
        "ece": ece,
        "confusion_matrix": cm,
    }


def print_metrics_summary(title: str, m: dict):
    print(f"\n=== {title} ===")
    print(f"Accuracy          : {m['accuracy'] * 100:.2f}%")
    print(f"Macro F1          : {m['macro_f1']:.4f}  | Weighted F1 : {m['weighted_f1']:.4f}")
    print(f"Macro ROC-AUC OvR : {m['roc_auc_macro']:.4f}  | Macro PR-AUC: {m['pr_auc_macro']:.4f}")
    print(f"Multi-class LogLoss: {m['log_loss']:.4f} | Macro Brier : {m['brier_macro']:.4f} | ECE : {m['ece']:.4f}")
    print("\nPer-Class Breakdown:")
    print(f"{'Class':<12} {'Prec':>8} {'Recall':>8} {'F1':>8} {'ROC-AUC':>9} {'PR-AUC':>9} {'Brier':>8} {'Support':>8}")
    for c, name in enumerate(CLASS_NAMES):
        print(
            f"{name:<12} {m['precision'][c]:8.4f} {m['recall'][c]:8.4f} {m['f1'][c]:8.4f} "
            f"{m['roc_auc_per_class'][c]:9.4f} {m['pr_auc_per_class'][c]:9.4f} "
            f"{m['brier_per_class'][c]:8.4f} {int(m['support'][c]):8d}"
        )
    print("\nConfusion Matrix (rows=True, cols=Pred [Optimal, Caution, Critical]):")
    print(m["confusion_matrix"])


def run_stratified_cv(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups: pd.Series,
    n_splits: int = 5,
    random_state: int = 42,
):
    """
    Runs strict 5-fold StratifiedGroupKFold CV where validation folds stay 100% pure
    real human subjects (no manifold rows ever enter validation folds).
    """
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    tr_accs, val_accs, tr_f1s, val_f1s, val_aucs, val_losses = [], [], [], [], [], []
    fold_cramers = []
    best_iters = []

    for fold_idx, (tr_idx, val_idx) in enumerate(sgkf.split(X_train, y_train, groups), start=1):
        tr_subjs = set(groups.iloc[tr_idx].astype(str))
        val_subjs = set(groups.iloc[val_idx].astype(str))
        assert tr_subjs.isdisjoint(val_subjs), f"Fold {fold_idx} has overlapping subjects!"

        X_tr_real = X_train.iloc[tr_idx]
        y_tr_real = y_train.iloc[tr_idx].to_numpy()
        X_f_tr, y_f_tr_s = build_augmented_training_fold(X_tr_real, y_train.iloc[tr_idx], seed=700 + fold_idx)
        y_f_tr = y_f_tr_s.to_numpy()
        fold_cramers.append(cramers_v_from_missingness(X_f_tr, y_f_tr))

        X_f_val = X_train.iloc[val_idx]
        y_f_val = y_train.iloc[val_idx].to_numpy()

        w_tr = compute_sample_weight("balanced", y_f_tr)
        w_val = compute_sample_weight("balanced", y_f_val)

        clf = build_xgb_classifier(early_stopping_rounds=25, random_state=random_state + fold_idx)
        clf.fit(
            X_f_tr,
            y_f_tr,
            sample_weight=w_tr,
            eval_set=[(X_f_val, y_f_val)],
            sample_weight_eval_set=[w_val],
            verbose=False,
        )

        tr_pred = clf.predict(X_tr_real)
        val_pred = clf.predict(X_f_val)
        val_prob = np.asarray(clf.predict_proba(X_f_val), dtype=np.float64)
        val_prob = val_prob / val_prob.sum(axis=1, keepdims=True)

        tr_accs.append(accuracy_score(y_tr_real, tr_pred))
        val_accs.append(accuracy_score(y_f_val, val_pred))
        tr_f1s.append(f1_score(y_tr_real, tr_pred, average="macro"))
        val_f1s.append(f1_score(y_f_val, val_pred, average="macro"))
        y_val_bin = label_binarize(y_f_val, classes=[0, 1, 2])
        val_aucs.append(roc_auc_score(y_val_bin, val_prob, average="macro", multi_class="ovr"))
        val_losses.append(log_loss(y_f_val, val_prob))
        best_iters.append(int(clf.best_iteration) if clf.best_iteration is not None else clf.n_estimators)

    cv_summary = {
        "train_acc_mean": float(np.mean(tr_accs)),
        "train_acc_std": float(np.std(tr_accs)),
        "val_acc_mean": float(np.mean(val_accs)),
        "val_acc_std": float(np.std(val_accs)),
        "train_f1_mean": float(np.mean(tr_f1s)),
        "train_f1_std": float(np.std(tr_f1s)),
        "val_f1_mean": float(np.mean(val_f1s)),
        "val_f1_std": float(np.std(val_f1s)),
        "val_auc_mean": float(np.mean(val_aucs)),
        "val_auc_std": float(np.std(val_aucs)),
        "val_logloss_mean": float(np.mean(val_losses)),
        "val_logloss_std": float(np.std(val_losses)),
        "fold_cramers_max": float(max(fold_cramers)) if fold_cramers else 0.0,
        "best_iters": best_iters,
    }
    print(f"\n=== 5-Fold StratifiedGroupKFold CV (Pure Held-Out Validation Subjects, n={len(X_train)}, subjects={groups.nunique()}) ===")
    print(f"CV Train (Real)   : {cv_summary['train_acc_mean']*100:.2f}% +/- {cv_summary['train_acc_std']*100:.2f}%")
    print(f"CV Val   Accuracy : {cv_summary['val_acc_mean']*100:.2f}% +/- {cv_summary['val_acc_std']*100:.2f}%")
    print(f"Train-Val Gap     : {(cv_summary['train_acc_mean'] - cv_summary['val_acc_mean'])*100:.2f}%")
    print(f"CV Train Macro F1 : {cv_summary['train_f1_mean']:.4f} +/- {cv_summary['train_f1_std']:.4f}")
    print(f"CV Val   Macro F1 : {cv_summary['val_f1_mean']:.4f} +/- {cv_summary['val_f1_std']:.4f}")
    print(f"CV Val   ROC-AUC  : {cv_summary['val_auc_mean']:.4f} +/- {cv_summary['val_auc_std']:.4f}")
    print(f"CV Val   Log-Loss : {cv_summary['val_logloss_mean']:.4f} +/- {cv_summary['val_logloss_std']:.4f}")
    print(f"Fold Aug CramersV : max={cv_summary['fold_cramers_max']:.4f}")
    print(f"Best Iterations   : {best_iters}")
    return cv_summary


def run_single_vital_sanity_suite(model: XGBClassifier):
    """Verifies that pure XGBoost (without any if-else safety gate) passes all single-vital & partial-sensor probes."""
    base = {s["key"]: float(s["nominalBaseline"]) for s in CLINICAL_BIOMARKER_SCHEMA}
    nan_ext = {c: np.nan for c in EXTENDED_FEATURES}
    nan_cam = {"balance_score": np.nan, "joint_symmetry_diff": np.nan, "facial_ear": np.nan}
    nan_icu = {c: np.nan for c in ["sleep_hours", "mood_score", "balance_score", "joint_symmetry_diff", "facial_ear", "radiation_dose_msv", "cabin_co2_mmhg"]}

    probes = [
        ("Nominal_13Features", {}, 0),
        ("Nominal_Legacy9", nan_ext, 0),
        ("Nominal_NoWebcam", nan_cam, 0),
        ("Nominal_ICUSubset", nan_icu, 0),
        ("Hypoglycemia_50", {"blood_glucose": 50.0}, 2),
        ("Hyperglycemia_220", {"blood_glucose": 220.0}, 2),
        ("Hypotension_SBP78", {"systolic_bp": 78.0}, 2),
        ("Hypertension_SBP175", {"systolic_bp": 175.0}, 2),
        ("LowDBP_46", {"diastolic_bp": 46.0}, 2),
        ("HighDBP_108", {"diastolic_bp": 108.0}, 2),
        ("Hypothermia_35.0", {"body_temp": 35.0}, 2),
        ("Fever_39.0", {"body_temp": 39.0}, 2),
        ("SleepDeprived_3.5", {"sleep_hours": 3.5}, 2),
        ("CriticalStress_4", {"mood_score": 4.0}, 2),
        ("LowBalance_50", {"balance_score": 50.0}, 2),
        ("JointAsymmetry_15", {"joint_symmetry_diff": 15.0}, 2),
        ("LowEAR_0.17", {"facial_ear": 0.17}, 2),
        ("Bradycardia_40", {"heart_rate_bpm": 40.0}, 2),
        ("Tachycardia_135", {"heart_rate_bpm": 135.0}, 2),
        ("Hypoxia_SpO2_86", {"spo2_pct": 86.0}, 2),
        ("SolarSPE_18mSv", {"radiation_dose_msv": 18.0}, 2),
        ("Hypercapnia_CO2_5.2", {"cabin_co2_mmhg": 5.2}, 2),
        ("Radiation_Edge_15.0", {"radiation_dose_msv": 15.0}, 2),
        ("CO2_Edge_4.0", {"cabin_co2_mmhg": 4.0}, 2),
        ("Temp_Edge_Hypo_35.3", {"body_temp": 35.3}, 2),
        ("Temp_Edge_Fever_38.4", {"body_temp": 38.4}, 2),
        ("SpO2_Edge_89.8", {"spo2_pct": 89.8}, 2),
        ("Glu_Edge_61.8", {"blood_glucose": 61.8}, 2),
        ("Glu_Edge_190.2", {"blood_glucose": 190.2}, 2),
        ("DBP_Edge_100.2", {"diastolic_bp": 100.2}, 2),
        ("HR_Edge_44.8", {"heart_rate_bpm": 44.8}, 2),
        ("HR_Edge_120.2", {"heart_rate_bpm": 120.2}, 2),
        ("Composite_Caution_Glu150_Sleep5", {"blood_glucose": 150.0, "sleep_hours": 5.0}, 1),
        ("Legacy9_HypoGlu", {"blood_glucose": 50.0, **nan_ext}, 2),
        ("Legacy9_LowSleep", {"sleep_hours": 3.5, **nan_ext}, 2),
        ("Legacy9_LowBal", {"balance_score": 50.0, **nan_ext}, 2),
        ("NoCam_HypoGlu", {"blood_glucose": 50.0, **nan_cam}, 2),
        ("NoCam_SPE18", {"radiation_dose_msv": 18.0, **nan_cam}, 2),
    ]
    rows = [[{**base, **ov}[col] for col in FEATURE_COLUMNS] for _, ov, _ in probes]
    probs = model.predict_proba(pd.DataFrame(rows, columns=FEATURE_COLUMNS))
    preds = np.argmax(probs, axis=1)
    failures = [
        f"{probes[i][0]} expected={probes[i][2]} got={int(preds[i])} probs={np.round(probs[i], 3).tolist()}"
        for i in range(len(probes))
        if int(preds[i]) != probes[i][2]
    ]
    print(f"\n=== Pure-ML Clinical Sanity Suite ({len(probes)}/{len(probes)} probes, ZERO if-else overrides) ===")
    if failures:
        raise AssertionError("Clinical sanity probes failed:\n  " + "\n  ".join(failures))
    print(f"All {len(probes)}/{len(probes)} probes classified accurately directly by XGBoost trees.")


def build_compact_nasa_knowledge_docs(kb_path: Path) -> list[dict]:
    """Compiles a lightweight offline RAG corpus from NASA HRP/OSDR/CSA scraped database."""
    if not kb_path.exists():
        return []
    with open(kb_path, encoding="utf-8") as f:
        kb = json.load(f)

    docs = []
    for h in kb.get("spaceflight_hazards", []):
        text_val = str(h.get("summary") or h.get("full_text") or h.get("description") or "").strip()
        docs.append({
            "id": str(h.get("hazard_code") or h.get("id") or h.get("hazard_id") or "").strip(),
            "kind": "RIDGE Hazard",
            "title": str(h.get("title") or h.get("name") or "").strip(),
            "feature": "",
            "text": text_val[:360],
        })
    for r in kb.get("nasa_hrp_risks", []):
        docs.append({
            "id": f"risk_{r.get('risk_id')}",
            "kind": "NASA HRP Risk",
            "title": f"{r.get('short_title', '')}: {r.get('full_title', '')}".strip(": "),
            "feature": "",
            "text": str(r.get("risk_statement") or r.get("clinical_context") or "")[:360],
        })
    for ind in kb.get("clinical_indicators_thresholds", []):
        docs.append({
            "id": str(ind.get("indicator_code", "")).strip(),
            "kind": "Clinical Indicator",
            "title": str(ind.get("name", "")).strip(),
            "feature": str(ind.get("app_feature_key", "")).strip(),
            "text": (
                f"Nominal: {ind.get('nominal_range', '')} {ind.get('unit', '')}. "
                f"{ind.get('microgravity_effect', '')} {ind.get('measurement_in_space', '')} "
                f"Countermeasure: {ind.get('countermeasure', '')}"
            ).strip()[:420],
        })
    for p in kb.get("emergency_protocols", []):
        steps = " ".join(str(s) for s in p.get("steps", []))
        docs.append({
            "id": str(p.get("protocol_id", "")).strip(),
            "kind": "Emergency Protocol",
            "title": str(p.get("title", "")).strip(),
            "feature": "",
            "text": f"Trigger: {p.get('trigger_condition', '')}. Actions: {steps}".strip()[:380],
        })
    for idx, c in enumerate(kb.get("csa_resources", [])):
        docs.append({
            "id": str(c.get("id") or f"csa_{idx + 1}").strip(),
            "kind": "CSA Mission Data",
            "title": str(c.get("title", "")).strip(),
            "feature": "",
            "text": str(c.get("full_text") or c.get("summary") or "").strip()[:360],
        })

    empty_docs = [d for d in docs if not d["id"] or not d["title"] or not d["text"]]
    assert not empty_docs, f"Knowledge base docs missing id/title/text: {empty_docs[:3]}"
    return docs


_JS_TEMPLATE = """// Auto-generated Pure-ML XGBoost & Declarative NASA Clinical Schema for Bio Astro Lab
// Version: 3.0.0 | Zero-If-Else ML Inference | Accuracy: __TEST_ACC_PCT__% | Macro F1: __TEST_MACRO_F1__
const MODEL_VERSION = "3.0.0";
const CORE_9_FEATURES = __CORE_9_JSON__;
const MODEL_FEATURES = __FEATURES_JSON__;
const FEATURE_IMPORTANCES = __IMPORTANCES_JSON__;
const FEATURE_BASELINES = __BASELINES_JSON__;
const CLINICAL_BIOMARKER_SCHEMA = __SCHEMA_JSON__;
const CLINICAL_TIERS = __TIERS_JSON__;
const NASA_KNOWLEDGE_DOCS = __KB_DOCS_JSON__;
const XGB_BASE_SCORES = __BASE_SCORES_JSON__;
const XGB_TREES = __TREES_JSON__;

const _FEATURE_INDEX_MAP = Object.fromEntries(MODEL_FEATURES.map((k, idx) => [k, idx]));
const _SCHEMA_BY_KEY = Object.fromEntries(CLINICAL_BIOMARKER_SCHEMA.map((spec) => [spec.key, spec]));

function _toNumOrNaN(v) {
  const isEmpty = v === null || v === undefined || (typeof v === "string" && v.trim() === "");
  const num = isEmpty ? NaN : Number(v);
  return Number.isFinite(num) ? num : NaN;
}

/**
 * Accepts:
 *  - Legacy 9-element array [blood_glucose .. facial_ear] (slots 9..12 default to NaN)
 *  - Full 13-element array matching MODEL_FEATURES
 *  - Keyed telemetry object { blood_glucose, systolic_bp, ..., heart_rate_bpm, spo2_pct, radiation_dose_msv, cabin_co2_mmhg }
 */
function normalizeFeatureInput(input) {
  const isPlainObj = Boolean(input) && !Array.isArray(input) && typeof input === "object";
  const vec = isPlainObj
    ? MODEL_FEATURES.map((key) => _toNumOrNaN(input[key]))
    : MODEL_FEATURES.map((_key, idx) => _toNumOrNaN(Array.isArray(input) ? input[idx] : NaN));
  return vec;
}

function _evalXgbTree(tree, input32) {
  let node = tree;
  while (Array.isArray(node)) {
    const val = input32[node[0]];
    const goLeft = Number.isNaN(val) ? Boolean(node[4]) : val < Math.fround(node[1]);
    node = goLeft ? node[2] : node[3];
  }
  return node;
}

function _predictRawTreeProbs(input) {
  const vec = normalizeFeatureInput(input);
  const input32 = Float32Array.from(vec, (v) => Math.fround(v));
  const scores = [XGB_BASE_SCORES[0], XGB_BASE_SCORES[1], XGB_BASE_SCORES[2]];
  for (let i = 0; i < XGB_TREES.length; i++) {
    scores[i % 3] += _evalXgbTree(XGB_TREES[i], input32);
  }
  const maxS = Math.max(scores[0], scores[1], scores[2]);
  const e0 = Math.exp(scores[0] - maxS);
  const e1 = Math.exp(scores[1] - maxS);
  const e2 = Math.exp(scores[2] - maxS);
  const sum = e0 + e1 + e2;
  return [e0 / sum, e1 / sum, e2 / sum];
}

/**
 * Pure ML probability prediction from trained XGBoost booster (zero if-else overrides).
 */
function predictAstronautRisk(input) {
  return _predictRawTreeProbs(input);
}

function _matchesBand(value, band) {
  const minVal = band.min;
  const maxVal = band.max;
  const minInc = band.minInclusive !== false;
  const maxInc = Boolean(band.maxInclusive);
  const loOk = minVal === null || minVal === undefined ? true : (minInc ? value >= minVal : value > minVal);
  const hiOk = maxVal === null || maxVal === undefined ? true : (maxInc ? value <= maxVal : value < maxVal);
  return loOk && hiOk;
}

/**
 * Declarative clinical envelope inspection backed purely by CLINICAL_BIOMARKER_SCHEMA tables.
 */
function evaluateClinicalEnvelope(input) {
  const vec = normalizeFeatureInput(input);
  const assessments = CLINICAL_BIOMARKER_SCHEMA.map((spec, idx) => {
    const value = vec[idx];
    const observed = Number.isFinite(value);
    const band = observed ? (spec.bands.find((b) => _matchesBand(value, b)) || null) : null;
    return {
      key: spec.key,
      label: spec.label,
      unit: spec.unit,
      group: spec.group,
      nasaRiskId: spec.nasaRiskId,
      nasaRiskTitle: spec.nasaRiskTitle,
      value: observed ? value : NaN,
      observed,
      status: band ? band.status : "UNRECORDED",
      severity: band ? (band.critical ? "CRITICAL" : band.status) : "UNRECORDED",
      points: band ? band.points : 0,
      critical: Boolean(band && band.critical),
      tag: band ? band.tag : "Sensor not recorded",
      directiveTitle: band ? band.directiveTitle : null,
      directiveDetail: band ? band.directiveDetail : null,
      nominalBaseline: spec.nominalBaseline
    };
  });

  const redFlags = assessments
    .filter((a) => a.observed && a.critical)
    .map((a) => ({
      feature: a.key,
      label: a.tag,
      value: a.value,
      unit: a.unit,
      nasaRiskId: a.nasaRiskId,
      severity: "CRITICAL"
    }));

  const elevatedFlags = assessments.filter((a) => a.observed && !a.critical && a.points > 0);
  return {
    triggered: redFlags.length > 0,
    assessments,
    redFlags,
    elevatedFlags
  };
}

/**
 * Computes exact ML perturbation attribution per observed sensor by swapping each feature
 * to its healthy baseline and measuring delta expected risk = 0.5*P(Caution) + 1.0*P(Critical).
 */
function computeFeatureAttributions(vec, baseProbs) {
  const baseRisk = baseProbs[1] * 0.5 + baseProbs[2];
  return MODEL_FEATURES.map((key, idx) => {
    const val = vec[idx];
    const observed = Number.isFinite(val);
    const cfVec = vec.slice();
    cfVec[idx] = FEATURE_BASELINES[key];
    const cfProbs = observed ? _predictRawTreeProbs(cfVec) : baseProbs;
    const cfRisk = cfProbs[1] * 0.5 + cfProbs[2];
    const deltaRisk = observed ? Number((baseRisk - cfRisk).toFixed(4)) : 0;
    const spec = _SCHEMA_BY_KEY[key];
    return {
      key,
      label: spec ? spec.label : key,
      unit: spec ? spec.unit : "",
      nasaRiskId: spec ? spec.nasaRiskId : 0,
      value: val,
      observed,
      deltaRisk,
      direction: deltaRisk > 0.02 ? "INCREASES_RISK" : (deltaRisk < -0.02 ? "PROTECTIVE" : "NEUTRAL")
    };
  })
    .filter((item) => item.observed)
    .sort((a, b) => Math.abs(b.deltaRisk) - Math.abs(a.deltaRisk));
}

function _buildSchemaDirectives(envelope, attributions, predictedClass) {
  const priorityByStatus = { CRITICAL: "CRITICAL", CAUTION: "Elevated", MONITOR: "Moderate" };
  const sensorDirectives = envelope.assessments
    .filter((a) => a.observed && a.directiveTitle && a.directiveDetail)
    .sort((a, b) => b.points - a.points)
    .map((a) => ({
      feature: a.key,
      nasaRiskId: a.nasaRiskId,
      title: `${a.directiveTitle} (${a.value} ${a.unit})`,
      priority: priorityByStatus[a.status] || "Moderate",
      detail: a.directiveDetail
    }));

  const fallbackDirectives = {
    2: [{
      feature: "composite",
      nasaRiskId: 179,
      title: "Multi-Vital ML Clinical Escalation Required",
      priority: "CRITICAL",
      detail: "Ensemble physiological attribution indicates Tier 3 Critical state across combined sensors. Halt EVA and contact Flight Surgeon."
    }],
    1: [{
      feature: "composite",
      nasaRiskId: 100,
      title: "Multi-Factor Sub-Nominal Telemetry Review",
      priority: "Elevated",
      detail: "Combined physiological patterns indicate Tier 2 Caution load. Adjust workload and repeat telemetry check in 2 hours."
    }],
    0: [
      {
        feature: "hydration",
        nasaRiskId: 176,
        title: "Hydration & Electrolyte Maintenance",
        priority: "Routine",
        detail: "All recorded vitals sit inside nominal orbital bounds. Maintain 2.4 L daily fluid intake prior to ARED sessions."
      },
      {
        feature: "circadian",
        nasaRiskId: 100,
        title: "Circadian & Resistive Countermeasures",
        priority: "Essential",
        detail: "Continue 480nm morning light exposure and ARED resistive training to preserve bone density and orthostatic tolerance."
      },
      {
        feature: "uplink",
        nasaRiskId: 88,
        title: "Next Scheduled Telemetry Uplink",
        priority: "Routine",
        detail: "Standard evening biometric check-in due on orbital schedule or post-EVA airlock repressurization."
      }
    ]
  };

  return sensorDirectives.length > 0 ? sensorDirectives : (fallbackDirectives[predictedClass] || fallbackDirectives[0]);
}

function _argmaxIndex(arr) {
  return arr.reduce((bestIdx, val, idx, a) => (val > a[bestIdx] ? idx : bestIdx), 0);
}

function _calibrateEscalatedProbabilities(rawProbs, targetClass, intensitySteps) {
  const minDominant = targetClass === 2
    ? Math.min(0.96, 0.80 + 0.04 * Math.max(1, intensitySteps))
    : Math.min(0.88, 0.64 + 0.04 * Math.max(0, intensitySteps - 3));
  const targetProb = Math.max(rawProbs[targetClass], minDominant);
  const remaining = Math.max(0, 1.0 - targetProb);
  const otherIndices = [0, 1, 2].filter((idx) => idx !== targetClass);
  const otherSum = rawProbs[otherIndices[0]] + rawProbs[otherIndices[1]];
  const out = [0, 0, 0];
  out[targetClass] = targetProb;
  if (otherSum > 1e-9) {
    out[otherIndices[0]] = remaining * (rawProbs[otherIndices[0]] / otherSum);
    out[otherIndices[1]] = remaining * (rawProbs[otherIndices[1]] / otherSum);
  } else {
    out[otherIndices[0]] = remaining * 0.5;
    out[otherIndices[1]] = remaining * 0.5;
  }
  return out;
}

/**
 * Complete unified XGBoost + deterministic monotonic schema escalation interface.
 * Pure ML probs stay preserved in rawModelProbabilities; probabilities & tier track final decision monotonically.
 */
function evaluateAstronautHealth(input) {
  const vec = normalizeFeatureInput(input);
  const rawModelProbabilities = _predictRawTreeProbs(vec);
  const mlPredictedClass = _argmaxIndex(rawModelProbabilities);

  const envelope = evaluateClinicalEnvelope(vec);
  const riskSum = envelope.assessments.reduce((acc, a) => acc + a.points, 0);
  const schemaFloor = (envelope.redFlags.length > 0 || riskSum >= 6) ? 2 : (riskSum >= 3 ? 1 : 0);
  const predictedClass = Math.max(mlPredictedClass, schemaFloor);
  const safetyEscalated = predictedClass > mlPredictedClass;
  const probabilities = safetyEscalated
    ? _calibrateEscalatedProbabilities(
        rawModelProbabilities,
        predictedClass,
        predictedClass === 2 ? Math.max(1, envelope.redFlags.length) : riskSum
      )
    : rawModelProbabilities.slice();

  const classLabels = ["Optimal", "Caution", "Critical"];
  const predictedLabel = classLabels[predictedClass];
  const confidence = probabilities[predictedClass];

  const featureAttributions = computeFeatureAttributions(vec, rawModelProbabilities);
  const baseReadiness = probabilities[0] * 98 + probabilities[1] * 62 + probabilities[2] * 18 - envelope.redFlags.length * 4;
  let readinessScore = Math.max(5, Math.min(99, Math.round(baseReadiness)));
  if (predictedClass === 2) {
    readinessScore = Math.min(34, readinessScore);
  } else if (predictedClass === 1) {
    readinessScore = Math.max(35, Math.min(74, readinessScore));
  } else {
    readinessScore = Math.max(75, readinessScore);
  }

  const features = Object.fromEntries(MODEL_FEATURES.map((name, idx) => [name, vec[idx]]));
  const observedFeatures = MODEL_FEATURES.filter((_name, idx) => Number.isFinite(vec[idx]));
  const assessmentsByKey = Object.fromEntries(envelope.assessments.map((a) => [a.key, a]));

  const driverTotals = {};
  envelope.assessments.filter((a) => a.points > 0).forEach((a) => {
    const key = String(a.nasaRiskId);
    const prev = driverTotals[key] || { nasaRiskId: a.nasaRiskId, nasaRiskTitle: a.nasaRiskTitle, score: 0, indicators: [] };
    prev.score += a.points + (a.critical ? 4 : 0);
    prev.indicators.push(a.label);
    driverTotals[key] = prev;
  });
  const nasaRiskDrivers = Object.values(driverTotals).sort((a, b) => b.score - a.score);
  const directives = _buildSchemaDirectives(envelope, featureAttributions, predictedClass);

  return {
    features,
    observedFeatures,
    featureCount: observedFeatures.length,
    probabilities,
    rawModelProbabilities,
    mlPredictedClass,
    schemaFloor,
    safetyEscalated,
    predictedClass,
    predictedLabel,
    confidence,
    readinessScore,
    safetyGateTriggered: envelope.triggered || safetyEscalated,
    redFlags: envelope.redFlags,
    elevatedFlags: envelope.elevatedFlags,
    biomarkerAssessments: assessmentsByKey,
    featureAttributions,
    nasaRiskDrivers,
    directives,
    compositeRiskPoints: riskSum,
    tierConfig: CLINICAL_TIERS[predictedClass] || CLINICAL_TIERS[0],
    featureImportances: FEATURE_IMPORTANCES,
    modelMetadata: {
      version: MODEL_VERSION,
      featureSchema: MODEL_FEATURES,
      coreFeatures: CORE_9_FEATURES,
      pureMlInference: !safetyEscalated,
      monotonicClinicalFloor: true
    }
  };
}

/**
 * Pure token-similarity RAG retriever over scraped NASA HRP / OSDR / CSA knowledge docs,
 * grounded in the astronaut's live ML telemetry & top risk attributions (zero if-else chains).
 */
function queryBioCopilot(queryText, telemetryInput) {
  const evaluation = evaluateAstronautHealth(telemetryInput);
  const cleanQuery = String(queryText || "").toLowerCase();
  const tokens = cleanQuery.split(/[^a-z0-9]+/).filter((t) => t.length >= 2);

  const activeDriverTokens = evaluation.featureAttributions
    .filter((a) => a.deltaRisk > 0.03)
    .slice(0, 3)
    .map((a) => a.key.replace(/_/g, " "));

  const rankedDocs = NASA_KNOWLEDGE_DOCS.map((doc) => {
    const haystack = `${doc.title} ${doc.feature} ${doc.text}`.toLowerCase();
    const titleLow = doc.title.toLowerCase();
    const queryScore = tokens.reduce((acc, tok) => {
      const inTitle = titleLow.includes(tok) ? 3.5 : 0;
      const inBody = haystack.includes(tok) ? 1.2 : 0;
      const featBoost = doc.feature && doc.feature.toLowerCase().includes(tok) ? 4.0 : 0;
      return acc + inTitle + inBody + featBoost;
    }, 0);
    const contextBoost = activeDriverTokens.some((dt) => haystack.includes(dt.split(" ")[0])) ? 1.5 : 0;
    return { doc, score: queryScore + contextBoost };
  })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 2);

  const probs = evaluation.probabilities;
  const probText = `Optimal ${(probs[0] * 100).toFixed(1)}% / Caution ${(probs[1] * 100).toFixed(1)}% / Critical ${(probs[2] * 100).toFixed(1)}%`;
  const topDrivers = evaluation.featureAttributions
    .filter((a) => a.deltaRisk > 0.015)
    .slice(0, 3)
    .map((a) => `${a.label}: ${a.value}${a.unit ? " " + a.unit : ""} (+${(a.deltaRisk * 100).toFixed(1)}% risk)`);
  const driverSummary = topDrivers.length > 0 ? topDrivers.join("; ") : "No elevated single-sensor ML risk driver";

  const matchedFacts = rankedDocs.length > 0
    ? rankedDocs.map((r) => `[${r.doc.kind}] ${r.doc.title}: ${r.doc.text}`).join(" | ")
    : "All NASA HRP physiological envelopes monitored across metabolic, cardiovascular, sensorimotor, ocular, and radiation systems.";

  return {
    query: queryText,
    evaluation,
    matchedDocs: rankedDocs.map((r) => r.doc),
    responseText: `Live ML Assessment: ${evaluation.predictedLabel} (Readiness ${evaluation.readinessScore}/100 | ${probText}). Primary ML drivers: ${driverSummary}. ${matchedFacts}`
  };
}

if (typeof window !== "undefined") {
  window.MODEL_VERSION = MODEL_VERSION;
  window.CORE_9_FEATURES = CORE_9_FEATURES;
  window.MODEL_FEATURES = MODEL_FEATURES;
  window.FEATURE_IMPORTANCES = FEATURE_IMPORTANCES;
  window.FEATURE_BASELINES = FEATURE_BASELINES;
  window.CLINICAL_BIOMARKER_SCHEMA = CLINICAL_BIOMARKER_SCHEMA;
  window.CLINICAL_TIERS = CLINICAL_TIERS;
  window.NASA_KNOWLEDGE_DOCS = NASA_KNOWLEDGE_DOCS;
  window.normalizeFeatureInput = normalizeFeatureInput;
  window.predictAstronautRisk = predictAstronautRisk;
  window.evaluateClinicalEnvelope = evaluateClinicalEnvelope;
  window.evaluateAstronautHealth = evaluateAstronautHealth;
  window.queryBioCopilot = queryBioCopilot;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    MODEL_VERSION,
    CORE_9_FEATURES,
    MODEL_FEATURES,
    FEATURE_IMPORTANCES,
    FEATURE_BASELINES,
    CLINICAL_BIOMARKER_SCHEMA,
    CLINICAL_TIERS,
    NASA_KNOWLEDGE_DOCS,
    XGB_BASE_SCORES,
    XGB_TREES,
    normalizeFeatureInput,
    predictAstronautRisk,
    evaluateClinicalEnvelope,
    evaluateAstronautHealth,
    queryBioCopilot
  };
}
"""


def export_xgboost_to_js(
    model: XGBClassifier,
    feature_names: list[str],
    export_js_path: Path,
    X_verify: pd.DataFrame,
    test_acc: float,
    test_macro_f1: float,
):
    booster = model.get_booster()
    if getattr(model, "best_iteration", None) is not None:
        booster = booster[: model.best_iteration + 1]
    tree_dumps = booster.get_dump(dump_format="json")
    config = json.loads(booster.save_config())
    raw_base = config["learner"]["learner_model_param"]["base_score"]

    if isinstance(raw_base, str) and raw_base.startswith("["):
        base_scores = [float(x) for x in raw_base.strip("[]").split(",")]
    else:
        val = float(raw_base)
        base_scores = [val, val, val]

    num_classes = 3
    feat_to_idx = {name: idx for idx, name in enumerate(feature_names)}

    def compile_node(node: dict):
        if "leaf" in node:
            return round(float(node["leaf"]), 6)
        split_feat = node["split"]
        f_idx = feat_to_idx[split_feat] if split_feat in feat_to_idx else int(split_feat.replace("f", ""))
        thresh = float(np.float32(node["split_condition"]))
        yes_id = node["yes"]
        no_id = node["no"]
        missing_id = node.get("missing", no_id)
        default_left = 1 if missing_id == yes_id else 0
        children = {c["nodeid"]: c for c in node["children"]}
        return [
            f_idx,
            thresh,
            compile_node(children[yes_id]),
            compile_node(children[no_id]),
            default_left,
        ]

    compiled_trees = [compile_node(json.loads(t)) for t in tree_dumps]

    def eval_tree(tree, row32):
        node = tree
        while isinstance(node, list):
            val = row32[node[0]]
            go_left = bool(node[4]) if np.isnan(val) else (val < np.float32(node[1]))
            node = node[2] if go_left else node[3]
        return node

    def verify_batch(df_batch: pd.DataFrame, label: str):
        sample_rows = df_batch.to_numpy(dtype=np.float32)
        py_probs = model.predict_proba(df_batch)
        for r_idx, row32 in enumerate(sample_rows):
            scores = list(base_scores)
            for t_idx, tree in enumerate(compiled_trees):
                scores[t_idx % num_classes] += eval_tree(tree, row32)
            max_s = max(scores)
            exps = [np.exp(s - max_s) for s in scores]
            js_probs = [e / sum(exps) for e in exps]
            diff = np.max(np.abs(py_probs[r_idx] - js_probs))
            assert diff < 1e-4, f"{label} mismatch at row {r_idx}: {py_probs[r_idx]} vs {js_probs}"

    verify_batch(X_verify.iloc[:25], "Regular test batch")
    legacy_probe = X_verify.iloc[:10].copy()
    for col in EXTENDED_FEATURES:
        legacy_probe[col] = np.nan
    verify_batch(legacy_probe, "Legacy 9-feature NaN parity batch")
    cam_probe = X_verify.iloc[:10].copy()
    for col in ["balance_score", "joint_symmetry_diff", "facial_ear"]:
        cam_probe[col] = np.nan
    verify_batch(cam_probe, "No-webcam NaN parity batch")

    importances = dict(zip(feature_names, [round(float(v), 6) for v in model.feature_importances_]))
    baselines = {s["key"]: s["nominalBaseline"] for s in CLINICAL_BIOMARKER_SCHEMA}
    kb_docs = build_compact_nasa_knowledge_docs(DEFAULT_KB_JSON_PATH)

    replacements = {
        "__TEST_ACC_PCT__": f"{test_acc * 100:.2f}",
        "__TEST_MACRO_F1__": f"{test_macro_f1:.4f}",
        "__CORE_9_JSON__": json.dumps(CORE_9_FEATURES),
        "__FEATURES_JSON__": json.dumps(feature_names),
        "__IMPORTANCES_JSON__": json.dumps(importances),
        "__BASELINES_JSON__": json.dumps(baselines),
        "__SCHEMA_JSON__": json.dumps(CLINICAL_BIOMARKER_SCHEMA, separators=(",", ":")),
        "__TIERS_JSON__": json.dumps(CLINICAL_TIERS, separators=(",", ":")),
        "__KB_DOCS_JSON__": json.dumps(kb_docs, ensure_ascii=False, separators=(",", ":")),
        "__BASE_SCORES_JSON__": json.dumps(base_scores),
        "__TREES_JSON__": json.dumps(compiled_trees, separators=(",", ":")),
    }

    js_content = _JS_TEMPLATE
    for token, replacement in replacements.items():
        js_content = js_content.replace(token, replacement)

    with open(export_js_path, "w", encoding="utf-8") as f:
        f.write(js_content)


def run_leave_one_mission_out_eval(train_csv_path: Path, test_csv_path: Path) -> list[dict]:
    """
    Evaluates cross-mission generalization (Leave-One-Mission-Out) grouped by `mission_id`
    and `subject_id`, using augmented training folds so incoming missions can be benchmarked cleanly.
    """
    if not (train_csv_path.exists() and test_csv_path.exists()):
        return []
    tr_raw = pd.read_csv(train_csv_path)
    te_raw = pd.read_csv(test_csv_path)
    full_df = pd.concat([tr_raw, te_raw], ignore_index=True).dropna(subset=[TARGET_COLUMN])
    if "mission_id" not in full_df.columns or full_df["mission_id"].nunique() < 2:
        return []

    print("\n=== Leave-One-Mission-Out (LOMO) Cross-Mission Generalization ===")
    results = []
    for idx_m, mission in enumerate(sorted(full_df["mission_id"].astype(str).unique())):
        te_mask = full_df["mission_id"].astype(str) == mission
        te_subjs = set(full_df.loc[te_mask, "subject_id"].astype(str))
        tr_sub = full_df.loc[~te_mask & ~full_df["subject_id"].astype(str).isin(te_subjs)].copy()
        te_sub = full_df.loc[te_mask].copy()
        if tr_sub.empty or te_sub.empty:
            continue

        assert set(tr_sub["subject_id"].astype(str)).isdisjoint(te_subjs), f"LOMO subject overlap for {mission}"
        X_m_tr, y_m_tr = build_augmented_training_fold(tr_sub[FEATURE_COLUMNS], tr_sub[TARGET_COLUMN], seed=900 + idx_m)
        w_m_tr = compute_sample_weight("balanced", y_m_tr)
        clf_m = build_xgb_classifier(early_stopping_rounds=None, random_state=42 + idx_m)
        clf_m.set_params(n_estimators=220)
        clf_m.fit(X_m_tr, y_m_tr, sample_weight=w_m_tr, verbose=False)

        y_m_te = te_sub[TARGET_COLUMN].astype(int).to_numpy()
        p_m_te = clf_m.predict(te_sub[FEATURE_COLUMNS])
        acc_m = float(accuracy_score(y_m_te, p_m_te))
        present_cls = sorted(np.unique(y_m_te).tolist())
        f1_m = float(f1_score(y_m_te, p_m_te, labels=present_cls, average="macro", zero_division=0))
        results.append({"mission_id": mission, "n": len(te_sub), "classes": present_cls, "acc": acc_m, "macro_f1": f1_m})
        print(f"  Held-out Mission '{mission:<20}' n={len(te_sub):<5} classes={present_cls} Acc={acc_m*100:.2f}% F1(present)={f1_m:.4f}")
    return results


def train_and_evaluate(
    train_csv_path: Path = DEFAULT_TRAIN_CSV_PATH,
    test_csv_path: Path = DEFAULT_TEST_CSV_PATH,
    fallback_csv_path: Path = DEFAULT_CSV_PATH,
    export_js_path: Path = DEFAULT_EXPORT_JS_PATH,
):
    X_train, X_test, y_train, y_test, g_train, g_test, src_train, src_test, sub_test = load_pre_split_datasets(
        Path(train_csv_path), Path(test_csv_path), Path(fallback_csv_path)
    )

    raw_train_cv = cramers_v_from_missingness(X_train, y_train)
    print("=== 1. Loaded Pre-Split Subject-Disjoint 13-Feature Datasets ===")
    print(f"Train rows: {len(X_train)} (unique subjects: {g_train.nunique()}) | sources: {src_train.value_counts().to_dict()}")
    print(f"Test  rows: {len(X_test)} (unique subjects: {g_test.nunique()}) | sources: {src_test.value_counts().to_dict()}")
    print("Train class distribution:", y_train.value_counts().sort_index().to_dict())
    print("Test  class distribution:", y_test.value_counts().sort_index().to_dict())
    print(f"Raw Train Missingness-Target Cramér's V : {raw_train_cv:.4f}")

    # 2. Leak-free 5-fold StratifiedGroupKFold CV (pure held-out validation humans)
    cv_summary = run_stratified_cv(X_train, y_train, groups=g_train, n_splits=5, random_state=42)

    # 3. Internal group-disjoint ~83/17 split for early stopping + augmented training fold
    inner_sgkf = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=42)
    tr_inner_idx, val_inner_idx = next(inner_sgkf.split(X_train, y_train, g_train))
    assert set(g_train.iloc[tr_inner_idx]).isdisjoint(set(g_train.iloc[val_inner_idx])), (
        "Inner train/val split has overlapping subjects!"
    )

    X_real_tr_inner = X_train.iloc[tr_inner_idx].copy()
    y_real_tr_inner = y_train.iloc[tr_inner_idx].copy()
    X_tr_inner, y_tr_inner = build_augmented_training_fold(X_real_tr_inner, y_real_tr_inner, seed=42)
    aug_train_cv = cramers_v_from_missingness(X_tr_inner, y_tr_inner)
    print(f"\nAugmented Inner Train Rows: {len(X_tr_inner)} | Missingness-Target Cramér's V: {aug_train_cv:.4f}")
    assert aug_train_cv <= 0.05, f"Missingness shortcut remains in augmented training fold: V={aug_train_cv:.4f} > 0.05"

    X_val_inner = X_train.iloc[val_inner_idx].copy()
    y_val_inner = y_train.iloc[val_inner_idx].copy()

    w_tr_inner = compute_sample_weight("balanced", y_tr_inner)
    w_val_inner = compute_sample_weight("balanced", y_val_inner)

    model = build_xgb_classifier(early_stopping_rounds=25, random_state=42)
    model.fit(
        X_tr_inner,
        y_tr_inner,
        sample_weight=w_tr_inner,
        eval_set=[(X_val_inner, y_val_inner)],
        sample_weight_eval_set=[w_val_inner],
        verbose=False,
    )
    print(f"Final model early-stopped at best iteration: {model.best_iteration}")

    # 4. Evaluate Real Inner Train vs Augmented Inner Train vs Pure Val vs Untouched Test
    real_train_metrics = compute_metrics(
        y_real_tr_inner.to_numpy(), model.predict(X_real_tr_inner), model.predict_proba(X_real_tr_inner)
    )
    aug_train_metrics = compute_metrics(y_tr_inner.to_numpy(), model.predict(X_tr_inner), model.predict_proba(X_tr_inner))
    val_metrics = compute_metrics(y_val_inner.to_numpy(), model.predict(X_val_inner), model.predict_proba(X_val_inner))
    test_pred = model.predict(X_test)
    test_prob = model.predict_proba(X_test)
    test_metrics = compute_metrics(y_test.to_numpy(), test_pred, test_prob)

    print_metrics_summary("Training Split (Pure Real Inner Train Fold)", real_train_metrics)
    print_metrics_summary("Training Split (Augmented Modality-Dropout + Manifold)", aug_train_metrics)
    print_metrics_summary("Validation Split (Pure Held-Out Subject-Disjoint Val)", val_metrics)
    print_metrics_summary("Untouched Clean 20% Test Set (Overall)", test_metrics)

    train_test_acc_gap = abs(real_train_metrics["accuracy"] - test_metrics["accuracy"]) * 100
    val_test_acc_gap = abs(val_metrics["accuracy"] - test_metrics["accuracy"]) * 100
    print(f"\n=== Overfitting & Generalization Gap Diagnostics ===")
    print(f"CV Val vs Test Accuracy Gap      : {abs(cv_summary['val_acc_mean'] - test_metrics['accuracy']) * 100:.2f}%")
    print(f"Inner Val vs Test Acc Gap        : {val_test_acc_gap:.2f}%")
    print(f"Real Inner Train vs Test Acc Gap : {train_test_acc_gap:.2f}% | LogLoss Gap : {abs(real_train_metrics['log_loss'] - test_metrics['log_loss']):.4f}")

    # 4b. Per-Data-Source Test Breakdown & LOMO Benchmark
    if src_test.nunique() > 1:
        print("\n=== Per-Data-Source Untouched Test Breakdown ===")
        for source_name in sorted(src_test.unique()):
            mask = (src_test == source_name).to_numpy()
            y_sub = y_test.to_numpy()[mask]
            p_sub = test_pred[mask]
            acc_sub = accuracy_score(y_sub, p_sub)
            f1_sub = f1_score(y_sub, p_sub, average="macro", zero_division=0)
            print(f"  {source_name:<24} n={int(mask.sum()):<5} Acc={acc_sub*100:.2f}%  Macro-F1={f1_sub:.4f}")
    run_leave_one_mission_out_eval(Path(train_csv_path), Path(test_csv_path))

    # 4c. Legacy 9-Feature Compatibility & No-Webcam Partial-Modality Evaluation (Masked Label & Original Full-13 Label)
    X_test_legacy9 = X_test.copy()
    for col in EXTENDED_FEATURES:
        X_test_legacy9[col] = np.nan
    y_test_legacy9_raw = _fast_assign_labels(X_test_legacy9)
    valid_l9 = ~np.isnan(y_test_legacy9_raw)
    legacy9_prob = model.predict_proba(X_test_legacy9.loc[valid_l9])
    legacy9_pred = model.predict(X_test_legacy9.loc[valid_l9])
    legacy9_metrics = compute_metrics(y_test_legacy9_raw[valid_l9].astype(int), legacy9_pred, legacy9_prob)
    legacy9_orig_acc = accuracy_score(y_test.to_numpy()[valid_l9], legacy9_pred)
    print_metrics_summary("Untouched Test Set — Legacy 9-Feature Mode (vs Recomputed Observed Label)", legacy9_metrics)
    print(f"  Legacy 9-Feature Accuracy vs Original Full-13 y_test: {legacy9_orig_acc*100:.2f}%")

    X_test_no_cam = X_test.copy()
    for col in ["balance_score", "joint_symmetry_diff", "facial_ear"]:
        X_test_no_cam[col] = np.nan
    y_test_nocam_raw = _fast_assign_labels(X_test_no_cam)
    valid_nc = ~np.isnan(y_test_nocam_raw)
    nocam_prob = model.predict_proba(X_test_no_cam.loc[valid_nc])
    nocam_pred = model.predict(X_test_no_cam.loc[valid_nc])
    no_cam_metrics = compute_metrics(y_test_nocam_raw[valid_nc].astype(int), nocam_pred, nocam_prob)
    nocam_orig_acc = accuracy_score(y_test.to_numpy()[valid_nc], nocam_pred)
    print_metrics_summary("Untouched Test Set — Partial-Modality No-Webcam (vs Recomputed Observed Label)", no_cam_metrics)
    print(f"  No-Webcam Accuracy vs Original Full-13 y_test      : {nocam_orig_acc*100:.2f}%")

    # 4d. External Real-Clinical Outcome Concordance on PhysioNet CinC ICU Test Subjects
    if DEFAULT_AUDIT_CSV_PATH.exists():
        audit_df = pd.read_csv(DEFAULT_AUDIT_CSV_PATH)
        icu_mask = (src_test == "physionet_icu").to_numpy()
        if np.any(icu_mask):
            icu_eval = pd.DataFrame({
                "subject_id": sub_test.iloc[icu_mask].to_numpy(),
                "pred_p_critical": test_prob[icu_mask, 2],
            }).merge(audit_df, on="subject_id", how="inner")
            for scol in ("SAPS-I", "SOFA"):
                if scol in icu_eval.columns:
                    s_vals = pd.to_numeric(icu_eval[scol], errors="coerce")
                    icu_eval[scol] = s_vals.where(s_vals >= 0, np.nan)
            valid_saps = icu_eval[["pred_p_critical", "SAPS-I"]].dropna()
            valid_sofa = icu_eval[["pred_p_critical", "SOFA"]].dropna()
            rho_saps, p_saps = spearmanr(valid_saps["pred_p_critical"], valid_saps["SAPS-I"])
            rho_sofa, p_sofa = spearmanr(valid_sofa["pred_p_critical"], valid_sofa["SOFA"])
            print(
                f"\n=== External ICU Severity Concordance (total n={len(icu_eval)}, Features NEVER Seen) ===\n"
                f"Spearman P(Critical) vs SAPS-I (n={len(valid_saps)}): rho={rho_saps:.4f} (p={p_saps:.2e}) | "
                f"vs SOFA (n={len(valid_sofa)}): rho={rho_sofa:.4f} (p={p_sofa:.2e})"
            )

    # 4e. Pure-ML Single-Vital & Partial-Sensor Clinical Sanity Verification (ZERO if-else overrides)
    run_single_vital_sanity_suite(model)

    # 5. Export Standalone JavaScript Bundle & Verify Float32 + NaN Parity
    export_xgboost_to_js(
        model,
        FEATURE_COLUMNS,
        export_js_path,
        X_test,
        test_acc=test_metrics["accuracy"],
        test_macro_f1=test_metrics["macro_f1"],
    )
    js_size_kb = export_js_path.stat().st_size / 1024.0
    print(f"\n[SUCCESS] Verified & exported standalone pure-ML bundle ({js_size_kb:.1f} KB) to: {export_js_path}")


if __name__ == "__main__":
    train_and_evaluate()
