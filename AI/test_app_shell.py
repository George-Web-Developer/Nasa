import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nasa_data import ROOT, eval_js_in_chrome


class TestAppShell(unittest.TestCase):
    def test_app_shell_utilities_persistence_and_protocols(self):
        target = ROOT / "app-shell.js"
        self.assertTrue(target.exists(), "app-shell.js must exist in project root")

        res = eval_js_in_chrome(
            """
            localStorage.clear();
            sessionStorage.clear();

            const S = window.BioShell;
            if (!S) throw new Error('window.BioShell missing');

            // 1. XSS escapeHtml
            const xss = S.escapeHtml(`<img src=x onerror="alert('1')">&`);
            if (xss.includes('<') || xss.includes('>') || xss.includes('"') || xss.includes("'")) {
              throw new Error('escapeHtml failed: ' + xss);
            }

            // 2. CSV formula injection sanitization
            const eq = S.sanitizeCsvCell('=HYPERLINK("http://evil")');
            const plus = S.sanitizeCsvCell('+cmd|"/c calc"');
            const minus = S.sanitizeCsvCell('-2+3');
            const at = S.sanitizeCsvCell('@SUM(A1:A2)');
            const tab = S.sanitizeCsvCell('\\t1+1');
            const ret = S.sanitizeCsvCell('\\r=cmd');
            const safeComma = S.sanitizeCsvCell('C001, ISS');
            for (const val of [eq, plus, minus, at, tab, ret]) {
              const stripped = val.replace(/^"/, '');
              if (!stripped.startsWith("'")) {
                throw new Error('Formula prefix not neutralized: ' + val);
              }
            }
            if (!safeComma.startsWith('"') || !safeComma.includes('C001, ISS')) {
              throw new Error('Comma CSV quoting failed: ' + safeComma);
            }

            // 3. CSV quoted-comma & OSDR header parsing
            const csvText = [
              'subject,mission_phase,glucose_value_milligram_per_deciliter,albumin_value_gram_per_deciliter,hemoglobin_value_gram_per_deciliter,white_blood_cell_count_10_3_per_microliter,crp_concentration_milligram_per_liter',
              '"C001, Crew","Post-Flight, Day 1",94.5,4.3,14.8,6.2,1.1',
              '"C002, Crew","In-Flight",102,4.1,15.1,7.0,1.4'
            ].join('\\n');
            const parsed = S.parseCsvTable(csvText);
            if (!parsed || parsed.rows.length !== 2) {
              throw new Error('parseCsvTable row count wrong');
            }
            if (parsed.rows[0].subject !== 'C001, Crew' || parsed.rows[0].mission_phase !== 'Post-Flight, Day 1') {
              throw new Error('Quoted comma split broken: ' + JSON.stringify(parsed.rows[0]));
            }
            if (parsed.mappedTelemetry[0].blood_glucose !== 94.5) {
              throw new Error('OSDR glucose column mapping failed: ' + JSON.stringify(parsed.mappedTelemetry[0]));
            }

            // 4. Environment persistence
            const defaultEnv = S.getEnvironment();
            if (defaultEnv !== 'Space Station') throw new Error('Default env not Space Station: ' + defaultEnv);
            S.setEnvironment('Lunar/Planetary Base');
            if (S.getEnvironment() !== 'Lunar/Planetary Base') throw new Error('Env persistence failed');

            // 5. Session NaN preservation round-trip (canonical MODEL_FEATURES keys)
            S.saveSession({
              environment: 'Rover',
              scanMode: 'Walk',
              features: {
                blood_glucose: NaN,
                systolic_bp: 118,
                diastolic_bp: 76,
                body_temp: 36.8,
                sleep_hours: NaN,
                mood_score: 1,
                balance_score: 94,
                joint_symmetry_diff: 1.5,
                facial_ear: 0.30,
                heart_rate_bpm: NaN,
                radiation_dose_msv: 0.95,
                cabin_co2_mmhg: 3.1,
                spo2_pct: NaN
              }
            });
            const restored = S.getSession();
            if (!Number.isNaN(restored.features.blood_glucose) || !Number.isNaN(restored.features.heart_rate_bpm)) {
              throw new Error('Session NaN coerced to 0/null instead of NaN: ' + JSON.stringify(restored.features));
            }
            if (restored.features.systolic_bp !== 118 || restored.features.balance_score !== 94 || restored.environment !== 'Rover') {
              throw new Error('Session non-NaN fields mismatch: ' + JSON.stringify(restored.features));
            }

            // 6. History append & resetHistoryToSeed
            const seed = S.getHistory();
            if (!Array.isArray(seed) || seed.length < 3) throw new Error('Seed history missing');
            S.appendHistory({ id: 'TEST-1', label: 'Nominal Check', status: 'Optimal', riskPct: 8.2 });
            if (S.getHistory().length !== seed.length + 1) throw new Error('appendHistory failed');
            S.resetHistoryToSeed();
            if (S.getHistory().length !== seed.length) throw new Error('resetHistoryToSeed failed');

            // 7. Chrome shell, 6 emergency protocols & Bilingual Copilot responseText rendering
            S.renderShellChrome({ activeRoute: 'scan.html' });
            S.openEmergencyModal();
            const protoBtns = document.querySelectorAll('[data-protocol-id]');
            const protoIds = Array.from(protoBtns).map(el => el.getAttribute('data-protocol-id'));
            S.selectEmergencySymptom('hypoxia-dcs');
            const detailText = document.getElementById('sosProtocolDetail')?.textContent || '';

            const copilotAns = S.askCopilot('مستوى الاشعاع');
            const copilotFeedText = document.getElementById('copilotFeed')?.textContent || '';

            return {
              xss, eq, safeComma,
              row0Subject: parsed.rows[0].subject,
              row0Glucose: parsed.mappedTelemetry[0].blood_glucose,
              protoCount: protoIds.length,
              protoIds,
              hasHypoxiaTitle: detailText.length > 20,
              hasCopilotBtn: !!document.getElementById('copilotToggleBtn'),
              hasCopilotAnswer: copilotFeedText.includes('Live ML Assessment:'),
              copilotMatchedDocs: (copilotAns && copilotAns.matchedDocs ? copilotAns.matchedDocs.length : 0),
              hasToastRegion: !!document.getElementById('toastRegion')
            };
            """,
            extra_scripts=["nasa-data.js", "ai-model.js", "app-shell.js"],
        )
        self.assertTrue(res.get("ok"), f"Chrome JS evaluation failed: {res.get('error')}")
        data = res["data"]
        self.assertEqual(data["protoCount"], 6)
        self.assertEqual(
            data["protoIds"],
            ["chest-pain", "dizziness", "balance-loss", "radiation", "hypoxia-dcs", "sans-vision"],
        )
        self.assertTrue(data["hasHypoxiaTitle"])
        self.assertTrue(data["hasCopilotBtn"])
        self.assertTrue(data["hasCopilotAnswer"], "Bio-Copilot askCopilot did not render responseText into feed")
        self.assertGreater(data["copilotMatchedDocs"], 0)
        self.assertTrue(data["hasToastRegion"])

    def test_real_osdr_csv_and_blank_risk_import(self):
        csv_path = ROOT / "AI" / "data" / "nasa_training" / "osdr_inspiration4_crew_matrix.csv"
        self.assertTrue(csv_path.exists(), "Real OSDR Inspiration4 matrix must exist")
        sample_lines = csv_path.read_text(encoding="utf-8").splitlines()[:3]
        csv_snippet = "\n".join(sample_lines)

        res = eval_js_in_chrome(
            f"""
            localStorage.clear();
            const osdrParsed = window.BioShell.parseCsvTable({json.dumps(csv_snippet)});
            const s0 = osdrParsed.serumRows[0];

            // Blank riskPct on a hypoxic/hypercapnic telemetry CSV row must compute ML risk instead of Number("") === 0
            if (typeof window.historyPage.importCsv === 'function') {{
              throw new Error('historyPage.importCsv should be removed');
            }}
            const telemetryCsv = [
              'id,label,riskPct,blood_glucose,systolic_bp,diastolic_bp,body_temp,sleep_hours,mood_score,balance_score,joint_symmetry_diff,facial_ear,heart_rate_bpm,spo2_pct,radiation_dose_msv,cabin_co2_mmhg',
              'IMP-HYP,Hypoxic Test,,135,148,94,37.8,4.2,4,68,8.5,0.18,118,86,3.5,6.8'
            ].join('\\n');
            const parsedTel = window.BioShell.parseCsvTable(telemetryCsv);
            const rawRisk = String(parsedTel.rows[0].riskPct ?? '').trim();
            const evalOut = window.evaluateAstronautHealth(parsedTel.mappedTelemetry[0]);
            const metrics = window.BioShell.extractRiskMetrics(evalOut);

            return {{
              s0,
              impRisk: rawRisk ? Number(rawRisk) : metrics.riskPct,
              impConf: metrics.confidencePct,
              impStatus: metrics.status
            }};
            """,
            extra_scripts=["nasa-data.js", "ai-model.js", "app-shell.js", "history.js"],
        )
        self.assertTrue(res.get("ok"), f"Chrome JS evaluation failed: {res.get('error')}")
        d = res["data"]
        s0 = d["s0"]
        self.assertEqual(s0["subject"], "C001_L-3")
        self.assertEqual(s0["glucose_mg_dl"], 69)
        self.assertEqual(s0["albumin_g_dl"], 4.9)
        self.assertEqual(s0["hemoglobin_g_dl"], 14.7)
        self.assertEqual(s0["wbc_10e3_ul"], 7.0)
        self.assertEqual(s0["crp_mg_l"], 5.13)
        self.assertGreater(d["impRisk"], 50.0, f"Blank riskPct coerced to 0 instead of ML risk: {d}")
        self.assertGreater(d["impConf"], 0.0)


if __name__ == "__main__":
    unittest.main()
