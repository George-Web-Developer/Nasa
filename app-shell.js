/**
 * Bio Astro Lab — Shared Application Shell, State Persistence, Safe Parsers,
 * 6-Protocol NASA Emergency Drawer & Bilingual Bio-Copilot.
 */
(function (global) {
  'use strict';

  const STORAGE_KEYS = {
    session: 'bioAstroLab.session.v1',
    history: 'bioAstroLab.history.v1',
    env: 'bioAstroLab.env.v1',
    crew: 'bioAstroLab.crew.v1',
    lang: 'bioAstroLab.lang.v1',
    theme: 'bioAstroLab.theme.v1',
    footer: 'bioAstroLab.footerCredits.v1',
    portrait: 'bioAstroLab.facePortrait',
    chatbotApiBase: 'bioAstroLab.chatbotApiBase.v1'
  };

  const CREW_PROFILES = [
    { id: 'C001', name: 'C001 — Commander Alex', role: 'Commander' },
    { id: 'C002', name: 'C002 — Dr. Sara', role: 'Crew Medical Officer' },
    { id: 'C003', name: 'C003 — Eng. Omar', role: 'Flight Engineer' }
  ];

  const UI_TRANSLATIONS = {
    en: {
      'nav.index.html': 'Mission',
      'nav.scan.html': 'Scan',
      'nav.decision.html': 'Decision',
      'nav.history.html': 'History',
      'nav.guide.html': 'NASA Guide',
      'scan.title': 'Crew Physical Health Scan',
      'scan.presets.title': 'Quick Mission Presets',
      'scan.presets.sub': 'Load sample NASA flight vitals into the 9 inputs below, or enter your own readings.',
      'scan.stage2.btn': 'Continue to Stage 2 Camera Check →',
      'scan.decision.btn': 'Run Clinical Evaluation →',
      'scan.back.btn': '← Edit Stage 1 Vitals',
      'decision.title': 'Physiological Decision & Body Inspector',
      'decision.back': '← Back to Scan',
      'decision.save': 'Save to History',
      'decision.print': 'Print / Save PDF Report',
      'decision.history': 'Open History & Trends →',
      'decision.sim.toggle': 'Adjust Any Input Live (What-If Simulator)',
      'history.title': 'Mission Physiological History',
      'history.new': '+ New Check-in',
      'guide.title': 'NASA Space Health Guide & Action Hub',
      'guide.scan': 'Run Crew Health Scan →'
    },
    ar: {
      'nav.index.html': 'الرئيسية',
      'nav.scan.html': 'الفحص',
      'nav.decision.html': 'القرار الطبي',
      'nav.history.html': 'السجل والرسوم',
      'nav.guide.html': 'دليل ناسا',
      'scan.title': 'الفحص الصحي البدني لرائد الفضاء',
      'scan.presets.title': 'سيناريوهات جاهزة سريعة',
      'scan.presets.sub': 'يمكنك تحميل قيم تجريبية جاهزة في الـ 9 خانات أو إدخال القيم يدوياً.',
      'scan.stage2.btn': 'الانتقال لمرحلة فحص الكاميرا ←',
      'scan.decision.btn': 'تحليل الذكاء الاصطناعي وعرض القرار ←',
      'scan.back.btn': '→ تعديل بيانات المرحلة الأولى',
      'decision.title': 'النتيجة الطبية وخريطة الجسم التفاعلية',
      'decision.back': '→ العودة للفحص',
      'decision.save': 'حفظ في السجل',
      'decision.print': 'طباعة / حفظ تقرير PDF',
      'decision.history': 'عرض السجل والرسوم ←',
      'decision.sim.toggle': 'تعديل أي مدخل يدوياً (محاكي السيناريوهات)',
      'history.title': 'السجل الطبي وتطور المؤشرات',
      'history.new': '+ فحص جديد',
      'guide.title': 'دليل صحة الفضاء وخطة العمل المخصصة',
      'guide.scan': 'بدء فحص جديد ←'
    }
  };

  const FEATURE_KEYS = [
    'blood_glucose',
    'systolic_bp',
    'diastolic_bp',
    'body_temp',
    'sleep_hours',
    'mood_score',
    'balance_score',
    'joint_symmetry_diff',
    'facial_ear',
    'heart_rate_bpm',
    'spo2_pct',
    'radiation_dose_msv',
    'cabin_co2_mmhg'
  ];

  const NAV_ROUTES = [
    { href: 'index.html', label: 'Mission' },
    { href: 'scan.html', label: 'Scan' },
    { href: 'decision.html', label: 'Decision' },
    { href: 'tracking.html', label: 'Tracking' },
    { href: 'astra.html', label: 'Muscle Missions' },
    { href: 'history.html', label: 'History' },
    { href: 'guide.html', label: 'NASA Guide' },
    { href: 'assistant.html', label: 'Assistant' }
  ];

  const DEFAULT_LOCAL_CHATBOT_API = 'http://127.0.0.1:8000';

  function isLocalOrigin(loc) {
    const target = loc || (typeof window !== 'undefined' ? window.location : null);
    if (!target) return true;
    const proto = String(target.protocol || '').toLowerCase();
    if (proto === 'file:' || proto === 'about:') return true;
    const host = String(target.hostname || '').toLowerCase();
    return host === '' || host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]' || host.endsWith('.local');
  }

  function normalizeChatbotApiUrl(raw) {
    const trimmed = String(raw || '').trim().replace(/\/+$/, '');
    if (!trimmed) return '';
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
      return parsed.href.replace(/\/+$/, '');
    } catch (_err) {
      return '';
    }
  }

  function resolveChatbotApiBase(loc) {
    const target = loc || (typeof window !== 'undefined' ? window.location : null);
    try {
      const search = target && target.search ? String(target.search) : '';
      if (search) {
        const params = new URLSearchParams(search);
        const queryApi = normalizeChatbotApiUrl(params.get('api'));
        if (queryApi) {
          if (typeof window !== 'undefined' && target === window.location && typeof localStorage !== 'undefined') {
            localStorage.setItem(STORAGE_KEYS.chatbotApiBase, queryApi);
          }
          return queryApi;
        }
      }
    } catch (_err) {}

    const globalOverride = normalizeChatbotApiUrl(global.BIO_ASTRO_CHATBOT_API);
    if (globalOverride) return globalOverride;

    try {
      if (typeof localStorage !== 'undefined') {
        const stored = normalizeChatbotApiUrl(localStorage.getItem(STORAGE_KEYS.chatbotApiBase));
        if (stored) return stored;
      }
    } catch (_err) {}

    return isLocalOrigin(target) ? DEFAULT_LOCAL_CHATBOT_API : '';
  }

  function getChatbotApiBase() {
    return resolveChatbotApiBase(typeof window !== 'undefined' ? window.location : null);
  }

  function setChatbotApiBase(url) {
    const clean = normalizeChatbotApiUrl(url);
    try {
      if (typeof localStorage !== 'undefined') {
        if (clean) {
          localStorage.setItem(STORAGE_KEYS.chatbotApiBase, clean);
        } else {
          localStorage.removeItem(STORAGE_KEYS.chatbotApiBase);
        }
      }
    } catch (_err) {}
    return clean || getChatbotApiBase();
  }
  const CREW_CHAT_ID_MAP = {
    C001: 1,
    C002: 1,
    C003: 1
  };

  const CSV_COLUMN_MAP = {
    blood_glucose: 'blood_glucose',
    glucose: 'blood_glucose',
    glucose_mg_dl: 'blood_glucose',
    glucose_value_milligram_per_deciliter: 'blood_glucose',
    systolic_bp: 'systolic_bp',
    systolic: 'systolic_bp',
    sbp: 'systolic_bp',
    diastolic_bp: 'diastolic_bp',
    diastolic: 'diastolic_bp',
    dbp: 'diastolic_bp',
    bp: 'blood_pressure_str',
    blood_pressure: 'blood_pressure_str',
    body_temp: 'body_temp',
    temp: 'body_temp',
    temperature: 'body_temp',
    temp_c: 'body_temp',
    sleep_hours: 'sleep_hours',
    sleep: 'sleep_hours',
    mood_score: 'mood_score',
    mood: 'mood_score',
    balance_score: 'balance_score',
    posture_score: 'balance_score',
    posture: 'balance_score',
    joint_symmetry_diff: 'joint_symmetry_diff',
    symmetry_diff: 'joint_symmetry_diff',
    joint_diff: 'joint_symmetry_diff',
    symmetry_coeff: 'symmetry_coeff_alias',
    symmetry: 'joint_symmetry_diff',
    facial_ear: 'facial_ear',
    ear_fatigue: 'facial_ear',
    ear: 'facial_ear',
    heart_rate_bpm: 'heart_rate_bpm',
    heart_rate: 'heart_rate_bpm',
    hr: 'heart_rate_bpm',
    hr_bpm: 'heart_rate_bpm',
    radiation_dose_msv: 'radiation_dose_msv',
    radiation_msv_day: 'radiation_dose_msv',
    radiation: 'radiation_dose_msv',
    cabin_co2_mmhg: 'cabin_co2_mmhg',
    co2: 'cabin_co2_mmhg',
    ppco2: 'cabin_co2_mmhg',
    spo2_pct: 'spo2_pct',
    spo2: 'spo2_pct'
  };

  const DEFAULT_FOOTER_CREDITS = {
    crewLead: 'Flight Surgeon & Crew Architecture (Click to edit)',
    missionOrg: 'NASA Space Apps 2026 — Bio Astro Lab',
    groundStation: 'Houston / Orbital Relay Node 04 (Click to edit)',
    telemetryNote: 'NASA HRP, RIDGE Hazards & OSDR Inspiration4 Matrix'
  };

  function safeJsonParse(raw, fallback) {
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function sanitizeCsvCell(value) {
    if (value == null) return '';
    let str = String(value);
    if (/^[=+\-@\t\r]/.test(str)) {
      str = "'" + str;
    }
    if (/[",\n\r']/.test(str)) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  function parseCsvLine(line) {
    const cells = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === ',' && !inQuotes) {
        cells.push(current.trim());
        current = '';
      } else {
        current += ch;
      }
    }
    cells.push(current.trim());
    return cells;
  }

  function toOptionalFloat(raw) {
    if (raw == null) return NaN;
    const cleaned = String(raw).replace(/^'/, '').trim();
    if (!cleaned || cleaned.toLowerCase() === 'nan' || cleaned === '--') return NaN;
    const num = Number(cleaned);
    return Number.isFinite(num) ? num : NaN;
  }

  function createBlankFeatures() {
    const out = {};
    for (const k of FEATURE_KEYS) out[k] = NaN;
    return out;
  }

  function normalizeFeatures(input) {
    const out = createBlankFeatures();
    if (!input || typeof input !== 'object') return out;
    const aliases = {
      balance_score: input.posture_score,
      facial_ear: input.ear_fatigue,
      heart_rate_bpm: input.heart_rate,
      radiation_dose_msv: input.radiation_msv_day
    };
    for (const k of FEATURE_KEYS) {
      const val = input[k] !== undefined ? input[k] : aliases[k];
      out[k] = typeof val === 'number' && Number.isFinite(val) ? val : NaN;
    }
    if (!Number.isFinite(out.joint_symmetry_diff) && typeof input.symmetry_coeff === 'number' && Number.isFinite(input.symmetry_coeff)) {
      const approxDeg = Math.max(0, Math.min(45, (1.0 - input.symmetry_coeff) * 180 / 0.45));
      out.joint_symmetry_diff = Number(approxDeg.toFixed(2));
    }
    return out;
  }

  function serializeFeatures(input) {
    const out = {};
    for (const k of FEATURE_KEYS) {
      const v = input ? input[k] : NaN;
      out[k] = typeof v === 'number' && Number.isFinite(v) ? v : null;
    }
    return out;
  }

  function parseCsvTable(csvText) {
    const lines = String(csvText || '')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .split('\n')
      .filter((l) => l.trim().length > 0);
    if (lines.length < 2) {
      return { headers: [], rows: [], mappedTelemetry: [], serumRows: [] };
    }

    const headers = parseCsvLine(lines[0]).map((h) => h.replace(/^\uFEFF/, '').trim());
    const rows = [];
    const mappedTelemetry = [];
    const serumRows = [];

    for (let r = 1; r < lines.length; r++) {
      const cols = parseCsvLine(lines[r]);
      const rowObj = {};
      const feat = createBlankFeatures();
      const serum = {};

      headers.forEach((hdr, idx) => {
        const rawVal = cols[idx] !== undefined ? cols[idx] : '';
        rowObj[hdr] = rawVal;
        const normKey = hdr.toLowerCase().replace(/[\s-]+/g, '_');
        const target = CSV_COLUMN_MAP[normKey];
        if (target === 'blood_pressure_str') {
          const m = String(rawVal).match(/(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)/);
          if (m) {
            feat.systolic_bp = Number(m[1]);
            feat.diastolic_bp = Number(m[2]);
          }
        } else if (target === 'symmetry_coeff_alias') {
          const coeff = toOptionalFloat(rawVal);
          if (Number.isFinite(coeff)) {
            feat.joint_symmetry_diff = Number(Math.max(0, Math.min(45, (1.0 - coeff) * 180 / 0.45)).toFixed(2));
          }
        } else if (target) {
          feat[target] = toOptionalFloat(rawVal);
        }

        if (normKey === 'subject') serum.subject = rawVal;
        else if (normKey === 'crew_tp' && rawVal) serum.subject = rawVal;
        else if (!serum.subject && normKey === 'sample_name') serum.subject = rawVal;
        if (normKey === 'mission_phase') serum.mission_phase = rawVal;
        const isBoundOrRatio =
          normKey.includes('range_min') ||
          normKey.includes('range_max') ||
          normKey.includes('_ratio');
        const isPercent = normKey.includes('percent');
        if (!isBoundOrRatio && !isPercent && (normKey === 'albumin_g_dl' || normKey === 'albumin_value_gram_per_deciliter' || normKey === 'albumin')) {
          serum.albumin_g_dl = toOptionalFloat(rawVal);
        }
        if (!isBoundOrRatio && (normKey === 'hemoglobin_g_dl' || normKey === 'hemoglobin_value_gram_per_deciliter' || normKey === 'hemoglobin_value_percent' || normKey === 'hemoglobin')) {
          serum.hemoglobin_g_dl = toOptionalFloat(rawVal);
        }
        if (!isBoundOrRatio && !isPercent && (normKey === 'wbc_10e3_ul' || normKey === 'white_blood_cell_count_10_3_per_microliter' || normKey === 'white_blood_cell_count_value_thousand_per_microliter' || normKey === 'wbc')) {
          serum.wbc_10e3_ul = toOptionalFloat(rawVal);
        }
        if (!isBoundOrRatio && !isPercent) {
          if (normKey === 'crp_concentration_picogram_per_milliliter') {
            const pg = toOptionalFloat(rawVal);
            serum.crp_mg_l = Number.isFinite(pg) ? Number((pg / 1e6).toFixed(2)) : NaN;
          } else if (normKey === 'crp_mg_l' || normKey === 'crp_concentration_milligram_per_liter' || normKey === 'crp') {
            serum.crp_mg_l = toOptionalFloat(rawVal);
          }
        }
        if (!isBoundOrRatio && !isPercent && (normKey === 'glucose_mg_dl' || normKey === 'glucose_value_milligram_per_deciliter' || normKey === 'glucose')) {
          serum.glucose_mg_dl = toOptionalFloat(rawVal);
        }
      });

      rows.push(rowObj);
      mappedTelemetry.push(feat);
      if (serum.subject || Number.isFinite(serum.albumin_g_dl) || Number.isFinite(serum.hemoglobin_g_dl)) {
        serumRows.push(serum);
      }
    }

    return { headers, rows, mappedTelemetry, serumRows };
  }

  function getEnvironments() {
    return (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.environments) || [
      {
        id: 'Space Station',
        label: 'Space Station (LEO)',
        gravity: '0 g Microgravity',
        baselineRadiation: 0.55,
        baselineCO2: 2.3,
        pressurePsi: '14.7 psi N2/O2',
        brief: 'Cephalic fluid shift, spinal elongation, circadian drift across 16 orbital day/night cycles.'
      }
    ];
  }

  function getEnvironmentMeta(envId) {
    const envs = getEnvironments();
    return envs.find((e) => e.id === envId) || envs[0];
  }

  function getEnvironment() {
    const saved = global.localStorage ? global.localStorage.getItem(STORAGE_KEYS.env) : null;
    const valid = getEnvironments().some((e) => e.id === saved);
    return valid ? saved : 'Space Station';
  }

  function setEnvironment(envId) {
    const meta = getEnvironmentMeta(envId);
    const chosen = meta.id;
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.env, chosen);
    }
    const sel = document.getElementById('globalEnvSelect');
    if (sel && sel.value !== chosen) sel.value = chosen;
    document.dispatchEvent(new CustomEvent('bio:env-change', { detail: { environment: chosen, meta } }));
    return chosen;
  }

  function getCrewProfiles() {
    return CREW_PROFILES.slice();
  }

  function getCrewProfile() {
    const saved = global.localStorage ? safeJsonParse(global.localStorage.getItem(STORAGE_KEYS.crew), null) : null;
    if (saved && saved.id) return saved;
    return CREW_PROFILES[0];
  }

  function setCrewProfile(profileOrId) {
    let next = CREW_PROFILES[0];
    if (typeof profileOrId === 'string') {
      const found = CREW_PROFILES.find((p) => p.id === profileOrId);
      next = found || { id: profileOrId, name: profileOrId, role: 'Crew Member' };
    } else if (profileOrId && typeof profileOrId === 'object') {
      next = {
        id: String(profileOrId.id || 'C001'),
        name: String(profileOrId.name || profileOrId.id || 'C001'),
        role: String(profileOrId.role || 'Crew Member')
      };
    }
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.crew, JSON.stringify(next));
    }
    document.dispatchEvent(new CustomEvent('bio:crew-change', { detail: next }));
    return next;
  }

  function getUiLang() {
    return 'en';
  }

  function applyUiTranslations() {
    if (typeof document === 'undefined') return;
    const dict = UI_TRANSLATIONS.en;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (key && dict[key]) el.textContent = dict[key];
    });
    if (document.documentElement) {
      document.documentElement.setAttribute('data-ui-lang', 'en');
    }
  }

  function setUiLang() {
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.lang, 'en');
    }
    applyUiTranslations('en');
    document.dispatchEvent(new CustomEvent('bio:lang-change', { detail: { lang: 'en' } }));
    return 'en';
  }

  function getTheme() {
    if (typeof window === 'undefined' || !global.localStorage) return 'dark';
    const saved = global.localStorage.getItem(STORAGE_KEYS.theme);
    return saved === 'light' ? 'light' : 'dark';
  }

  function setTheme(newTheme) {
    const theme = newTheme === 'light' ? 'light' : 'dark';
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.theme, theme);
    }
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme);
      const btn = document.getElementById('globalThemeToggle');
      if (btn) {
        btn.setAttribute('data-theme', theme);
        btn.setAttribute('title', theme === 'dark' ? 'Switch to Light Lab Mode' : 'Switch to Dark Cosmic Mode');
        btn.innerHTML = theme === 'dark'
          ? `<span class="theme-icon moon" aria-hidden="true">🌙</span><span class="theme-label sr-only">Dark Mode</span>`
          : `<span class="theme-icon sun" aria-hidden="true">☀️</span><span class="theme-label sr-only">Light Mode</span>`;
      }
    }
    document.dispatchEvent(new CustomEvent('bio:theme-change', { detail: { theme } }));
    return theme;
  }

  function toggleTheme() {
    const current = getTheme();
    return setTheme(current === 'dark' ? 'light' : 'dark');
  }

  function initTheme() {
    if (typeof document === 'undefined') return;
    const theme = getTheme();
    document.documentElement.setAttribute('data-theme', theme);
  }

  function initCosmicPreloader() {
    if (typeof document === 'undefined') return;
    if (!document.body) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCosmicPreloader, { once: true });
      }
      return;
    }
    if (document.getElementById('cosmicPreloader')) return;

    const preloader = document.createElement('div');
    preloader.id = 'cosmicPreloader';
    preloader.className = 'cosmic-preloader';
    preloader.innerHTML = `
      <div class="preloader-stars" aria-hidden="true"></div>
      <div class="preloader-core">
        <div class="orbital-sphere-stage">
          <div class="orbital-ring ring-outer"></div>
          <div class="orbital-ring ring-mid"></div>
          <div class="orbital-body earth-body">
            <div class="earth-atmosphere"></div>
            <div class="earth-landmass"></div>
          </div>
          <div class="orbital-satellite-orbit">
            <div class="orbital-satellite moon-body"></div>
          </div>
        </div>
        <div class="preloader-text-group">
          <div class="preloader-badge mono-num">BIO ASTRO LAB · ORBITAL TELEMETRY</div>
          <h2 class="preloader-title">Synchronizing Space Systems</h2>
          <div class="preloader-bar-wrap">
            <div id="preloaderProgressBar" class="preloader-bar-fill"></div>
          </div>
          <div id="preloaderStatusText" class="preloader-status mono-num">Calibrating physiological baselines...</div>
        </div>
      </div>
    `;
    document.body.prepend(preloader);

    const phases = [
      { pct: 20, text: 'Initializing Bio Astro Lab orbital telemetry...' },
      { pct: 45, text: 'Connecting spacecraft habitat sensors & biometrics...' },
      { pct: 72, text: 'Synchronizing NASA HRP clinical envelopes & flight telemetry...' },
      { pct: 90, text: 'Calibrating crew circadian baselines & exercise regimens...' },
      { pct: 100, text: 'Orbital telemetry online. Launching dashboard...' }
    ];

    let currentPhase = 0;
    const bar = document.getElementById('preloaderProgressBar');
    const status = document.getElementById('preloaderStatusText');

    const interval = setInterval(() => {
      if (currentPhase < phases.length) {
        if (bar) bar.style.width = phases[currentPhase].pct + '%';
        if (status) status.textContent = phases[currentPhase].text;
        currentPhase++;
      }
    }, 550);

    const dismiss = () => {
      clearInterval(interval);
      if (bar) bar.style.width = '100%';
      if (status) status.textContent = 'Orbital telemetry nominal.';
      setTimeout(() => {
        preloader.classList.add('preloader-fade-out');
        setTimeout(() => {
          if (preloader.parentNode) preloader.parentNode.removeChild(preloader);
        }, 500);
      }, 350);
    };

    // Keep preloader visible for ~2.8s to 3.2s so cosmic orbit animation is enjoyed
    setTimeout(dismiss, 2900);
  }

  function getSession() {
    if (!global.localStorage) return null;
    const parsed = safeJsonParse(global.localStorage.getItem(STORAGE_KEYS.session), null);
    if (!parsed || typeof parsed !== 'object') return null;
    return {
      environment: parsed.environment || getEnvironment(),
      scanMode: parsed.scanMode || 'Walk',
      scanDurationSec: parsed.scanDurationSec || 30,
      timestamp: parsed.timestamp || new Date().toISOString(),
      features: normalizeFeatures(parsed.features),
      meta: parsed.meta || {},
      result: parsed.result || null
    };
  }

  function saveSession(patch) {
    const existing = getSession() || {
      environment: getEnvironment(),
      scanMode: 'Walk',
      scanDurationSec: 30,
      timestamp: new Date().toISOString(),
      features: createBlankFeatures(),
      meta: {},
      result: null
    };
    const merged = {
      ...existing,
      ...patch,
      timestamp: (patch && patch.timestamp) || new Date().toISOString(),
      features: normalizeFeatures(patch && patch.features ? { ...existing.features, ...patch.features } : existing.features),
      meta: { ...(existing.meta || {}), ...((patch && patch.meta) || {}) }
    };
    if (global.localStorage) {
      const serializable = { ...merged, features: serializeFeatures(merged.features) };
      global.localStorage.setItem(STORAGE_KEYS.session, JSON.stringify(serializable));
    }
    return merged;
  }

  function clearSession() {
    if (global.localStorage) global.localStorage.removeItem(STORAGE_KEYS.session);
    if (global.sessionStorage) global.sessionStorage.removeItem(STORAGE_KEYS.portrait);
  }

  function getFacePortrait() {
    try {
      return global.sessionStorage ? global.sessionStorage.getItem(STORAGE_KEYS.portrait) : null;
    } catch {
      return null;
    }
  }

  function saveFacePortrait(dataUrl) {
    try {
      if (global.sessionStorage && dataUrl) {
        global.sessionStorage.setItem(STORAGE_KEYS.portrait, dataUrl);
      }
    } catch {
      // Ignore storage quota exceptions silently
    }
  }

  function extractRiskMetrics(evalOut) {
    if (!evalOut || typeof evalOut !== 'object') {
      return { status: 'Optimal', riskPct: NaN, confidencePct: NaN, readinessScore: NaN };
    }
    const probs = Array.isArray(evalOut.probabilities) ? evalOut.probabilities : [1, 0, 0];
    const rawRisk = (Number(probs[1] || 0) * 0.5 + Number(probs[2] || 0)) * 100;
    const confRaw = Number(evalOut.confidence);
    const confidencePct = Number.isFinite(confRaw)
      ? Number((confRaw <= 1 ? confRaw * 100 : confRaw).toFixed(1))
      : NaN;
    return {
      status: evalOut.predictedLabel || evalOut.predictedClassName || 'Optimal',
      riskPct: Number(rawRisk.toFixed(1)),
      confidencePct,
      readinessScore: Number.isFinite(evalOut.readinessScore) ? evalOut.readinessScore : NaN
    };
  }

  function buildSeedHistory() {
    const presets = (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.missionPresets) || [];
    const evalFn = typeof global.evaluateAstronautHealth === 'function' ? global.evaluateAstronautHealth : null;
    const now = Date.now();
    const hoursAgo = [72, 48, 24, 6];

    return presets.map((preset, idx) => {
      const feats = normalizeFeatures(preset.features);
      const evalOut = evalFn ? evalFn(feats) : null;
      const m = extractRiskMetrics(evalOut);
      return {
        id: 'SEED-' + (idx + 1),
        crewId: preset.crewId || 'C001',
        timestamp: new Date(now - (hoursAgo[idx] || (idx + 1) * 8) * 3600000).toISOString(),
        label: preset.label,
        environment: preset.environment || 'Space Station',
        scanMode: idx % 2 === 0 ? 'Walk' : 'Static',
        status: m.status,
        riskPct: Number.isFinite(m.riskPct) ? m.riskPct : 10,
        confidencePct: Number.isFinite(m.confidencePct) ? m.confidencePct : 90,
        features: serializeFeatures(feats),
        source: 'NASA Preset Seed'
      };
    });
  }

  function normalizeHistoryEntry(entry) {
    if (!entry || typeof entry !== 'object') return null;
    return {
      id: String(entry.id || 'LOG-' + Date.now()),
      crewId: String(entry.crewId || 'C001'),
      timestamp: entry.timestamp || new Date().toISOString(),
      label: String(entry.label || 'Crew Health Check-in'),
      environment: String(entry.environment || getEnvironment()),
      scanMode: String(entry.scanMode || 'Walk'),
      status: String(entry.status || 'NORMAL'),
      riskPct: Number.isFinite(Number(entry.riskPct)) ? Number(entry.riskPct) : NaN,
      confidencePct: Number.isFinite(Number(entry.confidencePct)) ? Number(entry.confidencePct) : NaN,
      features: entry.features ? serializeFeatures(normalizeFeatures(entry.features)) : serializeFeatures(createBlankFeatures()),
      source: String(entry.source || 'Crew Session')
    };
  }

  function getHistory() {
    if (!global.localStorage) return buildSeedHistory();
    const raw = safeJsonParse(global.localStorage.getItem(STORAGE_KEYS.history), null);
    if (!Array.isArray(raw) || raw.length === 0) {
      const seed = buildSeedHistory();
      global.localStorage.setItem(STORAGE_KEYS.history, JSON.stringify(seed));
      return seed;
    }
    return raw.map(normalizeHistoryEntry).filter(Boolean);
  }

  function appendHistory(entry) {
    const list = getHistory();
    const item = normalizeHistoryEntry(entry);
    if (!item) return list;
    const updated = [item, ...list].slice(0, 80);
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.history, JSON.stringify(updated));
    }
    return updated;
  }

  function resetHistoryToSeed() {
    const seed = buildSeedHistory();
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.history, JSON.stringify(seed));
    }
    return seed;
  }

  function replaceHistory(entries) {
    const cleaned = (entries || []).map(normalizeHistoryEntry).filter(Boolean);
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.history, JSON.stringify(cleaned));
    }
    return cleaned;
  }

  function exportHistoryCsv() {
    const rows = getHistory();
    const cols = ['id', 'timestamp', 'label', 'environment', 'scanMode', 'status', 'riskPct', ...FEATURE_KEYS];
    const headerLine = cols.map(sanitizeCsvCell).join(',');
    const bodyLines = rows.map((row) => {
      const f = row.features || {};
      const vals = [row.id, row.timestamp, row.label, row.environment, row.scanMode, row.status, row.riskPct, ...FEATURE_KEYS.map((k) => f[k])];
      return vals.map((v) => sanitizeCsvCell(v == null || (typeof v === 'number' && !Number.isFinite(v)) ? '' : v)).join(',');
    });
    return [headerLine, ...bodyLines].join('\n');
  }

  function getFooterCredits() {
    const saved = global.localStorage ? safeJsonParse(global.localStorage.getItem(STORAGE_KEYS.footer), {}) : {};
    return { ...DEFAULT_FOOTER_CREDITS, ...(saved || {}) };
  }

  function saveFooterCredits(patch) {
    const next = { ...getFooterCredits(), ...(patch || {}) };
    if (global.localStorage) {
      global.localStorage.setItem(STORAGE_KEYS.footer, JSON.stringify(next));
    }
    return next;
  }

  function showToast(message, variant) {
    let region = document.getElementById('toastRegion');
    if (!region) {
      region = document.createElement('div');
      region.id = 'toastRegion';
      region.className = 'toast-stack';
      region.setAttribute('aria-live', 'polite');
      document.body.appendChild(region);
    }
    const toast = document.createElement('div');
    toast.className = 'toast-item' + (variant === 'nominal' ? ' toast-nominal' : '');
    toast.textContent = String(message || '');
    region.appendChild(toast);
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 3600);
  }

  function getEmergencyProtocols() {
    return (global.NASA_DATA_BUNDLE && global.NASA_DATA_BUNDLE.emergencyProtocols) || [];
  }

  function selectEmergencySymptom(protocolId) {
    const protocols = getEmergencyProtocols();
    const chosen = protocols.find((p) => p.protocol_id === protocolId) || protocols[0];
    const buttons = document.querySelectorAll('[data-protocol-id]');
    buttons.forEach((btn) => {
      btn.classList.toggle('active', chosen && btn.getAttribute('data-protocol-id') === chosen.protocol_id);
    });
    const detail = document.getElementById('sosProtocolDetail');
    if (!detail || !chosen) return;

    const stepsHtml = (chosen.steps || [])
      .map((step, i) => `<li><strong>Step ${i + 1}:</strong> ${escapeHtml(step)}</li>`)
      .join('');
    detail.innerHTML = `
      <div class="ledger-card" style="background: var(--bg-paper);">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
          <strong style="font-size:15px;">${escapeHtml(chosen.title)}</strong>
          <span class="badge badge-critical">${escapeHtml(chosen.badge)} — ${escapeHtml(chosen.nasa_risk_id)}</span>
        </div>
        <p style="font-size:12.5px;color:var(--ink-muted-paper);margin-bottom:10px;">
          <strong>Trigger:</strong> ${escapeHtml(chosen.trigger_condition)}
        </p>
        <ol style="padding-left:18px;display:flex;flex-direction:column;gap:6px;font-size:13px;">
          ${stepsHtml}
        </ol>
      </div>`;
  }

  function openEmergencyModal(initialProtocolId) {
    const modal = document.getElementById('sosModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    const firstId = initialProtocolId || (getEmergencyProtocols()[0] && getEmergencyProtocols()[0].protocol_id);
    if (firstId) selectEmergencySymptom(firstId);
  }

  function closeEmergencyModal() {
    const modal = document.getElementById('sosModal');
    if (modal) modal.classList.add('hidden');
  }

  function toggleCopilot(forceOpen) {
    const drawer = document.getElementById('copilotDrawer');
    if (!drawer) return;
    const isHidden = drawer.classList.contains('hidden');
    const nextOpen = typeof forceOpen === 'boolean' ? forceOpen : isHidden;
    drawer.classList.toggle('hidden', !nextOpen);
    if (nextOpen) {
      const input = document.getElementById('copilotInput');
      if (input) input.focus();
    }
  }

  function appendCopilotBubble(role, text, docs) {
    const feed = document.getElementById('copilotFeed');
    if (!feed) return;
    const div = document.createElement('div');
    div.className = role === 'user' ? 'msg-user' : 'msg-bot';
    if (/[\u0600-\u06FF]/.test(text || '')) {
      div.setAttribute('dir', 'auto');
    }

    const p = document.createElement('p');
    p.textContent = String(text || '');
    p.style.whiteSpace = 'pre-line';
    div.appendChild(p);

    if (Array.isArray(docs) && docs.length > 0) {
      const refs = document.createElement('div');
      refs.style.marginTop = '8px';
      refs.style.paddingTop = '6px';
      refs.style.borderTop = '1px solid var(--border-paper)';
      refs.style.fontSize = '11px';
      refs.style.color = 'var(--ink-muted-paper)';
      refs.textContent = 'NASA Sources: ' + docs.slice(0, 3).map((d) => d.title || d.id).join(' | ');
      div.appendChild(refs);
    }

    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
  }

  function askCopilot(queryText) {
    const query = String(queryText || '').trim();
    if (!query) return null;
    toggleCopilot(true);
    appendCopilotBubble('user', query);

    const sess = getSession();
    const features = sess ? sess.features : createBlankFeatures();
    if (typeof global.queryBioCopilot === 'function') {
      const ans = global.queryBioCopilot(query, features);
      const reply = (ans && (ans.responseText || ans.answer)) || 'No telemetry response generated.';
      appendCopilotBubble('bot', reply, ans ? ans.matchedDocs : []);
      return ans;
    }
    appendCopilotBubble('bot', 'Bio-Copilot module is still initializing.');
    return null;
  }

  function getChatbotAstronautId() {
    const crew = getCrewProfile();
    return CREW_CHAT_ID_MAP[crew && crew.id] || 1;
  }

  function buildChatbotSignalsPayload() {
    const sess = getSession();
    const feats = sess && sess.features ? sess.features : {};
    const recent = {};
    if (Number.isFinite(feats.heart_rate_bpm)) recent.heart_rate_bpm = Number(feats.heart_rate_bpm.toFixed(1));
    if (Number.isFinite(feats.spo2_pct)) recent.spo2_pct = Number(feats.spo2_pct.toFixed(1));
    if (Number.isFinite(feats.sleep_hours)) recent.sleep_hours = Number(feats.sleep_hours.toFixed(1));
    if (Number.isFinite(feats.mood_score)) recent.mood_score = Math.round(feats.mood_score);
    if (Number.isFinite(feats.balance_score)) recent.balance_score = Number(feats.balance_score.toFixed(1));
    if (Number.isFinite(feats.facial_ear)) {
      recent.facial_ear = Number(feats.facial_ear.toFixed(3));
      recent.face_fatigue_score = Number(Math.max(0, Math.min(1, (0.34 - feats.facial_ear) / 0.14)).toFixed(2));
    }
    if (Number.isFinite(feats.blood_glucose)) recent.blood_glucose = Number(feats.blood_glucose.toFixed(1));
    if (Number.isFinite(feats.systolic_bp)) recent.systolic_bp = Math.round(feats.systolic_bp);
    if (Number.isFinite(feats.diastolic_bp)) recent.diastolic_bp = Math.round(feats.diastolic_bp);
    if (Number.isFinite(feats.body_temp)) recent.body_temp = Number(feats.body_temp.toFixed(1));
    if (Number.isFinite(feats.radiation_dose_msv)) recent.radiation_dose_msv = Number(feats.radiation_dose_msv.toFixed(2));
    if (Number.isFinite(feats.cabin_co2_mmhg)) recent.cabin_co2_mmhg = Number(feats.cabin_co2_mmhg.toFixed(2));
    const metrics = sess && sess.result ? extractRiskMetrics(sess.result) : null;
    if (metrics && metrics.status) recent.ai_decision = metrics.status;
    return { sess, recent };
  }

  function syncChatbotContext(opts) {
    if (typeof window === 'undefined') return null;
    const crew = getCrewProfile();
    const env = getEnvironment();
    const { sess, recent } = buildChatbotSignalsPayload();
    const metrics = sess && sess.result ? extractRiskMetrics(sess.result) : null;
    const summaryParts = [
      'Crew: ' + (crew ? crew.name : 'C001'),
      'Habitat: ' + env
    ];
    if (metrics) {
      summaryParts.push('Latest Scan: ' + metrics.status + ' (' + (Number.isFinite(metrics.riskPct) ? metrics.riskPct.toFixed(1) + '% risk' : 'Pending') + ')');
    }
    if (opts && opts.note) {
      summaryParts.push(String(opts.note));
    }
    const detailContext = {
      current_tab: (opts && opts.currentTab) || (typeof window !== 'undefined' && window.location ? window.location.pathname.split('/').pop() || 'index.html' : 'index.html'),
      note: summaryParts.join(' | ')
    };
    window.dispatchEvent(new CustomEvent('astro:context', { detail: detailContext }));
    if (Object.keys(recent).length > 0) {
      window.dispatchEvent(new CustomEvent('astro:signals-summary', { detail: { recent } }));
    }
    return { context: detailContext, recent };
  }

  let lastPostedSignalSessionId = null;
  function postSessionSignalsIfReady(sessionId) {
    const apiBase = getChatbotApiBase();
    if (!apiBase || !sessionId || typeof fetch !== 'function' || lastPostedSignalSessionId === sessionId) return;
    lastPostedSignalSessionId = sessionId;
    const { recent } = buildChatbotSignalsPayload();
    if (Object.keys(recent).length === 0) return;
    fetch(apiBase + '/sessions/' + encodeURIComponent(sessionId) + '/signals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel: 'multimodal',
        signals: recent,
        quality: 0.92
      })
    }).catch(() => {});
  }

  function mountAstroChatWidget(opts) {
    if (typeof document === 'undefined') return null;
    const target = (opts && opts.container) || document.body;
    const mode = (opts && opts.mode) || 'floating';
    const apiBase = getChatbotApiBase();
    const existing = document.getElementById('bioAstroChatWidget');
    if (existing) {
      existing.setAttribute('astronaut-id', String(getChatbotAstronautId()));
      existing.setAttribute('api-base', apiBase);
      return existing;
    }
    const el = document.createElement('astro-chat');
    el.id = 'bioAstroChatWidget';
    el.setAttribute('mode', mode);
    el.setAttribute('session-mode', (opts && opts.sessionMode) || 'companion');
    el.setAttribute('api-base', apiBase);
    el.setAttribute('astronaut-id', String(getChatbotAstronautId()));
    el.setAttribute('mission-day', '42');
    el.setAttribute('language', 'en');
    el.setAttribute('theme', 'dark');
    el.setAttribute('title-text', 'Mission Assistant');
    if (mode === 'floating') {
      el.setAttribute('full-page-href', 'assistant.html');
    }
    target.appendChild(el);
    return el;
  }

  function loadAstroChatWidgetScript(onReady, onError) {
    if (typeof document === 'undefined') return;
    if (typeof window !== 'undefined' && window.customElements && window.customElements.get('astro-chat')) {
      if (onReady) onReady();
      return;
    }
    if (typeof window !== 'undefined' && window.location && window.location.protocol === 'about:') {
      return;
    }
    let script = document.getElementById('astroChatWidgetScript');
    if (!script) {
      script = document.createElement('script');
      script.id = 'astroChatWidgetScript';
      script.src = 'Chat%20Bot/web/widget.js';
      script.defer = true;
      document.head.appendChild(script);
    }
    script.addEventListener('load', () => {
      if (onReady) onReady();
    }, { once: true });
    script.addEventListener('error', () => {
      if (onError) onError();
    }, { once: true });
  }

  function mountFooterInto(targetEl) {
    if (!targetEl) return;
    targetEl.className = 'mission-footer';
    targetEl.innerHTML = `
      <div class="footer-simple">
        <div>
          <strong style="color:#EAE5DA;font-size:13px;letter-spacing:0.06em;">BIO ASTRO LAB</strong>
          <span style="color:var(--ink-muted-dark);font-size:12px;margin-left:10px;">Autonomous Crew Health &amp; NASA HRP Triage</span>
        </div>
        <div class="footer-links-row">
          ${NAV_ROUTES.map((r) => `<a href="${r.href}" data-i18n="nav.${r.href}">${escapeHtml(r.label)}</a>`).join('')}
        </div>
      </div>
      <div class="footer-bottom">
        <span>NASA Space Apps 2026 · HRP, RIDGE Hazards &amp; OSDR Baselines</span>
        <span class="mono-num">NASA HRP PROTOCOLS · 13-FEATURE COHORT</span>
      </div>`;
  }

  function renderShellChrome(options) {
    const opts = options || {};
    const activeRoute = opts.activeRoute || 'index.html';
    const currentEnv = getEnvironment();
    const currentLang = getUiLang();
    const envs = getEnvironments();
    const protocols = getEmergencyProtocols();

    const envOptionsHtml = envs
      .map((e) => `<option value="${escapeHtml(e.id)}" ${e.id === currentEnv ? 'selected' : ''}>${escapeHtml(e.label)}</option>`)
      .join('');

    const navHtml = NAV_ROUTES.map(
      (r) => `<a href="${r.href}" data-i18n="nav.${r.href}" class="${r.href === activeRoute ? 'active' : ''}">${escapeHtml(r.label)}</a>`
    ).join('');

    let headerHost = document.getElementById('appHeader');
    if (!headerHost) {
      headerHost = document.createElement('header');
      headerHost.id = 'appHeader';
      document.body.prepend(headerHost);
    }
    headerHost.className = 'topbar';
    headerHost.innerHTML = `
      <a href="index.html" class="brand-link">
        <span>BIO ASTRO LAB</span>
      </a>
      <nav class="main-nav" id="primaryNav" aria-label="Primary Navigation">
        ${navHtml}
      </nav>
      <div class="header-actions">
        <button id="globalThemeToggle" type="button" class="theme-toggle-btn" title="${getTheme() === 'dark' ? 'Switch to Light Lab Mode' : 'Switch to Dark Cosmic Mode'}" aria-label="Toggle Theme">
          ${getTheme() === 'dark'
            ? '<span class="theme-icon moon" aria-hidden="true">🌙</span>'
            : '<span class="theme-icon sun" aria-hidden="true">☀️</span>'}
        </button>
        <div class="env-select-wrap">
          <label for="globalEnvSelect" class="sr-only">Mission Habitat Environment</label>
          <select id="globalEnvSelect" class="env-select">${envOptionsHtml}</select>
          <span class="env-caret" aria-hidden="true">▾</span>
        </div>
        <button id="mobileNavToggle" type="button" class="mobile-menu-btn" aria-expanded="false" aria-label="Toggle navigation">MENU</button>
      </div>`;

    let mobileDrawer = document.getElementById('mobileNavDrawer');
    if (!mobileDrawer) {
      mobileDrawer = document.createElement('nav');
      mobileDrawer.id = 'mobileNavDrawer';
      mobileDrawer.className = 'mobile-nav-drawer hidden';
      mobileDrawer.innerHTML = NAV_ROUTES.map(
        (r) => `<a href="${r.href}" style="color:${r.href === activeRoute ? '#EAE5DA' : '#9E9B93'};text-decoration:none;font-size:13px;font-weight:${r.href === activeRoute ? '700' : '400'};">${escapeHtml(r.label)}</a>`
      ).join('');
      headerHost.insertAdjacentElement('afterend', mobileDrawer);
    }

    if (!document.getElementById('toastRegion')) {
      const tr = document.createElement('div');
      tr.id = 'toastRegion';
      tr.className = 'toast-stack';
      tr.setAttribute('aria-live', 'polite');
      document.body.appendChild(tr);
    }

    if (!document.getElementById('sosModal')) {
      const sos = document.createElement('div');
      sos.id = 'sosModal';
      sos.className = 'sos-modal-backdrop hidden';
      sos.setAttribute('role', 'dialog');
      sos.setAttribute('aria-modal', 'true');
      sos.setAttribute('aria-label', 'NASA Emergency Protocol Drawer');
      sos.innerHTML = `
        <div class="sos-modal-card">
          <div class="sos-modal-head">
            <div>
              <div class="mono-num" style="font-size:10px;letter-spacing:0.12em;">AUTONOMOUS CREW TRIAGE · 6 NASA PROTOCOLS</div>
              <strong style="font-size:16px;">Emergency Flight Surgeon Checklists</strong>
            </div>
            <button id="closeSosModalBtn" type="button" class="btn-dark-ghost" style="padding:6px 12px;">Close</button>
          </div>
          <div class="sos-modal-body">
            <div class="sos-symptom-grid">
              ${protocols
                .map(
                  (p) => `<button type="button" class="sos-symptom-btn" data-protocol-id="${escapeHtml(p.protocol_id)}">${escapeHtml(p.title)}</button>`
                )
                .join('')}
            </div>
            <div id="sosProtocolDetail"></div>
          </div>
        </div>`;
      document.body.appendChild(sos);
    }

    if (activeRoute !== 'assistant.html') {
      if (!document.getElementById('copilotToggleBtn')) {
        const btn = document.createElement('button');
        btn.id = 'copilotToggleBtn';
        btn.type = 'button';
        btn.className = 'copilot-launcher';
        btn.textContent = 'BIO-COPILOT (OFFLINE)';
        document.body.appendChild(btn);
      }

      if (!document.getElementById('copilotDrawer')) {
        const drawer = document.createElement('aside');
        drawer.id = 'copilotDrawer';
        drawer.className = 'copilot-drawer hidden';
        drawer.setAttribute('aria-label', 'Bio-Copilot Assistant');
        drawer.innerHTML = `
          <div class="copilot-header">
            <div>
              <div class="mono-num" style="font-size:10px;color:#E77C5D;letter-spacing:0.1em;">OFFLINE NASA RAG FALLBACK</div>
              <strong style="font-size:14px;">Bio-Copilot Assistant</strong>
            </div>
            <button id="closeCopilotBtn" type="button" class="btn-dark-ghost" style="padding:4px 10px;font-size:11px;">Hide</button>
          </div>
          <div id="copilotFeed" class="copilot-feed">
            <div class="msg-bot">Ask about NASA HRP risks, vitals interpretation, CO2/SpO2, or SANS countermeasures.</div>
          </div>
          <div class="copilot-chips">
            <button type="button" class="copilot-chip" data-chip="Analyze current risk">Analyze current risk</button>
            <button type="button" class="copilot-chip" data-chip="Station radiation protocol">Radiation Protocol</button>
            <button type="button" class="copilot-chip" data-chip="Blood pressure and headache">BP &amp; Headache</button>
            <button type="button" class="copilot-chip" data-chip="CO2 and hypoxia protocol">CO2 / Hypoxia</button>
          </div>
          <form id="copilotForm" style="display:flex;gap:8px;padding:10px 12px;border-top:1px solid var(--border-paper);background:var(--bg-paper-card);">
            <input id="copilotInput" class="field-input" type="text" placeholder="Ask NASA Bio-Copilot..." style="flex:1;">
            <button type="submit" class="btn-primary" style="padding:8px 14px;font-size:12px;">Send</button>
          </form>`;
        document.body.appendChild(drawer);
      }

      loadAstroChatWidgetScript(() => {
        const mounted = mountAstroChatWidget({ mode: 'floating' });
        if (mounted) {
          const legacyBtn = document.getElementById('copilotToggleBtn');
          if (legacyBtn) legacyBtn.style.display = 'none';
          syncChatbotContext({ currentTab: activeRoute });
        }
      });
    }

    if (opts.showFooter !== false) {
      const footerHost = document.getElementById('appFooter');
      if (footerHost) mountFooterInto(footerHost);
    }

    // Wire events
    const themeBtn = document.getElementById('globalThemeToggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', toggleTheme);
    }

    const envSelect = document.getElementById('globalEnvSelect');
    if (envSelect) {
      envSelect.addEventListener('change', (e) => {
        const chosen = setEnvironment(e.target.value);
        showToast('Habitat switched to ' + chosen, 'nominal');
      });
    }

    const closeSosBtn = document.getElementById('closeSosModalBtn');
    if (closeSosBtn) closeSosBtn.addEventListener('click', closeEmergencyModal);

    const sosBackdrop = document.getElementById('sosModal');
    if (sosBackdrop) {
      sosBackdrop.addEventListener('click', (e) => {
        if (e.target === sosBackdrop) closeEmergencyModal();
      });
      sosBackdrop.querySelectorAll('[data-protocol-id]').forEach((btn) => {
        btn.addEventListener('click', () => selectEmergencySymptom(btn.getAttribute('data-protocol-id')));
      });
    }

    const mobToggle = document.getElementById('mobileNavToggle');
    if (mobToggle && mobileDrawer) {
      mobToggle.addEventListener('click', () => {
        const open = mobileDrawer.classList.toggle('hidden');
        mobToggle.setAttribute('aria-expanded', String(!open));
      });
    }

    const copBtn = document.getElementById('copilotToggleBtn');
    if (copBtn) copBtn.addEventListener('click', () => toggleCopilot());

    const closeCopBtn = document.getElementById('closeCopilotBtn');
    if (closeCopBtn) closeCopBtn.addEventListener('click', () => toggleCopilot(false));

    const copForm = document.getElementById('copilotForm');
    if (copForm) {
      copForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('copilotInput');
        if (!input || !input.value.trim()) return;
        const q = input.value;
        input.value = '';
        askCopilot(q);
      });
    }

    document.querySelectorAll('.copilot-chip[data-chip]').forEach((chip) => {
      chip.addEventListener('click', () => askCopilot(chip.getAttribute('data-chip')));
    });

    if (typeof window !== 'undefined' && !window.__bioChatbotBridgeWired) {
      window.__bioChatbotBridgeWired = true;
      window.addEventListener('astro:session', (e) => {
        const sid = e && e.detail ? e.detail.session_id : null;
        syncChatbotContext({ currentTab: activeRoute });
        postSessionSignalsIfReady(sid);
      });
    }

    applyUiTranslations('en');
  }

  function buildBodyHologramSvg(opts) {
    const visorClipId = (opts && opts.visorClipId) || 'decisionVisorClip';
    const visorImgId = (opts && opts.visorImgId) || 'decisionVisorImg';
    const gridId = (opts && opts.gridId) || 'decHoloGrid';
    const uid = visorImgId.replace(/[^a-zA-Z0-9]/g, '');

    return `
      <svg class="hologram-svg" viewBox="0 0 280 420" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Interactive realistic anatomical astronaut body inspector">
        <defs>
          <clipPath id="${visorClipId}">
            <circle cx="30" cy="30" r="17"></circle>
          </clipPath>
          <pattern id="${gridId}" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(120,165,205,0.07)" stroke-width="0.6"></path>
          </pattern>

          <!-- 3D Volumetric Anatomical Lighting Gradients -->
          <linearGradient id="skinVol_${uid}" x1="20%" y1="0%" x2="80%" y2="100%">
            <stop offset="0%" stop-color="#2B3E54" stop-opacity="0.58"/>
            <stop offset="50%" stop-color="#192534" stop-opacity="0.48"/>
            <stop offset="100%" stop-color="#0E151F" stop-opacity="0.72"/>
          </linearGradient>
          <radialGradient id="torsoShade_${uid}" cx="45%" cy="35%" r="60%">
            <stop offset="0%" stop-color="#3D5A78" stop-opacity="0.34"/>
            <stop offset="100%" stop-color="#101822" stop-opacity="0.05"/>
          </radialGradient>
          <radialGradient id="brainGrad_${uid}" cx="42%" cy="34%" r="65%">
            <stop offset="0%" stop-color="#F1B6A8"/>
            <stop offset="55%" stop-color="#C9786A"/>
            <stop offset="100%" stop-color="#763A37"/>
          </radialGradient>
          <linearGradient id="lungGrad_${uid}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#5B8EB5" stop-opacity="0.46"/>
            <stop offset="65%" stop-color="#2F5575" stop-opacity="0.38"/>
            <stop offset="100%" stop-color="#182D42" stop-opacity="0.48"/>
          </linearGradient>
          <radialGradient id="heartGrad_${uid}" cx="38%" cy="36%" r="65%">
            <stop offset="0%" stop-color="#EB5B62"/>
            <stop offset="52%" stop-color="#B12630"/>
            <stop offset="100%" stop-color="#581018"/>
          </radialGradient>
          <linearGradient id="aortaGrad_${uid}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#F05B5B"/>
            <stop offset="100%" stop-color="#8C1820"/>
          </linearGradient>
          <linearGradient id="veinGrad_${uid}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#5BA0E8"/>
            <stop offset="100%" stop-color="#214E8C"/>
          </linearGradient>
          <radialGradient id="liverGrad_${uid}" cx="35%" cy="32%" r="72%">
            <stop offset="0%" stop-color="#C66647"/>
            <stop offset="58%" stop-color="#8A3521"/>
            <stop offset="100%" stop-color="#4A1911"/>
          </radialGradient>
          <radialGradient id="gallbladderGrad_${uid}" cx="40%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#53B87A"/>
            <stop offset="100%" stop-color="#225B39"/>
          </radialGradient>
          <radialGradient id="spleenGrad_${uid}" cx="38%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#AD547A"/>
            <stop offset="65%" stop-color="#6F294A"/>
            <stop offset="100%" stop-color="#3E1428"/>
          </radialGradient>
          <radialGradient id="kidneyGrad_${uid}" cx="40%" cy="35%" r="65%">
            <stop offset="0%" stop-color="#C56657"/>
            <stop offset="60%" stop-color="#87332A"/>
            <stop offset="100%" stop-color="#4A1916"/>
          </radialGradient>
          <radialGradient id="bladderGrad_${uid}" cx="45%" cy="35%" r="62%">
            <stop offset="0%" stop-color="#D49582"/>
            <stop offset="65%" stop-color="#8E5044"/>
            <stop offset="100%" stop-color="#542B25"/>
          </radialGradient>
          <linearGradient id="boneGrad_${uid}" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#9EB4C8" stop-opacity="0.48"/>
            <stop offset="48%" stop-color="#DCE8F2" stop-opacity="0.72"/>
            <stop offset="100%" stop-color="#6B8299" stop-opacity="0.42"/>
          </linearGradient>
        </defs>

        <!-- Aerospace Background Grid & Hologram Pedestal -->
        <rect x="4" y="4" width="272" height="412" rx="4" fill="url(#${gridId})"></rect>
        <line x1="140" y1="8" x2="140" y2="412" stroke="rgba(120,165,205,0.12)" stroke-dasharray="3 4" stroke-width="0.8"></line>
        <ellipse cx="140" cy="404" rx="64" ry="8" fill="rgba(56,176,123,0.09)" stroke="rgba(74,209,150,0.42)" stroke-width="1"></ellipse>
        <ellipse cx="140" cy="404" rx="42" ry="4.5" fill="none" stroke="rgba(120,165,205,0.32)" stroke-width="0.75"></ellipse>

        <!-- Non-Obstructing Crew Visor Camera Lens (Top-Left Corner) -->
        <g pointer-events="none">
          <circle cx="30" cy="30" r="18" fill="rgba(18,24,33,0.9)" stroke="#495B70" stroke-width="1.2"></circle>
          <image id="${visorImgId}" x="13" y="13" width="34" height="34" preserveAspectRatio="xMidYMid slice" clip-path="url(#${visorClipId})" opacity="0.96" href=""></image>
          <text x="30" y="56" text-anchor="middle" fill="#6E8096" font-family="var(--font-mono)" font-size="6.5" letter-spacing="0.5">CREW CAM</text>
          <path d="M48 30 L118 33" stroke="rgba(110,160,200,0.28)" stroke-dasharray="2 2" stroke-width="0.8"></path>
        </g>

        <!-- Volumetric Realistic Standing Human Figure (Muscular & Anatomical Proportions) -->
        <path d="M140 12
                 C154 12 162 21 162 35
                 C162 46 157 57 149 63
                 C148 70 149 77 155 82
                 C169 86 189 91 200 101
                 C209 111 212 126 214 144
                 L221 180
                 C225 197 229 212 232 223
                 C236 234 233 250 227 252
                 C221 253 218 244 217 233
                 C215 239 212 237 212 228
                 C210 214 205 190 200 166
                 C197 150 192 135 190 126
                 C187 144 182 161 181 177
                 C184 192 190 209 188 229
                 C186 254 182 276 179 296
                 C183 317 180 340 175 365
                 L172 385
                 C175 393 180 400 177 404
                 C170 406 158 405 154 401
                 C153 395 156 388 157 382
                 L158 359
                 C152 335 152 313 157 294
                 C154 270 149 245 145 226
                 C142 220 138 220 135 226
                 C131 245 126 270 123 294
                 C128 313 128 335 122 359
                 L123 382
                 C124 388 127 395 126 401
                 C122 405 110 406 103 404
                 C100 400 105 393 108 385
                 L105 365
                 C100 340 97 317 101 296
                 C98 276 94 254 92 229
                 C90 209 96 192 99 177
                 C98 161 93 144 90 126
                 C88 135 83 150 80 166
                 C75 190 70 214 68 228
                 C68 237 65 239 63 233
                 C62 244 59 253 53 252
                 C47 250 44 234 48 223
                 C51 212 55 197 59 180
                 L66 144
                 C68 126 71 111 80 101
                 C91 91 111 86 125 82
                 C131 77 132 70 131 63
                 C123 57 118 46 118 35
                 C118 21 126 12 140 12 Z"
              fill="url(#skinVol_${uid})" stroke="#68829E" stroke-width="1.3"></path>

        <!-- Subtle Anatomical Musculature & Surface Depth Contours -->
        <g fill="none" stroke="rgba(155,190,225,0.16)" stroke-width="0.9" pointer-events="none">
          <!-- Sternocleidomastoid V + Pectoral & Abdominal Lineation -->
          <path d="M132 63 L137 83 M148 63 L143 83"></path>
          <path d="M98 118 Q119 128 138 118 M182 118 Q161 128 142 118" fill="url(#torsoShade_${uid})"></path>
          <path d="M140 122 L140 198 M124 146 Q140 149 156 146 M124 166 Q140 169 156 166"></path>
          <!-- Deltoid, Biceps & Quadriceps Muscle Contours -->
          <path d="M92 96 Q84 114 82 132 M188 96 Q196 114 198 132"></path>
          <path d="M111 245 Q115 268 118 286 M169 245 Q165 268 162 286"></path>
          <path d="M111 304 Q118 326 116 346 M169 304 Q162 326 164 346"></path>
        </g>

        <!-- 5. MUSCULOSKELETAL: Articulated Spine, Clavicles, Ribcage, Pelvis, Limb Bones & Synovial Joints -->
        <g class="holo-zone" data-system-id="musculoskeletal" data-tier="nominal">
          <title>Musculoskeletal, Spine &amp; Limb Kinetics</title>
          <!-- Generous clickable hit envelopes over spine, arms and legs -->
          <path class="holo-hit-target" d="M84 92 L44 250 L76 250 L96 114 Z M196 92 L236 250 L204 250 L184 114 Z M94 212 L186 212 L180 406 L152 406 L144 240 L136 240 L128 406 L100 406 Z" fill="rgba(0,0,0,0.001)" pointer-events="all" cursor="pointer"></path>

          <!-- Articulated Cervical, Thoracic & Lumbar Vertebrae -->
          <g fill="url(#boneGrad_${uid})" stroke="rgba(210,232,250,0.45)" stroke-width="0.65">
            <rect x="136.5" y="64" width="7" height="4.5" rx="1.5"></rect>
            <rect x="136" y="70" width="8" height="4.5" rx="1.5"></rect>
            <rect x="136" y="76" width="8" height="4.5" rx="1.5"></rect>
            <rect x="135.5" y="88" width="9" height="5" rx="1.5"></rect>
            <rect x="135.5" y="95" width="9" height="5" rx="1.5"></rect>
            <rect x="135.5" y="102" width="9" height="5" rx="1.5"></rect>
            <rect x="135.5" y="109" width="9" height="5" rx="1.5"></rect>
            <rect x="135" y="116" width="10" height="5.5" rx="1.5"></rect>
            <rect x="135" y="123.5" width="10" height="5.5" rx="1.5"></rect>
            <rect x="135" y="131" width="10" height="5.5" rx="1.5"></rect>
            <rect x="134.5" y="139" width="11" height="6" rx="1.8"></rect>
            <rect x="134" y="147" width="12" height="6.5" rx="1.8"></rect>
            <rect x="133.5" y="155.5" width="13" height="6.5" rx="1.8"></rect>
            <rect x="133.5" y="164" width="13" height="6.5" rx="1.8"></rect>
            <rect x="134" y="172.5" width="12" height="6.5" rx="1.8"></rect>
          </g>

          <!-- Clavicles & Sternum -->
          <path d="M136 86 C120 82 102 85 88 95 C89 98 103 91 136 90 Z" fill="url(#boneGrad_${uid})" stroke="rgba(215,235,250,0.5)" stroke-width="0.7"></path>
          <path d="M144 86 C160 82 178 85 192 95 C191 98 177 91 144 90 Z" fill="url(#boneGrad_${uid})" stroke="rgba(215,235,250,0.5)" stroke-width="0.7"></path>
          <path d="M136.5 87 L143.5 87 L142.5 130 L140 135 L137.5 130 Z" fill="url(#boneGrad_${uid})" stroke="rgba(215,235,250,0.45)" stroke-width="0.7"></path>

          <!-- Sculpted Pelvic Girdle (Iliac Wings, Sacrum & Pubic Arch) -->
          <path d="M134 179 L146 179 L143 200 L137 200 Z" fill="url(#boneGrad_${uid})" stroke="rgba(215,235,250,0.45)" stroke-width="0.7"></path>
          <path d="M134 181 C118 173 98 174 96 188 C95 202 104 215 117 216 C125 216 130 207 137 206 Z" fill="url(#boneGrad_${uid})" stroke="rgba(215,235,250,0.48)" stroke-width="0.8"></path>
          <path d="M146 181 C162 173 182 174 184 188 C185 202 176 215 163 216 C155 216 150 207 143 206 Z" fill="url(#boneGrad_${uid})" stroke="rgba(215,235,250,0.48)" stroke-width="0.8"></path>

          <!-- Upper & Lower Long Bones (Humerus, Radius/Ulna, Femur, Tibia/Fibula) -->
          <g stroke="url(#boneGrad_${uid})" stroke-linecap="round" fill="none">
            <path d="M87 98 L72 158 L61 215" stroke-width="4.4" opacity="0.72"></path>
            <path d="M193 98 L208 158 L219 215" stroke-width="4.4" opacity="0.72"></path>
            <path d="M111 206 L112 290 L114 378" stroke-width="5.6" opacity="0.78"></path>
            <path d="M169 206 L168 290 L166 378" stroke-width="5.6" opacity="0.78"></path>
          </g>

          <!-- Synovial Joint Articulation Halo Rings -->
          <g class="holo-halo" fill="none" stroke="currentColor" stroke-width="1.2">
            <circle cx="87" cy="98" r="5"></circle><circle cx="193" cy="98" r="5"></circle>
            <circle cx="72" cy="158" r="4"></circle><circle cx="208" cy="158" r="4"></circle>
            <circle cx="111" cy="206" r="5"></circle><circle cx="169" cy="206" r="5"></circle>
            <circle cx="112" cy="290" r="6"></circle><circle cx="168" cy="290" r="6"></circle>
            <circle cx="114" cy="378" r="4.2"></circle><circle cx="166" cy="378" r="4.2"></circle>
          </g>

          <!-- Leader callout -->
          <line class="holo-callout-line" x1="175" y1="290" x2="232" y2="290" stroke-dasharray="2 2" stroke-width="0.9"></line>
          <text class="holo-callout-text" x="235" y="293" font-family="var(--font-mono)" font-size="7.5" letter-spacing="0.4">JOINTS</text>
        </g>

        <!-- Realistic Thoracic Lungs, Trachea & Translucent Ribcage (Background Organ Depth) -->
        <g pointer-events="none">
          <!-- Ringed Trachea & Bronchi -->
          <path d="M137.5 64 L142.5 64 L142.5 96 L151 106 M137.5 96 L129 106" fill="none" stroke="#8FB2CE" stroke-width="2.2" opacity="0.6"></path>
          <path d="M137 69 H143 M137 73 H143 M137 77 H143 M137 81 H143 M137 85 H143" stroke="#D2E4F2" stroke-width="0.8" opacity="0.55"></path>
          <!-- 3D Shaded Right & Left Lung Lobes -->
          <path d="M135 91 C116 90 100 102 97 123 C95 136 101 144 114 143 C124 142 131 137 135 132 Z" fill="url(#lungGrad_${uid})" stroke="rgba(125,180,220,0.45)" stroke-width="0.85"></path>
          <path d="M145 91 C164 90 180 102 183 123 C185 136 179 144 166 143 C156 142 149 137 145 132 Z" fill="url(#lungGrad_${uid})" stroke="rgba(125,180,220,0.45)" stroke-width="0.85"></path>
          <path d="M100 122 Q118 128 134 122 M180 122 Q162 128 146 122" fill="none" stroke="rgba(160,205,235,0.28)" stroke-width="0.7"></path>
          <!-- Sweeping Translucent Costal Ribs -->
          <g fill="none" stroke="rgba(210,230,248,0.28)" stroke-width="1.3" stroke-linecap="round">
            <path d="M136 96 C115 95 102 99 98 106"></path><path d="M144 96 C165 95 178 99 182 106"></path>
            <path d="M136 104 C112 103 99 108 96 116"></path><path d="M144 104 C168 103 181 108 184 116"></path>
            <path d="M136 113 C111 112 97 118 95 126"></path><path d="M144 113 C169 112 183 118 185 126"></path>
            <path d="M136 122 C112 121 98 127 97 135"></path><path d="M144 122 C170 121 182 127 183 135"></path>
            <path d="M135 131 C116 131 103 137 101 143"></path><path d="M145 131 C164 131 177 137 179 143"></path>
          </g>
          <!-- Muscular Diaphragm Arch -->
          <path d="M96 144 Q140 132 184 144" fill="none" stroke="rgba(215,150,140,0.4)" stroke-width="1.1"></path>
        </g>

        <!-- 2. CARDIOVASCULAR: Realistic 3D Heart, Coronary Vessels, Aortic Arch & Vena Cava -->
        <g class="holo-zone" data-system-id="cardio" data-tier="nominal">
          <title>Cardiovascular &amp; Circulatory System</title>
          <!-- Generous clickable hit area -->
          <rect class="holo-hit-target" x="108" y="84" width="66" height="56" rx="10" fill="rgba(0,0,0,0.001)" pointer-events="all" cursor="pointer"></rect>
          <!-- Superior Vena Cava & Pulmonary Artery (Venous Blue) -->
          <path d="M131 92 L131 114" stroke="url(#veinGrad_${uid})" stroke-width="4.2" stroke-linecap="round" fill="none"></path>
          <path d="M141 112 C143 102 150 100 157 104" stroke="url(#veinGrad_${uid})" stroke-width="3.2" stroke-linecap="round" fill="none"></path>
          <!-- Ascending & Descending Aortic Arch + Carotid/Subclavian Trunks -->
          <path d="M138 112 C137 96 142 91 148 96 C152 99 151 108 148 116" stroke="url(#aortaGrad_${uid})" stroke-width="4.4" stroke-linecap="round" fill="none"></path>
          <path d="M140 93 L138 83 M144 92 L144 82 M148 94 L152 84" stroke="url(#aortaGrad_${uid})" stroke-width="1.8" stroke-linecap="round" fill="none"></path>
          <!-- 3D Muscular Heart (Right & Left Ventricles + Right Atrium) -->
          <path d="M141 107 C134 103 127 109 129 119 C130 128 140 135 151 139 C158 135 161 124 157 113 C153 106 147 104 141 107 Z"
                fill="url(#heartGrad_${uid})" stroke="#F28588" stroke-width="0.95"></path>
          <!-- Epicardial Surface Specular Highlight & Coronary Arteries -->
          <ellipse cx="139" cy="117" rx="4" ry="7" transform="rotate(-20 139 117)" fill="rgba(255,210,210,0.22)" stroke="none"></ellipse>
          <path d="M140 110 C143 119 145 127 149 135 M143 120 L136 125 M145 125 L153 124" fill="none" stroke="#FF9B9B" stroke-width="0.9" opacity="0.85"></path>
          <path d="M135 113 Q142 117 152 114" fill="none" stroke="#70B5FF" stroke-width="0.8" opacity="0.72"></path>
          <!-- Selection Glow Ring -->
          <ellipse class="holo-halo" cx="144" cy="120" rx="20" ry="22" fill="none" stroke="currentColor" stroke-dasharray="3 2"></ellipse>
          <!-- Leader callout -->
          <line class="holo-callout-line" x1="164" y1="118" x2="232" y2="118" stroke-dasharray="2 2" stroke-width="0.9"></line>
          <text class="holo-callout-text" x="235" y="121" font-family="var(--font-mono)" font-size="7.5" letter-spacing="0.4">HEART</text>
        </g>

        <!-- 3. IMMUNE & METABOLIC: 3D Hepatic Lobes, Gallbladder, Spleen & Thymus -->
        <g class="holo-zone" data-system-id="immune" data-tier="nominal">
          <title>Immune, Hepatic-Splenic &amp; Metabolic System</title>
          <!-- Generous clickable hit area -->
          <rect class="holo-hit-target" x="94" y="136" width="92" height="32" rx="8" fill="rgba(0,0,0,0.001)" pointer-events="all" cursor="pointer"></rect>
          <!-- Mediastinal Thymus Gland -->
          <path d="M136 93 C135 89 145 89 144 93 C145 99 141 101 140 99 C139 101 135 99 136 93 Z"
                fill="#D48B96" stroke="#F0BCC5" stroke-width="0.65" opacity="0.88"></path>
          <!-- Gallbladder under Right Hepatic Lobe -->
          <path d="M121 159 C118 163 121 168 125 166 C128 164 126 159 123 158 Z"
                fill="url(#gallbladderGrad_${uid})" stroke="#77D49A" stroke-width="0.65"></path>
          <!-- 3D Anatomical Right & Left Lobes of Liver -->
          <path d="M103 144 C117 139 135 141 149 146 C145 153 133 157 121 161 C111 165 103 163 101 154 C100 149 101 145 103 144 Z"
                fill="url(#liverGrad_${uid})" stroke="#E58B6E" stroke-width="0.9"></path>
          <!-- Falciform Ligament & Hepatic Specular Sheen -->
          <path d="M128 142 L125 157" fill="none" stroke="#F5B29A" stroke-width="0.85" opacity="0.65"></path>
          <ellipse cx="114" cy="149" rx="6.5" ry="2.8" transform="rotate(-12 114 149)" fill="rgba(255,215,195,0.18)"></ellipse>
          <!-- 3D Textured Spleen (Left Upper Quadrant) -->
          <path d="M164 144 C172 143 177 151 174 159 C171 163 164 161 162 154 C161 149 162 145 164 144 Z"
                fill="url(#spleenGrad_${uid})" stroke="#DF8CB2" stroke-width="0.85"></path>
          <path d="M165 151 Q169 152 172 155" fill="none" stroke="rgba(255,205,225,0.4)" stroke-width="0.7"></path>
          <!-- Selection Glow Halo -->
          <path class="holo-halo" d="M98 141 H178 V168 H98 Z" rx="8" fill="none" stroke="currentColor" stroke-dasharray="3 2" stroke-width="0.9" opacity="0.12"></path>
          <!-- Leader callout -->
          <line class="holo-callout-line" x1="100" y1="152" x2="48" y2="152" stroke-dasharray="2 2" stroke-width="0.9"></line>
          <text class="holo-callout-text" x="8" y="155" font-family="var(--font-mono)" font-size="7.5" letter-spacing="0.4">IMMUNE</text>
        </g>

        <!-- 4. RENAL & HYDRATION: Paired 3D Kidneys, Adrenals, Renal Vessels, Ureters & Bladder -->
        <g class="holo-zone" data-system-id="renal" data-tier="nominal">
          <title>Renal &amp; Fluid Regulation</title>
          <!-- Generous clickable hit area -->
          <rect class="holo-hit-target" x="104" y="162" width="72" height="52" rx="8" fill="rgba(0,0,0,0.001)" pointer-events="all" cursor="pointer"></rect>
          <!-- Renal Artery & Vein Hilum Branches -->
          <path d="M126 171 L140 170 L154 168" fill="none" stroke="url(#aortaGrad_${uid})" stroke-width="1.6"></path>
          <path d="M126 173 L140 172 L154 170" fill="none" stroke="url(#veinGrad_${uid})" stroke-width="1.4" opacity="0.85"></path>
          <!-- Endocrine Adrenal Glands -->
          <path d="M114 164 Q120 158 125 163 Z" fill="#E3AD5B" stroke="#F8D290" stroke-width="0.6"></path>
          <path d="M155 160 Q160 154 166 159 Z" fill="#E3AD5B" stroke="#F8D290" stroke-width="0.6"></path>
          <!-- Right & Left 3D Bean Kidneys -->
          <path d="M119 164 C112 164 110 173 112 180 C115 186 123 186 125 180 C126 177 123 175 123 173 C123 171 126 168 125 165 C124 164 121 164 119 164 Z"
                fill="url(#kidneyGrad_${uid})" stroke="#E58B7D" stroke-width="0.9"></path>
          <path d="M161 160 C168 160 170 169 168 176 C165 182 157 182 155 176 C154 173 157 171 157 169 C157 167 154 164 155 161 C156 160 159 160 161 160 Z"
                fill="url(#kidneyGrad_${uid})" stroke="#E58B7D" stroke-width="0.9"></path>
          <!-- Inner Renal Pelvis Highlight -->
          <path d="M115 170 Q117 175 116 179 M165 166 Q163 171 164 175" fill="none" stroke="rgba(255,210,195,0.4)" stroke-width="0.8"></path>
          <!-- Ureters & 3D Bladder -->
          <path d="M124 176 Q129 188 134 200 M156 172 Q151 185 146 200" fill="none" stroke="#E0C3AE" stroke-width="1.35"></path>
          <path d="M131 199 Q140 194 149 199 Q150 209 140 212 Q130 209 131 199 Z"
                fill="url(#bladderGrad_${uid})" stroke="#E8AF9E" stroke-width="0.9"></path>
          <!-- Selection Glow Halo -->
          <rect class="holo-halo" x="108" y="156" width="64" height="58" rx="10" fill="none" stroke="currentColor" stroke-dasharray="3 2"></rect>
          <!-- Leader callout -->
          <line class="holo-callout-line" x1="172" y1="170" x2="232" y2="170" stroke-dasharray="2 2" stroke-width="0.9"></line>
          <text class="holo-callout-text" x="235" y="173" font-family="var(--font-mono)" font-size="7.5" letter-spacing="0.4">RENAL</text>
        </g>

        <!-- 1. HEAD, BRAIN & CRANIAL NERVOUS SYSTEM (Unobstructed by Visor) -->
        <g class="holo-zone selected" data-system-id="head" data-tier="nominal">
          <title>Brain, Eyes &amp; Vestibular (SANS)</title>
          <!-- Generous clickable hit area -->
          <rect class="holo-hit-target" x="110" y="8" width="60" height="62" rx="14" fill="rgba(0,0,0,0.001)" pointer-events="all" cursor="pointer"></rect>
          <!-- Cranial Glow Ring & Brainstem -->
          <ellipse class="holo-halo" cx="140" cy="31" rx="22" ry="18" fill="none" stroke="currentColor" stroke-dasharray="3 2"></ellipse>
          <path d="M137 40 L143 40 L142 61 L138 61 Z" fill="#D5B2A8" stroke="rgba(240,210,200,0.6)" stroke-width="0.6"></path>
          <!-- Cerebellum Lobes -->
          <ellipse cx="133" cy="40" rx="6" ry="4" fill="#A55C54" stroke="#E09A8E" stroke-width="0.6"></ellipse>
          <ellipse cx="147" cy="40" rx="6" ry="4" fill="#A55C54" stroke="#E09A8E" stroke-width="0.6"></ellipse>
          <!-- Left & Right 3D Cerebral Cortex Hemispheres -->
          <path d="M139.5 16 C129 16 122 22 122 31 C122 37 128 40 137 40 C138.8 40 139.5 39 139.5 37 Z"
                fill="url(#brainGrad_${uid})" stroke="#F5C0B2" stroke-width="0.85"></path>
          <path d="M140.5 16 C151 16 158 22 158 31 C158 37 152 40 143 40 C141.2 40 140.5 39 140.5 37 Z"
                fill="url(#brainGrad_${uid})" stroke="#F5C0B2" stroke-width="0.85"></path>
          <!-- Convoluted Gyri & Sulci Grooves + Optic Nerves -->
          <g fill="none" stroke="#682B27" stroke-width="0.85" stroke-linecap="round" opacity="0.78">
            <path d="M126 24 Q131 20 135 24 M125 30 Q130 27 136 31 M127 36 Q133 34 137 37"></path>
            <path d="M154 24 Q149 20 145 24 M155 30 Q150 27 144 31 M153 36 Q147 34 143 37"></path>
          </g>
          <g fill="none" stroke="#9BD4F0" stroke-width="0.7" opacity="0.6">
            <circle cx="132" cy="47" r="2.2" fill="rgba(155,212,240,0.22)"></circle>
            <circle cx="148" cy="47" r="2.2" fill="rgba(155,212,240,0.22)"></circle>
            <path d="M133 45 L139 40 M147 45 L141 40"></path>
          </g>
          <!-- Leader callout -->
          <line class="holo-callout-line" x1="120" y1="30" x2="54" y2="30" stroke-dasharray="2 2" stroke-width="0.9"></line>
          <text class="holo-callout-text" x="87" y="24" text-anchor="middle" font-family="var(--font-mono)" font-size="7.5" letter-spacing="0.4">BRAIN</text>
        </g>
      </svg>`;
  }

  function mountAllBodyHolograms() {
    if (typeof document === 'undefined') return;
    document.querySelectorAll('[data-hologram-mount]').forEach((wrap) => {
      wrap.innerHTML = buildBodyHologramSvg({
        visorClipId: wrap.getAttribute('data-visor-clip') || 'decisionVisorClip',
        visorImgId: wrap.getAttribute('data-visor-img') || 'decisionVisorImg',
        gridId: wrap.getAttribute('data-grid') || 'decHoloGrid'
      });
    });
  }

  mountAllBodyHolograms();
  initTheme();
  initCosmicPreloader();

  global.BioShell = {
    STORAGE_KEYS,
    FEATURE_KEYS,
    escapeHtml,
    sanitizeCsvCell,
    parseCsvLine,
    parseCsvTable,
    createBlankFeatures,
    normalizeFeatures,
    getEnvironments,
    getEnvironmentMeta,
    getEnvironment,
    setEnvironment,
    getCrewProfiles,
    getCrewProfile,
    setCrewProfile,
    getUiLang,
    setUiLang,
    applyUiTranslations,
    getTheme,
    setTheme,
    toggleTheme,
    initTheme,
    initCosmicPreloader,
    getSession,
    saveSession,
    clearSession,
    getFacePortrait,
    saveFacePortrait,
    getHistory,
    appendHistory,
    resetHistoryToSeed,
    replaceHistory,
    exportHistoryCsv,
    getFooterCredits,
    saveFooterCredits,
    showToast,
    getEmergencyProtocols,
    selectEmergencySymptom,
    openEmergencyModal,
    closeEmergencyModal,
    toggleCopilot,
    askCopilot,
    get CHATBOT_API_BASE() { return getChatbotApiBase(); },
    isLocalOrigin,
    resolveChatbotApiBase,
    getChatbotApiBase,
    setChatbotApiBase,
    getChatbotAstronautId,
    syncChatbotContext,
    mountAstroChatWidget,
    loadAstroChatWidgetScript,
    mountFooterInto,
    mountAllBodyHolograms,
    renderShellChrome,
    extractRiskMetrics
  };
})(typeof window !== 'undefined' ? window : globalThis);
