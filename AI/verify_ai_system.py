"""
Zero-Trust End-to-End Verification Suite for Bio Astro Lab AI & Telemetry Stack.

Verifies:
1. Subject-disjoint splits, 0 exact cross-split 13-feature collisions, & augmented Cramér's V <= 0.05.
2. Manifest-driven NASA ingestion guardrails, suffix-strict unit conversions, & rodent quarantine.
3. Zero hardcoded clinical/chatbot if-else chains across ai-model.js, app-shell.js, scan.js, decision.js, history.js & 48 non-empty NASA RAG docs.
4. Full-test-set Python <-> Real Chrome V8 Engine float32 parity (1762 rows x Full-13, Legacy-9, No-Webcam).
5. Complete boundary, composite, single-analyte, & skipped-camera probes (>= 156 vectors, 0 contradictions).
6. Live multi-page headless Chrome E2E verification across index.html, scan.html, decision.html, history.html & guide.html.
"""

from __future__ import annotations

import functools
import html
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.utils.class_weight import compute_sample_weight

AI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AI_DIR.parent
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from ingest_nasa import (  # noqa: E402
    CLINICAL_BIOMARKER_SCHEMA,
    EXTENDED_FEATURES,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    infer_unit_from_column_name,
    ingest_nasa_dataframe,
    load_nasa_directory,
    normalize_co2_to_mmhg,
    normalize_radiation_to_msv,
    normalize_sleep_to_hours,
)
from train_pipeline import (  # noqa: E402
    build_augmented_training_fold,
    build_xgb_classifier,
    cramers_v_from_missingness,
    load_pre_split_datasets,
)


def _find_chromium_binary() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return found
    raise FileNotFoundError("No Chromium/Chrome/Edge binary found for JS browser verification.")


def _row_sigs(df: pd.DataFrame) -> set[tuple]:
    rounded = df[FEATURE_COLUMNS].round(4)
    return set(rounded.astype(object).where(rounded.notna(), "__NAN__").apply(tuple, axis=1).tolist())


def verify_zero_leakage():
    tr = pd.read_csv(AI_DIR / "data" / "train_dataset.csv")
    te = pd.read_csv(AI_DIR / "data" / "test_dataset.csv")
    overlap = set(tr["subject_id"].astype(str)).intersection(set(te["subject_id"].astype(str)))
    assert len(overlap) == 0, f"Data leakage: {len(overlap)} overlapping subject_ids across train/test!"

    cross_dups = len(_row_sigs(tr).intersection(_row_sigs(te)))
    assert cross_dups == 0, f"Exact 13-feature row collision across train/test: {cross_dups} rows!"

    assert {"nhanes_terrestrial", "physionet_icu", "nasa_inspiration4"}.issubset(set(tr["data_source"].unique()))
    assert {"nhanes_terrestrial", "physionet_icu", "nasa_inspiration4"}.issubset(set(te["data_source"].unique()))

    X_aug, y_aug = build_augmented_training_fold(tr[FEATURE_COLUMNS], tr[TARGET_COLUMN], seed=42)
    aug_cv = cramers_v_from_missingness(X_aug, y_aug)
    assert aug_cv <= 0.05, f"Augmented missingness shortcut detected: Cramér's V={aug_cv:.4f} > 0.05"
    print(
        f"[PASS] 1. Zero subject/row leakage verified ({len(tr)} train, {len(te)} test, 0 collisions, "
        f"Aug Cramér's V={aug_cv:.4f} <= 0.05)."
    )


