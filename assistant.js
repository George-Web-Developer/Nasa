/**
 * Bio Astro Lab — Dedicated Full-Page AI Assistant Controller
 */
(function (global) {
  'use strict';

  function getEl(id) {
    return document.getElementById(id);
  }

  function renderTelemetrySidebar() {
    const shell = global.BioShell;
    if (!shell) return;
    const envEl = getEl('assistantEnvTag');
    if (envEl) envEl.textContent = shell.getEnvironment().toUpperCase();

    const grid = getEl('assistantVitalsGrid');
    if (!grid) return;

    const sess = shell.getSession();
    const feats = (sess && sess.features) || {};
    const evalOut = sess && sess.result ? sess.result : (typeof global.evaluateAstronautHealth === 'function' && sess ? global.evaluateAstronautHealth(feats) : null);
    const metrics = evalOut ? shell.extractRiskMetrics(evalOut) : null;

    const fmt = (val, unit, decimals) => {
      if (!Number.isFinite(val)) return '—';
      const num = decimals != null ? Number(val).toFixed(decimals) : Math.round(val);
      return `${num}${unit ? ' ' + unit : ''}`;
    };

    const chips = [
      { k: 'Clinical Status', v: metrics ? `${metrics.status} (${Number.isFinite(metrics.riskPct) ? metrics.riskPct.toFixed(0) + '%' : '--'})` : 'Pending Scan' },
      { k: 'Heart Rate', v: fmt(feats.heart_rate_bpm, 'BPM') },
      { k: 'SpO2', v: fmt(feats.spo2_pct, '%', 1) },
      { k: 'Sleep', v: fmt(feats.sleep_hours, 'hrs', 1) },
      { k: 'Balance', v: fmt(feats.balance_score, '%', 0) },
      { k: 'Cabin CO2', v: fmt(feats.cabin_co2_mmhg, 'mmHg', 1) }
    ];

    grid.innerHTML = chips
      .map((c) => `
        <div class="assistant-vital-chip">
          <div class="v-k">${shell.escapeHtml(c.k)}</div>
          <div class="v-v">${shell.escapeHtml(c.v)}</div>
        </div>`)
      .join('');
  }

  async function checkBackendHealth() {
    const shell = global.BioShell;
    const apiBase = (shell && shell.CHATBOT_API_BASE) || 'http://127.0.0.1:8000';
    const pill = getEl('chatBackendStatusPill');
    const help = getEl('chatBackendHelpText');
    const fallbackBtn = getEl('openOfflineFallbackBtn');

    try {
      const res = await fetch(`${apiBase}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (pill) {
        pill.textContent = 'Online';
        pill.className = 'assistant-status-pill online';
      }
      if (help) {
        const modeNote = data && data.mock_llm ? 'Demo reply mode (MOCK_LLM=true — no API key needed).' : 'Live LLM connected.';
        help.innerHTML = `Connected to FastAPI service at <code>${apiBase}</code>. ${modeNote}`;
      }
      if (fallbackBtn) fallbackBtn.classList.add('hidden');
      return true;
    } catch (_err) {
      if (pill) {
        pill.textContent = 'Offline';
        pill.className = 'assistant-status-pill offline';
      }
      if (help) {
        help.innerHTML = `Server not detected on <code>${apiBase}</code>. Double-click <code>Chat Bot\\run.bat</code> to start live assistant sessions, or use the offline NASA guide below.`;
      }
      if (fallbackBtn) fallbackBtn.classList.remove('hidden');
      return false;
    }
  }

  function updateSessionMeta(sessionId, mode) {
    const el = getEl('assistantSessionMeta');
    const shell = global.BioShell;
    if (!el || !shell) return;
    const crew = shell.getCrewProfile();
    const modeLabel = mode === 'session' ? 'Daily Check-in (7Q)' : 'Open Discussion';
    el.innerHTML = `Crew: ${shell.escapeHtml(crew.name)}<br>Session ID: ${shell.escapeHtml(sessionId || 'Not connected')}<br>Mode: ${shell.escapeHtml(modeLabel)}`;
  }

  function mountTabAssistant() {
    const shell = global.BioShell;
    const mount = getEl('assistantChatMount');
    if (!shell || !mount) return;

    const selectedMode = getEl('assistantModeSelect')?.value || 'companion';
    mount.innerHTML = '';
    const el = document.createElement('astro-chat');
    el.id = 'bioAstroChatWidget';
    el.setAttribute('mode', 'tab');
    el.setAttribute('session-mode', selectedMode);
    el.setAttribute('api-base', shell.CHATBOT_API_BASE || 'http://127.0.0.1:8000');
    el.setAttribute('astronaut-id', String(shell.getChatbotAstronautId ? shell.getChatbotAstronautId() : 1));
    el.setAttribute('mission-day', '42');
    el.setAttribute('language', 'en');
    el.setAttribute('theme', 'dark');
    el.setAttribute('title-text', 'Mission Assistant');
    mount.appendChild(el);
    shell.syncChatbotContext?.({ currentTab: 'assistant.html' });
  }

  function bootstrapAssistant() {
    const shell = global.BioShell;
    if (!shell) return;
    shell.renderShellChrome({ activeRoute: 'assistant.html' });

    const crewSel = getEl('assistantCrewSelect');
    if (crewSel) {
      const profiles = shell.getCrewProfiles ? shell.getCrewProfiles() : [];
      const current = shell.getCrewProfile ? shell.getCrewProfile() : { id: 'C001' };
      crewSel.innerHTML = profiles
        .map((p) => `<option value="${shell.escapeHtml(p.id)}" ${p.id === current.id ? 'selected' : ''}>${shell.escapeHtml(p.name)}</option>`)
        .join('');
      crewSel.addEventListener('change', (e) => {
        const picked = shell.setCrewProfile(e.target.value);
        shell.syncChatbotContext?.({ currentTab: 'assistant.html' });
        updateSessionMeta(global.AstroChat?.getSessionId?.(), 'tab');
        shell.showToast('Active crew profile: ' + picked.name, 'nominal');
      });
    }

    renderTelemetrySidebar();
    mountTabAssistant();
    checkBackendHealth();

    document.addEventListener('bio:env-change', () => {
      renderTelemetrySidebar();
      shell.syncChatbotContext?.({ currentTab: 'assistant.html' });
    });

    global.addEventListener('astro:session', (e) => {
      const detail = e && e.detail ? e.detail : {};
      updateSessionMeta(detail.session_id, detail.mode || 'tab');
      checkBackendHealth();
    });

    global.addEventListener('astro:backend-offline', () => {
      checkBackendHealth();
    });

    getEl('assistantModeSelect')?.addEventListener('change', (e) => {
      const nextMode = e.target.value === 'session' ? 'session' : 'companion';
      mountTabAssistant();
      updateSessionMeta(global.AstroChat?.getSessionId?.(), nextMode);
      shell.showToast(nextMode === 'companion' ? 'Switched to Open Discussion mode' : 'Switched to Daily Check-in (7Q) mode', 'nominal');
    });

    getEl('restartChatSessionBtn')?.addEventListener('click', () => {
      mountTabAssistant();
      shell.showToast('Started a fresh assistant session', 'nominal');
    });

    getEl('retryChatBackendBtn')?.addEventListener('click', async () => {
      const ok = await checkBackendHealth();
      if (ok) {
        mountTabAssistant();
        shell.showToast('Connected to Mission Assistant service', 'nominal');
      } else {
        shell.showToast('Start Chat Bot\\run.bat first to connect port 8000');
      }
    });

    getEl('syncTelemetryBtn')?.addEventListener('click', () => {
      renderTelemetrySidebar();
      shell.syncChatbotContext?.({ currentTab: 'assistant.html', note: 'Manual telemetry refresh.' });
      shell.showToast('Latest Scan vitals synced to assistant context', 'nominal');
    });

    getEl('openOfflineFallbackBtn')?.addEventListener('click', () => {
      global.location.href = 'guide.html';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapAssistant);
  } else {
    bootstrapAssistant();
  }
})(typeof window !== 'undefined' ? window : globalThis);
