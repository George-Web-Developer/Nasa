/**
 * Bio Astro Lab — Personalized Physical Crew Action Guide & Reference Library (guide.js)
 * Builds a tailored action plan from recorded physical vitals, camera kinematics/rPPG,
 * and flight habitat, while keeping the full 38-record NASA archive inside a collapsible drawer.
 */
(function (global) {
  'use strict';

  // Declarative Physical x Environmental Guidance Rules
  const PHYSICAL_CONDITION_GUIDES = [
    {
      id: 'sleep-ocular',
      priority: 'HIGH',
      badgeClass: 'badge-critical',
      title: 'Sleep Deficit / Ocular Closure Fatigue (EAR)',
      riskIds: [84, 105],
      match: (f) =>
        (Number.isFinite(f.sleep_hours) && f.sleep_hours < 6.5) ||
        (Number.isFinite(f.facial_ear) && f.facial_ear < 0.21),
      triggerLabel: (f) => {
        const parts = [];
        if (Number.isFinite(f.sleep_hours)) parts.push(`Sleep ${f.sleep_hours} hrs`);
        if (Number.isFinite(f.facial_ear)) parts.push(`Ocular EAR ${f.facial_ear.toFixed(3)}`);
        return parts.join(' · ') || 'Sleep / Ocular Deficit';
      },
      why: 'Circadian sleep restriction or drooping ocular aperture (low EAR) slows reaction time and raises procedure/EVA handling risk.',
      actions: [
        'Defer high-consequence physical operations (EVA airlock ops, manual docking, rover driving) until rested.',
        'Schedule a protected 90-minute recovery nap + target >= 7.5 hours next sleep block under < 10 lux cabin lighting.',
        'Run blue-enriched (480 nm) wake illumination at shift start and enforce procedure cross-checks.',
        'Repeat camera EAR + physical check-in after the next sleep block.'
      ]
    },
    {
      id: 'co2-cardio',
      priority: 'CRITICAL',
      badgeClass: 'badge-critical',
      title: 'Hypercapnia / Cardiopulmonary Load',
      riskIds: [173, 179],
      protocolIds: ['hypoxia-dcs', 'chest-pain'],
      match: (f) =>
        (Number.isFinite(f.cabin_co2_mmhg) && f.cabin_co2_mmhg >= 3.0) ||
        (Number.isFinite(f.spo2_pct) && f.spo2_pct < 94) ||
        (Number.isFinite(f.heart_rate_bpm) && f.heart_rate_bpm >= 95),
      triggerLabel: (f) => {
        const parts = [];
        if (Number.isFinite(f.cabin_co2_mmhg)) parts.push(`ppCO2 ${f.cabin_co2_mmhg} mmHg`);
        if (Number.isFinite(f.spo2_pct)) parts.push(`SpO2 ${f.spo2_pct}%`);
        if (Number.isFinite(f.heart_rate_bpm)) parts.push(`HR ${Math.round(f.heart_rate_bpm)} BPM`);
        return parts.join(' · ') || 'Cardiopulmonary Strain';
      },
      why: 'Elevated cabin CO2 or borderline SpO2 induces cerebral vasodilation, headache risk, and elevated cardiovascular demand.',
      actions: [
        'Inspect ECLSS CO2 scrubber flow (CDRA / amine bed) and increase inter-module ventilation immediately toward ppCO2 <= 2.0 mmHg.',
        'Hold strenuous ergometer/ARED loading until resting HR < 90 BPM and SpO2 >= 95% is confirmed.',
        'If SpO2 drops below 90% or chest pain/headache worsens, initiate 100% O2 mask and Flight Surgeon telemetry.'
      ]
    },
    {
      id: 'glycemic-metabolic',
      priority: 'HIGH',
      badgeClass: 'badge-caution',
      title: 'Glycemic & Metabolic Homeostasis Adjustment',
      riskIds: [176],
      match: (f) => Number.isFinite(f.blood_glucose) && (f.blood_glucose < 72 || f.blood_glucose >= 130),
      triggerLabel: (f) => `Blood Glucose ${f.blood_glucose} mg/dL`,
      why: 'Microgravity alters insulin sensitivity and muscle glucose uptake; out-of-range blood glucose degrades physical stamina.',
      actions: [
        'If Blood Glucose < 70 mg/dL: consume 15-20 g rapid oral carbohydrate immediately, pause physical exertion, and re-test glucometry in 15 minutes.',
        'If Blood Glucose >= 130 mg/dL: complete 25-35 min moderate CEVIS cycle ergometer session (activates muscle GLUT4 uptake) and log hydration.',
        'Stabilize meal timing to match orbital wake cycles and repeat glucometry prior to next exercise block.'
      ]
    },
    {
      id: 'vestibular-eva',
      priority: 'HIGH',
      badgeClass: 'badge-caution',
      title: 'Vestibular / Gait Asymmetry Protection',
      riskIds: [88, 167, 168],
      protocolIds: ['balance-loss'],
      match: (f) =>
        (Number.isFinite(f.balance_score) && f.balance_score < 78) ||
        (Number.isFinite(f.joint_symmetry_diff) && f.joint_symmetry_diff > 7.5),
      triggerLabel: (f) => {
        const parts = [];
        if (Number.isFinite(f.balance_score)) parts.push(`Balance ${Math.round(f.balance_score)}%`);
        if (Number.isFinite(f.joint_symmetry_diff)) parts.push(`Joint Δ ${f.joint_symmetry_diff.toFixed(1)}°`);
        return parts.join(' · ');
      },
      why: 'Otolith adaptation shifts or unilateral knee kinematic asymmetry increase fall and joint strain risk during module translation or surface EVA.',
      actions: [
        'Maintain three-point handrail contact or foot restraints when translating through hatches and airlocks.',
        'Avoid rapid pitch/yaw head turns (mitigate Coriolis cross-coupling) and pause unilateral heavy ARED loading today.',
        'Run a slow 30-second Stage 2 Walk check after hydration/rest to verify Joint Symmetry Diff drops below 6.0 deg.'
      ]
    },
    {
      id: 'orthostatic-fluid',
      priority: 'HIGH',
      badgeClass: 'badge-caution',
      title: 'Cardiovascular / Orthostatic Shift Protocol',
      riskIds: [179, 105],
      protocolIds: ['dizziness', 'sans-vision'],
      match: (f) =>
        Number.isFinite(f.systolic_bp) &&
        (f.systolic_bp < 92 || f.systolic_bp >= 140 || (Number.isFinite(f.diastolic_bp) && f.diastolic_bp >= 90)),
      triggerLabel: (f) =>
        `BP ${Math.round(f.systolic_bp)}/${Number.isFinite(f.diastolic_bp) ? Math.round(f.diastolic_bp) : '--'} mmHg`,
      why: 'Microgravity cephalad fluid shift (~1.5-2 L) alters baroreceptor sensitivity, cerebral perfusion pressure, and SANS intraocular loading.',
      actions: [
        'If SBP < 92 mmHg: hydrate with 0.5-1.0 L oral electrolyte solution, avoid sudden upright transitions, and schedule LBNP assessment.',
        'If SBP >= 140 or DBP >= 90 mmHg: verify arm-cuff rest posture (5 min calm seated) and confirm cabin ppCO2 < 2.0 mmHg.',
        'Re-measure bilateral BP + resting HR after 20 minutes of quiet recovery.'
      ]
    },
    {
      id: 'radiation-immune',
      priority: 'CRITICAL',
      badgeClass: 'badge-critical',
      title: 'Ionizing Radiation / Thermal Countermeasure',
      riskIds: [95, 96, 101],
      protocolIds: ['radiation'],
      match: (f) =>
        (Number.isFinite(f.radiation_dose_msv) && f.radiation_dose_msv >= 1.5) ||
        (Number.isFinite(f.body_temp) && f.body_temp >= 37.8),
      triggerLabel: (f) => {
        const parts = [];
        if (Number.isFinite(f.radiation_dose_msv)) parts.push(`RIDGE ${f.radiation_dose_msv} mSv/d`);
        if (Number.isFinite(f.body_temp)) parts.push(`Temp ${f.body_temp.toFixed(1)} °C`);
        return parts.join(' · ');
      },
      why: 'Elevated space radiation flux and thermal/immune elevation heighten oxidative and inflammatory stress.',
      actions: [
        'Suspend external EVA; move crew schedule into polyethylene / water-wall shielded quarters during SPE peak windows.',
        'Verify personal CANS/RAD dosimeter reading and log crew hydration + nutrition compliance.',
        'If core body temperature >= 37.8 °C, run infection screen, monitor core temp every 2 hrs, and notify Flight Surgeon.'
      ]
    }
  ];

  const HABITAT_ROUTINES = {
    'Space Station': [
      'Complete 2.0 hr daily combined ARED resistive + CEVIS aerobic countermeasure to protect bone BMD and stroke volume in 0 g.',
      'Hold cabin ppCO2 <= 2.0 mmHg to reduce SANS optic disc edema and headache risk across 16 orbital day/night cycles.'
    ],
    'Deep Transit': [
      'Enforce strict 24-hr light/melatonin zeitgeber discipline during autonomous deep-space comms delay.',
      'Maintain continuous CANS/RAD dosimetry tracking and storm-shelter drill readiness.'
    ],
    'Moon Base': [
      'Perform suited ankle/knee balance calibration before 0.16 g dusty regolith EVAs and inspect suit HEPA filtration seals post-ingress.',
      'Hydrate pre-EVA with electrolytes and monitor joint symmetry diff for early suit-bearing soreness.'
    ],
    'Mars Surface': [
      'Schedule circadian shift alignment to the 24.6 hr Martian Sol and prioritize resistive loading to preserve 0.38 g ambulation.',
      'Re-verify O2/CO2 ECLSS scrubbers and water recovery loops weekly under autonomous surface contingency.'
    ],
    'Rover': [
      'Confirm pressurized cabin ppCO2 (< 2.0 mmHg) and backup O2 pressure before extended remote traverses.',
      'Enforce mandatory 15-min rest stops every 3 hours of surface driving for posture, hydration, and ocular fatigue resets.'
    ]
  };

  let activeTab = 'all';

  function formatMetric(val, unit, decimals) {
    if (!Number.isFinite(val)) return '--';
    const num = typeof decimals === 'number' ? val.toFixed(decimals) : Math.round(val);
    return unit ? `${num} ${unit}` : String(num);
  }

  function resolveGuidanceRecords() {
    const records = [];
    const sess = global.BioShell ? global.BioShell.getSession() : null;
    if (sess && sess.features) {
      const obsCount = Object.values(sess.features).filter((v) => Number.isFinite(Number(v))).length;
      if (obsCount > 0) {
        records.push({
          key: 'active-session',
          sourceLabel: 'ACTIVE CREW SCAN SESSION',
          selectLabel: `Active Scan (${obsCount}/13 features · ${sess.environment})`,
          environment: sess.environment || (global.BioShell ? global.BioShell.getEnvironment() : 'Space Station'),
          timestamp: sess.timestamp,
          features: sess.features
        });
      }
    }
    const hist = global.BioShell ? global.BioShell.getHistory() : [];
    hist.forEach((h) => {
      if (!h || !h.features) return;
      const dateStr = h.timestamp ? new Date(h.timestamp).toLocaleDateString() : 'Historical';
      records.push({
        key: 'hist:' + h.id,
        sourceLabel: `RECORDED CHECK-IN · ${h.label || h.id}`,
        selectLabel: `${h.label || h.id} · ${dateStr} (${h.environment || 'Space Station'})`,
        environment: h.environment || 'Space Station',
        timestamp: h.timestamp,
        features: h.features
      });
    });
    return records;
  }

  function renderPersonalizedGuide(records, selectedKey) {
    const snapEl = document.getElementById('personalSnapshotCard');
    const planEl = document.getElementById('personalCrossPlanWrap');
    const hrpEl = document.getElementById('personalHrpWrap');
    const esc = global.BioShell ? global.BioShell.escapeHtml : (s) => String(s || '');
    if (!snapEl || !planEl || !hrpEl) return;

    const record = records.find((r) => r.key === selectedKey) || records[0] || null;
    if (!record) {
      snapEl.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
          <div>
            <span class="badge badge-ghost">NO RECORDED DATA YET</span>
            <h2 style="font-size:20px;margin-top:8px;">Start a Crew Health Scan to Build Your Personalized Guide</h2>
            <p style="font-size:13.5px;color:var(--ink-muted-paper);margin-top:6px;">
              Enter your physical vitals in Stage 1 and run Stage 2 Camera Kinematics so this guide tailors every countermeasure to your readings.
            </p>
          </div>
          <a href="scan.html" class="btn-primary">Open Health Scan &rarr;</a>
        </div>`;
      planEl.innerHTML = '';
      hrpEl.innerHTML = '';
      return;
    }

    const evalOut = typeof global.evaluateAstronautHealth === 'function' ? global.evaluateAstronautHealth(record.features) : null;
    const f = (evalOut && evalOut.features) || record.features || {};
    const metrics = global.BioShell ? global.BioShell.extractRiskMetrics(evalOut) : { status: 'Optimal', readinessScore: 95 };
    const envMeta = global.BioShell ? global.BioShell.getEnvironmentMeta(record.environment) : { label: record.environment, gravity: '--' };
    const obsCount = evalOut ? evalOut.featureCount : Object.values(f).filter((v) => Number.isFinite(Number(v))).length;

    const tierBadgeClass = metrics.status === 'Critical' ? 'badge-critical' : metrics.status === 'Caution' ? 'badge-caution' : 'badge-nominal';

    const pillItems = [
      ['Blood Glucose', formatMetric(f.blood_glucose, 'mg/dL', 1)],
      ['Blood Pressure', Number.isFinite(f.systolic_bp) ? `${Math.round(f.systolic_bp)}/${Number.isFinite(f.diastolic_bp) ? Math.round(f.diastolic_bp) : '--'} mmHg` : '--'],
      ['Body Temp', formatMetric(f.body_temp, '°C', 1)],
      ['Heart Rate', formatMetric(f.heart_rate_bpm, 'BPM', 0)],
      ['SpO2', formatMetric(f.spo2_pct, '%', 1)],
      ['Sleep', formatMetric(f.sleep_hours, 'hrs', 1)],
      ['Balance Score', formatMetric(f.balance_score, '%', 0)],
      ['Joint Sym Δ', formatMetric(f.joint_symmetry_diff, '°', 1)],
      ['Ocular EAR', formatMetric(f.facial_ear, '', 3)],
      ['RIDGE Rad', formatMetric(f.radiation_dose_msv, 'mSv/d', 2)],
      ['Cabin ppCO2', formatMetric(f.cabin_co2_mmhg, 'mmHg', 1)]
    ];

    snapEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:16px;">
        <div>
          <span class="mono-num" style="font-size:11px;color:var(--accent-vermilion-paper);letter-spacing:0.06em;">${esc(record.sourceLabel)}</span>
          <h2 style="font-size:21px;margin-top:4px;">Your Recorded State: ${esc(envMeta.label || record.environment)}</h2>
          <p class="mono-num" style="font-size:12px;color:var(--ink-muted-paper);margin-top:4px;">
            ${esc(envMeta.gravity || '')} · ${obsCount}/13 channels measured · Physical &amp; environmental telemetry focus
          </p>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          <span class="badge ${tierBadgeClass}">${esc(metrics.status)} · Readiness ${Number.isFinite(metrics.readinessScore) ? metrics.readinessScore : '--'}/100</span>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:10px;">
        ${pillItems.map(([lbl, val]) => `
          <div style="padding:8px 10px;border:1px solid var(--border-paper);border-radius:6px;background:rgba(255,255,255,0.55);">
            <div class="mono-num" style="font-size:10px;color:var(--ink-muted-paper);text-transform:uppercase;">${esc(lbl)}</div>
            <div class="mono-num" style="font-size:13.5px;font-weight:700;margin-top:2px;">${esc(val)}</div>
          </div>
        `).join('')}
      </div>
    `;

    // Match physical & environmental rules
    const matchedRules = PHYSICAL_CONDITION_GUIDES.filter((rule) => rule.match(f, envMeta));
    const matchedRiskIds = new Set();
    const matchedProtocolIds = new Set();

    matchedRules.forEach((r) => {
      (r.riskIds || []).forEach((id) => matchedRiskIds.add(String(id)));
      (r.protocolIds || []).forEach((pid) => matchedProtocolIds.add(pid));
    });
    if (evalOut && Array.isArray(evalOut.nasaRiskDrivers)) {
      evalOut.nasaRiskDrivers.forEach((d) => matchedRiskIds.add(String(d.nasaRiskId)));
    }
    if (evalOut && evalOut.predictedClass >= 1) {
      const bundle = global.NASA_DATA_BUNDLE || {};
      (bundle.emergencyProtocols || []).forEach((p) => {
        if (matchedRiskIds.has(String(p.nasa_risk_id))) matchedProtocolIds.add(p.protocol_id);
      });
    }

    const individualDirs = (evalOut && evalOut.directives ? evalOut.directives : []).filter((d) => {
      if (!d || !d.title || !d.detail) return false;
      if (d.feature === 'mood_score') return false;
      const prio = String(d.priority || '').toLowerCase();
      return !['routine', 'essential', 'nominal', 'optimal'].includes(prio);
    });

    const ruleCardsHtml = matchedRules.map((rule) => `
      <article class="ledger-card" style="border-left:4px solid ${rule.badgeClass === 'badge-critical' ? 'var(--accent-vermilion)' : 'var(--accent-caution, #C68B2C)'};">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
          <span class="badge ${rule.badgeClass}">${esc(rule.priority)} PRIORITY · PHYSICAL PLAN</span>
          <span class="mono-num" style="font-size:11.5px;color:var(--ink-muted-paper);">
            Trigger: ${esc(rule.triggerLabel(f))}
          </span>
        </div>
        <h3 style="font-size:17px;margin-bottom:6px;">${esc(rule.title)}</h3>
        <p style="font-size:13px;color:var(--ink-muted-paper);line-height:1.5;margin-bottom:10px;">${esc(rule.why)}</p>
        <ul style="padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:13px;line-height:1.45;">
          ${rule.actions.map((act) => `<li>${esc(act)}</li>`).join('')}
        </ul>
      </article>
    `).join('');

    const soloDirHtml = individualDirs.length ? `
      <article class="ledger-card">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;">
          <h3 style="font-size:16px;">Biomarker &amp; Kinematic Adjustments Required</h3>
          <span class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);">${individualDirs.length} specific trigger(s)</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;">
          ${individualDirs.map((d) => {
            const prio = String(d.priority || 'Monitor');
            const badgeCls = prio.toUpperCase() === 'CRITICAL' ? 'badge-critical' : 'badge-caution';
            return `
            <div style="padding:10px 12px;border:1px solid var(--border-paper);border-radius:6px;background:rgba(255,255,255,0.45);">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:3px;">
                <strong style="font-size:13.5px;">${esc(d.title)}</strong>
                <span class="badge ${badgeCls}">${esc(prio)}</span>
              </div>
              <p style="font-size:12.5px;color:var(--ink-muted-paper);line-height:1.45;">${esc(d.detail)}</p>
            </div>`;
          }).join('')}
        </div>
      </article>` : '';

    const habitatSteps = HABITAT_ROUTINES[record.environment] || HABITAT_ROUTINES['Space Station'];
    const optimalFallbackHtml = (!matchedRules.length && !individualDirs.length) ? `
      <article class="ledger-card" style="border-left:4px solid var(--accent-nominal);">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
          <span class="badge badge-nominal">NOMINAL · PREVENTIVE MAINTENANCE</span>
          <span class="mono-num" style="font-size:11.5px;color:var(--ink-muted-paper);">${esc(envMeta.label || record.environment)}</span>
        </div>
        <h3 style="font-size:17px;margin-bottom:6px;">Cleared for Normal Mission Operations</h3>
        <p style="font-size:13px;color:var(--ink-muted-paper);line-height:1.5;margin-bottom:10px;">
          All measured physical vitals and kinematics sit within nominal aerospace envelopes. Maintain habitat-specific countermeasures:
        </p>
        <ul style="padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:13px;line-height:1.45;">
          ${habitatSteps.map((st) => `<li>${esc(st)}</li>`).join('')}
          <li>Protect a consistent 7.5-8.5 hr sleep window and re-run baseline gait + optical rPPG calibration on schedule.</li>
        </ul>
      </article>` : `
      <article class="ledger-card">
        <div class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);margin-bottom:6px;">HABITAT COUNTERMEASURE CONTEXT · ${esc((envMeta.label || record.environment).toUpperCase())}</div>
        <ul style="padding-left:18px;display:flex;flex-direction:column;gap:4px;font-size:12.5px;color:var(--ink-muted-paper);">
          ${habitatSteps.map((st) => `<li>${esc(st)}</li>`).join('')}
        </ul>
      </article>`;

    planEl.innerHTML = `
      <div class="section-header-rule" style="margin-bottom:4px;">
        <h2 class="section-title" style="font-size:21px;">Tailored Physical &amp; Habitat Action Plan</h2>
        <span class="section-meta">${matchedRules.length} physical plan(s) · ${individualDirs.length} biomarker action(s)</span>
      </div>
      ${ruleCardsHtml}
      ${soloDirHtml}
      ${optimalFallbackHtml}
    `;

    // Matched HRP risks & triggered emergency checklists rendered as compact click-to-expand accordions
    const bundle = global.NASA_DATA_BUNDLE || {};
    const relatedRisks = (bundle.hrpRisks || []).filter((r) => matchedRiskIds.has(String(r.risk_id)));
    const relatedProtocols = (bundle.emergencyProtocols || []).filter((p) => matchedProtocolIds.has(p.protocol_id));

    if (!relatedRisks.length && !relatedProtocols.length) {
      hrpEl.innerHTML = '';
    } else {
      hrpEl.innerHTML = `
        <div class="section-header-rule" style="margin-bottom:4px;">
          <h2 class="section-title" style="font-size:19px;">Triggered NASA Alerts &amp; Quick Checklists</h2>
          <span class="section-meta">${relatedProtocols.length} checklist(s) · ${relatedRisks.length} risk(s) — click any row to inspect</span>
        </div>
        <div class="cards-grid-2">
          ${relatedProtocols.map((p, idx) => `
            <details class="guide-accordion" ${idx === 0 ? 'open' : ''} style="border-left:4px solid var(--accent-vermilion);">
              <summary>
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                  <span class="badge badge-critical">${esc(p.badge)}</span>
                  <strong style="font-size:14px;">${esc(p.title)}</strong>
                </div>
                <span class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);">Expand &darr;</span>
              </summary>
              <div class="guide-accordion-body">
                <p style="color:var(--ink-muted-paper);margin-bottom:8px;"><strong>When to run:</strong> ${esc(p.trigger_condition)}</p>
                <ol style="padding-left:18px;display:flex;flex-direction:column;gap:4px;margin-bottom:10px;">
                  ${(p.steps || []).map((st) => `<li>${esc(st)}</li>`).join('')}
                </ol>
                <button type="button" class="btn-secondary open-sos-shortcut" data-proto="${esc(p.protocol_id)}" style="padding:5px 10px;font-size:11.5px;">Open in SOS Modal</button>
              </div>
            </details>
          `).join('')}
          ${relatedRisks.map((r) => `
            <details class="guide-accordion">
              <summary>
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                  <span class="badge badge-caution">Risk ${esc(r.risk_id)}</span>
                  <strong style="font-size:13.5px;">${esc(r.short_title)}</strong>
                </div>
                <span class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);">${esc(r.hrp_element)} &darr;</span>
              </summary>
              <div class="guide-accordion-body">
                <p style="color:var(--ink-dark);margin-bottom:4px;">${esc(r.risk_statement)}</p>
                <p style="color:var(--ink-muted-paper);font-size:12px;">${esc(r.clinical_context)}</p>
              </div>
            </details>
          `).join('')}
        </div>
      `;
      hrpEl.querySelectorAll('.open-sos-shortcut').forEach((btn) => {
        btn.addEventListener('click', () => {
          global.BioShell?.openEmergencyModal(btn.getAttribute('data-proto'));
        });
      });
    }
  }

  function matchesFilter(textParts, query) {
    if (!query) return true;
    const hay = textParts.filter(Boolean).join(' ').toLowerCase();
    return hay.includes(query);
  }

  function renderGuide() {
    const bundle = global.NASA_DATA_BUNDLE || {};
    const wrap = document.getElementById('guideSectionsWrap');
    const countEl = document.getElementById('guideMatchCount');
    const esc = global.BioShell ? global.BioShell.escapeHtml : (s) => String(s || '');
    if (!wrap) return;

    const query = (document.getElementById('guideSearchInput')?.value || '').trim().toLowerCase();
    const elemFilter = document.getElementById('hrpElementSelect')?.value || 'all';

    const hazards = (bundle.hazards || []).filter((h) => matchesFilter([h.code, h.title, h.summary], query));
    const risks = (bundle.hrpRisks || []).filter((r) => {
      const elemOk = elemFilter === 'all' || r.hrp_element === elemFilter;
      return elemOk && matchesFilter([r.risk_id, r.short_title, r.full_title, r.hrp_element, r.risk_statement, r.clinical_context], query);
    });
    const systems = (bundle.bodySystems || []).filter((b) =>
      matchesFilter([b.body_region, (b.nasa_risk_ids || []).join(' '), b.key_conditions, b.measurable_indicators, b.prevention_and_treatment], query)
    );
    const protocols = (bundle.emergencyProtocols || []).filter((p) =>
      matchesFilter([p.protocol_id, p.title, p.badge, p.nasa_risk_id, p.trigger_condition, (p.steps || []).join(' ')], query)
    );

    const blocks = [];
    let totalShown = 0;
    const autoOpenFirst = activeTab !== 'all' || query.length > 0;

    if (activeTab === 'all' || activeTab === 'protocols') {
      totalShown += protocols.length;
      if (protocols.length > 0) {
        blocks.push(`
          <section id="protocols">
            <div class="section-header-rule" style="margin-bottom:10px;">
              <h3 class="section-title" style="font-size:17px;">Emergency Flight Checklists</h3>
              <span class="section-meta">${protocols.length} checklist(s)</span>
            </div>
            <div class="cards-grid-2">
              ${protocols.map((p, i) => `
                <details class="guide-accordion" ${autoOpenFirst && i === 0 ? 'open' : ''} style="border-left:3px solid var(--accent-vermilion);">
                  <summary>
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                      <span class="badge badge-critical">${esc(p.badge)}</span>
                      <strong style="font-size:14px;">${esc(p.title)}</strong>
                    </div>
                    <span class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);">Steps &darr;</span>
                  </summary>
                  <div class="guide-accordion-body">
                    <p style="color:var(--ink-muted-paper);margin-bottom:6px;"><strong>Trigger:</strong> ${esc(p.trigger_condition)}</p>
                    <ol style="padding-left:18px;display:flex;flex-direction:column;gap:4px;margin-bottom:10px;">
                      ${(p.steps || []).map((st) => `<li>${esc(st)}</li>`).join('')}
                    </ol>
                    <button type="button" class="btn-secondary open-sos-shortcut" data-proto="${esc(p.protocol_id)}" style="padding:5px 10px;font-size:11.5px;">Open in SOS Modal</button>
                  </div>
                </details>
              `).join('')}
            </div>
          </section>`);
      }
    }

    if (activeTab === 'all' || activeTab === 'systems') {
      totalShown += systems.length;
      if (systems.length > 0) {
        blocks.push(`
          <section id="systems">
            <div class="section-header-rule" style="margin-bottom:10px;">
              <h3 class="section-title" style="font-size:17px;">5 Crew Body Systems</h3>
              <span class="section-meta">${systems.length} organ group(s)</span>
            </div>
            <div class="cards-grid-2">
              ${systems.map((b, i) => `
                <details class="guide-accordion" ${autoOpenFirst && i === 0 ? 'open' : ''}>
                  <summary>
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                      <span class="badge badge-nominal">SYSTEM</span>
                      <strong style="font-size:14px;">${esc(b.body_region)}</strong>
                    </div>
                    <span class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);">Details &darr;</span>
                  </summary>
                  <div class="guide-accordion-body">
                    <p style="margin-bottom:5px;"><strong>Conditions:</strong> ${esc(b.key_conditions)}</p>
                    <p style="margin-bottom:5px;"><strong>Monitored Vitals:</strong> ${esc(b.measurable_indicators)}</p>
                    <p style="color:var(--accent-nominal);"><strong>NASA Prevention:</strong> ${esc(b.prevention_and_treatment)}</p>
                  </div>
                </details>
              `).join('')}
            </div>
          </section>`);
      }
    }

    if (activeTab === 'all' || activeTab === 'hazards') {
      totalShown += hazards.length;
      if (hazards.length > 0) {
        blocks.push(`
          <section id="hazards">
            <div class="section-header-rule" style="margin-bottom:10px;">
              <h3 class="section-title" style="font-size:17px;">5 Spaceflight Hazards (RIDGE)</h3>
              <span class="section-meta">${hazards.length} hazard(s)</span>
            </div>
            <div class="cards-grid-2">
              ${hazards.map((h, i) => `
                <details class="guide-accordion" ${autoOpenFirst && i === 0 ? 'open' : ''}>
                  <summary>
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                      <span class="badge badge-ghost">${esc(h.code)}</span>
                      <strong style="font-size:14px;">${esc(h.title)}</strong>
                    </div>
                    <span class="mono-num" style="font-size:11px;color:var(--ink-muted-paper);">Read &darr;</span>
                  </summary>
                  <div class="guide-accordion-body">
                    <p style="color:var(--ink-muted-paper);">${esc(h.summary)}</p>
                  </div>
                </details>
              `).join('')}
            </div>
          </section>`);
      }
    }

    if (activeTab === 'all' || activeTab === 'hrp') {
      totalShown += risks.length;
      if (risks.length > 0) {
        blocks.push(`
          <section id="hrp">
            <div class="section-header-rule" style="margin-bottom:10px;">
              <h3 class="section-title" style="font-size:17px;">NASA HRP Clinical Risk Index</h3>
              <span class="section-meta">${risks.length} risk(s)</span>
            </div>
            <div class="cards-grid-2">
              ${risks.map((r) => `
                <details class="guide-accordion">
                  <summary>
                    <div style="display:flex;align-items:center;gap:8px;min-width:0;">
                      <span class="badge badge-caution" style="flex-shrink:0;">${esc(r.risk_id)}</span>
                      <strong style="font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(r.short_title)}</strong>
                    </div>
                    <span class="mono-num" style="font-size:10.5px;color:var(--ink-muted-paper);flex-shrink:0;">${esc(r.hrp_element)} &darr;</span>
                  </summary>
                  <div class="guide-accordion-body">
                    <p style="color:var(--ink-dark);margin-bottom:5px;">${esc(r.risk_statement)}</p>
                    <p style="color:var(--ink-muted-paper);font-size:12px;">${esc(r.clinical_context)}</p>
                  </div>
                </details>
              `).join('')}
            </div>
          </section>`);
      }
    }

    wrap.innerHTML = blocks.length
      ? blocks.join('')
      : `<p class="mono-num" style="font-size:12.5px;color:var(--ink-muted-paper);padding:12px;">No matching topics found — clear search text or switch topic category.</p>`;
    if (countEl) countEl.textContent = `${totalShown} topic(s)`;

    wrap.querySelectorAll('.open-sos-shortcut').forEach((btn) => {
      btn.addEventListener('click', () => {
        global.BioShell?.openEmergencyModal(btn.getAttribute('data-proto'));
      });
    });
  }

  function bootstrapGuide() {
    if (global.BioShell) {
      global.BioShell.renderShellChrome({ activeRoute: 'guide.html', showFooter: true });
    }
    const esc = global.BioShell ? global.BioShell.escapeHtml : (s) => String(s);

    const sourceSel = document.getElementById('personalSourceSelect');
    const syncSourceSelect = (recordsList, preferredKey) => {
      if (!sourceSel) return preferredKey || (recordsList[0] ? recordsList[0].key : '');
      sourceSel.innerHTML = recordsList.length
        ? recordsList.map((r) => `<option value="${esc(r.key)}">${esc(r.selectLabel)}</option>`).join('')
        : '<option value="">No recorded scans yet</option>';
      const chosen = (preferredKey && recordsList.some((r) => r.key === preferredKey))
        ? preferredKey
        : (recordsList[0] ? recordsList[0].key : '');
      if (chosen) sourceSel.value = chosen;
      return chosen;
    };

    const records = resolveGuidanceRecords();
    const initialKey = syncSourceSelect(records);
    if (sourceSel) {
      sourceSel.addEventListener('change', () => renderPersonalizedGuide(resolveGuidanceRecords(), sourceSel.value));
    }
    renderPersonalizedGuide(records, initialKey);

    const sel = document.getElementById('hrpElementSelect');
    const risks = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.hrpRisks) || [];
    if (sel) {
      const elements = Array.from(new Set(risks.map((r) => r.hrp_element).filter(Boolean))).sort();
      sel.innerHTML = '<option value="all">All HRP Elements</option>' +
        elements.map((e) => `<option value="${esc(e)}">${esc(e)}</option>`).join('');
      sel.addEventListener('change', renderGuide);
    }

    document.getElementById('guideSearchInput')?.addEventListener('input', renderGuide);

    document.querySelectorAll('[data-guide-tab]').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeTab = btn.getAttribute('data-guide-tab') || 'all';
        document.querySelectorAll('[data-guide-tab]').forEach((b) => b.classList.toggle('active', b === btn));
        renderGuide();
      });
    });

    const hashDrawer = global.location.hash;
    if (hashDrawer === '#protocols' || hashDrawer === '#hrp' || hashDrawer === '#hazards') {
      activeTab = hashDrawer.slice(1);
      const drawer = document.getElementById('referenceLibraryDrawer');
      if (drawer) drawer.open = true;
    }

    document.querySelectorAll('[data-guide-tab]').forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-guide-tab') === activeTab);
    });

    renderGuide();

    global.guidePage = {
      refreshPersonalized: (preferredKey) => {
        const recs = resolveGuidanceRecords();
        const chosen = syncSourceSelect(recs, preferredKey);
        renderPersonalizedGuide(recs, chosen);
      },
      renderGuide
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapGuide);
  } else {
    bootstrapGuide();
  }
})(typeof window !== 'undefined' ? window : globalThis);