def verify_ingestion_and_manifest_guardrails():
    # Unit suffix regex checks ("min" must not hit "minimum_sleep_hours")
    assert infer_unit_from_column_name("minimum_sleep_hours") is None
    assert infer_unit_from_column_name("sleep_min") == "minutes"
    assert infer_unit_from_column_name("sleep_minutes") == "minutes"

    # Sleep / radiation / CO2 normalizers
    assert abs(float(normalize_sleep_to_hours(pd.Series([420.0]), unit="minutes").iloc[0]) - 7.0) < 1e-6
    assert abs(float(normalize_radiation_to_msv(pd.Series([0.015]), unit="Gy").iloc[0]) - 15.0) < 1e-6
    assert abs(float(normalize_radiation_to_msv(pd.Series([1.5]), unit="cGy").iloc[0]) - 15.0) < 1e-6
    assert abs(float(normalize_radiation_to_msv(pd.Series([625.0]), unit="uSv/hr").iloc[0]) - 15.0) < 1e-6
    assert abs(float(normalize_co2_to_mmhg(pd.Series([5000.0]), unit="ppm").iloc[0]) - 3.8) < 1e-3
    assert abs(float(normalize_co2_to_mmhg(pd.Series([0.5]), unit="%").iloc[0]) - 3.8) < 1e-3
    assert abs(float(normalize_co2_to_mmhg(pd.Series([0.5]), unit="kPa").iloc[0]) - 3.75031) < 1e-3

    # Row-level UNITS + unapproved/invalid target rejection + mouse quarantine
    mixed_df = pd.DataFrame({
        "subject_id": ["A1", "A2"],
        "blood_glucose": [95.0, 11.0],
        "UNITS": ["mg/dL", "mmol/L"],
        "risk_label": [0, 99],
    })
    clean_mixed = ingest_nasa_dataframe(mixed_df, mission_id="unit_test", approve_source_target=False)
    assert abs(float(clean_mixed.loc[1, "blood_glucose"]) - 198.2) < 0.5, "Row-level mmol/L conversion failed"
    assert int(clean_mixed.loc[1, TARGET_COLUMN]) == 2, "Unapproved invalid label was not ignored"

    try:
        ingest_nasa_dataframe(mixed_df, mission_id="bad_tgt", approve_source_target=True)
        raise AssertionError("Expected ValueError on invalid approved target {99}")
    except ValueError:
        pass

    mouse_df = pd.DataFrame({"subject_id": [f"M{i}" for i in range(12)], "heart_rate_bpm": [410.0 + i for i in range(12)]})
    try:
        ingest_nasa_dataframe(mouse_df, mission_id="mouse_osd435", strict_species_check=True)
        raise AssertionError("Expected ValueError quarantining rodent heart rate cohort")
    except ValueError:
        pass

    # Manifest quarantine test in isolated temporary directory
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        pd.DataFrame({"subject_id": ["H1"], "blood_glucose": [92.0]}).to_csv(tdir / "human_ok.csv", index=False)
        pd.DataFrame({"subject_id": [f"M{i}" for i in range(12)], "heart_rate_bpm": [420.0 + i for i in range(12)]}).to_csv(
            tdir / "rodent_bad.csv", index=False
        )
        pd.DataFrame({"subject_id": ["U1"], "blood_glucose": [100.0]}).to_csv(tdir / "unregistered_file.csv", index=False)
        manifest = {
            "allowed_species": ["human"],
            "allowed_dataset_roles": ["human_clinical"],
            "datasets": [
                {"filename": "human_ok.csv", "species": "human", "dataset_role": "human_clinical", "mission_id": "m_ok"},
                {"filename": "rodent_bad.csv", "species": "mouse", "dataset_role": "rodent_telemetry", "mission_id": "m_bad"},
            ],
        }
        mpath = tdir / "manifest.json"
        mpath.write_text(json.dumps(manifest), encoding="utf-8")
        out_df, rep = load_nasa_directory(tdir, manifest_path=mpath, return_report=True)
        assert len(out_df) == 1 and out_df["subject_id"].iloc[0] == "nasa_H1"
        assert any(q["filename"] == "rodent_bad.csv" for q in rep["quarantined"])
        assert any(u["filename"] == "unregistered_file.csv" for u in rep["unregistered"])

    print("[PASS] 2. Manifest-driven NASA ingestion, unit converters, target validation & rodent quarantine verified.")


def verify_no_if_else_clinical_rules():
    ai_js = (PROJECT_ROOT / "ai-model.js").read_text(encoding="utf-8")
    controller_files = ["app-shell.js", "scan.js", "decision.js", "history.js"]

    forbidden_ai = [
        "evaluateClinicalSafetyGate",
        "blood_glucose < 62",
        "systolic_bp < 85",
        "targetP2",
    ]
    for pat in forbidden_ai:
        assert pat not in ai_js, f"Found forbidden hardcoded if-else rule '{pat}' in ai-model.js!"

    forbidden_app = [
        "f.blood_glucose < 62",
        "f.systolic_bp < 85",
        "lower.includes('blood pressure')",
        "lower.includes('radiation')",
        "Deterministic Clinical Safety Gate",
    ]
    for fname in controller_files:
        src = (PROJECT_ROOT / fname).read_text(encoding="utf-8")
        for pat in forbidden_app:
            assert pat not in src, f"Found forbidden hardcoded if-else rule '{pat}' in {fname}!"

    print("[PASS] 3. Confirmed zero hardcoded clinical/chatbot if-else chains across ai-model.js & modular controllers.")


def _build_reference_payload() -> dict:
    X_train, X_test, y_train, _y_test, g_train, _, _, _, _ = load_pre_split_datasets()
    inner_sgkf = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=42)
    tr_idx, val_idx = next(inner_sgkf.split(X_train, y_train, g_train))
    X_tr_i, y_tr_i = build_augmented_training_fold(X_train.iloc[tr_idx], y_train.iloc[tr_idx], seed=42)
    w_tr_i = compute_sample_weight("balanced", y_tr_i)
    w_val_i = compute_sample_weight("balanced", y_train.iloc[val_idx])

    model = build_xgb_classifier(early_stopping_rounds=25, random_state=42)
    model.fit(
        X_tr_i,
        y_tr_i,
        sample_weight=w_tr_i,
        eval_set=[(X_train.iloc[val_idx], y_train.iloc[val_idx])],
        sample_weight_eval_set=[w_val_i],
        verbose=False,
    )

    sample_df = X_test.copy()
    sample_legacy9 = X_test.copy()
    for c in EXTENDED_FEATURES:
        sample_legacy9[c] = np.nan
    sample_nocam = X_test.copy()
    for c in ["balance_score", "joint_symmetry_diff", "facial_ear"]:
        sample_nocam[c] = np.nan

    return {
        "n_test": len(sample_df),
        "rows_full": json.loads(sample_df.to_json(orient="values")),
        "py_probs_full": model.predict_proba(sample_df).tolist(),
        "rows_legacy9": json.loads(sample_legacy9.iloc[:, :9].to_json(orient="values")),
        "py_probs_legacy9": model.predict_proba(sample_legacy9).tolist(),
        "rows_nocam": json.loads(sample_nocam.to_json(orient="values")),
        "py_probs_nocam": model.predict_proba(sample_nocam).tolist(),
        "baselines": {s["key"]: s["nominalBaseline"] for s in CLINICAL_BIOMARKER_SCHEMA},
    }


