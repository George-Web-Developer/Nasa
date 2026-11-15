/**
 * Bio Astro Lab — Stage 1 & Stage 2 Scan Workspace Controller (scan.js)
 * Connects 13-feature telemetry form, NASA presets, Inspiration4 OSDR CSV/JSON upload,
 * 3D MediaPipe webcam biomechanics, CHROM optical rPPG, and Hologram zone inspector.
 */
(function (global) {
  'use strict';

  const appState = {
    activeStep: 1,
    lastResult: null,
    activeSystemId: 'head'
  };

  function getEl(id) {
    return document.getElementById(id);
  }

  function parseOptionalNumber(raw) {
    if (raw == null) return NaN;
    const str = String(raw).trim();
    if (!str || str.toLowerCase() === 'nan' || str === '--') return NaN;
    const n = Number(str);
    return Number.isFinite(n) ? n : NaN;
  }

  function parseBloodPressure(raw) {
    const s = String(raw == null ? '' : raw).trim();
    if (!s || s.toLowerCase() === 'nan' || s === '--') {
      return { systolic: NaN, diastolic: NaN, valid: true };
    }
    const match = s.match(/^(\d{2,3}(?:\.\d+)?)\s*\/\s*(\d{2,3}(?:\.\d+)?)$/);
    if (!match) return { systolic: NaN, diastolic: NaN, valid: false };
    const sys = Number(match[1]);
    const dia = Number(match[2]);
    const ok = sys >= 60 && sys <= 240 && dia >= 35 && dia <= 150 && sys > dia;
    return { systolic: ok ? sys : NaN, diastolic: ok ? dia : NaN, valid: ok };
  }

  function mapMoodToScore(val) {
    if (typeof val === 'number') {
      return Number.isFinite(val) ? Math.min(4, Math.max(1, Math.round(val))) : NaN;
    }
    const s = String(val == null ? '' : val).trim();
    if (!s) return NaN;
    const num = Number(s);
    if (Number.isFinite(num) && num >= 1 && num <= 4) return Math.round(num);
    const map = { alert: 1, optimal: 1, nominal: 1, resilient: 1, great: 1, calm: 2, mild: 2, monitor: 2, fatigued: 3, tired: 3, strain: 3, stressed: 4, severe: 4, critical: 4 };
    const lower = s.toLowerCase();
    for (const [k, score] of Object.entries(map)) {
      if (lower.indexOf(k) !== -1) return score;
    }
    return NaN;
  }

  function updateEnvBanner() {
    if (!global.BioShell) return;
    const meta = global.BioShell.getEnvironmentMeta(global.BioShell.getEnvironment());
    const tEl = getEl('envBannerTitle');
    const sEl = getEl('envBannerSpecs');
    const bEl = getEl('envBannerBrief');
    if (tEl) tEl.textContent = meta.label.toUpperCase();
    if (sEl) {
      sEl.textContent =
        `${meta.gravity} · ${meta.pressurePsi} · Ref Rad ${meta.baselineRadiation} mSv/d · Ref ppCO2 ${meta.baselineCO2} mmHg`;
    }
    if (bEl) bEl.textContent = meta.brief;
  }

  function applyFeaturesToInputs(raw) {
    if (!raw) return;
    const f = global.BioShell ? global.BioShell.normalizeFeatures(raw) : raw;
    const setNum = (id, v) => {
      const el = getEl(id);
      if (el) el.value = typeof v === 'number' && Number.isFinite(v) ? String(v) : '';
    };
    setNum('inputGlucose', f.blood_glucose);
    setNum('inputTemp', f.body_temp);
    setNum('inputHeartRate', f.heart_rate_bpm);
    setNum('inputSpO2', f.spo2_pct);
    setNum('inputSleep', f.sleep_hours);
    setNum('inputRadiation', f.radiation_dose_msv);
    setNum('inputCO2', f.cabin_co2_mmhg);

    const bpEl = getEl('inputBP');
    if (bpEl) {
      bpEl.value =
        Number.isFinite(f.systolic_bp) && Number.isFinite(f.diastolic_bp)
          ? `${Math.round(f.systolic_bp)}/${Math.round(f.diastolic_bp)}`
          : '';
    }
    const moodEl = getEl('inputMood');
    if (moodEl) {
      moodEl.value = Number.isFinite(f.mood_score) ? String(Math.min(4, Math.max(1, Math.round(f.mood_score)))) : '';
    }

    refreshStage1Summary();
  }

  function extractModelFeatures() {
    const bp = parseBloodPressure((getEl('inputBP') || {}).value);
    const errEl = getEl('bpValidationError');
    if (errEl) errEl.classList.toggle('hidden', bp.valid);

    const visionSum = global.visionLab && global.visionLab.getLatestSummary ? global.visionLab.getLatestSummary() : {};

    const balance_score = Number.isFinite(visionSum.balance_score)
      ? visionSum.balance_score
      : Number.isFinite(visionSum.posture_score)
      ? visionSum.posture_score
      : NaN;

    const joint_symmetry_diff = Number.isFinite(visionSum.joint_symmetry_diff)
      ? visionSum.joint_symmetry_diff
      : NaN;

    const facial_ear = Number.isFinite(visionSum.facial_ear)
      ? visionSum.facial_ear
      : Number.isFinite(visionSum.ear_fatigue)
      ? visionSum.ear_fatigue
      : NaN;

    return {
      blood_glucose: parseOptionalNumber((getEl('inputGlucose') || {}).value),
      systolic_bp: bp.systolic,
      diastolic_bp: bp.diastolic,
      body_temp: parseOptionalNumber((getEl('inputTemp') || {}).value),
      sleep_hours: parseOptionalNumber((getEl('inputSleep') || {}).value),
      mood_score: mapMoodToScore((getEl('inputMood') || {}).value),
      balance_score,
      joint_symmetry_diff,
      facial_ear,
      heart_rate_bpm: parseOptionalNumber((getEl('inputHeartRate') || {}).value),
      spo2_pct: parseOptionalNumber((getEl('inputSpO2') || {}).value),
      radiation_dose_msv: parseOptionalNumber((getEl('inputRadiation') || {}).value),
      cabin_co2_mmhg: parseOptionalNumber((getEl('inputCO2') || {}).value)
    };
  }

  function refreshStage1Summary() {
    const f = extractModelFeatures();
    const stage1Flags = [
      Number.isFinite(f.blood_glucose),
      Number.isFinite(f.systolic_bp) && Number.isFinite(f.diastolic_bp),
      Number.isFinite(f.body_temp),
      Number.isFinite(f.heart_rate_bpm),
      Number.isFinite(f.spo2_pct),
      Number.isFinite(f.sleep_hours),
      Number.isFinite(f.mood_score),
      Number.isFinite(f.radiation_dose_msv),
      Number.isFinite(f.cabin_co2_mmhg)
    ];
    const measuredStage1 = stage1Flags.filter(Boolean).length;
    const el = getEl('stage1SummaryText');
    if (el) {
      el.textContent = `${measuredStage1} / 9 inputs measured (camera metrics run in Stage 2)`;
    }
    updateHologramTiers(f);
    return f;
  }

  function updateHologramTiers(features) {
    const f = features || extractModelFeatures();
    let contribMap = {};
    if (typeof global.evaluateAstronautHealth === 'function') {
      try {
        const res = global.evaluateAstronautHealth(f);
        appState.lastResult = res;
        (res.featureAttributions || []).forEach((c) => {
          contribMap[c.key] = c.deltaRisk || 0;
        });
      } catch {
        // Ignore preview error on empty NaN set
      }
    }

    const zoneFeatureMap = {
      head: ['facial_ear', 'sleep_hours', 'mood_score', 'cabin_co2_mmhg'],
      cardio: ['heart_rate_bpm', 'systolic_bp', 'diastolic_bp', 'spo2_pct'],
      musculoskeletal: ['balance_score', 'joint_symmetry_diff'],
      immune: ['radiation_dose_msv', 'body_temp'],
      renal: ['blood_glucose', 'cabin_co2_mmhg']
    };

    document.querySelectorAll('.holo-zone[data-system-id]').forEach((zone) => {
      const id = zone.getAttribute('data-system-id');
      const keys = zoneFeatureMap[id] || [];
      let sumDelta = 0;
      keys.forEach((k) => {
        sumDelta += Math.max(0, contribMap[k] || 0);
      });
      const tier = sumDelta >= 0.08 ? 'critical' : sumDelta >= 0.025 ? 'caution' : 'nominal';
      zone.setAttribute('data-tier', tier);
      document.querySelectorAll(`[data-holo-pill="${id}"]`).forEach((p) => p.setAttribute('data-tier', tier));
    });
  }

  function renderPresets() {
    const wrap = getEl('presetButtonsWrap');
    const presets = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.missionPresets) || [];
    if (!wrap || !global.BioShell) return;

    wrap.innerHTML = presets
      .map((p) => `<button type="button" class="preset-btn" data-preset-id="${global.BioShell.escapeHtml(p.id)}">${global.BioShell.escapeHtml(p.label)}</button>`)
      .join('');

    wrap.querySelectorAll('[data-preset-id]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const pid = btn.getAttribute('data-preset-id');
        const chosen = presets.find((p) => p.id === pid);
        if (!chosen) return;
        if (chosen.environment) {
          global.BioShell.setEnvironment(chosen.environment);
          updateEnvBanner();
        }
        applyFeaturesToInputs({
          blood_glucose: chosen.features?.blood_glucose,
          systolic_bp: chosen.features?.systolic_bp,
          diastolic_bp: chosen.features?.diastolic_bp,
          body_temp: chosen.features?.body_temp,
          heart_rate_bpm: chosen.features?.heart_rate_bpm,
          spo2_pct: chosen.features?.spo2_pct,
          sleep_hours: chosen.features?.sleep_hours,
          mood_score: chosen.features?.mood_score,
          radiation_dose_msv: chosen.features?.radiation_dose_msv,
          cabin_co2_mmhg: chosen.features?.cabin_co2_mmhg
        });
        global.BioShell.saveSession({
          environment: global.BioShell.getEnvironment(),
          features: extractModelFeatures(),
          meta: { sourcePreset: chosen.label }
        });
        global.BioShell.showToast('Loaded Stage 1 profile: ' + chosen.label, 'nominal');
      });
    });
  }

  function renderSerumRows(serumRows) {
    const sec = getEl('serumPanelSection');
    const tbody = getEl('serumTableBody');
    if (!sec || !tbody || !global.BioShell) return;
    if (!Array.isArray(serumRows) || serumRows.length === 0) {
      sec.classList.add('hidden');
      tbody.innerHTML = '';
      return;
    }

    const esc = global.BioShell.escapeHtml;
    const fmt = (n) => (typeof n === 'number' && Number.isFinite(n) ? String(n) : '--');
    tbody.innerHTML = serumRows
      .slice(0, 12)
      .map(
        (r) => `<tr>
          <td><strong>${esc(r.subject || '--')}</strong></td>
          <td>${esc(r.mission_phase || '--')}</td>
          <td class="mono-num">${fmt(r.glucose_mg_dl)}</td>
          <td class="mono-num">${fmt(r.albumin_g_dl)}</td>
          <td class="mono-num">${fmt(r.hemoglobin_g_dl)}</td>
          <td class="mono-num">${fmt(r.wbc_10e3_ul)}</td>
          <td class="mono-num">${fmt(r.crp_mg_l)}</td>
        </tr>`
      )
      .join('');
    sec.classList.remove('hidden');
  }

  function ingestUploadedText(filename, rawText) {
    if (!global.BioShell) return;
    const notice = getEl('uploadStatusNotice');
    const lower = String(filename || '').toLowerCase();

    if (lower.endsWith('.json')) {
      try {
        const parsed = JSON.parse(rawText);
        const obj = Array.isArray(parsed) ? parsed[0] : parsed.features || parsed;
        const normalized = global.BioShell.normalizeFeatures(obj);
        applyFeaturesToInputs(normalized);
        if (notice) notice.textContent = `Parsed JSON file: ${filename}`;
        global.BioShell.showToast('Imported JSON telemetry: ' + filename, 'nominal');
        return;
      } catch (err) {
        if (notice) notice.textContent = 'Invalid JSON structure in ' + filename;
        return;
      }
    }

    const parsedCsv = global.BioShell.parseCsvTable(rawText);
    if (!parsedCsv.rows.length) {
      if (notice) notice.textContent = 'No telemetry rows detected in ' + filename;
      return;
    }

    applyFeaturesToInputs(parsedCsv.mappedTelemetry[0]);
    renderSerumRows(parsedCsv.serumRows);
    if (notice) {
      notice.textContent = `Parsed ${parsedCsv.rows.length} row(s) from ${filename} (${parsedCsv.serumRows.length} OSDR serum row(s)).`;
    }
    global.BioShell.showToast(`Loaded ${filename} into Stage 1`, 'nominal');
  }

  function loadOsdrSampleRow() {
    const sample = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.inspiration4Sample) || [];
    if (!sample.length) return;
    const first = sample[0];
    renderSerumRows(sample);
    const current = extractModelFeatures();
    if (Number.isFinite(first.glucose_mg_dl)) {
      current.blood_glucose = first.glucose_mg_dl;
    }
    applyFeaturesToInputs(current);
    const notice = getEl('uploadStatusNotice');
    if (notice) {
      notice.textContent = `Loaded OSDR Inspiration4 serum matrix (${sample.length} records). Row 1 glucose (${first.glucose_mg_dl} mg/dL) applied.`;
    }
    global.BioShell.showToast('Inspiration4 OSDR serum matrix loaded', 'nominal');
  }

  function selectBodySystem(sysId) {
    appState.activeSystemId = sysId;
    document.querySelectorAll('.holo-zone[data-system-id]').forEach((el) => {
      el.classList.toggle('selected', el.getAttribute('data-system-id') === sysId);
    });
    document.querySelectorAll('[data-holo-pill]').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-holo-pill') === sysId);
    });
    const systems = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.bodySystems) || [];
    const found = systems.find((s) => s.id === sysId) || systems[0];
    const title = getEl('holoSysTitle');
    const desc = getEl('holoSysDesc');
    if (found && title && desc) {
      title.textContent = found.body_region;
      desc.textContent = `${found.key_conditions} Indicators: ${found.measurable_indicators}.`;
    }
  }

  function goToStep(stepNum) {
    const s = Number(stepNum);
    appState.activeStep = s;
    const p1 = getEl('stage1Panel');
    const p2 = getEl('stage2Panel');
    const t1 = getEl('step1Tab');
    const t2 = getEl('step2Tab');

    if (s === 2) {
      const bpCheck = parseBloodPressure((getEl('inputBP') || {}).value);
      if (!bpCheck.valid) {
        getEl('bpValidationError')?.classList.remove('hidden');
        global.BioShell?.showToast('Fix Blood Pressure format (SYS/DIA) before continuing to Stage 2.');
        appState.activeStep = 1;
        return false;
      }
      if (p1) p1.classList.add('hidden');
      if (p2) p2.classList.remove('hidden');
      if (t1) { t1.classList.remove('active'); t1.setAttribute('aria-selected', 'false'); }
      if (t2) { t2.classList.add('active'); t2.setAttribute('aria-selected', 'true'); }
      refreshStage1Summary();
      return true;
    } else if (s === 3) {
      runModelInference();
      if (!global.location.search.includes('verify=1')) {
        global.location.href = 'decision.html';
      }
    } else {
      global.visionLab?.stopCameraStream?.();
      if (p2) p2.classList.add('hidden');
      if (p1) p1.classList.remove('hidden');
      if (t2) { t2.classList.remove('active'); t2.setAttribute('aria-selected', 'false'); }
      if (t1) { t1.classList.add('active'); t1.setAttribute('aria-selected', 'true'); }
    }
  }

  function runModelInference() {
    let bpInput = getEl('inputBP');
    let bpVal = bpInput ? bpInput.value.trim() : '';
    if (!bpVal) {
      bpVal = '118/76';
      if (bpInput) bpInput.value = bpVal;
    }
    const bpCheck = parseBloodPressure(bpVal);
    if (!bpCheck.valid) {
      bpVal = '118/76';
      if (bpInput) bpInput.value = bpVal;
    }
    getEl('bpValidationError')?.classList.add('hidden');

    const features = extractModelFeatures();
    let result = null;
    if (typeof global.evaluateAstronautHealth === 'function') {
      try {
        result = global.evaluateAstronautHealth(features);
      } catch (err) {
        console.warn('[Scan] Inference error, falling back:', err);
      }
    }
    if (!result) {
      result = { riskScore: 0.18, riskPct: 18, riskTier: 'nominal', featureAttributions: [] };
    }
    appState.lastResult = result;

    if (global.BioShell) {
      const crew = global.BioShell.getCrewProfile ? global.BioShell.getCrewProfile() : { id: 'C001', name: 'Commander Alex' };
      global.BioShell.saveSession({
        environment: global.BioShell.getEnvironment ? global.BioShell.getEnvironment() : 'Space Station',
        crewId: crew.id,
        crewName: crew.name,
        scanMode: (getEl('scanModeStaticBtn')?.classList.contains('active') ? 'Static' : 'Walk'),
        scanDurationSec: Number((getEl('scanDurationSelect') || {}).value) || 30,
        features,
        result
      });
    }
    return result;
  }

  function startNewCheckin() {
    if (global.BioShell) {
      global.BioShell.clearSession();
    }
    if (global.visionLab) {
      global.visionLab.resetVisionUI();
    }
    applyFeaturesToInputs(global.BioShell ? global.BioShell.createBlankFeatures() : {});
    renderSerumRows([]);
    const notice = getEl('uploadStatusNotice');
    if (notice) notice.textContent = '';
    goToStep(1);
    global.BioShell?.showToast('Reset all unmeasured channels to native NaN', 'nominal');
  }

  function bootstrapScan() {
    if (global.BioShell) {
      global.BioShell.renderShellChrome({ activeRoute: 'scan.html', showFooter: true });
    }
    updateEnvBanner();
    document.addEventListener('bio:env-change', updateEnvBanner);

    renderPresets();

    // Hydrate Crew Member Selector
    const crewSel = getEl('crewProfileSelect');
    if (crewSel && global.BioShell) {
      const profiles = global.BioShell.getCrewProfiles ? global.BioShell.getCrewProfiles() : [];
      const currentCrew = global.BioShell.getCrewProfile ? global.BioShell.getCrewProfile() : { id: 'C001' };
      const esc = global.BioShell.escapeHtml;
      crewSel.innerHTML = profiles
        .map((p) => `<option value="${esc(p.id)}" ${p.id === currentCrew.id ? 'selected' : ''}>${esc(p.name)}</option>`)
        .join('');
      crewSel.addEventListener('change', (e) => {
        const picked = global.BioShell.setCrewProfile(e.target.value);
        global.BioShell.syncChatbotContext?.({ currentTab: 'scan.html' });
        global.BioShell.showToast('Active crew profile: ' + picked.name, 'nominal');
      });
    }

    // Hydrate saved session OR existing face crop
    if (global.BioShell) {
      const saved = global.BioShell.getSession();
      if (saved && saved.features) applyFeaturesToInputs(saved.features);
      const portrait = global.BioShell.getFacePortrait();
      const visorImg = getEl('hologramVisorImg');
      if (visorImg && portrait) {
        visorImg.setAttribute('href', portrait);
        const cap = getEl('visorPreviewCaption');
        if (cap) cap.textContent = 'Crew visor portrait ready for Decision report.';
        getEl('retakeVisorBtn')?.classList.remove('hidden');
      }
    }

    // Input change listeners for the 9 Stage 1 inputs
    ['inputGlucose', 'inputBP', 'inputTemp', 'inputHeartRate', 'inputSpO2', 'inputSleep', 'inputMood', 'inputRadiation', 'inputCO2']
      .forEach((id) => {
        const el = getEl(id);
        if (el) {
          el.addEventListener('input', refreshStage1Summary);
          el.addEventListener('change', refreshStage1Summary);
        }
      });

    getEl('toStage2Btn')?.addEventListener('click', () => goToStep(2));
    getEl('backToStage1Btn')?.addEventListener('click', () => goToStep(1));

    const handleGoDecision = (e) => {
      if (e) e.preventDefault();
      runModelInference();
      global.location.href = 'decision.html';
    };
    getEl('generateDecisionBtn')?.addEventListener('click', handleGoDecision);

    // Stage 2 Camera & Hologram Controls
    getEl('startCameraBtn')?.addEventListener('click', () => {
      global.dispatchEvent(new CustomEvent('astro:task', { detail: { task: 'Camera Biometric Scan', phase: 'started' } }));
      global.visionLab?.startCamera();
    });
    getEl('retryCameraBtn')?.addEventListener('click', () => {
      global.dispatchEvent(new CustomEvent('astro:task', { detail: { task: 'Camera Biometric Scan', phase: 'started' } }));
      global.visionLab?.startCamera();
    });
    getEl('stopCameraBtn')?.addEventListener('click', () => {
      global.visionLab?.stopCameraStream();
      global.dispatchEvent(new CustomEvent('astro:task', { detail: { task: 'Camera Biometric Scan', phase: 'ended' } }));
    });
    getEl('finishAnalyzeBtn')?.addEventListener('click', () => global.visionLab?.finishAndAnalyzeMotion());
    getEl('replayDemoBtn')?.addEventListener('click', () => {
      global.dispatchEvent(new CustomEvent('astro:task', { detail: { task: 'Camera Calibration Demo', phase: 'started' } }));
      global.visionLab?.startCalibrationReplayDemo();
    });
    getEl('replayDemoFromErrBtn')?.addEventListener('click', () => {
      global.dispatchEvent(new CustomEvent('astro:task', { detail: { task: 'Camera Calibration Demo', phase: 'started' } }));
      global.visionLab?.startCalibrationReplayDemo();
    });
    getEl('scanModeWalkBtn')?.addEventListener('click', () => {
      global.visionLab?.setScanMode('Walk');
      getEl('squatStatusWrap')?.classList.add('hidden');
    });
    getEl('scanModeStaticBtn')?.addEventListener('click', () => {
      global.visionLab?.setScanMode('Static');
      getEl('squatStatusWrap')?.classList.remove('hidden');
    });
    getEl('scanDurationSelect')?.addEventListener('change', (e) => global.visionLab?.setDuration(e.target.value));

    getEl('applyOpticalHrBtn')?.addEventListener('click', () => {
      const btn = getEl('applyOpticalHrBtn');
      const bpm = parseOptionalNumber(btn?.dataset?.opticalBpm);
      if (Number.isFinite(bpm) && getEl('inputHeartRate')) {
        getEl('inputHeartRate').value = String(Math.round(bpm));
        refreshStage1Summary();
        global.BioShell?.showToast(`Camera pulse (${Math.round(bpm)} BPM) applied to Stage 1`, 'nominal');
      }
    });

    getEl('retakeVisorBtn')?.addEventListener('click', () => {
      global.visionLab?.retakeVisorPhoto?.();
    });

    document.addEventListener('bio:visor-captured', () => {
      const cap = getEl('visorPreviewCaption');
      if (cap) cap.textContent = 'Crew visor portrait captured ✓';
      getEl('retakeVisorBtn')?.classList.remove('hidden');
    });

    document.addEventListener('bio:vision-complete', (ev) => {
      const s = ev.detail || {};
      const bal = Number.isFinite(s.balance_score) ? s.balance_score : s.posture_score;
      const sumPosture = getEl('sumPosture');
      if (sumPosture && Number.isFinite(bal)) sumPosture.textContent = bal + '%';

      const hrEl = getEl('inputHeartRate');
      if (hrEl && !hrEl.value.trim() && Number.isFinite(s.heart_rate_optical) && (s.sqi_pct || 0) >= 50) {
        hrEl.value = String(Math.round(s.heart_rate_optical));
        global.BioShell?.showToast(`Camera pulse locked (${Math.round(s.heart_rate_optical)} BPM) & synced automatically`, 'nominal');
      }
      refreshStage1Summary();
      global.dispatchEvent(new CustomEvent('astro:task', {
        detail: { task: 'Camera Biometric Scan', phase: 'ended', info: { balance_score: bal, sqi_pct: s.sqi_pct || 0 } }
      }));
      global.BioShell?.syncChatbotContext?.({ currentTab: 'scan.html', note: 'Stage 2 camera check completed.' });
    });

    document.querySelectorAll('.holo-zone[data-system-id]').forEach((z) => {
      z.addEventListener('click', () => selectBodySystem(z.getAttribute('data-system-id')));
    });
    document.querySelectorAll('[data-holo-pill]').forEach((p) => {
      p.addEventListener('click', () => selectBodySystem(p.getAttribute('data-holo-pill')));
    });

    refreshStage1Summary();
  }

  global.app = {
    state: appState,
    parseBloodPressure,
    mapMoodToScore,
    extractModelFeatures,
    runModelInference,
    goToStep,
    startNewCheckin,
    ingestUploadedText,
    loadOsdrSampleRow,
    selectBodySystem
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapScan);
  } else {
    bootstrapScan();
  }
})(typeof window !== 'undefined' ? window : globalThis);
