/**
 * Bio Astro Lab — Stage 3 Clinical Evaluation, 5-System Hologram Inspector & What-If Simulator (decision.js)
 */
(function (global) {
  'use strict';

  const SYSTEM_FEATURE_MAP = {
    head: ['facial_ear', 'sleep_hours', 'mood_score', 'cabin_co2_mmhg'],
    cardio: ['heart_rate_bpm', 'systolic_bp', 'diastolic_bp', 'spo2_pct'],
    musculoskeletal: ['balance_score', 'joint_symmetry_diff'],
    immune: ['radiation_dose_msv', 'body_temp'],
    renal: ['blood_glucose', 'cabin_co2_mmhg']
  };

  const SLIDER_SPECS = [
    { key: 'blood_glucose', label: 'Blood Glucose (mg/dL)', min: 50, max: 240, step: 1 },
    { key: 'systolic_bp', label: 'Systolic BP (mmHg)', min: 80, max: 190, step: 1 },
    { key: 'diastolic_bp', label: 'Diastolic BP (mmHg)', min: 50, max: 120, step: 1 },
    { key: 'body_temp', label: 'Body Temp (°C)', min: 35.0, max: 40.0, step: 0.1 },
    { key: 'sleep_hours', label: 'Sleep Duration (hrs)', min: 3.0, max: 10.0, step: 0.1 },
    { key: 'mood_score', label: 'Mood State (1–4)', min: 1, max: 4, step: 1 },
    { key: 'balance_score', label: 'Balance Stability (%)', min: 55, max: 100, step: 0.5 },
    { key: 'joint_symmetry_diff', label: 'Joint ROM Delta (°)', min: 0, max: 20, step: 0.5 },
    { key: 'facial_ear', label: 'Facial EAR Ratio', min: 0.12, max: 0.40, step: 0.01 },
    { key: 'heart_rate_bpm', label: 'Heart Rate (BPM)', min: 45, max: 145, step: 1 },
    { key: 'spo2_pct', label: 'SpO2 (%)', min: 85, max: 100, step: 0.5 },
    { key: 'radiation_dose_msv', label: 'Radiation (mSv/d)', min: 0.2, max: 18.0, step: 0.1 },
    { key: 'cabin_co2_mmhg', label: 'Cabin ppCO2 (mmHg)', min: 0.5, max: 8.0, step: 0.1 }
  ];

  let baselineFeatures = null;
  let workingFeatures = null;
  let currentEval = null;
  let activeSystemId = 'head';

  function getEl(id) {
    return document.getElementById(id);
  }

  function renderVerdict(evalOut, features) {
    const badge = getEl('step3StatusBadge');
    const probEl = getEl('riskProbDisplay');
    const confEl = getEl('confidenceDisplay');
    const verEl = getEl('modelVersionDisplay');
    const risksWrap = getEl('decisionRiskBadges');

    if (!evalOut) return;

    const m = global.BioShell ? global.BioShell.extractRiskMetrics(evalOut) : { status: evalOut.predictedLabel, riskPct: 0, confidencePct: 0 };

    if (badge) {
      badge.textContent = m.status;
      badge.className =
        'badge ' +
        (evalOut.predictedClass === 2 ? 'badge-critical' : evalOut.predictedClass === 1 ? 'badge-caution' : 'badge-nominal');
    }
    if (probEl) probEl.textContent = `${m.riskPct}% (Readiness ${m.readinessScore}/100)`;
    if (confEl) confEl.textContent = `${m.confidencePct}%`;
    if (verEl) verEl.textContent = (evalOut.modelMetadata && evalOut.modelMetadata.version) || evalOut.modelVersion || 'Clinical Protocol v3.0';
    const hasFiniteFeature = Object.values(features || {}).some((v) => typeof v === 'number' && Number.isFinite(v));
    const saveBtn = getEl('saveHistoryBtn');
    if (saveBtn) saveBtn.disabled = !hasFiniteFeature;

    // Render top 3 NASA HRP Risk Drivers (cleaner, uncluttered badge row)
    if (risksWrap && global.BioShell) {
      const esc = global.BioShell.escapeHtml;
      const drivers = Array.isArray(evalOut.nasaRiskDrivers) ? evalOut.nasaRiskDrivers : [];
      if (drivers.length > 0) {
        const shown = drivers.slice(0, 3)
          .map((d) => `<span class="badge ${d.score >= 4 ? 'badge-critical' : 'badge-caution'}">HRP #${esc(d.nasaRiskId)} · ${esc(d.nasaRiskTitle)}</span>`)
          .join('');
        const extra = drivers.length > 3
          ? `<a href="guide.html#hrp" class="badge badge-ghost" style="text-decoration:none;">+${drivers.length - 3} more in Guide &rarr;</a>`
          : '';
        risksWrap.innerHTML = shown + extra;
      } else {
        risksWrap.innerHTML = `<span class="badge badge-nominal">Nominal Crew Readiness — Routine Monitoring</span>`;
      }
    }

    // Render Top 3 Quick Takeaways box (Plain explanation before diving into charts)
    const takeEl = getEl('decisionQuickTakeaways');
    if (takeEl && global.BioShell) {
      const esc = global.BioShell.escapeHtml;
      const posDrivers = (evalOut.featureAttributions || [])
        .filter((c) => (c.deltaRisk || 0) > 0.005)
        .sort((a, b) => (b.deltaRisk || 0) - (a.deltaRisk || 0))
        .slice(0, 3);
      const recs = Array.isArray(evalOut.recommendations) ? evalOut.recommendations.slice(0, 3) : [];
      const driverBullets = posDrivers.map((d) => {
        const k = d.key || d.feature;
        const val = features && Number.isFinite(features[k]) ? features[k] : '--';
        return `<li><strong>${esc(d.label || k)} (${esc(String(val))}):</strong> adds +${((d.deltaRisk || 0) * 100).toFixed(1)}% risk shift</li>`;
      });
      const recLine = recs[0] ? esc(recs[0]) : 'All measured parameters are within nominal flight range. Continue scheduled monitoring.';
      takeEl.innerHTML = `
        <div class="quick-takeaways-head">
          <strong>Key Takeaways &amp; Priority Action</strong>
          <a href="guide.html" class="mono-num" style="font-size:11px;color:var(--accent-vermilion-paper);text-decoration:none;">Open Personal Action Plan &rarr;</a>
        </div>
        ${driverBullets.length
          ? `<ul class="quick-takeaways-list">${driverBullets.join('')}</ul>`
          : `<p style="font-size:12.5px;color:var(--ink-muted-paper);margin:4px 0;">No elevated physical risk drivers detected in your active channels.</p>`}
        <p style="font-size:12.5px;color:var(--accent-nominal);margin:6px 0 0;"><strong>Next Step:</strong> ${recLine}</p>`;
    }

    // Update Hologram zone colors & compute 5-system strain scores for charts
    const contribMap = {};
    (evalOut.featureAttributions || []).forEach((c) => {
      contribMap[c.key] = Math.abs(c.deltaRisk || 0) * (c.deltaRisk >= 0 ? 1 : 0.2);
    });
    const assessments = evalOut.biomarkerAssessments || {};
    const systemStrains = {};
    document.querySelectorAll('.holo-zone[data-system-id]').forEach((zone) => {
      const id = zone.getAttribute('data-system-id');
      const keys = SYSTEM_FEATURE_MAP[id] || [];
      const hasCritical = keys.some((k) => assessments[k] && assessments[k].critical);
      const hasCaution = keys.some((k) => assessments[k] && (assessments[k].points || 0) >= 1);
      const sum = keys.reduce((acc, k) => acc + Math.max(0, contribMap[k] || 0), 0);
      const tier = hasCritical || sum >= 0.08 ? 'critical' : hasCaution || sum >= 0.025 ? 'caution' : 'nominal';
      zone.setAttribute('data-tier', tier);
      document.querySelectorAll(`[data-holo-pill="${id}"]`).forEach((p) => p.setAttribute('data-tier', tier));

      // Strain score 0..100 derived from SHAP sum + clinical warning points
      const maxPts = keys.reduce((acc, k) => acc + (assessments[k]?.points || 0), 0);
      const pct = Math.min(100, Math.round(sum * 650 + maxPts * 16 + (hasCritical ? 25 : 0)));
      systemStrains[id] = { pct: Math.max(pct, tier === 'nominal' ? 8 : tier === 'caution' ? 42 : 76), tier };
    });

    renderWaterfall(evalOut.featureAttributions || [], features || {});
    renderSubCharts(evalOut, features || {}, systemStrains, m);
  }

  function featureToSystem(key) {
    for (const [sysId, keys] of Object.entries(SYSTEM_FEATURE_MAP)) {
      if (keys.includes(key)) return sysId;
    }
    return 'head';
  }

  function renderWaterfall(contribs, features) {
    const list = getEl('shapWaterfallList');
    if (!list || !global.BioShell) return;
    const esc = global.BioShell.escapeHtml;
    const sorted = contribs.slice().sort((a, b) => Math.abs(b.deltaRisk || 0) - Math.abs(a.deltaRisk || 0));

    if (sorted.length === 0) {
      list.innerHTML = `<p class="mono-num" style="font-size:12px;color:var(--ink-muted-paper);padding:14px 8px;">All 13 channels currently unmeasured (NaN) — drag any simulator slider below or scan vitals to plot live SHAP impacts.</p>`;
      return;
    }

    const maxObserved = sorted.reduce((m, item) => Math.max(m, Math.abs(item.deltaRisk || 0)), 0);
    const maxAbs = Math.max(0.004, maxObserved * 1.12);

    list.innerHTML = sorted
      .slice(0, 10)
      .map((item) => {
        const key = item.key || item.feature;
        const val = features[key];
        const valText = typeof val === 'number' && Number.isFinite(val) ? val.toFixed(2).replace(/\.00$/, '') : 'NaN';
        const d = item.deltaRisk || 0;
        const halfWidthPct = Math.min(48, Math.max(2.5, Math.round((Math.abs(d) / maxAbs) * 48)));
        const isPos = d >= 0;
        const fill = d > 0.0005 ? 'var(--accent-vermilion)' : d < -0.0005 ? 'var(--accent-nominal)' : '#94A3B8';
        const leftPct = isPos ? 50 : 50 - halfWidthPct;
        const sign = d > 0 ? '+' : '';
        const targetSys = featureToSystem(key);
        return `
          <div class="waterfall-row" data-wf-sys="${esc(targetSys)}" title="Click to inspect ${esc(targetSys)} organ on hologram">
            <span class="mono-num wf-label">${esc(item.label || key)}</span>
            <span class="mono-num wf-val">${esc(valText)}</span>
            <div class="wf-diverge-track">
              <div class="wf-diverge-zero"></div>
              <div class="wf-diverge-fill" style="left:${leftPct}%;width:${halfWidthPct}%;background:${fill};"></div>
            </div>
            <span class="mono-num wf-delta" style="color:${fill};">${sign}${(d * 100).toFixed(1)}%</span>
          </div>`;
      })
      .join('');

    list.querySelectorAll('[data-wf-sys]').forEach((row) => {
      row.addEventListener('click', () => {
        const sys = row.getAttribute('data-wf-sys');
        if (sys) selectBodySystem(sys);
      });
    });
  }

  function renderSubCharts(evalOut, features, systemStrains, metrics) {
    const strainEl = getEl('organStrainChart');
    const donutEl = getEl('readinessDonutChart');
    const covEl = getEl('channelCoveragePill');

    const finiteCount = Object.values(features || {}).filter((v) => typeof v === 'number' && Number.isFinite(v)).length;
    if (covEl) covEl.textContent = `${finiteCount}/13 Active`;

    if (strainEl) {
      const systems = [
        { id: 'head', label: 'Brain' },
        { id: 'cardio', label: 'Heart' },
        { id: 'immune', label: 'Immune' },
        { id: 'renal', label: 'Renal' },
        { id: 'musculoskeletal', label: 'Joints' }
      ];
      const tierColor = { nominal: '#1C7C54', caution: '#C97A16', critical: '#D14D28' };
      const chartW = 330;
      const chartH = 160;
      const baseLineY = 128;
      const maxBarH = 102;

      const bars = systems
        .map((sys, idx) => {
          const info = systemStrains[sys.id] || { pct: 8, tier: 'nominal' };
          const h = Math.max(8, Math.round((info.pct / 100) * maxBarH));
          const x = 36 + idx * 58;
          const y = baseLineY - h;
          const color = tierColor[info.tier] || '#1C7C54';
          return `
            <g class="strain-bar-grp" data-chart-system="${sys.id}" style="cursor:pointer;">
              <rect x="${x}" y="22" width="34" height="${maxBarH + 4}" rx="3" fill="rgba(17,19,24,0.035)"></rect>
              <rect x="${x}" y="${y}" width="34" height="${h}" rx="3" fill="${color}" opacity="0.9"></rect>
              <text x="${x + 17}" y="${y - 5}" text-anchor="middle" font-family="var(--font-mono)" font-size="9.5" font-weight="700" fill="${color}">${info.pct}%</text>
              <text x="${x + 17}" y="146" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="#4B525E">${sys.label}</text>
            </g>`;
        })
        .join('');

      strainEl.innerHTML = `
        <svg viewBox="0 0 ${chartW} ${chartH}" style="width:100%;height:auto;max-height:170px;" role="img" aria-label="5-organ physiological strain column chart">
          <line x1="28" y1="${baseLineY - maxBarH * 0.75}" x2="${chartW - 10}" y2="${baseLineY - maxBarH * 0.75}" stroke="rgba(209,77,40,0.22)" stroke-dasharray="3 3" stroke-width="0.9"></line>
          <line x1="28" y1="${baseLineY - maxBarH * 0.50}" x2="${chartW - 10}" y2="${baseLineY - maxBarH * 0.50}" stroke="rgba(20,24,31,0.08)" stroke-width="0.8"></line>
          <line x1="28" y1="${baseLineY - maxBarH * 0.25}" x2="${chartW - 10}" y2="${baseLineY - maxBarH * 0.25}" stroke="rgba(20,24,31,0.08)" stroke-width="0.8"></line>
          <line x1="28" y1="${baseLineY}" x2="${chartW - 10}" y2="${baseLineY}" stroke="rgba(20,24,31,0.28)" stroke-width="1"></line>
          <text x="23" y="${baseLineY - maxBarH * 0.75 + 3}" text-anchor="end" font-family="var(--font-mono)" font-size="8" fill="#8D939E">75</text>
          <text x="23" y="${baseLineY - maxBarH * 0.50 + 3}" text-anchor="end" font-family="var(--font-mono)" font-size="8" fill="#8D939E">50</text>
          <text x="23" y="${baseLineY + 3}" text-anchor="end" font-family="var(--font-mono)" font-size="8" fill="#8D939E">0</text>
          ${bars}
        </svg>`;

      strainEl.querySelectorAll('[data-chart-system]').forEach((grp) => {
        grp.addEventListener('click', () => {
          const id = grp.getAttribute('data-chart-system');
          if (id) selectBodySystem(id);
        });
      });
    }

    if (donutEl) {
      const readiness = Number.isFinite(metrics.readinessScore) ? metrics.readinessScore : 97;
      const risk = Number.isFinite(metrics.riskPct) ? metrics.riskPct : 1.2;
      const conf = Number.isFinite(metrics.confidencePct) ? metrics.confidencePct : 98.8;
      const r = 42;
      const c = 2 * Math.PI * r;
      const readyLen = Math.max(0, Math.min(c, (readiness / 100) * c));
      const riskColor = evalOut.predictedClass === 2 ? '#D14D28' : evalOut.predictedClass === 1 ? '#C97A16' : '#1C7C54';
      const topPos = (evalOut.featureAttributions || []).slice().sort((a, b) => (b.deltaRisk || 0) - (a.deltaRisk || 0))[0];
      const topDriverText = topPos && topPos.deltaRisk > 0.001
        ? `${topPos.label} (+${(topPos.deltaRisk * 100).toFixed(1)}%)`
        : 'All Nominal';

      donutEl.innerHTML = `
        <div style="display:flex;align-items:center;gap:14px;width:100%;">
          <svg viewBox="0 0 110 110" style="width:110px;height:110px;flex-shrink:0;" role="img" aria-label="Mission readiness donut gauge">
            <circle cx="55" cy="55" r="${r}" fill="none" stroke="rgba(209,77,40,0.20)" stroke-width="11"></circle>
            <circle cx="55" cy="55" r="${r}" fill="none" stroke="${riskColor}" stroke-width="11"
                    stroke-dasharray="${readyLen.toFixed(1)} ${c.toFixed(1)}" stroke-linecap="round"
                    transform="rotate(-90 55 55)"></circle>
            <text x="55" y="52" text-anchor="middle" font-family="var(--font-mono)" font-size="18" font-weight="700" fill="#17191E">${Math.round(readiness)}</text>
            <text x="55" y="66" text-anchor="middle" font-family="var(--font-mono)" font-size="8.5" fill="#68707C">READINESS</text>
          </svg>
          <div style="display:flex;flex-direction:column;gap:6px;font-size:11.5px;min-width:0;flex:1;">
            <div style="display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--border-paper);padding-bottom:4px;">
              <span style="color:var(--ink-muted-paper);">Predicted Risk</span>
              <strong class="mono-num" style="color:${riskColor};">${risk}%</strong>
            </div>
            <div style="display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--border-paper);padding-bottom:4px;">
              <span style="color:var(--ink-muted-paper);">Confidence</span>
              <strong class="mono-num">${conf}%</strong>
            </div>
            <div>
              <span style="color:var(--ink-muted-paper);display:block;font-size:10.5px;">Top Risk Driver</span>
              <strong class="mono-num" style="font-size:11px;color:var(--ink-paper);">${global.BioShell ? global.BioShell.escapeHtml(topDriverText) : topDriverText}</strong>
            </div>
          </div>
        </div>`;
    }
  }

  function renderWhatIfSliders() {
    const grid = getEl('whatIfGrid');
    if (!grid || !global.BioShell || !workingFeatures) return;
    const esc = global.BioShell.escapeHtml;

    grid.innerHTML = SLIDER_SPECS.map((spec) => {
      const cur = workingFeatures[spec.key];
      const hasVal = typeof cur === 'number' && Number.isFinite(cur);
      const displayVal = hasVal ? String(cur) : 'NaN';
      const sliderVal = hasVal ? cur : (spec.min + spec.max) / 2;
      return `
        <div class="field-group" style="background:var(--bg-paper);padding:12px 14px;border:1px solid var(--border-paper);border-radius:6px;gap:8px;">
          <label for="slider-${esc(spec.key)}" style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <span style="font-size:12.5px;white-space:nowrap;">${esc(spec.label)}</span>
            <span class="mono-num" id="sval-${esc(spec.key)}" style="color:var(--accent-vermilion);font-size:12px;">${esc(displayVal)}</span>
          </label>
          <div style="display:flex;align-items:center;gap:8px;">
            <input id="slider-${esc(spec.key)}" type="range" min="${spec.min}" max="${spec.max}" step="${spec.step}" value="${sliderVal}" data-whatif-key="${esc(spec.key)}" style="flex:1;min-width:0;">
            <input id="num-${esc(spec.key)}" type="number" min="${spec.min}" max="${spec.max}" step="${spec.step}" value="${hasVal ? cur : ''}" placeholder="--" data-whatif-num="${esc(spec.key)}" aria-label="${esc(spec.label)} numeric input" class="input-field" style="width:76px;padding:4px 6px;font-size:12px;text-align:right;">
          </div>
        </div>`;
    }).join('');

    const applyUpdate = (k, rawVal, sourceType) => {
      if (rawVal === '' && sourceType === 'num') {
        workingFeatures[k] = NaN;
        const lbl = getEl('sval-' + k);
        if (lbl) lbl.textContent = 'NaN';
      } else {
        const num = Number(rawVal);
        if (!Number.isFinite(num)) return;
        workingFeatures[k] = num;
        const lbl = getEl('sval-' + k);
        if (lbl) lbl.textContent = String(num);
        const sliderEl = getEl('slider-' + k);
        const numEl = getEl('num-' + k);
        if (sourceType !== 'slider' && sliderEl) sliderEl.value = String(num);
        if (sourceType !== 'num' && numEl) numEl.value = String(num);
      }
      if (typeof global.evaluateAstronautHealth === 'function') {
        currentEval = global.evaluateAstronautHealth(workingFeatures);
        renderVerdict(currentEval, workingFeatures);
      }
    };

    grid.querySelectorAll('input[data-whatif-key]').forEach((input) => {
      input.addEventListener('input', () => applyUpdate(input.getAttribute('data-whatif-key'), input.value, 'slider'));
    });
    grid.querySelectorAll('input[data-whatif-num]').forEach((input) => {
      input.addEventListener('input', () => applyUpdate(input.getAttribute('data-whatif-num'), input.value, 'num'));
    });
  }

  function selectBodySystem(sysId) {
    const normalizedId = (sysId === 'limbs') ? 'musculoskeletal' : sysId;
    activeSystemId = normalizedId;
    document.querySelectorAll('.holo-zone[data-system-id]').forEach((el) => {
      const zid = el.getAttribute('data-system-id');
      el.classList.toggle('selected', zid === normalizedId || (normalizedId === 'musculoskeletal' && (zid === 'limbs' || zid === 'musculoskeletal')));
    });
    document.querySelectorAll('[data-holo-pill]').forEach((btn) => {
      const pid = btn.getAttribute('data-holo-pill');
      btn.classList.toggle('active', pid === normalizedId || (normalizedId === 'musculoskeletal' && (pid === 'limbs' || pid === 'musculoskeletal')));
    });
    const systems = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.bodySystems) || [];
    const found = systems.find((s) => s.id === normalizedId) || systems[0];
    if (!found) return;
    if (getEl('decHoloTitle')) getEl('decHoloTitle').textContent = found.body_region;
    if (getEl('decHoloDesc')) {
      getEl('decHoloDesc').textContent = `${found.key_conditions} Indicators: ${found.measurable_indicators}.`;
    }
    if (getEl('decHoloCountermeasure')) {
      getEl('decHoloCountermeasure').textContent = 'NASA Prevention / Care: ' + found.prevention_and_treatment;
    }
  }

  function loadSessionOrEmpty() {
    if (!global.BioShell) return;
    const envEl = getEl('decEnvText');
    if (envEl) envEl.textContent = global.BioShell.getEnvironment().toUpperCase();
    const crewEl = getEl('decCrewText');
    const sess = global.BioShell.getSession();
    const activeCrew = (sess && sess.crewName) || (global.BioShell.getCrewProfile ? global.BioShell.getCrewProfile().name : 'C001');
    if (crewEl) crewEl.textContent = activeCrew;
    const banner = getEl('emptySessionBanner');

    const portrait = global.BioShell.getFacePortrait();
    const visorImg = getEl('decisionVisorImg');
    const visorTag = getEl('visorStatusTag');
    if (visorImg && portrait) {
      visorImg.setAttribute('href', portrait);
      if (visorTag) {
        visorTag.textContent = 'Visor Captured';
        visorTag.className = 'badge badge-nominal';
      }
    }

    if (sess && sess.features) {
      if (banner) banner.classList.add('hidden');
      baselineFeatures = { ...sess.features };
      workingFeatures = { ...sess.features };
      if (typeof global.evaluateAstronautHealth === 'function') {
        currentEval = global.evaluateAstronautHealth(workingFeatures);
        renderVerdict(currentEval, workingFeatures);
      }
      renderWhatIfSliders();
      selectBodySystem(activeSystemId);
    } else {
      if (banner) banner.classList.remove('hidden');
      baselineFeatures = global.BioShell.createBlankFeatures();
      workingFeatures = global.BioShell.createBlankFeatures();
      if (typeof global.evaluateAstronautHealth === 'function') {
        currentEval = global.evaluateAstronautHealth(workingFeatures);
        renderVerdict(currentEval, workingFeatures);
      }
      renderWhatIfSliders();
      selectBodySystem('head');
    }
  }

  function bootstrapDecision() {
    if (global.BioShell) {
      global.BioShell.renderShellChrome({ activeRoute: 'decision.html', showFooter: true });
    }
    loadSessionOrEmpty();

    document.addEventListener('bio:env-change', () => {
      if (getEl('decEnvText') && global.BioShell) {
        getEl('decEnvText').textContent = global.BioShell.getEnvironment().toUpperCase();
      }
    });

    getEl('loadDecisionSampleBtn')?.addEventListener('click', () => {
      const first = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.missionPresets && global.NASA_DATA_BUNDLE.missionPresets[0]) || null;
      if (!first || !global.BioShell) return;
      const env = first.environment || global.BioShell.getEnvironment();
      if (typeof global.BioShell.setEnvironment === 'function') {
        global.BioShell.setEnvironment(env);
      }
      const envEl = getEl('decEnvText');
      if (envEl) envEl.textContent = env.toUpperCase();
      baselineFeatures = global.BioShell.normalizeFeatures(first.features);
      workingFeatures = { ...baselineFeatures };
      currentEval = global.evaluateAstronautHealth ? global.evaluateAstronautHealth(workingFeatures) : null;
      global.BioShell.saveSession({
        environment: env,
        features: workingFeatures,
        result: currentEval,
        meta: { sourcePreset: first.label }
      });
      getEl('emptySessionBanner')?.classList.add('hidden');
      renderVerdict(currentEval, workingFeatures);
      renderWhatIfSliders();
      selectBodySystem(activeSystemId);
      global.BioShell.syncChatbotContext?.({ currentTab: 'decision.html', note: 'Loaded baseline telemetry.' });
      global.BioShell.showToast('Loaded C001 Baseline for inspection', 'nominal');
    });

    getEl('resetBaselineBtn')?.addEventListener('click', () => {
      if (!baselineFeatures) return;
      workingFeatures = { ...baselineFeatures };
      if (typeof global.evaluateAstronautHealth === 'function') {
        currentEval = global.evaluateAstronautHealth(workingFeatures);
        renderVerdict(currentEval, workingFeatures);
      }
      renderWhatIfSliders();
      global.BioShell?.showToast('Reset simulator sliders to scanned baseline', 'nominal');
    });

    getEl('printReportBtn')?.addEventListener('click', () => {
      if (typeof global.print === 'function') global.print();
    });

    getEl('saveHistoryBtn')?.addEventListener('click', () => {
      if (!global.BioShell || !workingFeatures) return;
      const evalOut = typeof global.evaluateAstronautHealth === 'function' ? global.evaluateAstronautHealth(workingFeatures) : currentEval;
      if (!evalOut) return;
      const m = global.BioShell.extractRiskMetrics(evalOut);
      const sess = global.BioShell.getSession();
      const crew = global.BioShell.getCrewProfile ? global.BioShell.getCrewProfile() : { id: 'C001', name: 'C001 — Commander Alex' };
      const crewId = (sess && sess.crewId) || crew.id || 'C001';
      global.BioShell.appendHistory({
        id: 'CREW-' + String(Date.now()).slice(-5),
        crewId,
        timestamp: new Date().toISOString(),
        label: (sess && sess.meta && sess.meta.sourcePreset) || `${crewId} Triage Check-in`,
        environment: global.BioShell.getEnvironment(),
        scanMode: (sess && sess.scanMode) || 'Walk',
        status: m.status,
        riskPct: m.riskPct,
        confidencePct: m.confidencePct,
        features: workingFeatures,
        source: 'Clinical Protocol v3.0'
      });
      global.BioShell.showToast('Saved evaluation to Mission History log', 'nominal');
    });

    const holoMount = document.querySelector('[data-hologram-mount]');
    if (holoMount) {
      holoMount.addEventListener('click', (e) => {
        const zone = e.target.closest('.holo-zone[data-system-id]');
        if (zone) {
          selectBodySystem(zone.getAttribute('data-system-id'));
        }
      });
    }

    document.querySelectorAll('.holo-zone[data-system-id]').forEach((z) => {
      z.addEventListener('click', () => selectBodySystem(z.getAttribute('data-system-id')));
    });
    document.querySelectorAll('[data-holo-pill]').forEach((p) => {
      p.addEventListener('click', () => selectBodySystem(p.getAttribute('data-holo-pill')));
    });

    init3DHologramMotion();
  }

  function init3DHologramMotion() {
    const wrap = document.querySelector('[data-hologram-mount]');
    if (!wrap) return;
    const svg = wrap.querySelector('svg');
    if (!svg) return;

    wrap.addEventListener('mousemove', (e) => {
      const rect = wrap.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      const rotY = (x * 16).toFixed(1);
      const rotX = (-y * 14).toFixed(1);
      svg.style.transform = `perspective(800px) rotateY(${rotY}deg) rotateX(${rotX}deg) scale3d(1.03, 1.03, 1.03)`;
    });

    wrap.addEventListener('mouseleave', () => {
      svg.style.transform = 'perspective(800px) rotateY(0deg) rotateX(0deg) scale3d(1, 1, 1)';
    });
  }

  global.decisionPage = {
    loadSessionOrEmpty,
    selectBodySystem
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapDecision);
  } else {
    bootstrapDecision();
  }
})(typeof window !== 'undefined' ? window : globalThis);