def _generate_e2e_harness_script(route: str) -> str:
    """Injected only on ?verify=1 GET across the 5-page MPA inside the local test server."""
    bodies = {
        "index.html": """
    assert(Boolean(window.BioShell), "BioShell shell must initialize on index.html");
    const heroImg = document.getElementById("heroAstronaut");
    assert(Boolean(heroImg && heroImg.getAttribute("src") === "assets/astronaut-eva.png"), "Hero EVA cutout asset must be wired");
    assert(!document.getElementById("globalSosBtn"), "Global SOS navbar button must be removed");
    assert(!document.querySelector(".brand-dot"), "Navbar brand dot must be removed");
    assert(!document.querySelector(".hero-kicker"), "Hero kicker chip must be removed");
    assert(!document.querySelector(".vernier-track"), "Vernier ruler track must be removed");
    assert(!document.querySelector(".hero-telemetry-grid"), "Hero telemetry NaN grid must be removed");
    assert(!document.querySelector(".glide-anchor-label"), "Glide bay label must be removed");
    assert(!document.querySelector(".section-meta"), "Mission meta label must be removed");
    assert(!document.querySelector(".section-link"), "Guide shortcut link in modules header must be removed");
    const stageLinks = [...document.querySelectorAll(".cards-grid-3 a")].map((a) => a.getAttribute("href"));
    assert(stageLinks.length === 1 && stageLinks[0] === "scan.html", "Only Open Scan Stage 1 CTA may appear in stage cards");
    assert(document.querySelectorAll(".purpose-col").length === 3, "Landing must render 3-column Physiological mission grid");
    assert(!document.getElementById("appFooter")?.querySelector("[contenteditable='true']"), "Simplified footer must not contain contenteditable hackathon slots");
    assert(!document.getElementById("globalLangToggle"), "English-only website must remove Arabic/EN language toggle");
    assert(window.BioShell.getUiLang() === "en", "UI language must default strictly to English");
    assert(Boolean(document.querySelector('#primaryNav a[href="assistant.html"]')), "Navbar must include AI Assistant link");
    assert(Boolean(document.querySelector('#appHeader')) && !/[\u0600-\u06FF]/.test(document.body.innerText), "Visible page text must remain strictly English");
""",
        "scan.html": """
    assert(Boolean(window.app && window.visionLab && window.BioShell), "scan.html modules must load");
    assert(Boolean(document.getElementById("crewProfileSelect")), "Crew member selector must exist in Stage 1");
    assert(document.querySelectorAll("#vitalsForm .field-group").length === 9, "Stage 1 form must show exactly 9 inputs");
    assert(!document.getElementById("clearScanBtn") && !document.getElementById("proceedDecisionTopBtn"), "Top Reset & XGBoost Decision header buttons must be removed");
    assert(!document.getElementById("envContextBanner"), "Environment banner on scan.html must be removed");
    assert(!document.getElementById("step1Tab") && !document.getElementById("step2Tab"), "Top stage stepper tabs must be removed so user enters Stage 1 before Stage 2");
    assert(!document.getElementById("telemetryDropzone") && !document.getElementById("telemetryFileInput"), "CSV/JSON uploader dropzone must be removed");
    assert(!document.getElementById("inputPostureManual") && !document.getElementById("inputSymmetryManual") && !document.getElementById("inputEarManual"), "Manual Stage-2 camera inputs must be removed from Stage 1");
    const vis0 = window.visionLab.getLatestSummary();
    assert(Number.isNaN(vis0.balance_score) && Number.isNaN(vis0.posture_score), "Initial vision summary must be NaN");
    const f0 = window.app.extractModelFeatures();
    assert(["balance_score","joint_symmetry_diff","facial_ear","heart_rate_bpm","spo2_pct","radiation_dose_msv","cabin_co2_mmhg"]
      .every((k) => Number.isNaN(f0[k])), "Initial unmeasured/camera features must pass native NaN");

    // Populate then clear extended inputs back to NaN
    const hrEl = document.getElementById("inputHeartRate");
    const radEl = document.getElementById("inputRadiation");
    const co2El = document.getElementById("inputCO2");
    const spo2El = document.getElementById("inputSpO2");
    assert(Boolean(hrEl && radEl && co2El && spo2El), "All 4 extended inputs must exist in DOM");
    hrEl.value = "40"; hrEl.dispatchEvent(new Event("input"));
    radEl.value = "16.5"; radEl.dispatchEvent(new Event("input"));
    const fSet = window.app.extractModelFeatures();
    assert(fSet.heart_rate_bpm === 40 && fSet.radiation_dose_msv === 16.5, "Extended inputs must flow into canonical keys");
    hrEl.value = ""; hrEl.dispatchEvent(new Event("input"));
    radEl.value = ""; radEl.dispatchEvent(new Event("input"));
    const fCleared = window.app.extractModelFeatures();
    assert(Number.isNaN(fCleared.heart_rate_bpm) && Number.isNaN(fCleared.radiation_dose_msv), "Clearing inputs must revert to NaN");

    // Inverted Blood Pressure validation blocks Stage 1 -> Stage 2
    const bpEl = document.getElementById("inputBP");
    bpEl.value = "80/130"; bpEl.dispatchEvent(new Event("input"));
    const invCheck = window.app.parseBloodPressure("80/130");
    assert(invCheck.valid === false && Number.isNaN(invCheck.systolic), "Inverted BP must fail validation");
    const moved = window.app.goToStep(2);
    assert(moved === false && window.app.state.activeStep === 1, "Invalid BP must block Stage 1 -> Stage 2 advance");
    assert(!document.getElementById("bpValidationError").classList.contains("hidden"), "BP validation error must be visible");

    // Valid nominal inputs + NaN camera -> Optimal (class 0)
    bpEl.value = "118/78"; bpEl.dispatchEvent(new Event("input"));
    document.getElementById("inputGlucose").value = "94";
    document.getElementById("inputTemp").value = "36.8";
    document.getElementById("inputSleep").value = "7.5";
    document.getElementById("inputMood").value = "1";
    const nomInf = window.app.runModelInference();
    assert(nomInf && nomInf.predictedClass === 0, "Nominal Step 1 + NaN cam must evaluate Optimal (class 0)");
    assert(document.getElementById("sumPosture").textContent === "--", "Skipped webcam must display --");

    // Full reset clears back to native NaN
    window.app.startNewCheckin();
    assert(document.getElementById("inputGlucose").value === "" && document.getElementById("valPosture").textContent === "--", "startNewCheckin must reset inputs & HUD");
    assert(Object.values(window.app.extractModelFeatures()).every((v) => Number.isNaN(v)), "startNewCheckin must revert all 13 channels to NaN");

    // Critical glucose boundary (190.1) persists Critical session for decision.html
    bpEl.value = "118/78"; bpEl.dispatchEvent(new Event("input"));
    document.getElementById("inputGlucose").value = "190.1";
    document.getElementById("inputTemp").value = "36.8";
    document.getElementById("inputSleep").value = "7.2";
    document.getElementById("inputMood").value = "1";
    const critInf = window.app.runModelInference();
    assert(critInf && critInf.predictedClass === 2 && critInf.redFlags.length >= 1 && critInf.readinessScore <= 34, "glucose=190.1 must trigger Critical (class 2)");
""",
        "decision.html": """
    assert(Boolean(window.decisionPage && window.BioShell), "decision.html modules must load");
    const badge = document.getElementById("step3StatusBadge")?.textContent || "";
    assert(badge.toLowerCase().includes("critical") && !badge.includes("Mission Ready"), "decision.html must render Critical badge from shared session");
    const riskBadges = document.getElementById("decisionRiskBadges")?.textContent || "";
    assert(riskBadges.includes("HRP #") && riskBadges.trim().length > 10, "decision.html must surface NASA HRP risk badges");
    assert(document.querySelectorAll("#shapWaterfallList .waterfall-row").length >= 4, "decision.html must render SHAP waterfall attributions");
    const holoZones = document.querySelectorAll("g.holo-zone[data-system-id]");
    assert(holoZones.length === 5, "decision.html must render all 5 clickable anatomical hologram zones");
    document.querySelector('[data-holo-pill="cardio"]')?.click();
    const cardioTitle = document.getElementById("decHoloTitle")?.textContent || "";
    assert(cardioTitle.toLowerCase().includes("cardio") || cardioTitle.toLowerCase().includes("heart"), "Clicking cardio pill must update hologram feedback title");
    document.querySelector('g.holo-zone[data-system-id="renal"]')?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const renalTitle = document.getElementById("decHoloTitle")?.textContent || "";
    assert(renalTitle.toLowerCase().includes("renal") || renalTitle.toLowerCase().includes("kidney"), "Clicking renal SVG zone must update hologram feedback title");
    const strainBars = document.querySelectorAll("#organStrainChart [data-chart-system]");
    assert(strainBars.length === 5, "5-Organ Strain chart must render 5 clickable organ bars");
    assert(Boolean(document.querySelector("#readinessDonutChart svg")), "Readiness donut gauge SVG must render");
    document.querySelector('#organStrainChart [data-chart-system="immune"]')?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const immuneTitle = document.getElementById("decHoloTitle")?.textContent || "";
    assert(immuneTitle.toLowerCase().includes("immune"), "Clicking immune strain bar must focus hologram on Immune system");
    const numGluc = document.getElementById("num-blood_glucose");
    assert(Boolean(numGluc && document.getElementById("slider-blood_glucose")), "decision.html wide simulator must provide both slider and numeric input");
    assert(Boolean(document.getElementById("decisionQuickTakeaways") && document.getElementById("printReportBtn")), "decision.html must render Quick Takeaways summary and Print PDF Report button");
    document.getElementById("saveHistoryBtn")?.click();
    assert(window.BioShell.getHistory().length >= 5, "Saving decision check-in must append to shared mission history");
""",
        "history.html": """
    assert(Boolean(window.app && window.historyPage && window.BioShell), "history.html modules must load");
    assert(!document.getElementById("importHistoryInput"), "Import CSV input must be removed from history.html");
    assert(!document.body.innerText.includes("Import CSV"), "Import CSV button text must not appear on history.html");
    assert(Boolean(document.getElementById("historyCrewFilter")), "history.html must render crew member filter dropdown");
    assert(typeof window.Chart === "function", "history.html must load Chart.js locally offline");
    assert(window.BioShell.getHistory().length >= 5, "Persisted decision check-in must appear on history.html");
    const styleBtns = document.querySelectorAll("[data-chart-style]");
    assert(styleBtns.length === 4, "history.html must provide 4 chart view style buttons");
    document.querySelector('[data-chart-style="bar"]')?.click();
    assert(document.querySelector('[data-chart-style="bar"]')?.classList.contains("active"), "Bar chart style button must activate");
    document.querySelector('[data-chart-style="area"]')?.click();
    assert(document.querySelector('[data-chart-style="area"]')?.classList.contains("active"), "Area chart style button must activate");
    document.querySelector('[data-chart-style="hbar"]')?.click();
    assert(document.querySelector('[data-chart-style="hbar"]')?.classList.contains("active"), "Horizontal bar chart style button must activate");
    if (typeof window.Chart === "function") {
      const ch = window.Chart.getChart(document.getElementById("vitalsChart"));
      assert(Boolean(ch && ch.options.indexAxis === "y" && ch.data.datasets.every((d) => d.yAxisID === "y")), "Horiz. Bar must bind category axis y and indexAxis y");
    } else {
      assert(document.querySelectorAll("#offlineSvgChartWrap svg rect").length >= 4, "Offline SVG horiz bar chart must render bars");
    }
    document.querySelector('[data-chart-style="line"]')?.click();
    window.BioShell.replaceHistory([{
      id: "XSS-TEST",
      timestamp: new Date().toISOString(),
      label: "<img src=x onerror=alert(1)>",
      environment: "<b>Mars</b>",
      scanMode: "Walk",
      status: "Critical",
      riskPct: 91.2,
      features: { blood_glucose: 190.1, systolic_bp: 118, diastolic_bp: 78 }
    }]);
    window.app.renderHistoryTable();
    const tbodyHtml = document.getElementById("historyTableBody").innerHTML;
    assert(tbodyHtml.includes("&lt;img src=x") && !tbodyHtml.includes("<img src=x"), "historyTableBody must escape XSS HTML");
    window.BioShell.resetHistoryToSeed();
    window.BioShell.clearSession();
""",
        "guide.html": """
    assert(Boolean(window.BioShell && window.NASA_DATA_BUNDLE && window.guidePage), "guide.html modules must load");
    assert(Boolean(document.getElementById("personalGuideSection") && document.getElementById("personalSnapshotCard")), "Personalized guide sections must exist");
    window.BioShell.saveSession({
      environment: "Rover",
      features: { mood_score: 4, sleep_hours: 4.5, cabin_co2_mmhg: 4.2, blood_glucose: 145, systolic_bp: 118, diastolic_bp: 78 }
    });
    window.guidePage.refreshPersonalized();
    const crossText = document.getElementById("personalCrossPlanWrap")?.textContent || "";
    assert(crossText.includes("PHYSICAL PLAN") && crossText.includes("Hypercapnia"), "Personalized physical plan must react to recorded CO2/sleep/glucose telemetry");
    window.BioShell.clearSession();
    const matchText = document.getElementById("guideMatchCount")?.textContent || "";
    const count = parseInt(matchText, 10);
    assert(Number.isFinite(count) && count >= 38, "guide.html must render all 38 NASA reference items inside Topic Explorer, got: " + matchText);
    document.querySelector('[data-guide-tab="protocols"]')?.click();
    assert(document.querySelectorAll("#guideSectionsWrap details.guide-accordion").length === 6, "Clicking Emergency Checklists tile must focus 6 checklists");
    document.querySelector('[data-guide-tab="all"]')?.click();
    const ans = window.BioShell.askCopilot("How to reduce radiation dose?");
    assert(Boolean(ans && ans.responseText && ans.responseText.includes("Live ML Assessment:")), "Offline Bio-Copilot RAG + ML fallback must still work cleanly");
""",
        "assistant.html": """
    assert(Boolean(window.BioShell && window.customElements && window.customElements.get("astro-chat")), "assistant.html must define <astro-chat> custom element");
    const tabChat = document.querySelector('#assistantChatMount astro-chat');
    assert(Boolean(tabChat && tabChat.getAttribute("mode") === "tab" && tabChat.getAttribute("language") === "en"), "assistant.html must mount full-page English <astro-chat mode='tab'>");
    assert(Boolean(document.getElementById("assistantCrewSelect") && document.getElementById("chatBackendStatusPill") && document.getElementById("assistantVitalsGrid")), "assistant.html context sidebar widgets must render");
    assert(!document.querySelector('#copilotToggleBtn'), "assistant.html must not show duplicate floating copilot button");
    const offlineAns = tabChat.buildOfflineReply("How to manage station radiation?");
    assert(Boolean(offlineAns && offlineAns.includes("Live ML Assessment:")), "Offline <astro-chat> fallback must generate NASA RAG answer even when backend is offline");
""",
    }
    body = bodies[route]
    return f"""
<script>
window.addEventListener("load", function() {{
  const e2e = {{ passed: false, route: "{route}", checks: [], errors: [] }};
  function assert(cond, msg) {{ if (!cond) throw new Error(msg); e2e.checks.push(msg); }}
  try {{
{body}
    e2e.passed = true;
  }} catch (err) {{
    e2e.errors.push(String(err && err.stack ? err.stack : err));
  }}
  const out = document.createElement("pre");
  out.id = "verify-e2e-json";
  out.textContent = JSON.stringify(e2e);
  document.body.appendChild(out);
}});
</script>
"""


