import http.server
import json
import os
import re
import socketserver
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def eval_js_in_chrome(script_body: str, extra_scripts: list[str] | None = None) -> dict:
    """Load script files in local Chrome V8 and parse JSON printed into #out."""
    extra_scripts = extra_scripts or []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tags = "\n".join(f'<script src="/{s}"></script>' for s in extra_scripts)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{tags}</head>
<body><pre id="out">{{}}</pre>
<script>
try {{
  const res = (function() {{ {script_body} }})();
  document.getElementById('out').textContent = JSON.stringify({{ ok: true, data: res }});
}} catch (err) {{
  document.getElementById('out').textContent = JSON.stringify({{ ok: false, error: String(err && err.stack || err) }});
}}
</script></body></html>"""
        harness_path = ROOT / "AI" / "_tmp_test_harness.html"
        harness_path.write_text(html, encoding="utf-8")

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ROOT), **kwargs)

            def log_message(self, format, *args):
                pass

        try:
            with socketserver.TCPServer(("127.0.0.1", 0), QuietHandler) as httpd:
                port = httpd.server_address[1]
                t = threading.Thread(target=httpd.serve_forever, daemon=True)
                t.start()
                try:
                    cmd = [
                        CHROME,
                        "--headless=new",
                        "--disable-gpu",
                        "--dump-dom",
                        "--virtual-time-budget=2500",
                        f"http://127.0.0.1:{port}/AI/_tmp_test_harness.html",
                    ]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
                    m = re.search(r'<pre id="out">(.*?)</pre>', proc.stdout, re.S)
                    if not m:
                        raise AssertionError(f"Missing #out in DOM dump. rc={proc.returncode} stderr={proc.stderr[:400]}")
                    raw = m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                    return json.loads(raw)
                finally:
                    httpd.shutdown()
        finally:
            if harness_path.exists():
                harness_path.unlink()


class TestNasaDataBundle(unittest.TestCase):
    def test_nasa_data_js_exists_and_exposes_grounded_tables(self):
        target = ROOT / "nasa-data.js"
        self.assertTrue(target.exists(), "nasa-data.js must exist in project root")

        res = eval_js_in_chrome(
            """
            const b = window.NASA_DATA_BUNDLE;
            if (!b) throw new Error('window.NASA_DATA_BUNDLE missing');
            return {
              hazards: b.hazards?.length,
              hrpRisks: b.hrpRisks?.length,
              bodySystems: b.bodySystems?.length,
              protocols: (b.emergencyProtocols || []).map(p => p.protocol_id),
              clinicalIndicators: b.clinicalIndicators?.length,
              environments: (b.environments || []).map(e => e.id),
              presetsCount: b.missionPresets?.length,
              presetFirstKeys: Object.keys((b.missionPresets && b.missionPresets[0]?.features) || {}),
              i4Rows: b.inspiration4Sample?.length,
              i4First: (b.inspiration4Sample && b.inspiration4Sample[0]) || null
            };
            """,
            extra_scripts=["nasa-data.js"],
        )
        self.assertTrue(res.get("ok"), res.get("error"))
        d = res["data"]
        self.assertEqual(d["hazards"], 5)
        self.assertEqual(d["hrpRisks"], 22)
        self.assertEqual(d["bodySystems"], 5)
        self.assertEqual(len(d["protocols"]), 6)
        self.assertIn("hypoxia-dcs", d["protocols"])
        self.assertIn("sans-vision", d["protocols"])
        self.assertEqual(d["clinicalIndicators"], 12)
        self.assertEqual(d["environments"], ["Space Station", "Spacecraft", "Rover", "Lunar/Planetary Base"])
        self.assertGreaterEqual(d["presetsCount"], 4)
        self.assertEqual(
            sorted(d["presetFirstKeys"]),
            sorted([
                "blood_glucose",
                "systolic_bp",
                "diastolic_bp",
                "body_temp",
                "sleep_hours",
                "mood_score",
                "balance_score",
                "joint_symmetry_diff",
                "facial_ear",
                "heart_rate_bpm",
                "spo2_pct",
                "radiation_dose_msv",
                "cabin_co2_mmhg",
            ]),
        )
        self.assertGreaterEqual(d["i4Rows"], 4)
        i4_first = d["i4First"]
        self.assertIsNotNone(i4_first)
        self.assertEqual(i4_first["subject"], "C001_L-3")
        self.assertEqual(i4_first["glucose_mg_dl"], 69.0)
        self.assertEqual(i4_first["albumin_g_dl"], 4.9)
        self.assertEqual(i4_first["hemoglobin_g_dl"], 14.7)
        self.assertEqual(i4_first["wbc_10e3_ul"], 7.0)
        self.assertEqual(i4_first["crp_mg_l"], 5.13)


if __name__ == "__main__":
    unittest.main(verbosity=2)
