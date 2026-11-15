/**
 * Bio Astro Lab — Computer Vision, 3D Locomotion Biomechanics,
 * Experimental Optical rPPG (CHROM), and Cranial Visor Capture (vision.js)
 */
let FilesetResolver = null;
let PoseLandmarker = null;
let FaceLandmarker = null;

(function (global) {
  'use strict';

  // ==========================================================
  // Pure Testable Biomechanics & Signal Processing Primitives
  // ==========================================================
  function calculateAngle3D(a, b, c) {
    if (!a || !b || !c) return NaN;
    const ax = Number(a.x), ay = Number(a.y), az = Number(a.z || 0);
    const bx = Number(b.x), by = Number(b.y), bz = Number(b.z || 0);
    const cx = Number(c.x), cy = Number(c.y), cz = Number(c.z || 0);
    if (![ax, ay, az, bx, by, bz, cx, cy, cz].every(Number.isFinite)) return NaN;

    const bax = ax - bx, bay = ay - by, baz = az - bz;
    const bcx = cx - bx, bcy = cy - by, bcz = cz - bz;
    const magBA = Math.hypot(bax, bay, baz);
    const magBC = Math.hypot(bcx, bcy, bcz);
    if (magBA < 1e-6 || magBC < 1e-6) return NaN;

    const dot = bax * bcx + bay * bcy + baz * bcz;
    const cosTheta = Math.max(-1, Math.min(1, dot / (magBA * magBC)));
    return (Math.acos(cosTheta) * 180) / Math.PI;
  }

  function evaluateUprightPostureScore(params) {
    const p = params || {};
    const tilt = Number.isFinite(p.coronalTiltDeg) ? Math.abs(p.coronalTiltDeg) : 0;
    const head = Number.isFinite(p.headOffsetDeg) ? Math.abs(p.headOffsetDeg) : 0;
    // Deliberately invariant to camera horizontal centerX so lateral pacing never triggers false abnormalities
    const penalty = tilt * 1.9 + head * 1.3;
    return Math.max(52, Math.min(99.4, 100 - penalty));
  }

  class RollingROMSymmetryTracker {
    constructor(windowMs = 3000) {
      this.windowMs = windowMs;
      this.samples = [];
    }

    pushSample(tMs, leftAngle, rightAngle) {
      if (!Number.isFinite(tMs) || !Number.isFinite(leftAngle) || !Number.isFinite(rightAngle)) return;
      this.samples.push({ t: tMs, l: leftAngle, r: rightAngle });
      const cutoff = tMs - this.windowMs;
      while (this.samples.length > 0 && this.samples[0].t < cutoff) {
        this.samples.shift();
      }
    }

    evaluate(nowMs) {
      if (this.samples.length === 0) {
        return { romLeft: NaN, romRight: NaN, romDiffDeg: NaN, symmetryCoeff: NaN, status: 'Warmup' };
      }
      const cutoff = (Number.isFinite(nowMs) ? nowMs : this.samples[this.samples.length - 1].t) - this.windowMs;
      const active = this.samples.filter((s) => s.t >= cutoff);
      if (active.length < 4) {
        return { romLeft: NaN, romRight: NaN, romDiffDeg: NaN, symmetryCoeff: NaN, status: 'Warmup' };
      }

      let lMin = Infinity, lMax = -Infinity, rMin = Infinity, rMax = -Infinity;
      for (const s of active) {
        if (s.l < lMin) lMin = s.l;
        if (s.l > lMax) lMax = s.l;
        if (s.r < rMin) rMin = s.r;
        if (s.r > rMax) rMax = s.r;
      }

      const romLeft = lMax - lMin;
      const romRight = rMax - rMin;
      const maxRom = Math.max(romLeft, romRight, 12);
      const romDiffDeg = Math.abs(romLeft - romRight);
      const ratioPenalty = romDiffDeg / maxRom;
      const coeff = Math.max(0.55, Math.min(0.99, 0.99 - Math.max(0, ratioPenalty - 0.03) * 0.72));

      let status = 'Balanced';
      if (coeff < 0.78) status = 'Asymmetric';
      else if (coeff < 0.90) status = 'Moderate Asym';

      return { romLeft, romRight, romDiffDeg, symmetryCoeff: coeff, status };
    }

    reset() {
      this.samples = [];
    }
  }

  function isYawAngleGated(landmarks, aspectRatio = 1) {
    if (!landmarks || !landmarks.lShoulder || !landmarks.rShoulder || !landmarks.lHip || !landmarks.rHip) {
      return false;
    }
    const { lShoulder, rShoulder, lHip, rHip } = landmarks;
    const aspect = Number.isFinite(aspectRatio) && aspectRatio > 0 ? aspectRatio : 1;
    const shoulderSpanX = Math.abs((lShoulder.x || 0) - (rShoulder.x || 0)) * aspect;
    const midShoulderY = ((lShoulder.y || 0) + (rShoulder.y || 0)) / 2;
    const midHipY = ((lHip.y || 0) + (rHip.y || 0)) / 2;
    const torsoLen = Math.max(Math.abs(midHipY - midShoulderY), 0.12);
    return shoulderSpanX / torsoLen < 0.24;
  }

  function trimmedMean(values, trimFrac = 0.10) {
    const clean = (values || []).filter((v) => typeof v === 'number' && Number.isFinite(v));
    if (clean.length === 0) return NaN;
    clean.sort((a, b) => a - b);
    const k = Math.floor(clean.length * trimFrac);
    const start = Math.min(k, Math.floor((clean.length - 1) / 2));
    const end = Math.max(start + 1, clean.length - start);
    let sum = 0;
    for (let i = start; i < end; i++) sum += clean[i];
    return sum / (end - start);
  }

  function computePitchAwareEar(rawEar, headPitchDeg = 0) {
    if (!Number.isFinite(rawEar)) return NaN;
    const clampedPitch = Math.max(-30, Math.min(30, Number(headPitchDeg) || 0));
    const rad = (clampedPitch * Math.PI) / 180;
    const denom = Math.max(0.78, Math.cos(rad * 0.55));
    return Math.max(0.05, Math.min(0.45, rawEar / denom));
  }

  function applyBiquadFiltfilt(signal, b0, b1, b2, a1, a2) {
    const n = signal.length;
    if (n < 8) return Float64Array.from(signal);
    const pad = Math.min(n - 1, 21);
    const total = n + pad * 2;
    const padded = new Float64Array(total);
    for (let i = 0; i < pad; i++) {
      padded[i] = 2 * signal[0] - signal[pad - i];
    }
    for (let i = 0; i < n; i++) {
      padded[pad + i] = signal[i];
    }
    for (let i = 0; i < pad; i++) {
      padded[pad + n + i] = 2 * signal[n - 1] - signal[n - 2 - i];
    }

    const runPass = (src) => {
      const dst = new Float64Array(src.length);
      let z1 = 0, z2 = 0;
      for (let i = 0; i < src.length; i++) {
        const x = src[i];
        const y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        dst[i] = y;
      }
      return dst;
    };

    const fwd = runPass(padded);
    const revIn = new Float64Array(total);
    for (let i = 0; i < total; i++) revIn[i] = fwd[total - 1 - i];
    const revOut = runPass(revIn);

    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) out[i] = revOut[total - 1 - (pad + i)];
    return out;
  }

  function bandpassCardiacZeroPhase(signal, fs) {
    // 2nd-order Butterworth HPF (0.75 Hz = 45 BPM) + LPF (2.80 Hz = 168 BPM), run zero-phase
    const kh = Math.tan((Math.PI * 0.75) / fs);
    const nh = 1 / (1 + Math.SQRT2 * kh + kh * kh);
    const afterHp = applyBiquadFiltfilt(
      signal,
      nh,
      -2 * nh,
      nh,
      2 * (kh * kh - 1) * nh,
      (1 - Math.SQRT2 * kh + kh * kh) * nh
    );

    const kl = Math.tan((Math.PI * 2.80) / fs);
    const nl = 1 / (1 + Math.SQRT2 * kl + kl * kl);
    const b0l = kl * kl * nl;
    return applyBiquadFiltfilt(
      afterHp,
      b0l,
      2 * b0l,
      b0l,
      2 * (kl * kl - 1) * nl,
      (1 - Math.SQRT2 * kl + kl * kl) * nl
    );
  }

  function resampleUniformRgb(valid, fpsEstimate) {
    const m = valid.length;
    const hasTimestamps = valid.every((s) => Number.isFinite(s.t));
    const spanRaw = hasTimestamps ? valid[m - 1].t - valid[0].t : 0;
    const targetFs = 30;

    if (!hasTimestamps || spanRaw < 1000) {
      let fps = Number(fpsEstimate);
      if (!Number.isFinite(fps) || fps <= 4) fps = 30;
      const tMaxMs = ((m - 1) / fps) * 1000;
      const nOut = Math.max(90, Math.round((tMaxMs / 1000) * targetFs) + 1);
      const rArr = new Float64Array(nOut);
      const gArr = new Float64Array(nOut);
      const bArr = new Float64Array(nOut);
      for (let k = 0; k < nOut; k++) {
        const idxFloat = Math.min(m - 1, (k / targetFs) * fps);
        const i0 = Math.floor(idxFloat);
        const i1 = Math.min(m - 1, i0 + 1);
        const frac = idxFloat - i0;
        rArr[k] = valid[i0].r + frac * (valid[i1].r - valid[i0].r);
        gArr[k] = valid[i0].g + frac * (valid[i1].g - valid[i0].g);
        bArr[k] = valid[i0].b + frac * (valid[i1].b - valid[i0].b);
      }
      return { fs: targetFs, r: rArr, g: gArr, b: bArr };
    }

    // Use up to latest 10 seconds onto uniform 30 Hz grid to absorb webcam FPS jitter
    const tEnd = valid[m - 1].t;
    const tStart = Math.max(valid[0].t, tEnd - 10000);
    const durationSec = Math.max(1.5, (tEnd - tStart) / 1000);
    const nOut = Math.min(300, Math.max(90, Math.round(durationSec * targetFs)));
    const rArr = new Float64Array(nOut);
    const gArr = new Float64Array(nOut);
    const bArr = new Float64Array(nOut);

    let ptr = 0;
    for (let k = 0; k < nOut; k++) {
      const tk = nOut > 1 ? tStart + (k / (nOut - 1)) * (tEnd - tStart) : tEnd;
      while (ptr < m - 2 && valid[ptr + 1].t < tk) ptr++;
      const s0 = valid[ptr];
      const s1 = valid[Math.min(m - 1, ptr + 1)];
      const dt = Math.max(1e-3, s1.t - s0.t);
      const frac = Math.max(0, Math.min(1, (tk - s0.t) / dt));
      rArr[k] = s0.r + frac * (s1.r - s0.r);
      gArr[k] = s0.g + frac * (s1.g - s0.g);
      bArr[k] = s0.b + frac * (s1.b - s0.b);
    }
    return { fs: nOut > 1 ? (nOut - 1) / durationSec : targetFs, r: rArr, g: gArr, b: bArr };
  }

  function computeChromBpm(samples, fpsEstimate) {
    const valid = (samples || []).filter((s) => s && [s.r, s.g, s.b].every(Number.isFinite));
    if (valid.length < 90) {
      return { bpm: NaN, sqiPct: 0, waveform: [] };
    }

    const uniform = resampleUniformRgb(valid, fpsEstimate);
    const n = uniform.r.length;
    const fs = uniform.fs;

    let sumR = 0, sumG = 0, sumB = 0;
    for (let i = 0; i < n; i++) {
      sumR += uniform.r[i];
      sumG += uniform.g[i];
      sumB += uniform.b[i];
    }
    const meanR = sumR / n || 1;
    const meanG = sumG / n || 1;
    const meanB = sumB / n || 1;

    const rn = new Float64Array(n);
    const gn = new Float64Array(n);
    const bn = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      rn[i] = uniform.r[i] / meanR - 1;
      gn[i] = uniform.g[i] / meanG - 1;
      bn[i] = uniform.b[i] / meanB - 1;
    }

    // Zero-phase Butterworth cardiac bandpass (0.75-2.80 Hz = 45-168 BPM)
    const dr = bandpassCardiacZeroPhase(rn, fs);
    const dg = bandpassCardiacZeroPhase(gn, fs);
    const db = bandpassCardiacZeroPhase(bn, fs);

    const xs = new Float64Array(n);
    const ys = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      xs[i] = 3 * dr[i] - 2 * dg[i];
      ys[i] = 1.5 * dr[i] + dg[i] - 1.5 * db[i];
    }

    const std = (arr) => {
      let m = 0;
      for (let i = 0; i < arr.length; i++) m += arr[i];
      m /= arr.length;
      let v = 0;
      for (let i = 0; i < arr.length; i++) {
        const d = arr[i] - m;
        v += d * d;
      }
      return Math.sqrt(v / arr.length);
    };

    const stdX = std(xs);
    const stdY = std(ys);
    const alpha = stdY > 1e-7 ? stdX / stdY : 0;
    const pulse = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      pulse[i] = xs[i] - alpha * ys[i];
    }

    let sig = pulse;
    const sigStd = std(sig);
    if (sigStd < 5e-5) {
      if (stdX < 5e-5) return { bpm: NaN, sqiPct: 0, waveform: [] };
      sig = xs;
    }

    // Soft-limit transient motion spikes (> 3.2 std) without distorting normal cardiac peaks
    const refStd = Math.max(std(sig), 1e-6);
    const limit = 3.2 * refStd;
    const cleaned = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const v = sig[i];
      cleaned[i] = Math.abs(v) > limit ? Math.sign(v) * limit * Math.tanh(Math.abs(v) / limit) : v;
    }

    // Hann window before spectral power search over 45..168 BPM
    const windowed = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const w = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1)));
      windowed[i] = cleaned[i] * w;
    }

    const powers = [];
    let bestBpm = 72;
    let bestPower = -1;
    let totalPower = 0;

    for (let bpm = 45; bpm <= 168; bpm += 0.5) {
      const freq = bpm / 60;
      let re = 0, im = 0;
      for (let i = 0; i < n; i++) {
        const angle = (2 * Math.PI * freq * i) / fs;
        re += windowed[i] * Math.cos(angle);
        im -= windowed[i] * Math.sin(angle);
      }
      const pwr = re * re + im * im;
      powers.push({ bpm, pwr });
      totalPower += pwr;
      if (pwr > bestPower) {
        bestPower = pwr;
        bestBpm = bpm;
      }
    }

    const lobeHalfBpm = Math.max(5.0, 28 / Math.max(3.0, n / fs));
    let neighborPower = 0;
    const sortedPowers = powers.map((item) => item.pwr).sort((a, b) => a - b);
    const medianPower = sortedPowers.length ? sortedPowers[Math.floor(sortedPowers.length / 2)] : 0;
    const snrRatio = medianPower > 1e-12 ? bestPower / medianPower : 0;

    for (const item of powers) {
      if (Math.abs(item.bpm - bestBpm) <= lobeHalfBpm) {
        neighborPower += item.pwr;
      }
    }
    const rawSqi = totalPower > 0 ? (neighborPower / totalPower) * 100 : 0;
    // Penalize flat/1-over-f camera noise spectra that lack a true cardiac peak above median power
    const snrScale = Math.min(1, Math.max(0, (snrRatio - 2.5) / 5.5));
    const sqiPct = Math.round(Math.max(0, Math.min(99, rawSqi * snrScale)));
    const waveform = Array.from(cleaned.slice(-105)).map((v) => Number(v.toFixed(5)));

    return {
      bpm: sqiPct >= 50 && snrRatio >= 4.5 ? Math.round(bestBpm) : NaN,
      sqiPct,
      snrRatio: Number(snrRatio.toFixed(2)),
      waveform
    };
  }

  // ==========================================================
  // Module State & Session Configuration
  // ==========================================================
  class MetricSmoother {
    constructor(alpha = 0.16) {
      this.alpha = alpha;
      this.ema = null;
    }
    update(v) {
      if (!Number.isFinite(v)) return this.ema;
      this.ema = this.ema === null ? v : this.alpha * v + (1 - this.alpha) * this.ema;
      return this.ema;
    }
    get() {
      return this.ema === null ? NaN : this.ema;
    }
    reset() {
      this.ema = null;
    }
  }

  class LandmarkTrackSmoother {
    constructor(opts) {
      const o = opts || {};
      this.minAlpha = Number.isFinite(o.minAlpha) ? o.minAlpha : 0.20;
      this.maxAlpha = Number.isFinite(o.maxAlpha) ? o.maxAlpha : 0.72;
      this.speedGain = Number.isFinite(o.speedGain) ? o.speedGain : 7.5;
      this.staleResetMs = Number.isFinite(o.staleResetMs) ? o.staleResetMs : 600;
      this.state = [];
      this.lastUpdateMs = -Infinity;
    }

    update(landmarks, nowMs) {
      if (!Array.isArray(landmarks) || landmarks.length === 0) return null;
      const t = Number.isFinite(nowMs) ? nowMs : 0;
      if (t - this.lastUpdateMs > this.staleResetMs) {
        this.state = [];
      }
      this.lastUpdateMs = t;

      const out = new Array(landmarks.length);
      for (let i = 0; i < landmarks.length; i++) {
        const raw = landmarks[i];
        if (!raw || !Number.isFinite(raw.x) || !Number.isFinite(raw.y)) {
          out[i] = null;
          continue;
        }
        const prev = this.state[i];
        const z = Number.isFinite(raw.z) ? raw.z : 0;
        const vis = Number.isFinite(raw.visibility) ? raw.visibility : 1;
        if (!prev) {
          const init = { x: raw.x, y: raw.y, z, visibility: vis };
          this.state[i] = init;
          out[i] = { ...init };
          continue;
        }
        const speed = Math.hypot(raw.x - prev.x, raw.y - prev.y);
        const alpha = Math.min(this.maxAlpha, Math.max(this.minAlpha, this.minAlpha + speed * this.speedGain));
        const smoothed = {
          x: prev.x + alpha * (raw.x - prev.x),
          y: prev.y + alpha * (raw.y - prev.y),
          z: prev.z + alpha * (z - prev.z),
          visibility: prev.visibility + 0.35 * (vis - prev.visibility)
        };
        this.state[i] = smoothed;
        out[i] = { ...smoothed };
      }
      return out;
    }

    reset() {
      this.state = [];
      this.lastUpdateMs = -Infinity;
    }
  }

  function isLandmarkVisible(pt, minVis = 0.45) {
    if (!pt || !Number.isFinite(pt.x) || !Number.isFinite(pt.y)) return false;
    const vis = pt.visibility === undefined ? 1 : pt.visibility;
    if (vis < minVis) return false;
    return pt.x >= -0.06 && pt.x <= 1.06 && pt.y >= -0.06 && pt.y <= 1.06;
  }

  const smoothers = {
    posture: new MetricSmoother(0.16),
    tilt: new MetricSmoother(0.18),
    ear: new MetricSmoother(0.24)
  };
  const poseNormSmoother = new LandmarkTrackSmoother({ minAlpha: 0.18, maxAlpha: 0.72, speedGain: 7.5 });
  const poseWorldSmoother = new LandmarkTrackSmoother({ minAlpha: 0.20, maxAlpha: 0.72, speedGain: 6.5 });
  const faceSmoother = new LandmarkTrackSmoother({ minAlpha: 0.25, maxAlpha: 0.78, speedGain: 8.5 });

  const gaitTracker = new RollingROMSymmetryTracker(3000);

  let poseLandmarker = null;
  let faceLandmarker = null;
  let isModelsLoading = false;
  let isModelsReady = false;

  let videoStream = null;
  let isRunning = false;
  let isSyntheticDemo = false;
  let animationFrameId = null;
  let simIntervalId = null;
  let sessionTimerId = null;
  let lastVideoTime = -1;

  let scanMode = 'Walk';
  let scanDurationSec = 30;
  let countdownRemaining = 30;
  let sessionStartMs = 0;
  let frameCount = 0;
  let lastFpsCheckMs = 0;
  let currentFps = 30;

  let squatState = 'UP';
  let squatReps = 0;
  let blinkCount = 0;
  let isEyeClosed = false;
  let closedFramesCount = 0;
  let trackedFaceFrames = 0;
  let faceCapturedForSession = false;

  const WARMUP_MS = 2500;
  const rppgSamples = [];
  const opticalBpmWindow = [];
  const offscreenCanvas = document.createElement('canvas');
  offscreenCanvas.width = 192;
  offscreenCanvas.height = 144;
  const portraitCanvas = document.createElement('canvas');
  portraitCanvas.width = 180;
  portraitCanvas.height = 180;

  const sessionSamples = {
    postureScores: [],
    coronalTilts: [],
    symmetryCoeffs: [],
    jointDeltas: [],
    earValues: [],
    opticalBpms: [],
    opticalSqis: []
  };

  let latestSummary = {
    balance_score: NaN,
    joint_symmetry_diff: NaN,
    facial_ear: NaN,
    posture_score: NaN,
    symmetry_coeff: NaN,
    ear_fatigue: NaN,
    heart_rate_optical: NaN,
    sqi_pct: 0,
    isSynthetic: false
  };

  let dom = {};
  function cacheDom() {
    dom = {
      webcam: document.getElementById('webcam'),
      visionCanvas: document.getElementById('visionCanvas'),
      cameraBox: document.getElementById('cameraBox'),
      hudLiveOverlay: document.getElementById('hudLiveOverlay'),
      hudLockPill: document.getElementById('hudLockPill'),
      hudLockLabel: document.getElementById('hudLockLabel'),
      hudResFpsLabel: document.getElementById('hudResFpsLabel'),
      hudFramingGuide: document.getElementById('hudFramingGuide'),
      retakeVisorBtn: document.getElementById('retakeVisorBtn'),
      visorPreviewCaption: document.getElementById('visorPreviewCaption'),
      cameraIdleState: document.getElementById('cameraIdleState'),
      cameraActiveState: document.getElementById('cameraActiveState'),
      cameraLoadingState: document.getElementById('cameraLoadingState'),
      cameraErrorState: document.getElementById('cameraErrorState'),
      cameraErrorText: document.getElementById('cameraErrorText'),
      modelStatusNotice: document.getElementById('modelStatusNotice'),
      startCameraBtn: document.getElementById('startCameraBtn'),
      stopCameraBtn: document.getElementById('stopCameraBtn'),
      finishAnalyzeBtn: document.getElementById('finishAnalyzeBtn'),
      replayDemoBtn: document.getElementById('replayDemoBtn'),
      generateDecisionBtn: document.getElementById('generateDecisionBtn'),
      scanModeWalkBtn: document.getElementById('scanModeWalkBtn'),
      scanModeStaticBtn: document.getElementById('scanModeStaticBtn'),
      scanDurationSelect: document.getElementById('scanDurationSelect'),
      countdownTimer: document.getElementById('countdownTimer'),
      countdownProgressBar: document.getElementById('countdownProgressBar'),
      streamFps: document.getElementById('streamFps'),
      landmarkTrackingStatus: document.getElementById('landmarkTrackingStatus'),
      squatCountVal: document.getElementById('squatCountVal'),
      valPosture: document.getElementById('valPosture'),
      badgePosture: document.getElementById('badgePosture'),
      valCoronalTilt: document.getElementById('valCoronalTilt'),
      valSway: document.getElementById('valSway'),
      valJoint: document.getElementById('valJoint'),
      badgeJoint: document.getElementById('badgeJoint'),
      valJointDelta: document.getElementById('valJointDelta'),
      valRepsCount: document.getElementById('valRepsCount'),
      valFatigue: document.getElementById('valFatigue'),
      badgeFatigue: document.getElementById('badgeFatigue'),
      valEar: document.getElementById('valEar'),
      valBlinkStatus: document.getElementById('valBlinkStatus'),
      valOpticalHr: document.getElementById('valOpticalHr'),
      badgeOpticalSqi: document.getElementById('badgeOpticalSqi'),
      rppgWaveCanvas: document.getElementById('rppgWaveCanvas'),
      applyOpticalHrBtn: document.getElementById('applyOpticalHrBtn'),
      hologramVisorImg: document.getElementById('hologramVisorImg'),
      movementAnalysisBanner: document.getElementById('movementAnalysisBanner')
    };
  }

  function setBadge(el, text, level) {
    if (!el) return;
    el.textContent = text;
    const cls = level === 'nominal' ? 'badge-nominal' : level === 'caution' ? 'badge-caution' : level === 'critical' ? 'badge-critical' : 'badge-ghost';
    el.className = 'badge ' + cls;
  }

  function updateModelNotice(msg) {
    if (dom.modelStatusNotice) dom.modelStatusNotice.textContent = msg;
  }

  async function initVisionModels() {
    if (isModelsReady || isModelsLoading) return;
    isModelsLoading = true;
    cacheDom();
    if (dom.cameraLoadingState) dom.cameraLoadingState.classList.remove('hidden');
    updateModelNotice('Loading MediaPipe Pose & Face Landmarker...');

    try {
      if (!FilesetResolver || !PoseLandmarker || !FaceLandmarker) {
        const mp = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14');
        FilesetResolver = mp.FilesetResolver;
        PoseLandmarker = mp.PoseLandmarker;
        FaceLandmarker = mp.FaceLandmarker;
      }
      const vision = await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm');
      const loadModels = async (delegate) => {
        try {
          poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task',
              delegate
            },
            runningMode: 'VIDEO',
            numPoses: 1,
            minPoseDetectionConfidence: 0.55,
            minPosePresenceConfidence: 0.55,
            minTrackingConfidence: 0.65
          });
        } catch {
          poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
              delegate
            },
            runningMode: 'VIDEO',
            numPoses: 1,
            minPoseDetectionConfidence: 0.50,
            minPosePresenceConfidence: 0.50,
            minTrackingConfidence: 0.55
          });
        }
        faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
            delegate
          },
          runningMode: 'VIDEO',
          numFaces: 1,
          minFaceDetectionConfidence: 0.55,
          minFacePresenceConfidence: 0.55,
          minTrackingConfidence: 0.60
        });
      };

      try {
        await loadModels('GPU');
        updateModelNotice('MediaPipe 3D Vision Ready (GPU)');
      } catch {
        await loadModels('CPU');
        updateModelNotice('MediaPipe 3D Vision Ready (CPU)');
      }
      isModelsReady = true;
    } catch (err) {
      updateModelNotice('MediaPipe CDN unreachable — camera HUD requires online WASM or Synthetic Demo replay.');
    } finally {
      isModelsLoading = false;
      if (dom.cameraLoadingState) dom.cameraLoadingState.classList.add('hidden');
    }
  }

  function showCameraError(reason) {
    cacheDom();
    activateLiveUI(false);
    if (dom.cameraIdleState) dom.cameraIdleState.classList.add('hidden');
    if (dom.cameraErrorState) dom.cameraErrorState.classList.remove('hidden');
    if (dom.cameraErrorText) dom.cameraErrorText.textContent = reason;
    if (dom.landmarkTrackingStatus) dom.landmarkTrackingStatus.textContent = 'Camera Blocked / Unavailable (Metrics NaN)';
  }

  async function startCamera() {
    cacheDom();
    if (dom.cameraErrorState) dom.cameraErrorState.classList.add('hidden');
    if (dom.cameraLoadingState) dom.cameraLoadingState.classList.remove('hidden');
    updateModelNotice('Initializing optical camera sensor...');

    // 1. Try to open user webcam first
    let stream = null;
    if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
          audio: false
        });
      } catch (err) {
        console.warn('[Vision] Live webcam getUserMedia denied/failed:', err);
      }
    }

    if (stream) {
      videoStream = stream;
      if (dom.webcam) {
        dom.webcam.srcObject = videoStream;
        try {
          await dom.webcam.play();
        } catch (e) {
          console.warn('[Vision] webcam play warning:', e);
        }
      }
      if (dom.cameraLoadingState) dom.cameraLoadingState.classList.add('hidden');
      isSyntheticDemo = false;
      beginTrackingLoop();

      // Attempt to load full AI models asynchronously without blocking live video feed
      if (!isModelsReady && !isModelsLoading) {
        initVisionModels().catch((e) => console.warn('[Vision] Background models load failed, using live optical tracker:', e));
      }
      return true;
    }

    // 2. If camera hardware is unavailable or permission denied, seamlessly activate Calibration Demo
    if (dom.cameraLoadingState) dom.cameraLoadingState.classList.add('hidden');
    if (global.BioShell && typeof global.BioShell.showToast === 'function') {
      global.BioShell.showToast('Webcam unavailable or denied. Starting Optical Calibration Demo.', 'nominal');
    }
    startCalibrationReplayDemo();
    return true;
  }

  function syncCanvasToVideo() {
    if (!dom.visionCanvas) return;
    if (!isSyntheticDemo && dom.webcam && dom.webcam.videoWidth > 0 && dom.webcam.videoHeight > 0) {
      const vw = dom.webcam.videoWidth;
      const vh = dom.webcam.videoHeight;
      if (dom.visionCanvas.width !== vw || dom.visionCanvas.height !== vh) {
        dom.visionCanvas.width = vw;
        dom.visionCanvas.height = vh;
      }
      if (dom.cameraBox) {
        dom.cameraBox.style.aspectRatio = vw + ' / ' + vh;
      }
    } else if (isSyntheticDemo) {
      if (dom.visionCanvas.width !== 960 || dom.visionCanvas.height !== 540) {
        dom.visionCanvas.width = 960;
        dom.visionCanvas.height = 540;
      }
      if (dom.cameraBox) {
        dom.cameraBox.style.aspectRatio = '16 / 9';
      }
    }
  }

  function updateHudOverlay(opts) {
    const o = opts || {};
    if (dom.hudLockPill) dom.hudLockPill.setAttribute('data-lock', o.lock || 'partial');
    if (dom.hudLockLabel && o.lockText) dom.hudLockLabel.textContent = o.lockText;
    if (dom.hudResFpsLabel) {
      const resTag = isSyntheticDemo
        ? 'CALIBRATION DEMO'
        : dom.webcam && dom.webcam.videoWidth
        ? dom.webcam.videoWidth + '×' + dom.webcam.videoHeight
        : 'CAMERA';
      dom.hudResFpsLabel.textContent = resTag + ' · ' + currentFps + ' FPS';
    }
    if (dom.hudFramingGuide && o.guideText) {
      dom.hudFramingGuide.textContent = o.guideText;
      dom.hudFramingGuide.setAttribute('data-tone', o.guideTone || 'neutral');
    }
  }

  function beginTrackingLoop() {
    cacheDom();
    syncCanvasToVideo();
    activateLiveUI(true);
    resetSessionMetrics();
    isRunning = true;
    lastVideoTime = -1;
    sessionStartMs = performance.now();
    lastFpsCheckMs = performance.now();
    frameCount = 0;

    updateHudOverlay({
      lock: 'partial',
      lockText: isSyntheticDemo ? 'CALIBRATION REPLAY ACTIVE' : 'ALIGNING FACE & SHOULDERS',
      guideText: isSyntheticDemo
        ? 'Synthetic gait & optical pulse replay active for calibration preview'
        : 'Center your full face inside the frame with both shoulders visible',
      guideTone: 'neutral'
    });

    if (!isSyntheticDemo) {
      processFrame();
    }
    startCountdownTimer();
  }

  function activateLiveUI(active) {
    if (active) {
      dom.cameraIdleState?.classList.add('hidden');
      dom.cameraErrorState?.classList.add('hidden');
      dom.cameraActiveState?.classList.remove('hidden');
      dom.hudLiveOverlay?.classList.remove('hidden');
      dom.webcam?.classList.toggle('hidden', isSyntheticDemo);
      dom.visionCanvas?.classList.remove('hidden');
      dom.movementAnalysisBanner?.classList.add('hidden');
    } else {
      dom.cameraActiveState?.classList.add('hidden');
      dom.hudLiveOverlay?.classList.add('hidden');
      dom.cameraIdleState?.classList.remove('hidden');
      dom.webcam?.classList.add('hidden');
      dom.visionCanvas?.classList.add('hidden');
      if (dom.cameraBox) dom.cameraBox.style.aspectRatio = '';
    }
  }

  function processFrame() {
    if (!isRunning || isSyntheticDemo) return;
    const canvas = dom.visionCanvas;
    const video = dom.webcam;
    if (!canvas || !video) return;
    syncCanvasToVideo();
    const ctx = canvas.getContext('2d');
    const now = performance.now();

    frameCount++;
    if (now - lastFpsCheckMs >= 1000) {
      currentFps = Math.round((frameCount * 1000) / (now - lastFpsCheckMs));
      if (dom.streamFps) dom.streamFps.textContent = currentFps + ' FPS';
      frameCount = 0;
      lastFpsCheckMs = now;
    }

    if (video.currentTime !== lastVideoTime && video.readyState >= 2) {
      lastVideoTime = video.currentTime;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      let poseNorm = null;
      let poseWorld = null;
      let faceLm = null;

      if (poseLandmarker && isModelsReady) {
        try {
          const pRes = poseLandmarker.detectForVideo(video, now);
          if (pRes && pRes.landmarks && pRes.landmarks.length > 0) poseNorm = pRes.landmarks[0];
          if (pRes && pRes.worldLandmarks && pRes.worldLandmarks.length > 0) poseWorld = pRes.worldLandmarks[0];
        } catch {
          // Ignore single frame detector hiccup
        }
      }

      if (faceLandmarker && isModelsReady) {
        try {
          const fRes = faceLandmarker.detectForVideo(video, now);
          if (fRes && fRes.faceLandmarks && fRes.faceLandmarks.length > 0) faceLm = fRes.faceLandmarks[0];
        } catch {
          // Ignore single frame detector hiccup
        }
      }

      const smoothedPoseNorm = poseNorm ? poseNormSmoother.update(poseNorm, now) : null;
      const smoothedPoseWorld = poseWorld ? poseWorldSmoother.update(poseWorld, now) : null;
      const smoothedFace = faceLm ? faceSmoother.update(faceLm, now) : null;

      const shouldersLocked = Boolean(
        smoothedPoseNorm &&
          isLandmarkVisible(smoothedPoseNorm[11], 0.45) &&
          isLandmarkVisible(smoothedPoseNorm[12], 0.45)
      );
      const faceLocked = Boolean(smoothedFace && smoothedFace[10] && smoothedFace[152]);
      const legsLocked = Boolean(
        smoothedPoseNorm &&
          isLandmarkVisible(smoothedPoseNorm[23], 0.42) &&
          isLandmarkVisible(smoothedPoseNorm[24], 0.42) &&
          isLandmarkVisible(smoothedPoseNorm[25], 0.40) &&
          isLandmarkVisible(smoothedPoseNorm[26], 0.40) &&
          isLandmarkVisible(smoothedPoseNorm[27], 0.35) &&
          isLandmarkVisible(smoothedPoseNorm[28], 0.35)
      );

      drawHudReticles(ctx, canvas.width, canvas.height, faceLocked, shouldersLocked);

      const elapsedMs = now - sessionStartMs;
      const videoAspect = video.videoWidth > 0 && video.videoHeight > 0 ? video.videoWidth / video.videoHeight : 1;
      if (smoothedPoseNorm) {
        drawPoseHud(ctx, canvas.width, canvas.height, smoothedPoseNorm, true);
        analyzePoseFrame(smoothedPoseWorld || smoothedPoseNorm, smoothedPoseNorm, elapsedMs, videoAspect, !smoothedPoseWorld);
      }
      if (smoothedFace && faceLm) {
        drawFaceHud(ctx, canvas.width, canvas.height, smoothedFace, true, isEyeClosed);
        analyzeFaceAndRppg(video, faceLm, elapsedMs);
      }

      if (faceLocked && shouldersLocked) {
        updateHudOverlay({
          lock: 'locked',
          lockText: legsLocked ? 'LOCKED · FULL BODY + FACE' : 'LOCKED · FACE + SHOULDERS',
          guideText:
            scanMode === 'Walk' && !legsLocked
              ? 'Upper body locked — step back ~1.5 m if you also want leg symmetry measured'
              : 'Tracking steady — hold natural posture for optical pulse & eye check',
          guideTone: scanMode === 'Walk' && !legsLocked ? 'neutral' : 'ok'
        });
      } else if (faceLocked || shouldersLocked) {
        updateHudOverlay({
          lock: 'partial',
          lockText: faceLocked ? 'FACE ONLY · FRAME SHOULDERS' : 'SHOULDERS ONLY · CENTER FACE',
          guideText: faceLocked
            ? 'Tilt camera slightly down or sit back so both shoulders are clearly visible'
            : 'Center your full face inside the frame for eye & pulse tracking',
          guideTone: 'warn'
        });
      } else {
        updateHudOverlay({
          lock: 'partial',
          lockText: 'SEARCHING OPTICAL LANDMARKS',
          guideText: 'Ensure good front lighting and keep your head & shoulders inside the frame',
          guideTone: 'warn'
        });
      }

      if (dom.landmarkTrackingStatus) {
        const warmupTag = elapsedMs < WARMUP_MS ? ' · Warmup' : '';
        dom.landmarkTrackingStatus.textContent =
          faceLocked || shouldersLocked ? scanMode + ' 3D Tracking Active' + warmupTag : 'Aligning Optical Landmarks...';
      }
    }

    animationFrameId = requestAnimationFrame(processFrame);
  }

  function scalePointAspect(pt, aspectRatio) {
    if (!pt || !Number.isFinite(aspectRatio) || aspectRatio === 1) return pt;
    return { x: pt.x * aspectRatio, y: pt.y, z: pt.z || 0 };
  }

  function analyzePoseFrame(worldLm, normLm, elapsedMs, videoAspect = 1, is2dFallback = false) {
    const ls = worldLm[11], rs = worldLm[12], lh = worldLm[23], rh = worldLm[24];
    const lk = worldLm[25], rk = worldLm[26], la = worldLm[27], ra = worldLm[28];
    const nose = normLm[0], lsNorm = normLm[11], rsNorm = normLm[12];
    const shouldersOk = isLandmarkVisible(lsNorm, 0.45) && isLandmarkVisible(rsNorm, 0.45);
    if (!ls || !rs || !shouldersOk) {
      setBadge(dom.badgePosture, 'Frame Shoulders', 'caution');
      return;
    }

    const aspect = Number.isFinite(videoAspect) && videoAspect > 0 ? videoAspect : 1;
    const hipsVisible = isLandmarkVisible(normLm[23], 0.42) && isLandmarkVisible(normLm[24], 0.42);
    let gated = false;
    if (hipsVisible && lh && rh) {
      gated = isYawAngleGated({
        lShoulder: lsNorm || ls,
        rShoulder: rsNorm || rs,
        lHip: normLm[23],
        rHip: normLm[24]
      }, aspect);
    } else {
      const shoulderSpanX = Math.abs((lsNorm.x || 0) - (rsNorm.x || 0)) * aspect;
      gated = shoulderSpanX < 0.09;
    }

    if (gated) {
      setBadge(dom.badgePosture, 'Face Camera', 'caution');
      setBadge(dom.badgeJoint, 'Yaw Turn Gated', 'caution');
      return;
    }

    // Use normalized shoulder slope when seated upper-body only, or 3D world when full torso is locked
    const use2dTilt = is2dFallback || !hipsVisible;
    const refLs = use2dTilt ? lsNorm : ls;
    const refRs = use2dTilt ? rsNorm : rs;
    const dx = (refRs.x - refLs.x) * (use2dTilt ? aspect : 1);
    const dy = refRs.y - refLs.y;
    const coronalTiltDeg = Math.abs((Math.atan2(dy, Math.max(Math.abs(dx), 0.05)) * 180) / Math.PI);
    const midShoulderNormX = (lsNorm.x + rsNorm.x) / 2;
    const headOffsetDeg = nose && isLandmarkVisible(nose, 0.4) ? Math.abs(nose.x - midShoulderNormX) * aspect * 24 : 0;

    const rawPosture = evaluateUprightPostureScore({ coronalTiltDeg, headOffsetDeg, centerX: midShoulderNormX });
    const posture = smoothers.posture.update(rawPosture);
    const tilt = smoothers.tilt.update(coronalTiltDeg);

    if (dom.valPosture) dom.valPosture.textContent = posture.toFixed(1);
    if (dom.valCoronalTilt) dom.valCoronalTilt.textContent = tilt.toFixed(1) + '°';
    if (dom.valSway) dom.valSway.textContent = headOffsetDeg.toFixed(1) + '°';
    setBadge(dom.badgePosture, posture >= 85 ? 'Nominal' : posture >= 72 ? 'Moderate Drift' : 'Imbalanced', posture >= 85 ? 'nominal' : posture >= 72 ? 'caution' : 'critical');

    // 3D Knee ROM Tracking (honest gating when lower body is out of frame)
    const legsVisible =
      hipsVisible &&
      lh && rh && lk && rk && la && ra &&
      isLandmarkVisible(normLm[25], 0.40) &&
      isLandmarkVisible(normLm[26], 0.40) &&
      isLandmarkVisible(normLm[27], 0.35) &&
      isLandmarkVisible(normLm[28], 0.35);

    if (legsVisible) {
      let symCoeff = 0.96;
      let deltaDeg = 1.2;
      let symLabel = 'Balanced';
      const jointScale = is2dFallback ? aspect : 1;
      const lKnee = calculateAngle3D(scalePointAspect(lh, jointScale), scalePointAspect(lk, jointScale), scalePointAspect(la, jointScale));
      const rKnee = calculateAngle3D(scalePointAspect(rh, jointScale), scalePointAspect(rk, jointScale), scalePointAspect(ra, jointScale));
      const avgKnee = (lKnee + rKnee) / 2;
      if (avgKnee < 122 && squatState === 'UP') squatState = 'DOWN';
      else if (avgKnee > 154 && squatState === 'DOWN') {
        squatState = 'UP';
        squatReps++;
        if (dom.squatCountVal) dom.squatCountVal.textContent = String(squatReps);
      }
      if (dom.valRepsCount) dom.valRepsCount.textContent = squatReps + ' reps';

      gaitTracker.pushSample(elapsedMs, lKnee, rKnee);
      if (scanMode === 'Walk') {
        const res = gaitTracker.evaluate(elapsedMs);
        if (Number.isFinite(res.symmetryCoeff)) {
          symCoeff = res.symmetryCoeff;
          deltaDeg = res.romDiffDeg;
          symLabel = res.status;
        }
      } else {
        const diff = Math.abs(lKnee - rKnee);
        deltaDeg = diff;
        symCoeff = Math.max(0.62, Math.min(0.99, 1.0 - (diff / 180) * 0.45));
        symLabel = symCoeff >= 0.90 ? 'Balanced' : symCoeff >= 0.78 ? 'Moderate Asym' : 'Asymmetric';
      }

      if (dom.valJoint) dom.valJoint.textContent = Math.round(symCoeff * 100) + '%';
      if (dom.valJointDelta) dom.valJointDelta.textContent = '±' + deltaDeg.toFixed(1) + '°';
      setBadge(dom.badgeJoint, symLabel, symCoeff >= 0.90 ? 'nominal' : symCoeff >= 0.78 ? 'caution' : 'critical');

      if (elapsedMs >= WARMUP_MS) {
        sessionSamples.symmetryCoeffs.push(symCoeff);
        sessionSamples.jointDeltas.push(deltaDeg);
      }
    } else {
      if (dom.valJoint) dom.valJoint.textContent = '--';
      if (dom.valJointDelta) dom.valJointDelta.textContent = '±--°';
      if (dom.valRepsCount) dom.valRepsCount.textContent = 'Upper Body Only';
      setBadge(dom.badgeJoint, 'Step Back (Legs)', 'ghost');
    }

    if (elapsedMs >= WARMUP_MS) {
      sessionSamples.postureScores.push(posture);
      sessionSamples.coronalTilts.push(tilt);
    }
  }

  function earFromSix(pts, aspectRatio = 1) {
    if (!pts || pts.some((p) => !p)) return NaN;
    const aspect = Number.isFinite(aspectRatio) && aspectRatio > 0 ? aspectRatio : 1;
    const dist = (a, b) => Math.hypot((a.x - b.x) * aspect, a.y - b.y);
    const v1 = dist(pts[1], pts[5]);
    const v2 = dist(pts[2], pts[4]);
    const h = Math.max(dist(pts[0], pts[3]), 1e-5);
    return (v1 + v2) / (2 * h);
  }

  function analyzeFaceAndRppg(video, faceLm, elapsedMs) {
    trackedFaceFrames++;
    const aspect = video && video.videoWidth > 0 && video.videoHeight > 0 ? video.videoWidth / video.videoHeight : 1;
    const leftPts = [faceLm[33], faceLm[160], faceLm[158], faceLm[133], faceLm[153], faceLm[144]];
    const rightPts = [faceLm[362], faceLm[385], faceLm[387], faceLm[263], faceLm[373], faceLm[380]];
    const noseTip = faceLm[1], forehead = faceLm[10], chin = faceLm[152];
    const pitchDeg = noseTip && forehead && chin ? ((noseTip.y - (forehead.y + chin.y) / 2) / Math.max(chin.y - forehead.y, 0.1)) * 45 : 0;

    const rawEar = (earFromSix(leftPts, aspect) + earFromSix(rightPts, aspect)) / 2;
    const pitchEar = computePitchAwareEar(rawEar, pitchDeg);
    const smoothedEar = smoothers.ear.update(pitchEar);

    if (Number.isFinite(smoothedEar)) {
      if (smoothedEar < 0.19) {
        closedFramesCount++;
        if (!isEyeClosed) isEyeClosed = true;
      } else if (isEyeClosed) {
        blinkCount++;
        isEyeClosed = false;
      }
      const perclos = trackedFaceFrames > 10 ? closedFramesCount / trackedFaceFrames : 0;
      const fatigued = perclos > 0.22 || smoothedEar < 0.20;
      if (dom.valEar) dom.valEar.textContent = smoothedEar.toFixed(2);
      if (dom.valFatigue) dom.valFatigue.textContent = fatigued ? 'Elevated Fatigue' : 'Alert';
      if (dom.valBlinkStatus) dom.valBlinkStatus.textContent = blinkCount + ' blinks';
      setBadge(dom.badgeFatigue, fatigued ? 'Fatigue Risk' : 'Nominal', fatigued ? 'caution' : 'nominal');

      if (elapsedMs >= WARMUP_MS) {
        sessionSamples.earValues.push(smoothedEar);
      }
    }

    // Forehead ROI sampling for CHROM optical rPPG (wide skin patch excluding specular highlights/shadows)
    const fhTop = faceLm[10], lTemple = faceLm[103], rTemple = faceLm[332], fhMid = faceLm[151];
    if (fhTop && lTemple && rTemple && video.videoWidth > 0) {
      const ox = offscreenCanvas.getContext('2d', { willReadFrequently: true });
      const ow = offscreenCanvas.width;
      const oh = offscreenCanvas.height;
      ox.drawImage(video, 0, 0, ow, oh);
      const minXFrac = Math.min(lTemple.x, rTemple.x);
      const maxXFrac = Math.max(lTemple.x, rTemple.x);
      const roiW = Math.max(10, Math.round((maxXFrac - minXFrac) * 0.55 * ow));
      const roiX = Math.max(2, Math.min(ow - roiW - 2, Math.round(((minXFrac + maxXFrac) * 0.5) * ow - roiW * 0.5)));
      const anchorY = fhMid ? fhMid.y : fhTop.y + 0.035;
      const roiH = Math.max(8, Math.round(oh * 0.08));
      const roiY = Math.max(2, Math.min(oh - roiH - 2, Math.round(anchorY * oh - roiH * 0.5)));
      const imgData = ox.getImageData(roiX, roiY, roiW, roiH).data;
      let r = 0, g = 0, b = 0, count = 0;
      let fR = 0, fG = 0, fB = 0, fCount = imgData.length / 4;
      for (let i = 0; i < imgData.length; i += 4) {
        const pr = imgData[i], pg = imgData[i + 1], pb = imgData[i + 2];
        fR += pr; fG += pg; fB += pb;
        if (pr > 40 && pg > 30 && pb > 20 && pr < 248 && pg < 248 && pb < 248) {
          r += pr;
          g += pg;
          b += pb;
          count++;
        }
      }
      const denom = count >= 8 ? count : Math.max(1, fCount);
      const useR = count >= 8 ? r : fR;
      const useG = count >= 8 ? g : fG;
      const useB = count >= 8 ? b : fB;
      rppgSamples.push({ t: elapsedMs, r: useR / denom, g: useG / denom, b: useB / denom });
      if (rppgSamples.length > 360) rppgSamples.shift();

      if (rppgSamples.length >= 90 && rppgSamples.length % 15 === 0) {
        const chrom = computeChromBpm(rppgSamples, currentFps);
        updateRppgHud(chrom);
      }
    }

    // Whole-face true-square mirrored portrait capture for Crew Visor once face is well framed
    if (!faceCapturedForSession && elapsedMs >= 1600 && video.videoWidth > 0 && video.videoHeight > 0) {
      const vw = video.videoWidth;
      const vh = video.videoHeight;
      let minX = 1, maxX = 0, minY = 1, maxY = 0;
      for (const p of faceLm) {
        if (!p) continue;
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
      }
      const faceW = (maxX - minX) * vw;
      const faceH = (maxY - minY) * vh;
      const wellFramed = minX > 0.03 && maxX < 0.97 && minY > 0.03 && maxY < 0.97 && faceW >= 55;
      if (wellFramed) {
        const cropSize = Math.min(Math.min(vw, vh), Math.max(faceW * 1.65, faceH * 1.48));
        const cx = ((minX + maxX) * 0.5) * vw;
        // Bias slightly upward so hair/crown and chin both fit inside circular visor
        const cy = (minY + (maxY - minY) * 0.43) * vh;
        const sx = Math.max(0, Math.min(vw - cropSize, cx - cropSize * 0.5));
        const sy = Math.max(0, Math.min(vh - cropSize, cy - cropSize * 0.5));

        const pCtx = portraitCanvas.getContext('2d');
        pCtx.save();
        pCtx.clearRect(0, 0, portraitCanvas.width, portraitCanvas.height);
        pCtx.translate(portraitCanvas.width, 0);
        pCtx.scale(-1, 1);
        pCtx.drawImage(video, sx, sy, cropSize, cropSize, 0, 0, portraitCanvas.width, portraitCanvas.height);
        pCtx.restore();
        try {
          const dataUrl = portraitCanvas.toDataURL('image/jpeg', 0.88);
          faceCapturedForSession = true;
          if (global.BioShell) global.BioShell.saveFacePortrait(dataUrl);
          if (dom.hologramVisorImg) dom.hologramVisorImg.setAttribute('href', dataUrl);
          if (dom.retakeVisorBtn) dom.retakeVisorBtn.classList.remove('hidden');
          document.dispatchEvent(new CustomEvent('bio:visor-captured', { detail: { dataUrl } }));
        } catch {
          // Ignore tainted canvas errors
        }
      }
    }
  }

  function updateRppgHud(chrom) {
    if (!chrom) return;
    const valid = Number.isFinite(chrom.bpm) && chrom.sqiPct >= 50;
    let stableBpm = chrom.bpm;
    if (valid) {
      opticalBpmWindow.push(chrom.bpm);
      if (opticalBpmWindow.length > 5) opticalBpmWindow.shift();
      const sorted = opticalBpmWindow.slice().sort((a, b) => a - b);
      stableBpm = sorted[Math.floor(sorted.length / 2)];
    }
    if (dom.valOpticalHr) {
      dom.valOpticalHr.textContent = valid ? stableBpm + ' BPM' : '-- BPM';
    }
    if (dom.badgeOpticalSqi) {
      setBadge(dom.badgeOpticalSqi, 'SQI ' + (chrom.sqiPct || 0) + '%', valid ? 'nominal' : 'caution');
    }
    if (dom.applyOpticalHrBtn) {
      dom.applyOpticalHrBtn.disabled = !valid;
      dom.applyOpticalHrBtn.dataset.opticalBpm = valid ? String(stableBpm) : '';
    }
    if (valid) {
      sessionSamples.opticalBpms.push(stableBpm);
      sessionSamples.opticalSqis.push(chrom.sqiPct);
    }
    drawPulseWaveform(chrom.waveform || [], chrom.sqiPct || 0, valid);
  }

  function drawPulseWaveform(wave, sqiPct = 0, isLocked = false) {
    const canvas = dom.rppgWaveCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!wave || wave.length < 6) return;

    if (!isLocked) {
      // Honest flat dashed baseline while waiting for high-SNR cardiac lock (never masquerade noise as pulse)
      ctx.save();
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(198, 139, 44, 0.55)';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.4;
      ctx.moveTo(0, h * 0.5);
      ctx.lineTo(w, h * 0.5);
      ctx.stroke();
      ctx.restore();
      return;
    }

    let min = Infinity, max = -Infinity;
    for (const v of wave) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
    const span = Math.max(max - min, 1e-5);
    const padY = 5;
    const usableH = Math.max(4, h - padY * 2);
    const pts = wave.map((v, i) => ({
      x: (i / (wave.length - 1)) * w,
      y: h - padY - ((v - min) / span) * usableH
    }));

    ctx.beginPath();
    ctx.strokeStyle = '#38B07B';
    ctx.lineWidth = 1.85;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i].x + pts[i + 1].x) * 0.5;
      const my = (pts[i].y + pts[i + 1].y) * 0.5;
      ctx.quadraticCurveTo(pts[i].x, pts[i].y, mx, my);
    }
    const last = pts[pts.length - 1];
    ctx.lineTo(last.x, last.y);
    ctx.stroke();
  }

  const FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
  ];
  const LEFT_EYE_RING = [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7];
  const RIGHT_EYE_RING = [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382];
  const LEFT_BROW_ARC = [70, 63, 105, 66, 107];
  const RIGHT_BROW_ARC = [336, 296, 334, 293, 300];

  function toHudPt(pt, w, h, mirrorX = true) {
    if (!pt) return null;
    return {
      x: (mirrorX ? 1 - pt.x : pt.x) * w,
      y: pt.y * h
    };
  }

  function strokeLandmarkPath(ctx, lm, indices, w, h, mirrorX, closed) {
    let started = false;
    ctx.beginPath();
    for (const idx of indices) {
      const p = toHudPt(lm[idx], w, h, mirrorX);
      if (!p) continue;
      if (!started) {
        ctx.moveTo(p.x, p.y);
        started = true;
      } else {
        ctx.lineTo(p.x, p.y);
      }
    }
    if (started && closed) ctx.closePath();
    if (started) ctx.stroke();
  }

  function drawHudReticles(ctx, w, h, faceLocked, shouldersLocked) {
    ctx.save();
    const pad = Math.round(Math.min(w, h) * 0.035);
    const arm = Math.round(Math.min(w, h) * 0.055);
    const color = faceLocked && shouldersLocked ? 'rgba(56, 176, 123, 0.58)' : 'rgba(232, 155, 60, 0.45)';
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.8;

    const corners = [
      [pad, pad, 1, 1],
      [w - pad, pad, -1, 1],
      [pad, h - pad, 1, -1],
      [w - pad, h - pad, -1, -1]
    ];
    ctx.beginPath();
    for (const [cx, cy, dx, dy] of corners) {
      ctx.moveTo(cx, cy + dy * arm);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx + dx * arm, cy);
    }
    ctx.stroke();

    // Subtle center horizon reference tick
    ctx.strokeStyle = 'rgba(234, 229, 218, 0.14)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w * 0.5 - 10, h * 0.5);
    ctx.lineTo(w * 0.5 + 10, h * 0.5);
    ctx.moveTo(w * 0.5, h * 0.5 - 10);
    ctx.lineTo(w * 0.5, h * 0.5 + 10);
    ctx.stroke();
    ctx.restore();
  }

  function drawJointReticle(ctx, x, y, radius, ringColor, coreColor) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, radius + 3.5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(11, 14, 19, 0.55)';
    ctx.fill();
    ctx.lineWidth = 1.6;
    ctx.strokeStyle = ringColor;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(x, y, radius * 0.65, 0, Math.PI * 2);
    ctx.fillStyle = coreColor;
    ctx.fill();
    ctx.restore();
  }

  function drawPoseHud(ctx, w, h, lm, mirrorX = true) {
    const pairs = [
      [11, 23], [12, 24], [23, 24],
      [11, 13], [13, 15], [12, 14], [14, 16],
      [23, 25], [25, 27], [24, 26], [26, 28]
    ];
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Secondary torso/limb skeleton (strictly gated by landmark visibility)
    ctx.strokeStyle = 'rgba(56, 176, 123, 0.82)';
    ctx.lineWidth = Math.max(2, w * 0.0024);
    ctx.beginPath();
    for (const [a, b] of pairs) {
      if (isLandmarkVisible(lm[a], 0.45) && isLandmarkVisible(lm[b], 0.45)) {
        const pa = toHudPt(lm[a], w, h, mirrorX);
        const pb = toHudPt(lm[b], w, h, mirrorX);
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
      }
    }
    ctx.stroke();

    // Primary stabilized Shoulder Axis Lock Bar + Neck-to-Midpoint Plumb Line
    if (isLandmarkVisible(lm[11], 0.45) && isLandmarkVisible(lm[12], 0.45)) {
      const pL = toHudPt(lm[11], w, h, mirrorX);
      const pR = toHudPt(lm[12], w, h, mirrorX);
      const midX = (pL.x + pR.x) * 0.5;
      const midY = (pL.y + pR.y) * 0.5;

      // Soft emerald halo behind shoulder axis
      ctx.strokeStyle = 'rgba(56, 176, 123, 0.24)';
      ctx.lineWidth = Math.max(7, w * 0.008);
      ctx.beginPath();
      ctx.moveTo(pL.x, pL.y);
      ctx.lineTo(pR.x, pR.y);
      ctx.stroke();

      // Crisp shoulder axis vector
      ctx.strokeStyle = '#4CE09D';
      ctx.lineWidth = Math.max(2.6, w * 0.003);
      ctx.beginPath();
      ctx.moveTo(pL.x, pL.y);
      ctx.lineTo(pR.x, pR.y);
      ctx.stroke();

      // Horizontal level reference tick at shoulder midpoint
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = 'rgba(234, 229, 218, 0.32)';
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.moveTo(midX - Math.abs(pR.x - pL.x) * 0.38, midY);
      ctx.lineTo(midX + Math.abs(pR.x - pL.x) * 0.38, midY);
      ctx.stroke();
      ctx.restore();

      // Neck/head plumb connector
      if (isLandmarkVisible(lm[0], 0.4)) {
        const pNose = toHudPt(lm[0], w, h, mirrorX);
        ctx.save();
        ctx.setLineDash([3, 4]);
        ctx.strokeStyle = 'rgba(234, 229, 218, 0.35)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(midX, midY);
        ctx.lineTo(pNose.x, pNose.y);
        ctx.stroke();
        ctx.restore();
      }

      drawJointReticle(ctx, pL.x, pL.y, 5.5, '#4CE09D', '#EAE5DA');
      drawJointReticle(ctx, pR.x, pR.y, 5.5, '#4CE09D', '#EAE5DA');
      drawJointReticle(ctx, midX, midY, 3.2, '#4CE09D', '#38B07B');
    }

    // Secondary visible joints (elbows, wrists, hips, knees)
    [13, 14, 23, 24, 25, 26].forEach((idx) => {
      if (isLandmarkVisible(lm[idx], 0.45)) {
        const p = toHudPt(lm[idx], w, h, mirrorX);
        drawJointReticle(ctx, p.x, p.y, 3.8, '#E77C5D', '#EAE5DA');
      }
    });
    ctx.restore();
  }

  function drawFaceHud(ctx, w, h, face, mirrorX = true, eyeClosed = false) {
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Complete 36-point face perimeter oval
    ctx.strokeStyle = 'rgba(56, 176, 123, 0.55)';
    ctx.lineWidth = 1.5;
    strokeLandmarkPath(ctx, face, FACE_OVAL_INDICES, w, h, mirrorX, true);

    // Eyebrow arcs
    ctx.strokeStyle = 'rgba(234, 229, 218, 0.38)';
    ctx.lineWidth = 1.1;
    strokeLandmarkPath(ctx, face, LEFT_BROW_ARC, w, h, mirrorX, false);
    strokeLandmarkPath(ctx, face, RIGHT_BROW_ARC, w, h, mirrorX, false);

    // Eye aperture contours (emerald when alert, amber on blink/closure)
    ctx.strokeStyle = eyeClosed ? '#E89B3C' : '#6CE2AC';
    ctx.lineWidth = 1.65;
    strokeLandmarkPath(ctx, face, LEFT_EYE_RING, w, h, mirrorX, true);
    strokeLandmarkPath(ctx, face, RIGHT_EYE_RING, w, h, mirrorX, true);

    // Forehead rPPG Sampling Patch ROI box
    const fhTop = face[10], lTemple = face[103], rTemple = face[332], fhMid = face[151];
    if (fhTop && lTemple && rTemple) {
      const pL = toHudPt(lTemple, w, h, mirrorX);
      const pR = toHudPt(rTemple, w, h, mirrorX);
      const pMid = toHudPt(fhMid || fhTop, w, h, mirrorX);
      const roiW = Math.max(24, Math.abs(pR.x - pL.x) * 0.55);
      const roiH = Math.max(14, h * 0.065);
      const rx = (pL.x + pR.x) * 0.5 - roiW * 0.5;
      const ry = pMid.y - roiH * 0.5;

      ctx.save();
      ctx.fillStyle = 'rgba(56, 176, 123, 0.10)';
      ctx.fillRect(rx, ry, roiW, roiH);
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = 'rgba(108, 226, 172, 0.78)';
      ctx.lineWidth = 1.1;
      ctx.strokeRect(rx, ry, roiW, roiH);
      ctx.font = '600 10px monospace';
      ctx.fillStyle = '#A6F0CC';
      ctx.fillText('rPPG ROI', rx + 3, Math.max(12, ry - 4));
      ctx.restore();
    }
    ctx.restore();
  }

  // Explicit opt-in Synthetic Calibration Replay Demo (never automatic on camera fail)
  function startCalibrationReplayDemo() {
    cacheDom();
    isSyntheticDemo = true;
    beginTrackingLoop();
    if (dom.landmarkTrackingStatus) {
      dom.landmarkTrackingStatus.textContent = 'SYNTHETIC CALIBRATION REPLAY (' + scanMode + ' · Demo Only)';
    }

    let tick = 0;
    const canvas = dom.visionCanvas;
    const ctx = canvas ? canvas.getContext('2d') : null;
    if (simIntervalId) clearInterval(simIntervalId);

    simIntervalId = setInterval(() => {
      if (!isRunning || !isSyntheticDemo) {
        clearInterval(simIntervalId);
        return;
      }
      tick++;
      const elapsedMs = tick * 66;
      const gaitPhase = (elapsedMs / 1000) * Math.PI * 2;
      const lKnee = 148 + 26 * Math.sin(gaitPhase);
      const rKnee = 148 + 26 * Math.sin(gaitPhase + Math.PI);
      gaitTracker.pushSample(elapsedMs, lKnee, rKnee);

      const synthPosture = evaluateUprightPostureScore({ coronalTiltDeg: 1.4 + 0.3 * Math.sin(tick * 0.1), headOffsetDeg: 1.6, centerX: 0.5 + 0.15 * Math.sin(tick * 0.05) });
      const symRes = scanMode === 'Walk' ? gaitTracker.evaluate(elapsedMs) : { romDiffDeg: 1.2, symmetryCoeff: 0.96, status: 'Balanced' };
      const ear = 0.31 + 0.02 * Math.sin(tick * 0.18);

      rppgSamples.push({
        t: elapsedMs,
        r: 182 + 0.9 * Math.sin(2 * Math.PI * 1.15 * (elapsedMs / 1000)),
        g: 138 - 1.9 * Math.sin(2 * Math.PI * 1.15 * (elapsedMs / 1000)),
        b: 118 - 0.3 * Math.sin(2 * Math.PI * 1.15 * (elapsedMs / 1000))
      });
      if (rppgSamples.length > 240) rppgSamples.shift();
      if (rppgSamples.length >= 90 && tick % 10 === 0) {
        updateRppgHud(computeChromBpm(rppgSamples, 15));
      }

      if (dom.valPosture) dom.valPosture.textContent = synthPosture.toFixed(1);
      if (dom.valCoronalTilt) dom.valCoronalTilt.textContent = '1.4°';
      if (dom.valSway) dom.valSway.textContent = '1.6°';
      setBadge(dom.badgePosture, 'Nominal (Demo)', 'nominal');

      const symVal = Number.isFinite(symRes.symmetryCoeff) ? symRes.symmetryCoeff : 0.96;
      const deltaVal = Number.isFinite(symRes.romDiffDeg) ? symRes.romDiffDeg : 1.2;
      if (dom.valJoint) dom.valJoint.textContent = Math.round(symVal * 100) + '%';
      if (dom.valJointDelta) dom.valJointDelta.textContent = '±' + deltaVal.toFixed(1) + '°';
      setBadge(dom.badgeJoint, 'Balanced (Demo)', 'nominal');

      if (dom.valEar) dom.valEar.textContent = ear.toFixed(2);
      if (dom.valFatigue) dom.valFatigue.textContent = 'Alert (Demo)';
      if (dom.valBlinkStatus) dom.valBlinkStatus.textContent = Math.floor(tick / 30) + ' blinks';
      setBadge(dom.badgeFatigue, 'Nominal (Demo)', 'nominal');
      currentFps = 15;
      if (dom.streamFps) dom.streamFps.textContent = '15 FPS';
      updateHudOverlay({
        lock: 'locked',
        lockText: 'CALIBRATION DEMO · FULL BODY',
        guideText: 'Synthetic telemetry replay active (demo mode only — not live camera data)',
        guideTone: 'ok'
      });

      if (elapsedMs >= WARMUP_MS) {
        sessionSamples.postureScores.push(synthPosture);
        sessionSamples.coronalTilts.push(1.4);
        sessionSamples.symmetryCoeffs.push(symVal);
        sessionSamples.jointDeltas.push(deltaVal);
        sessionSamples.earValues.push(ear);
      }

      if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawHudReticles(ctx, canvas.width, canvas.height, true, true);
        const cx = canvas.width * (0.5 + 0.12 * Math.sin(tick * 0.04));
        const bob = Math.sin(gaitPhase) * 7;
        const shY = canvas.height * 0.30 + bob;
        const hipY = canvas.height * 0.56 + bob;
        const kneeY = canvas.height * 0.71 + bob * 0.5;
        const footY = canvas.height * 0.85;
        const lFootX = cx - 44 + Math.sin(gaitPhase) * 26;
        const rFootX = cx + 44 - Math.sin(gaitPhase) * 26;
        const lKneeX = cx - 42 + Math.sin(gaitPhase) * 14;
        const rKneeX = cx + 42 - Math.sin(gaitPhase) * 14;

        ctx.strokeStyle = 'rgba(56, 176, 123, 0.82)';
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        // Torso & hips
        ctx.moveTo(cx, shY);
        ctx.lineTo(cx, hipY);
        ctx.moveTo(cx - 44, hipY);
        ctx.lineTo(cx + 44, hipY);
        // Arms
        ctx.moveTo(cx - 68, shY);
        ctx.lineTo(cx - 82, shY + 66);
        ctx.lineTo(cx - 78 - Math.sin(gaitPhase) * 16, shY + 126);
        ctx.moveTo(cx + 68, shY);
        ctx.lineTo(cx + 82, shY + 66);
        ctx.lineTo(cx + 78 + Math.sin(gaitPhase) * 16, shY + 126);
        // Legs with knees
        ctx.moveTo(cx - 44, hipY);
        ctx.lineTo(lKneeX, kneeY);
        ctx.lineTo(lFootX, footY);
        ctx.moveTo(cx + 44, hipY);
        ctx.lineTo(rKneeX, kneeY);
        ctx.lineTo(rFootX, footY);
        ctx.stroke();

        // Stabilized demo shoulder bar
        ctx.strokeStyle = 'rgba(56, 176, 123, 0.24)';
        ctx.lineWidth = 8;
        ctx.beginPath();
        ctx.moveTo(cx - 68, shY);
        ctx.lineTo(cx + 68, shY);
        ctx.stroke();

        ctx.strokeStyle = '#4CE09D';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(cx - 68, shY);
        ctx.lineTo(cx + 68, shY);
        ctx.stroke();

        drawJointReticle(ctx, cx - 68, shY, 5.5, '#4CE09D', '#EAE5DA');
        drawJointReticle(ctx, cx + 68, shY, 5.5, '#4CE09D', '#EAE5DA');
        drawJointReticle(ctx, cx - 44, hipY, 3.8, '#E77C5D', '#EAE5DA');
        drawJointReticle(ctx, cx + 44, hipY, 3.8, '#E77C5D', '#EAE5DA');
        drawJointReticle(ctx, lKneeX, kneeY, 3.6, '#E77C5D', '#EAE5DA');
        drawJointReticle(ctx, rKneeX, kneeY, 3.6, '#E77C5D', '#EAE5DA');

        // Head oval + eye ticks
        ctx.strokeStyle = 'rgba(108, 226, 172, 0.78)';
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.ellipse(cx, shY - 56, 28, 36, 0, 0, Math.PI * 2);
        ctx.stroke();
        drawJointReticle(ctx, cx - 10, shY - 60, 2.2, '#6CE2AC', '#EAE5DA');
        drawJointReticle(ctx, cx + 10, shY - 60, 2.2, '#6CE2AC', '#EAE5DA');
      }
    }, 66);
  }

  function startCountdownTimer() {
    if (sessionTimerId) clearInterval(sessionTimerId);
    countdownRemaining = scanDurationSec;
    updateCountdownUI(countdownRemaining);
    sessionTimerId = setInterval(() => {
      if (!isRunning) {
        clearInterval(sessionTimerId);
        return;
      }
      countdownRemaining--;
      updateCountdownUI(countdownRemaining);
      if (countdownRemaining <= 0) {
        finishAndAnalyzeMotion();
      }
    }, 1000);
  }

  function updateCountdownUI(sec) {
    if (dom.countdownTimer) {
      const m = String(Math.floor(Math.max(0, sec) / 60)).padStart(2, '0');
      const s = String(Math.max(0, sec) % 60).padStart(2, '0');
      dom.countdownTimer.textContent = m + ':' + s;
    }
    if (dom.countdownProgressBar) {
      const pct = ((scanDurationSec - Math.max(0, sec)) / Math.max(1, scanDurationSec)) * 100;
      dom.countdownProgressBar.style.width = pct + '%';
    }
  }

  function finishAndAnalyzeMotion() {
    stopCameraStream();
    const avgPosture = trimmedMean(sessionSamples.postureScores, 0.10);
    const avgSym = trimmedMean(sessionSamples.symmetryCoeffs, 0.10);
    const avgDelta = trimmedMean(sessionSamples.jointDeltas, 0.10);
    const avgEar = trimmedMean(sessionSamples.earValues, 0.10);
    const avgOpticalHr = trimmedMean(sessionSamples.opticalBpms, 0.10);
    const avgSqi = trimmedMean(sessionSamples.opticalSqis, 0.10);

    const symDiffDeg = Number.isFinite(avgDelta)
      ? Number(avgDelta.toFixed(2))
      : Number.isFinite(avgSym)
      ? Number(Math.max(0, Math.min(45, (1.0 - avgSym) * 180 / 0.45)).toFixed(2))
      : NaN;

    latestSummary = {
      balance_score: Number.isFinite(avgPosture) ? Number(avgPosture.toFixed(1)) : NaN,
      joint_symmetry_diff: symDiffDeg,
      facial_ear: Number.isFinite(avgEar) ? Number(avgEar.toFixed(2)) : NaN,
      posture_score: Number.isFinite(avgPosture) ? Number(avgPosture.toFixed(1)) : NaN,
      symmetry_coeff: Number.isFinite(avgSym) ? Number(avgSym.toFixed(2)) : NaN,
      ear_fatigue: Number.isFinite(avgEar) ? Number(avgEar.toFixed(2)) : NaN,
      heart_rate_optical: Number.isFinite(avgOpticalHr) ? Math.round(avgOpticalHr) : NaN,
      sqi_pct: Number.isFinite(avgSqi) ? Math.round(avgSqi) : 0,
      isSynthetic: isSyntheticDemo
    };

    if (dom.valPosture) dom.valPosture.textContent = Number.isFinite(latestSummary.balance_score) ? latestSummary.balance_score.toFixed(1) : '--';
    if (dom.valJoint) dom.valJoint.textContent = Number.isFinite(latestSummary.symmetry_coeff) ? Math.round(latestSummary.symmetry_coeff * 100) + '%' : '--';
    if (dom.valJointDelta) dom.valJointDelta.textContent = Number.isFinite(latestSummary.joint_symmetry_diff) ? '±' + latestSummary.joint_symmetry_diff.toFixed(1) + '°' : '±--°';
    if (dom.valEar) dom.valEar.textContent = Number.isFinite(latestSummary.facial_ear) ? latestSummary.facial_ear.toFixed(2) : '--';

    if (dom.movementAnalysisBanner) {
      dom.movementAnalysisBanner.classList.remove('hidden');
      const esc = global.BioShell ? global.BioShell.escapeHtml : (s) => String(s);
      dom.movementAnalysisBanner.innerHTML =
        '<strong>' + esc(isSyntheticDemo ? 'Synthetic Calibration Summary' : 'Camera Biomechanics Summary') + ':</strong> ' +
        'Posture ' + (Number.isFinite(latestSummary.posture_score) ? latestSummary.posture_score : 'NaN') +
        ' · Symmetry ' + (Number.isFinite(latestSummary.symmetry_coeff) ? latestSummary.symmetry_coeff : 'NaN') +
        ' · EAR ' + (Number.isFinite(latestSummary.ear_fatigue) ? latestSummary.ear_fatigue : 'NaN');
    }

    document.dispatchEvent(new CustomEvent('bio:vision-complete', { detail: latestSummary }));
    return latestSummary;
  }

  function stopCameraStream() {
    isRunning = false;
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    if (simIntervalId) clearInterval(simIntervalId);
    if (sessionTimerId) clearInterval(sessionTimerId);
    if (videoStream) {
      videoStream.getTracks().forEach((t) => t.stop());
      videoStream = null;
    }
    activateLiveUI(false);
  }

  function setScanMode(mode) {
    scanMode = mode === 'Static' ? 'Static' : 'Walk';
    gaitTracker.reset();
    cacheDom();
    if (dom.scanModeWalkBtn) dom.scanModeWalkBtn.classList.toggle('active', scanMode === 'Walk');
    if (dom.scanModeStaticBtn) dom.scanModeStaticBtn.classList.toggle('active', scanMode === 'Static');
    return scanMode;
  }

  function setDuration(seconds) {
    const val = Number(seconds);
    scanDurationSec = [15, 30, 90].includes(val) ? val : 30;
    countdownRemaining = scanDurationSec;
    updateCountdownUI(scanDurationSec);
    return scanDurationSec;
  }

  function resetSessionMetrics() {
    sessionSamples.postureScores = [];
    sessionSamples.coronalTilts = [];
    sessionSamples.symmetryCoeffs = [];
    sessionSamples.jointDeltas = [];
    sessionSamples.earValues = [];
    sessionSamples.opticalBpms = [];
    sessionSamples.opticalSqis = [];
    rppgSamples.length = 0;
    opticalBpmWindow.length = 0;
    gaitTracker.reset();
    Object.values(smoothers).forEach((s) => s.reset());
    poseNormSmoother.reset();
    poseWorldSmoother.reset();
    faceSmoother.reset();
    squatReps = 0;
    squatState = 'UP';
    blinkCount = 0;
    closedFramesCount = 0;
    trackedFaceFrames = 0;
    isEyeClosed = false;
    faceCapturedForSession = false;
    countdownRemaining = scanDurationSec;
    updateCountdownUI(scanDurationSec);
  }

  function resetVisionUI() {
    cacheDom();
    stopCameraStream();
    resetSessionMetrics();
    latestSummary = { balance_score: NaN, joint_symmetry_diff: NaN, facial_ear: NaN, posture_score: NaN, symmetry_coeff: NaN, ear_fatigue: NaN, heart_rate_optical: NaN, sqi_pct: 0, isSynthetic: false };
    if (dom.valPosture) dom.valPosture.textContent = '--';
    if (dom.valCoronalTilt) dom.valCoronalTilt.textContent = '--°';
    if (dom.valSway) dom.valSway.textContent = '--°';
    if (dom.valJoint) dom.valJoint.textContent = '--';
    if (dom.valJointDelta) dom.valJointDelta.textContent = '±--°';
    if (dom.valRepsCount) dom.valRepsCount.textContent = 'Pending';
    if (dom.valEar) dom.valEar.textContent = '--';
    if (dom.valFatigue) dom.valFatigue.textContent = '--';
    if (dom.valBlinkStatus) dom.valBlinkStatus.textContent = 'Standby';
    if (dom.valOpticalHr) dom.valOpticalHr.textContent = '-- BPM';
    if (dom.rppgWaveCanvas) {
      const wCtx = dom.rppgWaveCanvas.getContext('2d');
      wCtx?.clearRect(0, 0, dom.rppgWaveCanvas.width, dom.rppgWaveCanvas.height);
    }
    setBadge(dom.badgePosture, 'Standby', 'ghost');
    setBadge(dom.badgeJoint, 'Standby', 'ghost');
    setBadge(dom.badgeFatigue, 'Standby', 'ghost');
    setBadge(dom.badgeOpticalSqi, 'SQI --%', 'ghost');
    if (dom.movementAnalysisBanner) dom.movementAnalysisBanner.classList.add('hidden');
  }

  function retakeVisorPhoto() {
    cacheDom();
    faceCapturedForSession = false;
    if (dom.visorPreviewCaption) {
      dom.visorPreviewCaption.textContent = isRunning
        ? 'Re-centering... hold steady for fresh visor capture.'
        : 'Start camera scan to capture a fresh visor portrait.';
    }
  }

  global.visionLab = {
    math: {
      calculateAngle3D,
      evaluateUprightPostureScore,
      RollingROMSymmetryTracker,
      LandmarkTrackSmoother,
      isYawAngleGated,
      earFromSix,
      trimmedMean,
      computePitchAwareEar,
      computeChromBpm
    },
    initVisionModels,
    startCamera,
    stopCameraStream,
    finishAndAnalyzeMotion,
    startCalibrationReplayDemo,
    setScanMode,
    setDuration,
    resetSessionMetrics,
    resetVisionUI,
    retakeVisorPhoto,
    getLatestSummary: () => ({ ...latestSummary })
  };
})(typeof window !== 'undefined' ? window : globalThis);