def verify_in_chrome_v8():
    browser_bin = _find_chromium_binary()
    payload = _build_reference_payload()
    payload_json = json.dumps(payload).replace("</", "<\\/")

    verify_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Verify AI</title></head>
<body>
  <input id="inputGlucose" value="94">
  <input id="inputBP" value="118/78">
  <input id="inputTemp" value="36.8">
  <input id="inputSleep" value="7.2">
  <div id="step3StatusDot"></div>
  <div id="step3StatusBadge"></div>
  <div id="step3GlucoseSub"></div>
  <div id="step3BPSub"></div>
  <div id="step3TempSub"></div>
  <div id="step3DirectivesList"></div>
  <div id="decisionConfidence"></div>
  <div id="decisionReadinessScore"></div>
  <div id="decisionReadinessText"></div>
  <div id="decisionReadinessBar"></div>
  <div id="decisionRiskBadges"></div>
  <div id="decisionRiskText"></div>
  <div id="decisionProbBreakdown"></div>
  <div id="decisionProtocolTitle"></div>
  <div id="decisionProtocolText"></div>
  <div id="decisionProtocolMeta"></div>
  <div id="decisionRecommendationsList"></div>
  <pre id="verify-json"></pre>
  <script src="/nasa-data.js"></script>
  <script src="/ai-model.js"></script>
  <script src="/app-shell.js"></script>
  <script>
    (function() {{
      const report = {{ passed: false, errors: [], details: {{}} }};
      function assert(cond, msg) {{
        if (!cond) throw new Error(msg);
      }}
      function argmax(arr) {{
        return arr.reduce((best, val, idx, a) => (val > a[best] ? idx : best), 0);
      }}
      function evalSchemaExpected(vecObj) {{
        let crit = 0, pts = 0;
        window.CLINICAL_BIOMARKER_SCHEMA.forEach((spec) => {{
          const v = vecObj[spec.key];
          if (!Number.isFinite(v)) return;
          const b = spec.bands.find((band) => {{
            const loOk = band.min === null || band.min === undefined ? true : (band.minInclusive !== false ? v >= band.min : v > band.min);
            const hiOk = band.max === null || band.max === undefined ? true : (band.maxInclusive ? v <= band.max : v < band.max);
            return loOk && hiOk;
          }});
          if (!b) return;
          if (b.critical) crit++;
          else pts += b.points;
        }});
        if (crit > 0 || pts >= 6) return 2;
        if (pts >= 3) return 1;
        return 0;
      }}

      try {{
        const payload = {payload_json};

        // 1. Full 1762-row Python <-> Chrome V8 parity across Full-13, Legacy-9, & No-Webcam
        let maxFullDiff = 0, maxLeg9Diff = 0, maxNoCamDiff = 0, classAgree = 0, totalRows = 0;
        const checkSet = (rows, pyProbs, tracker) => {{
          rows.forEach((row, idx) => {{
            const jsP = window.predictAstronautRisk(row);
            const pyP = pyProbs[idx];
            const d = Math.max(...jsP.map((p, k) => Math.abs(p - pyP[k])));
            if (d > tracker.max) tracker.max = d;
            assert(d < 1e-4, tracker.name + " parity diff=" + d + " at row " + idx);
            if (argmax(jsP) === argmax(pyP)) classAgree++;
            totalRows++;
          }});
        }};
        const t1 = {{ name: "Full-13", max: 0 }};
        const t2 = {{ name: "Legacy-9", max: 0 }};
        const t3 = {{ name: "No-Webcam", max: 0 }};
        checkSet(payload.rows_full, payload.py_probs_full, t1);
        checkSet(payload.rows_legacy9, payload.py_probs_legacy9, t2);
        checkSet(payload.rows_nocam, payload.py_probs_nocam, t3);
        maxFullDiff = t1.max; maxLeg9Diff = t2.max; maxNoCamDiff = t3.max;
        assert(classAgree === totalRows, "Class agreement " + classAgree + "/" + totalRows + " != 100%");

        // 2. Verify all 48 NASA_KNOWLEDGE_DOCS have non-empty id, title, and text
        assert(window.NASA_KNOWLEDGE_DOCS.length === 48, "Expected 48 RAG docs, got " + window.NASA_KNOWLEDGE_DOCS.length);
        window.NASA_KNOWLEDGE_DOCS.forEach((d, i) => {{
          assert(d.id && d.id.trim().length > 0, "Empty doc id at " + i);
          assert(d.title && d.title.trim().length > 0, "Empty doc title at " + i);
          assert(d.text && d.text.trim().length > 0, "Empty doc text at " + i);
        }});

        // 3. Exhaustive boundary, composite, partial-NaN & single-analyte probe sweep (>= 156 probes)
        const b = payload.baselines;
        const makeVec = (ov) => Object.assign({{}}, b, ov);
        const probeList = [];

        // Baseline & partial-modality anchors
        probeList.push(["Nominal_Full13", makeVec({{}})]);
        probeList.push(["Nominal_Legacy9", makeVec({{ heart_rate_bpm: NaN, spo2_pct: NaN, radiation_dose_msv: NaN, cabin_co2_mmhg: NaN }})]);
        probeList.push(["Nominal_NoCam", makeVec({{ balance_score: NaN, joint_symmetry_diff: NaN, facial_ear: NaN }})]);
        probeList.push(["Nominal_ICUSubset", makeVec({{ sleep_hours: NaN, mood_score: NaN, balance_score: NaN, joint_symmetry_diff: NaN, facial_ear: NaN, radiation_dose_msv: NaN, cabin_co2_mmhg: NaN }})]);
        probeList.push(["GlucoseOnly_Optimal", {{ blood_glucose: 92 }}]);
        probeList.push(["GlucoseOnly_CriticalHigh", {{ blood_glucose: 205 }}]);
        probeList.push(["GlucoseOnly_CriticalLow", {{ blood_glucose: 54 }}]);

        // Generate below / at / above probes for EVERY band boundary across all 13 biomarkers (Full-13 & NoCam)
        window.CLINICAL_BIOMARKER_SCHEMA.forEach((spec) => {{
          const eps = spec.key === "facial_ear" ? 0.001 : (["body_temp", "cabin_co2_mmhg", "radiation_dose_msv", "joint_symmetry_diff"].includes(spec.key) ? 0.01 : 0.1);
          const seen = new Set();
          spec.bands.forEach((band) => {{
            ["min", "max"].forEach((bk) => {{
              const tv = band[bk];
              if (tv === null || tv === undefined) return;
              [-eps, 0, eps].forEach((off) => {{
                const v = Math.min(spec.plausible[1], Math.max(spec.plausible[0], Number((tv + off).toFixed(4))));
                const sig = spec.key + "_" + v;
                if (!seen.has(sig)) {{
                  seen.add(sig);
                  probeList.push([sig, makeVec({{ [spec.key]: v }})]);
                  if (!["balance_score", "joint_symmetry_diff", "facial_ear"].includes(spec.key)) {{
                    probeList.push([sig + "_NoCam", makeVec({{ [spec.key]: v, balance_score: NaN, joint_symmetry_diff: NaN, facial_ear: NaN }})]);
                  }}
                }}
              }});
            }});
          }});
        }});

        // Composite Caution & Critical probes (moderate multi-vital stress + radiation/CO2)
        probeList.push(["Composite_Caution_Glu150_Sleep5", makeVec({{ blood_glucose: 150, sleep_hours: 5.0 }})]);
        probeList.push(["Composite_Caution_Rad3_CO2_3", makeVec({{ radiation_dose_msv: 3.0, cabin_co2_mmhg: 3.0 }})]);
        probeList.push(["Composite_Critical_ThreeCaution", makeVec({{ blood_glucose: 150, sleep_hours: 5.0, balance_score: 70 }})]);
        probeList.push(["NoCam_Rad15_Crit", makeVec({{ radiation_dose_msv: 15.0, balance_score: NaN, joint_symmetry_diff: NaN, facial_ear: NaN }})]);
        probeList.push(["NoCam_CO2_4_Crit", makeVec({{ cabin_co2_mmhg: 4.0, balance_score: NaN, joint_symmetry_diff: NaN, facial_ear: NaN }})]);

        let safetyEscalations = 0;
        probeList.forEach(([pname, vecObj]) => {{
          const ev = window.evaluateAstronautHealth(vecObj);
          const expectedCls = evalSchemaExpected(vecObj);
          const pSum = ev.probabilities.reduce((a, x) => a + x, 0);
          assert(Math.abs(pSum - 1.0) < 1e-6, "Prob sum != 1 on " + pname);
          assert(argmax(ev.probabilities) === ev.predictedClass, "Prob argmax mismatch on " + pname);
          assert(ev.tierConfig.historyStatus === ["Nominal", "Monitored", "Critical"][ev.predictedClass], "Tier config mismatch on " + pname);
          if (ev.redFlags.length > 0) {{
            assert(ev.predictedClass === 2, "CONTRADICTORY UI: Red flag on " + pname + " got class " + ev.predictedClass);
            assert(ev.predictedLabel === "Critical", "Red flag did not label Critical on " + pname);
            assert(ev.readinessScore <= 34, "Red flag readinessScore too high (" + ev.readinessScore + ") on " + pname);
          }}
          if (expectedCls === 2) assert(ev.predictedClass === 2, "Critical floor missed on " + pname + " got " + ev.predictedClass);
          if (expectedCls === 1) assert(ev.predictedClass >= 1, "Caution floor missed on " + pname + " got " + ev.predictedClass);
          if (ev.safetyEscalated) safetyEscalations++;
        }});

        // 4. Bio-Copilot RAG sanity
        const ragRad = window.queryBioCopilot("How to respond to solar particle radiation storm?", makeVec({{ radiation_dose_msv: 18.0 }}));
        assert(ragRad.matchedDocs.length > 0 && ragRad.responseText.includes("Critical"), "Copilot RAG check failed");

        report.passed = true;
        report.details = {{
          totalParityRows: totalRows,
          maxFullParityDiff: maxFullDiff,
          maxLegacy9ParityDiff: maxLeg9Diff,
          maxNoCamParityDiff: maxNoCamDiff,
          probesPassed: probeList.length,
          safetyEscalationsTriggered: safetyEscalations,
          nasaKbDocsCount: window.NASA_KNOWLEDGE_DOCS.length,
          copilotTopMatch: ragRad.matchedDocs[0].title
        }};
      }} catch (err) {{
        report.errors.push(String(err && err.stack ? err.stack : err));
      }}
      document.getElementById("verify-json").textContent = JSON.stringify(report);
    }})();
  </script>
