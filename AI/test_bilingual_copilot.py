import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nasa_data import eval_js_in_chrome


class TestBilingualCopilot(unittest.TestCase):
    def test_arabic_queries_retrieve_matching_nasa_docs(self):
        res = eval_js_in_chrome(
            """
            const nominal = {
              blood_glucose: 92, systolic_bp: 118, diastolic_bp: 76,
              body_temp: 36.8, sleep_hours: 7.5, mood_score: 1,
              posture_deg: 95, joint_symmetry: 0.95, facial_ear: 0.31,
              heart_rate: 68, radiation_msv: 0.55, cabin_co2: 2.3, spo2_pct: 98
            };
            const rad = window.queryBioCopilot('مستوى الاشعاع في المحطة', nominal);
            const bp = window.queryBioCopilot('عندي ارتفاع في ضغط الدم وصداع', nominal);
            const resp = window.queryBioCopilot('نسبة الاكسجين وثاني اكسيد الكربون', nominal);
            const fatigue = window.queryBioCopilot('اشعر بتعب وارهاق وقلة نوم', nominal);
            return {
              radCount: rad.matchedDocs.length,
              radTitles: rad.matchedDocs.map(d => (d.title + ' ' + d.text).toLowerCase()),
              bpCount: bp.matchedDocs.length,
              bpTitles: bp.matchedDocs.map(d => (d.title + ' ' + d.text).toLowerCase()),
              respCount: resp.matchedDocs.length,
              respTitles: resp.matchedDocs.map(d => (d.title + ' ' + d.text).toLowerCase()),
              fatigueCount: fatigue.matchedDocs.length,
              fatigueTitles: fatigue.matchedDocs.map(d => (d.title + ' ' + d.feature + ' ' + d.text).toLowerCase()),
            };
            """,
            extra_scripts=["ai-model.js"],
        )
        self.assertTrue(res.get("ok"), res.get("error"))
        d = res["data"]
        self.assertGreater(d["radCount"], 0, "Expected radiation docs for Arabic query")
        self.assertTrue(any("radiation" in t or "rad" in t for t in d["radTitles"]), d["radTitles"])
        self.assertGreater(d["bpCount"], 0, "Expected BP docs for Arabic query")
        self.assertTrue(any("pressure" in t or "fluid" in t or "sans" in t for t in d["bpTitles"]), d["bpTitles"])
        self.assertGreater(d["respCount"], 0, "Expected respiratory docs for Arabic query")
        self.assertTrue(any("co2" in t or "hypoxia" in t or "oxygen" in t or "spo2" in t for t in d["respTitles"]), d["respTitles"])
        self.assertGreater(d["fatigueCount"], 0, "Expected fatigue docs for Arabic query")
        self.assertTrue(any("fatigue" in t or "sleep" in t or "ear" in t for t in d["fatigueTitles"]), d["fatigueTitles"])
        self.assertFalse(any("heart" in t and "fatigue" not in t and "sleep" not in t for t in d["fatigueTitles"]), d["fatigueTitles"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
