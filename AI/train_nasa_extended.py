"""
train_nasa_extended.py
Verifies that the expanded 13-feature NASA-grounded spaceflight clinical triage
dataset (AI/data/nasa_training/spaceflight_clinical_triage_{train,test}.csv)
trains cleanly with XGBoost and reports full holdout metrics.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

BASE = Path(__file__).resolve().parent / "data" / "nasa_training"
FEATURES = [
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


def main():
    tr = pd.read_csv(BASE / "spaceflight_clinical_triage_train.csv")
    te = pd.read_csv(BASE / "spaceflight_clinical_triage_test.csv")

    X_tr, y_tr = tr[FEATURES], tr["health_risk_label"].astype(int)
    X_te, y_te = te[FEATURES], te["health_risk_label"].astype(int)

    sw = compute_sample_weight("balanced", y_tr)
    clf = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.06,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        random_state=42,
    )
    clf.fit(X_tr, y_tr, sample_weight=sw, verbose=False)
    preds = clf.predict(X_te)

    acc = accuracy_score(y_te, preds)
    macro_f1 = f1_score(y_te, preds, average="macro")
    print(f"=== Extended Spaceflight 13-Feature XGBoost Verification ===")
    print(f"Train rows: {len(X_tr)} | Test rows: {len(X_te)}")
    print(f"Holdout Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f}")
    print("\nClassification Report (0=Optimal, 1=Caution, 2=Critical):")
    print(classification_report(y_te, preds, target_names=["Optimal", "Caution", "Critical"]))

    # Also verify training a Risk-Driver classifier (predicting primary_nasa_risk_id on non-optimal rows)
    tr_risk = tr[tr["primary_nasa_risk_id"] > 0].copy()
    te_risk = te[te["primary_nasa_risk_id"] > 0].copy()
    risk_classes = sorted(tr_risk["primary_nasa_risk_id"].unique())
    cls_map = {c: i for i, c in enumerate(risk_classes)}
    te_risk = te_risk[te_risk["primary_nasa_risk_id"].isin(cls_map)].copy()

    r_clf = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.07,
        objective="multi:softprob",
        num_class=len(risk_classes),
        random_state=42,
    )
    r_clf.fit(tr_risk[FEATURES], tr_risk["primary_nasa_risk_id"].map(cls_map), verbose=False)
    r_preds = r_clf.predict(te_risk[FEATURES])
    r_acc = accuracy_score(te_risk["primary_nasa_risk_id"].map(cls_map), r_preds)
    print(f"=== NASA HRP Primary Risk-Driver Classifier Verification ===")
    print(f"Risk classes ({len(risk_classes)}): {risk_classes}")
    print(f"Holdout Risk-Driver Accuracy: {r_acc:.4f}")


if __name__ == "__main__":
    main()
