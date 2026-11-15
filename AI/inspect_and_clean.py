from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "cleaned"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# الكلمات المفتاحية للبحث عن الـ 9 مدخلات المطلوبة في الملفات اللي نزلت
TARGET_KEYWORDS = {
    "blood_glucose": ["glucose", "lbxglu", "glu", "sugar"],
    "systolic_bp": ["systolic", "bpxsy", "sbp", "sys_bp"],
    "diastolic_bp": ["diastolic", "bpxdi", "dbp", "dia_bp"],
    "body_temp": ["temp", "temperature", "bt"],
    "sleep_hours": ["sleep", "duration", "sld"],
    "mood_score": ["mood", "stress", "panas", "fatigue_score", "anxiety"],
    "balance_score": ["balance", "sway", "cop", "postur", "stability"],
    "joint_symmetry_diff": ["symmetry", "angle", "gait", "tilt", "asymmetry"],
    "facial_ear": ["ear", "eye_aspect", "blink", "eye_state", "drowsi", "perclos"]
}

def audit_and_clean():
    if not RAW_DIR.exists():
        print(f"[ERROR] Folder not found: {RAW_DIR}")
        return

    csv_files = list(RAW_DIR.glob("*.csv"))
    if not csv_files:
        print(f"[WARNING] No CSV files found inside {RAW_DIR}")
        return

    print(f"=== Found {len(csv_files)} CSV files in {RAW_DIR} ===\n")
    found_features = {k: [] for k in TARGET_KEYWORDS}

    for file_path in csv_files:
        df = pd.read_csv(file_path)
        initial_rows = len(df)

        # 1. تنظيف أساسي: حذف الأعمدة الفاضية بالكامل والصفوف المكررة
        df = df.dropna(axis=1, how="all")
        df = df.drop_duplicates()

        # 2. حذف الصفوف اللي أكتر من 50% من بياناتها مفقودة
        df = df.dropna(thresh=max(1, int(df.shape[1] * 0.5)))

        # 3. تنظيف القيم الرقمية (استبدال القيم اللانهائية بـ NaN)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

        clean_path = CLEAN_DIR / f"clean_{file_path.name}"
        df.to_csv(clean_path, index=False)

        print(f"File: {file_path.name}")
        print(f"  -> Rows: {initial_rows} raw  ==>  {len(df)} cleaned")
        print(f"  -> Columns: {list(df.columns)}\n")

        # 4. فحص أي أعمدة تطابق الـ 9 مدخلات المطلوبة
        for col in df.columns:
            col_lower = col.lower()
            for target_feat, keywords in TARGET_KEYWORDS.items():
                if any(kw in col_lower for kw in keywords):
                    found_features[target_feat].append(f"{file_path.name} -> [{col}]")

    print("==================================================")
    print("=== AUDIT REPORT: AVAILABLE vs. MISSING INPUTS ===")
    print("==================================================")
    missing_list = []
    for feat, matches in found_features.items():
        if matches:
            print(f"[OK]      {feat:<22} : Found in {', '.join(matches)}")
        else:
            print(f"[MISSING] {feat:<22} : NOT FOUND in raw files!")
            missing_list.append(feat)

    print("\nSummary:")
    if missing_list:
        print(f"Missing inputs ({len(missing_list)}/9): {missing_list}")
    else:
        print("All 9 required inputs are available and ready for dataset fusion!")

if __name__ == "__main__":
    audit_and_clean()