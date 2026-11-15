/**
 * Bio Astro Lab — Circadian Rhythms & Daily Routine Tracking (tracking.js)
 * NASA Space Apps 2026 — Rule-Based Astronaut Health & Routine System
 * Strictly Rule-Based / No AI / LocalStorage Persistent
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'bioAstroLab.tracking.v1';

  // Default initial seed data (NASA HRP flight baseline)
  const DEFAULT_TRACKING_STATE = {
    schedule: {
      bedtime: '22:00',
      waketime: '06:00',
      preset: 'nominal',
      preSleepChecklist: {
        lights: false,
        screens: false,
        hydration: false,
        gear: false
      }
    },
    weeklySchedule: [
      { day: 'Mon', sol: 'Sol 42', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 7.8, status: 'nominal' },
      { day: 'Tue', sol: 'Sol 43', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 7.5, status: 'nominal' },
      { day: 'Wed', sol: 'Sol 44', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 8.1, status: 'optimal' },
      { day: 'Thu', sol: 'Sol 45', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 7.2, status: 'mild-deficit' },
      { day: 'Fri', sol: 'Sol 46', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 7.9, status: 'nominal' },
      { day: 'Sat', sol: 'Sol 47', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 8.3, status: 'optimal' },
      { day: 'Sun', sol: 'Sol 48', planned: '22:00 - 06:00', targetHours: 8.0, actualHours: 7.6, status: 'nominal' }
    ],
    sleepLogs: [
      {
        id: 'log-1',
        date: '2026-10-14 (Sol 48)',
        bedtime: '22:15',
        waketime: '06:00',
        actualHours: 7.75,
        plannedHours: 8.0,
        awakenings: 1,
        quality: 4,
        notes: 'Felt well-rested. Cabin ventilation noise was minimal.'
      },
      {
        id: 'log-2',
        date: '2026-10-13 (Sol 47)',
        bedtime: '21:50',
        waketime: '06:10',
        actualHours: 8.33,
        plannedHours: 8.0,
        awakenings: 0,
        quality: 5,
        notes: 'Deep uninterrupted sleep following heavy ARED resistance training.'
      },
      {
        id: 'log-3',
        date: '2026-10-12 (Sol 46)',
        bedtime: '22:10',
        waketime: '06:05',
        actualHours: 7.92,
        plannedHours: 8.0,
        awakenings: 1,
        quality: 4,
        notes: 'Slight muscle soreness in calves, sleep eye mask helped.'
      },
      {
        id: 'log-4',
        date: '2026-10-11 (Sol 45)',
        bedtime: '22:45',
        waketime: '06:00',
        actualHours: 7.25,
        plannedHours: 8.0,
        awakenings: 2,
        quality: 3,
        notes: 'Mission EVA prep debrief ran late; took 30 mins to fall asleep.'
      },
      {
        id: 'log-5',
        date: '2026-10-10 (Sol 44)',
        bedtime: '22:00',
        waketime: '06:05',
        actualHours: 8.08,
        plannedHours: 8.0,
        awakenings: 0,
        quality: 5,
        notes: 'Nominal restorative night.'
      },
      {
        id: 'log-6',
        date: '2026-10-09 (Sol 43)',
        bedtime: '22:30',
        waketime: '06:00',
        actualHours: 7.50,
        plannedHours: 8.0,
        awakenings: 1,
        quality: 4,
        notes: 'Standard orbital cycle sleep.'
      },
      {
        id: 'log-7',
        date: '2026-10-08 (Sol 42)',
        bedtime: '22:10',
        waketime: '06:00',
        actualHours: 7.83,
        plannedHours: 8.0,
        awakenings: 1,
        quality: 4,
        notes: 'Cabin air temperature nominal 21°C.'
      }
    ],
    routines: [
      { id: 'r1', title: 'Morning hygiene & circadian blue-light exposure', start: '06:00', end: '06:45', category: 'Wake-up routine', completed: true },
      { id: 'r2', title: 'Breakfast & crew daily morning conference (DMC)', start: '07:00', end: '07:45', category: 'Meals', completed: true },
      { id: 'r3', title: 'ISS science payload & bio-culture maintenance', start: '08:00', end: '11:30', category: 'Work sessions', completed: true },
      { id: 'r4', title: 'ARED Heavy Resistance Exercise (Squats & Rows)', start: '11:30', end: '12:30', category: 'Exercise', completed: true },
      { id: 'r5', title: 'Midday meal & fluid replenishment log', start: '12:45', end: '13:30', category: 'Meals', completed: true },
      { id: 'r6', title: 'Habitat ECLSS inspection & filter valve maintenance', start: '14:00', end: '17:00', category: 'Work sessions', completed: false },
      { id: 'r7', title: 'CEVIS cycle ergometer cardiovascular session (35m)', start: '17:15', end: '18:00', category: 'Exercise', completed: false },
      { id: 'r8', title: 'Evening dinner & crew debrief with Houston CAPCOM', start: '18:30', end: '19:30', category: 'Meals', completed: false },
      { id: 'r9', title: 'Downtime, orbital window viewing & family comms', start: '19:30', end: '21:00', category: 'Breaks and relaxation', completed: false },
      { id: 'r10', title: 'Pre-sleep wind-down checklist & dim lighting protocol', start: '21:00', end: '22:00', category: 'Sleep preparation', completed: false },
      { id: 'r11', title: 'Crew quarters sleep block (Cabin blackout)', start: '22:00', end: '06:00', category: 'Bedtime', completed: false }
    ]
  };

  let trackingState = null;
  let sleepChartInstance = null;

  // --- Utility Functions ---

  function timeToMinutes(t) {
    if (!t || typeof t !== 'string') return 0;
    const parts = t.split(':').map(Number);
    return (parts[0] || 0) * 60 + (parts[1] || 0);
  }

  function minutesToFormatted(mins) {
    const h = Math.floor(mins / 60);
    const m = Math.round(mins % 60);
    return `${h}h ${m < 10 ? '0' : ''}${m}m`;
  }

  function calculateDurationMinutes(start, end) {
    const s = timeToMinutes(start);
    const e = timeToMinutes(end);
    let diff = e - s;
    if (diff <= 0) diff += 1440; // spans past midnight
    return diff;
  }

  function calculateDurationHours(start, end) {
    const mins = calculateDurationMinutes(start, end);
    return Math.round((mins / 60) * 100) / 100;
  }

  // --- Local Storage Management ---

  function loadTrackingState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.schedule && Array.isArray(parsed.sleepLogs) && Array.isArray(parsed.routines)) {
          return parsed;
        }
      }
    } catch (e) {
      console.warn('[Tracking] Failed to parse local storage, loading default seed.', e);
    }
    return JSON.parse(JSON.stringify(DEFAULT_TRACKING_STATE));
  }

  function saveTrackingState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trackingState));
    } catch (e) {
      console.error('[Tracking] Failed to save state to localStorage', e);
    }
  }

  // --- Active Light Phase Calculation ---

  function getCurrentActiveLightPhase() {
    const now = new Date();
    const currentMins = now.getHours() * 60 + now.getMinutes();

    // 00:00 - 06:00 Sleep/Dark
    // 06:00 - 08:00 Morning Wake-up
    // 08:00 - 19:30 Daytime Working
    // 19:30 - 22:00 Evening Wind-Down
    // 22:00 - 24:00 Sleep/Dark
    if (currentMins >= 360 && currentMins < 480) {
      return { phase: 'Morning / Wake-up Lighting', spec: 'Blue-Enriched (480nm) · 06:00 – 08:00', color: '#00E5FF' };
    } else if (currentMins >= 480 && currentMins < 1170) {
      return { phase: 'Daytime Nominal', spec: '500 Lux Full-Spectrum · 08:00 – 19:30', color: '#43A047' };
    } else if (currentMins >= 1170 && currentMins < 1320) {
      return { phase: 'Evening Wind-Down', spec: 'Amber <50 Lux · 19:30 – 22:00', color: '#FB8C00' };
    } else {
      return { phase: 'Sleep / Dark Period', spec: '0 Lux Blackout · 22:00 – 06:00', color: '#90CAF9' };
    }
  }

  // --- Rendering UI Modules ---

  function renderDashboardSummary() {
    const sched = trackingState.schedule;
    const durMins = calculateDurationMinutes(sched.bedtime, sched.waketime);
    const durHrs = (durMins / 60).toFixed(1);

    // 1. Planned Sleep
    const kpiPlannedSleep = document.getElementById('kpiPlannedSleep');
    const kpiPlannedTimes = document.getElementById('kpiPlannedTimes');
    if (kpiPlannedSleep) kpiPlannedSleep.textContent = minutesToFormatted(durMins);
    if (kpiPlannedTimes) kpiPlannedTimes.textContent = `${sched.bedtime} – ${sched.waketime} (${durHrs} hrs)`;

    // 2. Last Recorded Sleep
    const kpiLastSleep = document.getElementById('kpiLastSleep');
    const kpiSleepDiff = document.getElementById('kpiSleepDiff');
    const lastLog = trackingState.sleepLogs[0];
    if (lastLog) {
      const actualMins = Math.round(lastLog.actualHours * 60);
      if (kpiLastSleep) kpiLastSleep.textContent = minutesToFormatted(actualMins);
      const diffMins = actualMins - durMins;
      const diffSign = diffMins >= 0 ? `+${diffMins}m` : `${diffMins}m`;
      if (kpiSleepDiff) {
        kpiSleepDiff.textContent = `${diffSign} vs planned target`;
        kpiSleepDiff.style.color = Math.abs(diffMins) <= 30 ? 'var(--accent-nominal)' : 'var(--accent-vermilion-paper)';
      }
    }

    // 3. Sleep Schedule Status / Countdown
    const kpiNextEvent = document.getElementById('kpiNextEvent');
    const kpiCountdown = document.getElementById('kpiCountdown');
    const now = new Date();
    const nowMins = now.getHours() * 60 + now.getMinutes();
    const bedMins = timeToMinutes(sched.bedtime);
    const prepMins = (bedMins - 60 + 1440) % 1440;

    if (nowMins >= prepMins && nowMins < bedMins) {
      if (kpiNextEvent) kpiNextEvent.textContent = 'Active: Sleep Wind-Down';
      const toBed = bedMins - nowMins;
      if (kpiCountdown) kpiCountdown.textContent = `Bedtime in ${toBed}m (${sched.bedtime})`;
    } else if (nowMins >= bedMins || nowMins < timeToMinutes(sched.waketime)) {
      if (kpiNextEvent) kpiNextEvent.textContent = 'Active: Sleep Quarters';
      const wakeM = timeToMinutes(sched.waketime);
      let toWake = wakeM - nowMins;
      if (toWake < 0) toWake += 1440;
      if (kpiCountdown) kpiCountdown.textContent = `Wakeup at ${sched.waketime} (in ${Math.floor(toWake/60)}h ${toWake%60}m)`;
    } else {
      if (kpiNextEvent) kpiNextEvent.textContent = 'Next: Sleep Prep (T-60m)';
      let toPrep = prepMins - nowMins;
      if (toPrep < 0) toPrep += 1440;
      const prepHourStr = `${Math.floor(prepMins/60).toString().padStart(2, '0')}:${(prepMins%60).toString().padStart(2, '0')}`;
      if (kpiCountdown) kpiCountdown.textContent = `T- ${Math.floor(toPrep/60)}h ${toPrep%60}m (at ${prepHourStr})`;
    }

    // 4. Daily Routine Progress
    const kpiRoutinePct = document.getElementById('kpiRoutinePct');
    const kpiRoutineCounts = document.getElementById('kpiRoutineCounts');
    const totalRoutines = trackingState.routines.length;
    const completedRoutines = trackingState.routines.filter(r => r.completed).length;
    const routinePct = totalRoutines > 0 ? Math.round((completedRoutines / totalRoutines) * 100) : 0;
    if (kpiRoutinePct) kpiRoutinePct.textContent = `${routinePct}%`;
    if (kpiRoutineCounts) kpiRoutineCounts.textContent = `${completedRoutines} of ${totalRoutines} activities completed`;

    // 5. Active Light Phase
    const kpiLightPhase = document.getElementById('kpiLightPhase');
    if (kpiLightPhase) {
      const activePhase = getCurrentActiveLightPhase();
      kpiLightPhase.textContent = activePhase.phase;
      kpiLightPhase.style.color = activePhase.color;
      const sub = kpiLightPhase.parentElement.querySelector('.kpi-sub');
      if (sub) sub.textContent = activePhase.spec;
    }
  }

  function renderWeeklyScheduleStrip() {
    const wrap = document.getElementById('weeklyScheduleGrid');
    if (!wrap) return;

    const plannedHrs = calculateDurationHours(trackingState.schedule.bedtime, trackingState.schedule.waketime);
    const html = trackingState.weeklySchedule.map(item => {
      const diff = Math.round((item.actualHours - plannedHrs) * 10) / 10;
      const diffStr = diff >= 0 ? `+${diff}h` : `${diff}h`;
      const badgeClass = item.status === 'optimal' ? 'badge-nominal' : (item.status === 'nominal' ? 'badge-ghost' : 'badge-warn');
      return `
        <div style="background:var(--bg-paper);border:1px solid var(--border-paper);border-radius:4px;padding:8px 6px;text-align:center;min-width:76px;">
          <div class="mono-num" style="font-size:11px;font-weight:700;color:var(--ink-paper);">${item.day}</div>
          <div style="font-size:10px;color:var(--ink-muted-paper);">${item.sol}</div>
          <div class="mono-num" style="font-size:13px;font-weight:700;margin:4px 0;color:var(--accent-nominal-dark);">${item.actualHours.toFixed(1)}h</div>
          <span class="badge ${badgeClass}" style="font-size:9.5px;padding:1px 4px;">${diffStr}</span>
        </div>
      `;
    }).join('');

    wrap.innerHTML = html;
  }

  function renderPreSleepChecklist() {
    const checks = trackingState.schedule.preSleepChecklist || {};
    const inputNodes = document.querySelectorAll('.prep-check');
    let completedCount = 0;

    inputNodes.forEach(node => {
      const key = node.getAttribute('data-item');
      const isDone = !!checks[key];
      node.checked = isDone;
      if (isDone) completedCount++;
    });

    const badge = document.getElementById('prepBadge');
    if (badge) {
      if (completedCount === inputNodes.length && inputNodes.length > 0) {
        badge.className = 'badge badge-nominal';
        badge.textContent = `Completed (${completedCount}/${inputNodes.length})`;
      } else if (completedCount > 0) {
        badge.className = 'badge badge-warn';
        badge.textContent = `In Progress (${completedCount}/${inputNodes.length})`;
      } else {
        badge.className = 'badge badge-ghost';
        badge.textContent = `Pending (0/${inputNodes.length})`;
      }
    }
  }

  function renderSleepTrendsAndChart() {
    const logs = trackingState.sleepLogs || [];
    if (logs.length === 0) return;

    // Calculate Metrics
    const totalActual = logs.reduce((sum, item) => sum + (Number(item.actualHours) || 0), 0);
    const avgSleep = (totalActual / logs.length).toFixed(1);

    const totalPlanned = logs.reduce((sum, item) => sum + (Number(item.plannedHours) || 8.0), 0);
    const netDebt = (totalActual - totalPlanned).toFixed(1);

    // Consistency score = 100 - (mean absolute deviation from planned in hours * 10)
    const totalAbsDev = logs.reduce((sum, item) => sum + Math.abs((Number(item.actualHours) || 0) - (Number(item.plannedHours) || 8.0)), 0);
    const meanDev = totalAbsDev / logs.length;
    const consistencyPct = Math.max(70, Math.min(100, Math.round(100 - (meanDev * 12))));

    const statAvgSleep = document.getElementById('statAvgSleep');
    const statConsistency = document.getElementById('statConsistency');
    const statSleepDebt = document.getElementById('statSleepDebt');

    if (statAvgSleep) statAvgSleep.textContent = `${avgSleep} hrs`;
    if (statConsistency) statConsistency.textContent = `${consistencyPct}%`;
    if (statSleepDebt) {
      const debtVal = Number(netDebt);
      statSleepDebt.textContent = debtVal >= 0 ? `+${debtVal} hrs` : `${debtVal} hrs`;
      statSleepDebt.style.color = debtVal >= 0 ? 'var(--accent-nominal)' : 'var(--accent-vermilion-paper)';
    }

    // Render Chart.js
    const canvas = document.getElementById('sleepDurationChart');
    if (!canvas || typeof Chart === 'undefined') return;

    // Take last 7 entries in chronological order (oldest to newest)
    const chartLogs = [...logs].reverse().slice(-7);
    const labels = chartLogs.map(l => {
      // Short label e.g. "Sol 48" or date
      const match = l.date.match(/Sol \d+/);
      return match ? match[0] : l.date.slice(5, 10);
    });
    const actualData = chartLogs.map(l => l.actualHours);
    const plannedData = chartLogs.map(l => l.plannedHours || 8.0);

    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)';
    const textColor = isLight ? '#4B5563' : '#8A99AD';

    if (sleepChartInstance) {
      sleepChartInstance.destroy();
    }

    sleepChartInstance = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Actual Sleep (hrs)',
            data: actualData,
            backgroundColor: isLight ? 'rgba(43, 108, 163, 0.75)' : 'rgba(0, 229, 255, 0.65)',
            borderColor: isLight ? '#2B6CA3' : '#00E5FF',
            borderWidth: 1.5,
            borderRadius: 3,
            order: 2
          },
          {
            label: 'Planned Target (hrs)',
            data: plannedData,
            type: 'line',
            borderColor: isLight ? '#D14D28' : '#FB8C00',
            backgroundColor: 'transparent',
            borderWidth: 2,
            borderDash: [5, 5],
            pointRadius: 4,
            pointBackgroundColor: isLight ? '#D14D28' : '#FB8C00',
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              boxWidth: 12,
              font: { size: 11, family: 'Space Grotesk, sans-serif' },
              color: textColor
            }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} hrs`
            }
          }
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: textColor, font: { size: 11, family: 'Space Grotesk, monospace' } }
          },
          y: {
            min: 4,
            max: 10,
            grid: { color: gridColor },
            ticks: {
              stepSize: 1,
              color: textColor,
              font: { size: 11, family: 'Space Grotesk, monospace' },
              callback: (val) => `${val}h`
            }
          }
        }
      }
    });
  }

  function renderSleepHistoryTable() {
    const tbody = document.getElementById('sleepHistoryTableBody');
    if (!tbody) return;

    if (trackingState.sleepLogs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:var(--ink-muted-paper);padding:16px;">No sleep logs recorded yet.</td></tr>`;
      return;
    }

    const html = trackingState.sleepLogs.map(item => {
      const stars = '★'.repeat(item.quality) + '☆'.repeat(5 - item.quality);
      const diff = Math.round(((item.actualHours || 0) - (item.plannedHours || 8.0)) * 10) / 10;
      const diffBadge = diff >= 0 
        ? `<span class="badge badge-nominal">+${diff}h</span>`
        : `<span class="badge badge-warn">${diff}h</span>`;

      return `
        <tr>
          <td class="mono-num" style="font-weight:600;">${item.date}</td>
          <td class="mono-num">${item.bedtime}</td>
          <td class="mono-num">${item.waketime}</td>
          <td class="mono-num" style="font-weight:700;color:var(--accent-nominal-dark);">${Number(item.actualHours).toFixed(2)}h</td>
          <td>${item.plannedHours ? item.plannedHours.toFixed(1) + 'h ' + diffBadge : '8.0h'}</td>
          <td class="mono-num">${item.awakenings || 0}</td>
          <td><span style="color:#F59E0B;letter-spacing:1px;" title="${item.quality}/5">${stars}</span></td>
          <td style="max-width:260px;font-size:11.5px;color:var(--ink-muted-paper);">${item.notes || '—'}</td>
          <td>
            <button type="button" class="btn-outline delete-sleep-log-btn" data-id="${item.id}" style="padding:2px 8px;font-size:11px;color:var(--accent-vermilion-paper);">Delete</button>
          </td>
        </tr>
      `;
    }).join('');

    tbody.innerHTML = html;

    // Attach delete listeners
    tbody.querySelectorAll('.delete-sleep-log-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        if (confirm('Delete this historical sleep record?')) {
          trackingState.sleepLogs = trackingState.sleepLogs.filter(l => l.id !== id);
          saveTrackingState();
          renderDashboardSummary();
          renderSleepTrendsAndChart();
          renderSleepHistoryTable();
        }
      });
    });
  }

  function renderRoutineList() {
    const wrap = document.getElementById('routineListWrap');
    if (!wrap) return;

    if (trackingState.routines.length === 0) {
      wrap.innerHTML = `<div style="text-align:center;padding:20px;color:var(--ink-muted-paper);">No routine activities registered today. Click "+ Add Activity" above.</div>`;
      return;
    }

    const html = trackingState.routines.map(item => {
      const isDone = !!item.completed;
      return `
        <div class="routine-item ${isDone ? 'completed' : ''}" data-id="${item.id}">
          <input type="checkbox" class="routine-check" data-id="${item.id}" ${isDone ? 'checked' : ''} aria-label="Mark ${item.title} as completed">
          <div class="routine-time mono-num">${item.start} – ${item.end}</div>
          <div class="routine-content">
            <div class="routine-title">${item.title}</div>
            <div class="routine-cat">${item.category}</div>
          </div>
          <button type="button" class="btn-outline delete-routine-btn" data-id="${item.id}" style="padding:2px 6px;font-size:11px;color:var(--ink-muted-paper);" title="Remove activity">&times;</button>
        </div>
      `;
    }).join('');

    wrap.innerHTML = html;

    // Checkbox toggle listener
    wrap.querySelectorAll('.routine-check').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const id = e.target.getAttribute('data-id');
        const routine = trackingState.routines.find(r => r.id === id);
        if (routine) {
          routine.completed = e.target.checked;
          saveTrackingState();
          const parentItem = e.target.closest('.routine-item');
          if (parentItem) {
            if (routine.completed) parentItem.classList.add('completed');
            else parentItem.classList.remove('completed');
          }
          renderDashboardSummary();
        }
      });
    });

    // Delete routine listener
    wrap.querySelectorAll('.delete-routine-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        trackingState.routines = trackingState.routines.filter(r => r.id !== id);
        saveTrackingState();
        renderDashboardSummary();
        renderRoutineList();
      });
    });
  }

  // --- Wire Form Submissions & Events ---

  function wireSleepScheduleControls() {
    const form = document.getElementById('sleepScheduleForm');
    const bedtimeInput = document.getElementById('schedBedtime');
    const waketimeInput = document.getElementById('schedWaketime');
    const calcDurationEl = document.getElementById('calcTargetDuration');

    if (bedtimeInput && waketimeInput && calcDurationEl) {
      bedtimeInput.value = trackingState.schedule.bedtime;
      waketimeInput.value = trackingState.schedule.waketime;

      const updateCalc = () => {
        const mins = calculateDurationMinutes(bedtimeInput.value, waketimeInput.value);
        calcDurationEl.textContent = minutesToFormatted(mins);
      };

      bedtimeInput.addEventListener('input', updateCalc);
      waketimeInput.addEventListener('input', updateCalc);
      updateCalc();
    }

    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        trackingState.schedule.bedtime = bedtimeInput.value;
        trackingState.schedule.waketime = waketimeInput.value;
        saveTrackingState();
        renderDashboardSummary();
        renderWeeklyScheduleStrip();
        renderSleepTrendsAndChart();
        alert('Planned sleep schedule saved successfully.');
      });
    }

    // Schedule Presets buttons
    document.querySelectorAll('.schedule-preset-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const preset = e.currentTarget.getAttribute('data-preset');
        if (preset === 'nominal') {
          bedtimeInput.value = '22:00';
          waketimeInput.value = '06:00';
        } else if (preset === 'eva') {
          bedtimeInput.value = '21:30';
          waketimeInput.value = '06:00';
        } else if (preset === 'shift') {
          bedtimeInput.value = '23:00';
          waketimeInput.value = '06:30';
        }
        const mins = calculateDurationMinutes(bedtimeInput.value, waketimeInput.value);
        if (calcDurationEl) calcDurationEl.textContent = minutesToFormatted(mins);
      });
    });

    // Pre-sleep checklist items
    document.querySelectorAll('.prep-check').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const item = e.target.getAttribute('data-item');
        if (!trackingState.schedule.preSleepChecklist) {
          trackingState.schedule.preSleepChecklist = {};
        }
        trackingState.schedule.preSleepChecklist[item] = e.target.checked;
        saveTrackingState();
        renderPreSleepChecklist();
      });
    });
  }

  function wireSleepLogForm() {
    const form = document.getElementById('sleepLogForm');
    const sleepTimeInput = document.getElementById('logSleepTime');
    const wakeTimeInput = document.getElementById('logWakeTime');
    const calcHoursEl = document.getElementById('logCalculatedHours');
    const awakeningsEl = document.getElementById('logAwakenings');
    const qualityEl = document.getElementById('logQuality');
    const notesEl = document.getElementById('logNotes');

    const updateLogCalc = () => {
      if (sleepTimeInput && wakeTimeInput && calcHoursEl) {
        const mins = calculateDurationMinutes(sleepTimeInput.value, wakeTimeInput.value);
        calcHoursEl.textContent = minutesToFormatted(mins);
      }
    };

    if (sleepTimeInput && wakeTimeInput) {
      sleepTimeInput.addEventListener('input', updateLogCalc);
      wakeTimeInput.addEventListener('input', updateLogCalc);
      updateLogCalc();
    }

    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const sleepTime = sleepTimeInput.value;
        const wakeTime = wakeTimeInput.value;
        const durHours = calculateDurationHours(sleepTime, wakeTime);

        const now = new Date();
        const dateStr = `${now.toISOString().slice(0, 10)} (Sol 49)`;

        const newLog = {
          id: 'log-' + Date.now(),
          date: dateStr,
          bedtime: sleepTime,
          waketime: wakeTime,
          actualHours: durHours,
          plannedHours: calculateDurationHours(trackingState.schedule.bedtime, trackingState.schedule.waketime),
          awakenings: Number(awakeningsEl.value) || 0,
          quality: Number(qualityEl.value) || 4,
          notes: notesEl.value.trim()
        };

        trackingState.sleepLogs.unshift(newLog);
        saveTrackingState();

        notesEl.value = '';
        renderDashboardSummary();
        renderSleepTrendsAndChart();
        renderSleepHistoryTable();
        alert(`Sleep entry recorded: ${durHours} hours logged.`);
      });
    }
  }

  function wireRoutineControls() {
    const toggleBtn = document.getElementById('toggleAddActivityBtn');
    const addForm = document.getElementById('addActivityForm');
    const cancelBtn = document.getElementById('cancelAddActivityBtn');
    const resetChecklistBtn = document.getElementById('resetChecklistBtn');

    if (toggleBtn && addForm) {
      toggleBtn.addEventListener('click', () => {
        addForm.classList.toggle('hidden');
      });
    }

    if (cancelBtn && addForm) {
      cancelBtn.addEventListener('click', () => {
        addForm.classList.add('hidden');
      });
    }

    if (addForm) {
      addForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const title = document.getElementById('actName').value.trim();
        const start = document.getElementById('actStart').value;
        const end = document.getElementById('actEnd').value;
        const category = document.getElementById('actCategory').value;

        if (!title) return;

        const newRoutine = {
          id: 'r-' + Date.now(),
          title,
          start,
          end,
          category,
          completed: false
        };

        trackingState.routines.push(newRoutine);
        // Sort routines by start time
        trackingState.routines.sort((a, b) => timeToMinutes(a.start) - timeToMinutes(b.start));

        saveTrackingState();
        addForm.reset();
        addForm.classList.add('hidden');
        renderDashboardSummary();
        renderRoutineList();
      });
    }

    if (resetChecklistBtn) {
      resetChecklistBtn.addEventListener('click', () => {
        if (confirm('Reset all daily routine checkmarks for a new day? Your activities and sleep history will be preserved.')) {
          trackingState.routines.forEach(r => { r.completed = false; });
          saveTrackingState();
          renderDashboardSummary();
          renderRoutineList();
        }
      });
    }

    // Reset Tracking Seed Button
    const resetSeedBtn = document.getElementById('resetTrackingSeedBtn');
    if (resetSeedBtn) {
      resetSeedBtn.addEventListener('click', () => {
        if (confirm('Reset tracking data back to NASA flight seed baseline? This will overwrite manual changes.')) {
          trackingState = JSON.parse(JSON.stringify(DEFAULT_TRACKING_STATE));
          saveTrackingState();
          initAll();
        }
      });
    }
  }

  function initAll() {
    if (global.BioShell && typeof global.BioShell.renderShellChrome === 'function') {
      global.BioShell.renderShellChrome({ activeRoute: 'tracking.html', showFooter: true });
    }
    trackingState = loadTrackingState();
    renderDashboardSummary();
    renderWeeklyScheduleStrip();
    renderPreSleepChecklist();
    renderSleepTrendsAndChart();
    renderSleepHistoryTable();
    renderRoutineList();
    wireSleepScheduleControls();
    wireSleepLogForm();
    wireRoutineControls();
  }

  // Run when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Export to global for debug or testing
  global.BioTracking = {
    getState: () => trackingState,
    resetToSeed: () => {
      trackingState = JSON.parse(JSON.stringify(DEFAULT_TRACKING_STATE));
      saveTrackingState();
      initAll();
    }
  };

})(window);