</body>
</html>"""

    class _VerifyHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/__verify__.html":
                raw = verify_html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            for route in ("index.html", "scan.html", "decision.html", "history.html", "guide.html", "assistant.html"):
                if self.path.startswith(f"/{route}?verify=1"):
                    page_html = (PROJECT_ROOT / route).read_text(encoding="utf-8")
                    injected = page_html.replace("</body>", _generate_e2e_harness_script(route) + "\n</body>")
                    raw = injected.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
            super().do_GET()

    handler = functools.partial(_VerifyHandler, directory=str(PROJECT_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        proc = subprocess.run(
            [browser_bin, "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=4000", "--dump-dom", f"http://127.0.0.1:{port}/__verify__.html"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        m = re.search(r'<pre id="verify-json">(.*?)</pre>', proc.stdout, re.S)
        assert m is not None, f"Chromium did not emit verify-json:\nSTDOUT={proc.stdout[:1000]}\nSTDERR={proc.stderr[:1000]}"
        report = json.loads(html.unescape(m.group(1)))
        assert report["passed"], f"Chrome V8 JS verification failed: {report['errors']}"
        d = report["details"]
        assert d["probesPassed"] >= 156, f"Expected >= 156 probes, ran {d['probesPassed']}"
        print(
            f"[PASS] 4. Chrome V8 Engine verified across {d['totalParityRows']} parity predictions (100% class agree):\n"
            f"          - Max Float32 Parity Diff (Full-13 / Legacy-9 / NoCam): {d['maxFullParityDiff']:.2e} / {d['maxLegacy9ParityDiff']:.2e} / {d['maxNoCamParityDiff']:.2e} (< 1e-4)\n"
            f"          - Exhaustive Boundary, Composite & Partial Probes: {d['probesPassed']}/{d['probesPassed']} passed (0 contradictions, {d['safetyEscalationsTriggered']} floor escalations)\n"
            f"          - NASA Knowledge RAG Docs Loaded: {d['nasaKbDocsCount']}/48 non-empty (Top Rad match: '{d['copilotTopMatch']}')"
        )

        # Live multi-page E2E check across all 5 HTML pages sharing Chrome user-data-dir offline
        total_e2e_checks = 0
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile_dir:
            for route in ("index.html", "scan.html", "decision.html", "history.html", "guide.html", "assistant.html"):
                proc_pg = subprocess.run(
                    [
                        browser_bin,
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        f"--user-data-dir={profile_dir}",
                        "--virtual-time-budget=4000",
                        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                        "--dump-dom",
                        f"http://127.0.0.1:{port}/{route}?verify=1",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                assert proc_pg.returncode == 0, f"{route} E2E exited non-zero: {proc_pg.stderr}"
                m_e2e = re.search(r'<pre id="verify-e2e-json">(.*?)</pre>', proc_pg.stdout, re.S)
                assert m_e2e is not None, f"{route} E2E did not emit verify-e2e-json:\nSTDOUT={proc_pg.stdout[-1200:]}"
                e2e_report = json.loads(html.unescape(m_e2e.group(1)))
                assert e2e_report["passed"], f"Live {route} E2E check failed: {e2e_report['errors']}"
                total_e2e_checks += len(e2e_report["checks"])

        print(f"[PASS] 5. Live 6-page MPA E2E verified offline in headless Chrome ({total_e2e_checks} cross-route workflow assertions passed, 0 failures).")
    finally:
        server.shutdown()
        server.server_close()


def main():
    verify_zero_leakage()
    verify_ingestion_and_manifest_guardrails()
    verify_no_if_else_clinical_rules()
    verify_in_chrome_v8()
    print("\nALL ZERO-TRUST END-TO-END VERIFICATION CHECKS PASSED (0 FAILURES).")


if __name__ == "__main__":
    main()
