"""
fetch_raw_data.py
Downloads REAL, open-access (no login) datasets into AI/data/raw/.
No synthetic rows are generated: every CSV is a direct conversion/extraction
(or per-subject aggregation, where noted) of a public source file.

Sources
-------
1. CDC NHANES 2017-2018 (public domain)
   - BPX_J  (Blood Pressure exam)          -> nhanes_bp.csv
   - GLU_J  (Plasma Fasting Glucose)       -> nhanes_glucose.csv
   - SLQ_J  (Sleep Disorders questionnaire)+ DPQ_J (PHQ-9 mood/depression)
                                            -> sleep_stress_data.csv (merged on SEQN)
2. PhysioNet Human Balance Evaluation Database v1.0.0 (ODC-BY, open access)
   - BDSinfo.txt (subject/trial metadata, Mini-BESTest, FES-I, TMT, IPAQ)
                                            -> balance_data.csv
3. PhysioNet / CinC Challenge 2012, set-a (ODC-BY, open access, real ICU records)
   - per-patient median Temp, HR, BP, Glucose, RespRate, SpO2 ...
                                            -> vitals_temp_data.csv
4. UCI "EEG Eye State" (via OpenML id 1471, CC-BY) - real eye open/closed labels
                                            -> eye_fatigue_data.csv
"""
import io
import os
import sys
import tarfile

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
os.makedirs(RAW, exist_ok=True)

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (research data fetch)"


def get(url, timeout=180):
    print(f"  GET {url}")
    r = SESSION.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def first_ok(urls, validator=None):
    last = None
    for u in urls:
        try:
            data = get(u)
            if validator and not validator(data):
                raise ValueError("content failed validation (probably an HTML page)")
            return data, u
        except Exception as e:  # try next mirror
            print(f"    failed: {e}")
            last = e
    raise RuntimeError(f"All URLs failed: {urls}") from last


def save(df, name, source):
    path = os.path.join(RAW, name)
    df.to_csv(path, index=False)
    print(f"  saved {name}  ({len(df)} rows)  <- {source}")


# ---------------------------------------------------------------- NHANES
def nhanes(code):
    urls = [
        f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/{code}.xpt",
        f"https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/{code}.XPT",
    ]
    data, url = first_ok(urls, validator=lambda b: b[:6] == b"HEADER")
    df = pd.read_sas(io.BytesIO(data), format="xport", encoding="infer")
    return df, url


def fetch_nhanes():
    print("[1] CDC NHANES 2017-2018")
    bp, u = nhanes("BPX_J")
    save(bp, "nhanes_bp.csv", u)
    glu, u = nhanes("GLU_J")
    save(glu, "nhanes_glucose.csv", u)

    print("[3a] NHANES Sleep (SLQ_J) + Mood/PHQ-9 (DPQ_J)")
    slq, u1 = nhanes("SLQ_J")
    dpq, u2 = nhanes("DPQ_J")
    merged = slq.merge(dpq, on="SEQN", how="outer")
    save(merged, "sleep_stress_data.csv", f"{u1} + {u2}")


# ---------------------------------------------------------------- Balance
def fetch_balance():
    print("[2] PhysioNet Human Balance Evaluation Database (hbedb 1.0.0)")
    data, url = first_ok(
        ["https://physionet.org/files/hbedb/1.0.0/BDSinfo.txt"],
        validator=lambda b: not b.lstrip().lower().startswith(b"<!doctype"),
    )
    text = data.decode("utf-8", errors="replace")
    sep = "\t" if text.splitlines()[0].count("\t") > 0 else None
    df = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
    df.columns = [str(c).strip() for c in df.columns]
    save(df, "balance_data.csv", url)


# ---------------------------------------------------------------- Vitals / Temp
def fetch_vitals():
    print("[3b] PhysioNet CinC Challenge 2012 set-a (real ICU vitals incl. Temp)")
    base = "https://physionet.org/files/challenge-2012/1.0.0/"
    tgz = get(base + "set-a.tar.gz", timeout=600)
    rows = []
    with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith(".txt"):
                continue
            rec = pd.read_csv(tf.extractfile(m))  # Time,Parameter,Value
            rec = rec[rec["Value"] >= 0]  # -1 = missing in this dataset
            static = rec[rec["Time"] == "00:00"].groupby("Parameter")["Value"].first()
            med = rec.groupby("Parameter")["Value"].median()
            row = {"RecordID": int(static.get("RecordID", -1))}
            for p in ["Age", "Gender", "Height", "Weight"]:
                row[p] = static.get(p)
            for p in ["Temp", "HR", "SysABP", "DiasABP", "MAP", "NISysABP",
                      "NIDiasABP", "Glucose", "RespRate", "SaO2", "GCS"]:
                row[f"{p}_median"] = med.get(p)
            row["Temp_n_obs"] = int((rec["Parameter"] == "Temp").sum())
            rows.append(row)
    df = pd.DataFrame(rows)
    outcomes = pd.read_csv(io.BytesIO(get(base + "Outcomes-a.txt")))
    df = df.merge(outcomes, on="RecordID", how="left")
    save(df, "vitals_temp_data.csv", base + "set-a.tar.gz (per-patient medians)")


# ---------------------------------------------------------------- Eye state
def fetch_eye():
    print("[4] UCI EEG Eye State (OpenML 1471)")
    try:
        meta = SESSION.get("https://www.openml.org/api/v1/json/data/1471", timeout=60).json()
        fid = meta["data_set_description"]["file_id"]
        data, url = first_ok([f"https://www.openml.org/data/get_csv/{fid}"])
        df = pd.read_csv(io.BytesIO(data))
    except Exception as e:
        print(f"    OpenML failed ({e}); falling back to UCI ARFF")
        from scipy.io import arff
        url = ("https://archive.ics.uci.edu/ml/machine-learning-databases/00264/"
               "EEG%20Eye%20State.arff")
        data = get(url)
        arr, _ = arff.loadarff(io.StringIO(data.decode("utf-8")))
        df = pd.DataFrame(arr)
        df["eyeDetection"] = df["eyeDetection"].str.decode("utf-8").astype(int)
    save(df, "eye_fatigue_data.csv", url)


def summary():
    print("\n" + "=" * 70 + "\nSUMMARY of AI/data/raw/\n" + "=" * 70)
    for f in sorted(os.listdir(RAW)):
        if f.endswith(".csv"):
            df = pd.read_csv(os.path.join(RAW, f), low_memory=False)
            print(f"\n{f}  |  rows: {len(df)}  |  columns: {df.shape[1]}")
            print("  " + ", ".join(map(str, df.columns)))


if __name__ == "__main__":
    failures = []
    for step in (fetch_nhanes, fetch_balance, fetch_vitals, fetch_eye):
        try:
            step()
        except Exception as e:
            print(f"!! {step.__name__} FAILED: {e}")
            failures.append(step.__name__)
    summary()
    if failures:
        print("\nFAILED steps:", failures)
        sys.exit(1)
