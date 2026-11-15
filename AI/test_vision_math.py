import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nasa_data import ROOT, eval_js_in_chrome


class TestVisionMath(unittest.TestCase):
    def test_biomechanics_math_and_honest_camera_denial(self):
        target = ROOT / "vision.js"
        self.assertTrue(target.exists(), "vision.js must exist")

        res = eval_js_in_chrome(
            """
            const V = window.visionLab;
            if (!V || !V.math) throw new Error('visionLab.math pure exports missing');
            const M = V.math;

            // 1. 3D Angle invariance across depth tilt (2D XY would collapse if Z dominates)
            const a90 = M.calculateAngle3D({ x: 1, y: 0, z: 0 }, { x: 0, y: 0, z: 0 }, { x: 0, y: 1, z: 0 });
            const depth90 = M.calculateAngle3D({ x: 0, y: 0, z: 1 }, { x: 0, y: 0, z: 0 }, { x: 0, y: 1, z: 0 });
            const nanCheck = M.calculateAngle3D(null, { x: 0, y: 0, z: 0 }, { x: 0, y: 1, z: 0 });
            if (Math.abs(a90 - 90) > 0.1 || Math.abs(depth90 - 90) > 0.1) {
              throw new Error('3D angle invariance failed: ' + a90 + ', ' + depth90);
            }
            if (!Number.isNaN(nanCheck)) throw new Error('Null landmark did not return NaN');

            // 2. Zero lateral room-offset penalty: left side (x=0.2) vs right side (x=0.8) upright posture identical
            const leftFrameScore = M.evaluateUprightPostureScore({ coronalTiltDeg: 1.5, headOffsetDeg: 2.0, centerX: 0.2 });
            const rightFrameScore = M.evaluateUprightPostureScore({ coronalTiltDeg: 1.5, headOffsetDeg: 2.0, centerX: 0.8 });
            if (Math.abs(leftFrameScore - rightFrameScore) > 0.001 || leftFrameScore < 93) {
              throw new Error('Lateral camera offset penalized posture: L=' + leftFrameScore + ' R=' + rightFrameScore);
            }

            // 3. Alternating out-of-phase walking gait over 3.0s produces symmetrical bilateral ROM -> Balanced
            const tracker = new M.RollingROMSymmetryTracker(3000);
            for (let t = 0; t <= 3000; t += 100) {
              const phase = (t / 1000) * Math.PI * 2 * 1.0; // 1 stride/sec
              const lKnee = 145 + 30 * Math.sin(phase);       // 115..175 => 60 deg ROM
              const rKnee = 145 + 30 * Math.sin(phase + Math.PI); // opposite phase, SAME 60 deg ROM
              tracker.pushSample(t, lKnee, rKnee);
            }
            const gaitSym = tracker.evaluate(3000);
            if (gaitSym.romDiffDeg >= 2.0 || gaitSym.symmetryCoeff < 0.95 || gaitSym.status !== 'Balanced') {
              throw new Error('Normal walking gait flagged abnormal: ' + JSON.stringify(gaitSym));
            }

            // Asymmetric limp should still be caught
            const limpTracker = new M.RollingROMSymmetryTracker(3000);
            for (let t = 0; t <= 3000; t += 100) {
              const phase = (t / 1000) * Math.PI * 2;
              limpTracker.pushSample(t, 145 + 32 * Math.sin(phase), 165 + 10 * Math.sin(phase + Math.PI));
            }
            const limpSym = limpTracker.evaluate(3000);
            if (limpSym.symmetryCoeff >= 0.78 || limpSym.status !== 'Asymmetric') {
              throw new Error('True asymmetric gait missed: ' + JSON.stringify(limpSym));
            }

            // 4. Side-on yaw turn gate (< 0.24 ratio)
            const frontPose = {
              lShoulder: { x: -0.20, y: 0.30, z: 0 },
              rShoulder: { x: 0.20, y: 0.30, z: 0 },
              lHip: { x: -0.14, y: -0.25, z: 0 },
              rHip: { x: 0.14, y: -0.25, z: 0 }
            };
            const sidePose = {
              lShoulder: { x: 0.02, y: 0.30, z: -0.18 },
              rShoulder: { x: -0.02, y: 0.30, z: 0.18 },
              lHip: { x: 0.01, y: -0.25, z: -0.10 },
              rHip: { x: -0.01, y: -0.25, z: 0.10 }
            };
            if (M.isYawAngleGated(frontPose) !== false) throw new Error('Front pose falsely yaw-gated');
            if (M.isYawAngleGated(sidePose) !== true) throw new Error('Side-on yaw turn not gated');

            // 4b. 16:9 normalized-coordinate aspect scaling for yaw gating & EAR
            const wideYawPose = {
              lShoulder: { x: 0.42, y: 0.25, z: 0 },
              rShoulder: { x: 0.56, y: 0.25, z: 0 }, // 0.14 norm span * 16/9 = 0.249; torso = 0.55 => ratio 0.45 >= 0.24
              lHip: { x: 0.44, y: 0.80, z: 0 },
              rHip: { x: 0.54, y: 0.80, z: 0 }
            };
            if (M.isYawAngleGated(wideYawPose, 16 / 9) !== false) {
              throw new Error('16:9 shoulder span not scaled by aspectRatio');
            }
            const wideEye = [
              { x: 0.30, y: 0.50 },
              { x: 0.32, y: 0.475 },
              { x: 0.36, y: 0.475 },
              { x: 0.38, y: 0.50 }, // dx = 0.08 -> in 16:9 horizontal span = 0.1422, v = 0.05 -> EAR ~= 0.35 (not 0.625)
              { x: 0.36, y: 0.525 },
              { x: 0.32, y: 0.525 }
            ];
            const wideEar = M.earFromSix(wideEye, 16 / 9);
            if (!(wideEar > 0.30 && wideEar < 0.40)) {
              throw new Error('16:9 EAR distortion detected: ' + wideEar);
            }

            // 5. Trimmed mean ignores 10% extreme outliers & returns NaN if empty
            const tMean = M.trimmedMean([98, 99, 100, 100, 101, 100, 99, 100, 15, 210], 0.10);
            if (Math.abs(tMean - 99.625) > 0.2) throw new Error('trimmedMean outlier leak: ' + tMean);
            if (!Number.isNaN(M.trimmedMean([]))) throw new Error('Empty trimmedMean must be NaN');

            // 6. Pitch-aware EAR stays stable on mild pitch without collapsing
            const pitchEar = M.computePitchAwareEar(0.31, 12);
            if (!(pitchEar >= 0.28 && pitchEar <= 0.36)) throw new Error('Pitch-aware EAR out of expected bounds: ' + pitchEar);

            // 7. CHROM optical rPPG recovers 1.2 Hz -> 72 BPM (+/- 3 BPM) with SQI >= 60%
            const fps = 30;
            const samples = [];
            for (let i = 0; i < fps * 10; i++) {
              const t = i / fps;
              const pulse = Math.sin(2 * Math.PI * 1.2 * t);
              samples.push({
                t: i * (1000 / fps),
                r: 182 + 0.9 * pulse,
                g: 138 - 1.9 * pulse,
                b: 118 - 0.3 * pulse
              });
            }
            const chromGood = M.computeChromBpm(samples, fps);
            if (!Number.isFinite(chromGood.bpm) || Math.abs(chromGood.bpm - 72) > 3.5 || chromGood.sqiPct < 60) {
              throw new Error('CHROM failed on 72 BPM signal: ' + JSON.stringify(chromGood));
            }
            const chromFlat = M.computeChromBpm(Array.from({ length: 120 }, (_, i) => ({ t: i * 33, r: 150, g: 130, b: 120 })), fps);
            if (Number.isFinite(chromFlat.bpm) && chromFlat.sqiPct >= 40) {
              throw new Error('CHROM hallucinated confident HR on flat signal: ' + JSON.stringify(chromFlat));
            }

            // 7b. Jittered-timestamp (~24fps) 58 BPM + high-freq noise + drift, plus 96 BPM check (never locked to 66-69 BPM)
            const jitter58 = [];
            let tCur = 0;
            for (let i = 0; i < 240; i++) {
              tCur += 41.6 + Math.sin(i * 1.7) * 6.5;
              const sec = tCur / 1000;
              const pulse = Math.sin(2 * Math.PI * (58 / 60) * sec);
              const hfNoise = 0.7 * Math.sin(2 * Math.PI * 5.8 * sec);
              const drift = 4.0 * Math.sin(2 * Math.PI * 0.12 * sec);
              jitter58.push({
                t: tCur,
                r: 180 + drift + 0.9 * pulse + hfNoise,
                g: 136 + drift - 1.9 * pulse + hfNoise,
                b: 116 + drift - 0.3 * pulse + hfNoise
              });
            }
            const res58 = M.computeChromBpm(jitter58, 24);
            if (!Number.isFinite(res58.bpm) || Math.abs(res58.bpm - 58) > 3.5 || res58.sqiPct < 45) {
              throw new Error('CHROM failed jittered 58 BPM + HF noise recovery: ' + JSON.stringify(res58));
            }
            const s96 = Array.from({ length: 240 }, (_, i) => {
              const sec = i / 30;
              const pulse = Math.sin(2 * Math.PI * (96 / 60) * sec);
              return { t: sec * 1000, r: 182 + 0.9 * pulse, g: 138 - 1.9 * pulse, b: 118 - 0.3 * pulse };
            });
            const res96 = M.computeChromBpm(s96, 30);
            if (!Number.isFinite(res96.bpm) || Math.abs(res96.bpm - 96) > 3.5) {
              throw new Error('CHROM failed 96 BPM recovery: ' + JSON.stringify(res96));
            }
            // 7c. Broadband / uncorrelated RGB camera noise without cardiac periodicity must stay unconfident (NaN BPM)
            const noiseSamples = [];
            let state = 1337;
            const rand = () => { state = (state * 1664525 + 1013904223) >>> 0; return (state / 4294967296) - 0.5; };
            for (let i = 0; i < 180; i++) {
              noiseSamples.push({
                t: i * (1000 / 30),
                r: 175 + rand() * 3.5,
                g: 135 + rand() * 3.5,
                b: 115 + rand() * 3.5
              });
            }
            const resNoise = M.computeChromBpm(noiseSamples, 30);
            if (Number.isFinite(resNoise.bpm)) {
              throw new Error('CHROM falsely locked BPM on uncorrelated noise: ' + JSON.stringify(resNoise));
            }

            // 8. Honest denied-webcam UX: never auto-spoof metrics when camera unavailable
            const divIdle = document.createElement('div'); divIdle.id = 'cameraIdleState';
            const divErr = document.createElement('div'); divErr.id = 'cameraErrorState'; divErr.className = 'hidden';
            const spanErr = document.createElement('span'); spanErr.id = 'cameraErrorText';
            const spanPosture = document.createElement('span'); spanPosture.id = 'valPosture'; spanPosture.textContent = '--';
            document.body.append(divIdle, divErr, spanErr, spanPosture);
            try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
            V.startCamera();
            if (divErr.classList.contains('hidden')) throw new Error('cameraErrorState remained hidden on missing camera');
            if (spanPosture.textContent !== '--') throw new Error('startCamera spoofed posture metric: ' + spanPosture.textContent);
            if (!Number.isNaN(V.getLatestSummary().posture_score)) throw new Error('summary posture_score should stay NaN');

            // 9. LandmarkTrackSmoother damps static shoulder micro-jitter & tracks real movement
            const lmSmooth = new M.LandmarkTrackSmoother({ minAlpha: 0.18, maxAlpha: 0.72, speedGain: 7.5 });
            lmSmooth.update([{ x: 0.40, y: 0.50, z: 0, visibility: 0.99 }], 0);
            const jittered = lmSmooth.update([{ x: 0.41, y: 0.49, z: 0, visibility: 0.99 }], 33);
            if (Math.abs(jittered[0].x - 0.40) > 0.005) {
              throw new Error('LandmarkTrackSmoother did not damp micro-jitter: ' + JSON.stringify(jittered[0]));
            }
            const jumped = lmSmooth.update([{ x: 0.65, y: 0.50, z: 0, visibility: 0.99 }], 66);
            if (jumped[0].x < 0.55) {
              throw new Error('LandmarkTrackSmoother lagged too much on rapid movement: ' + JSON.stringify(jumped[0]));
            }

            return {
              a90, depth90, leftFrameScore, gaitSym, limpSym,
              tMean, pitchEar, wideEar, chromGood, errMsg: spanErr.textContent
            };
            """,
            extra_scripts=["vision.js"],
        )
        self.assertTrue(res.get("ok"), f"Chrome JS evaluation failed: {res.get('error')}")
        data = res["data"]
        self.assertAlmostEqual(data["gaitSym"]["symmetryCoeff"], 0.99, delta=0.05)
        self.assertLess(abs(data["chromGood"]["bpm"] - 72.0), 3.5)


if __name__ == "__main__":
    unittest.main()
