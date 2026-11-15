/**
 * Bio Astro Lab — Mission History Table, Multi-Series Chart.js & Safe CSV Export/Import (history.js)
 */
(function (global) {
  'use strict';

  const CHART_PALETTE = ['#17191E', '#1C7C54', '#D14D28', '#2B6CA3'];

  const METRIC_GROUPS = {
    readiness: {
      hint: 'Healthy target: keep Overall Health Risk low (0-25%), Body Balance high (85-100%), and Left/Right Leg Difference small (< 5 deg).',
      leftTitle: 'Percentage (%)',
      rightTitle: 'Leg Asymmetry (deg)',
      series: [
        { label: 'Overall Health Risk (%)', unit: '%', yAxisID: 'y', extract: (e) => e.riskPct },
        { label: 'Body Balance Score (%)', unit: '%', yAxisID: 'y', extract: (e) => e.features?.balance_score },
        { label: 'Left / Right Leg Diff (°)', unit: '°', yAxisID: 'y1', extract: (e) => e.features?.joint_symmetry_diff }
      ]
    },
    cardio: {
      hint: 'Healthy target: resting Heart Rate 55-90 BPM, Systolic BP 95-130 mmHg, and Blood Oxygen SpO2 >= 95%.',
      leftTitle: 'BPM / mmHg / %',
      rightTitle: '',
      series: [
        { label: 'Heart Rate (BPM)', unit: ' BPM', yAxisID: 'y', extract: (e) => e.features?.heart_rate_bpm },
        { label: 'Systolic BP (mmHg)', unit: ' mmHg', yAxisID: 'y', extract: (e) => e.features?.systolic_bp },
        { label: 'Blood Oxygen SpO2 (%)', unit: '%', yAxisID: 'y', extract: (e) => e.features?.spo2_pct }
      ]
    },
    metabolic: {
      hint: 'Healthy target: Blood Glucose 70-115 mg/dL (left axis) and Sleep 7-8.5 hrs + Body Temp ~36.8 C (right axis).',
      leftTitle: 'Glucose (mg/dL)',
      rightTitle: 'Sleep (hrs) / Temp (°C)',
      series: [
        { label: 'Blood Glucose (mg/dL)', unit: ' mg/dL', yAxisID: 'y', extract: (e) => e.features?.blood_glucose },
        { label: 'Sleep Duration (hrs)', unit: ' hrs', yAxisID: 'y1', extract: (e) => e.features?.sleep_hours },
        { label: 'Body Temp (°C)', unit: ' °C', yAxisID: 'y1', extract: (e) => e.features?.body_temp }
      ]
    },
    hazards: {
      hint: 'Healthy target: keep Cabin CO2 <= 2.0 mmHg (left axis) and daily Radiation Dose low (right axis).',
      leftTitle: 'Cabin CO2 (mmHg)',
      rightTitle: 'Radiation (mSv/day)',
      series: [
        { label: 'Cabin CO2 Level (mmHg)', unit: ' mmHg', yAxisID: 'y', extract: (e) => e.features?.cabin_co2_mmhg },
        { label: 'Radiation Dose (mSv/d)', unit: ' mSv/d', yAxisID: 'y1', extract: (e) => e.features?.radiation_dose_msv }
      ]
    }
  };

  let activeGroup = 'readiness';
  let activeStyle = 'line';
  let activeCrewFilter = 'all';
  let chartInstance = null;

  function fmtVal(val, suffix) {
    return typeof val === 'number' && Number.isFinite(val) ? `${val}${suffix || ''}` : '--';
  }

  function getFilteredRows() {
    if (!global.BioShell) return [];
    const all = global.BioShell.getHistory();
    if (activeCrewFilter === 'all') return all;
    return all.filter((e) => String(e.crewId || 'C001') === activeCrewFilter);
  }

  function renderHistoryTable() {
    const tbody = document.getElementById('historyTableBody');
    const countLabel = document.getElementById('historyCountLabel');
    if (!tbody || !global.BioShell) return;

    const esc = global.BioShell.escapeHtml;
    const rows = getFilteredRows();
    if (countLabel) countLabel.textContent = `${rows.length} record(s)`;

    tbody.innerHTML = rows
      .map((entry) => {
        const f = entry.features || {};
        const parsedDate = entry.timestamp ? new Date(entry.timestamp) : null;
        const dt = parsedDate && !Number.isNaN(parsedDate.getTime()) ? parsedDate.toLocaleString() : '--';
        const statusUpper = String(entry.status || 'NORMAL').toUpperCase();
        const badgeCls = statusUpper.includes('RISK') || statusUpper.includes('CRITICAL')
          ? 'badge-critical'
          : statusUpper.includes('MONITOR') || statusUpper.includes('CAUTION')
          ? 'badge-caution'
          : 'badge-nominal';
        const bpStr = Number.isFinite(f.systolic_bp) && Number.isFinite(f.diastolic_bp)
          ? `${Math.round(f.systolic_bp)}/${Math.round(f.diastolic_bp)}`
          : '--';
        const diffStr = Number.isFinite(f.joint_symmetry_diff) ? `±${f.joint_symmetry_diff.toFixed(1)}°` : '--';
        const crewTag = entry.crewId || 'C001';

        return `<tr>
          <td class="mono-num" style="font-size:11.5px;white-space:nowrap;">${esc(dt)}</td>
          <td><strong>${esc(entry.label)}</strong><div class="mono-num" style="font-size:10.5px;color:var(--ink-muted-paper);">${esc(crewTag)} · ${esc(entry.source || '')}</div></td>
          <td>${esc(entry.environment)}</td>
          <td class="mono-num">${esc(entry.scanMode || 'Walk')}</td>
          <td><span class="badge ${badgeCls}">${esc(entry.status)}</span></td>
          <td class="mono-num"><strong>${Number.isFinite(entry.riskPct) ? entry.riskPct + '%' : '--'}</strong></td>
          <td class="mono-num">${esc(fmtVal(f.heart_rate_bpm, ' BPM'))} / ${esc(fmtVal(f.spo2_pct, '%'))}</td>
          <td class="mono-num">${esc(fmtVal(f.blood_glucose, ''))} / ${esc(bpStr)}</td>
          <td class="mono-num">${esc(fmtVal(f.balance_score, '%'))} / ${esc(diffStr)}</td>
        </tr>`;
      })
      .join('');

    renderHistoryChart(rows);
  }

  function renderOfflineSvgChart(wrap, labels, datasets, style) {
    if (!wrap) return;
    const esc = global.BioShell ? global.BioShell.escapeHtml : (s) => String(s || '');
    const W = 900;
    const H = 285;
    const padL = style === 'hbar' ? 145 : 46;
    const padR = 24;
    const padT = 18;
    const padB = 34;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const n = Math.max(1, labels.length);
    const allVals = datasets.flatMap((d) => d.data.filter((v) => typeof v === 'number' && Number.isFinite(v)));
    const maxV = Math.max(10, ...allVals, 100);
    const gridLines = [0, 0.25, 0.5, 0.75, 1];
    let svgInner = '';

    if (style === 'hbar') {
      svgInner += gridLines.map((f) => {
        const x = padL + f * plotW;
        return `<line x1="${x}" y1="${padT}" x2="${x}" y2="${H - padB}" stroke="rgba(20,24,31,0.1)" stroke-width="1"/>
                <text x="${x}" y="${H - 12}" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="#68707C">${Math.round(f * maxV)}</text>`;
      }).join('');
      const rowH = plotH / n;
      const barH = Math.max(4, Math.min(12, (rowH - 8) / Math.max(1, datasets.length)));
      labels.forEach((lbl, i) => {
        const y0 = padT + i * rowH + 4;
        svgInner += `<text x="${padL - 8}" y="${y0 + rowH / 2 - 2}" text-anchor="end" font-family="var(--font-mono)" font-size="10" fill="#4B525E">${esc(lbl.slice(0, 22))}</text>`;
        datasets.forEach((ds, si) => {
          const val = ds.data[i];
          if (typeof val !== 'number' || !Number.isFinite(val)) return;
          const bw = Math.max(2, (val / maxV) * plotW);
          const y = y0 + si * (barH + 2);
          svgInner += `<rect x="${padL}" y="${y}" width="${bw}" height="${barH}" rx="2" fill="${ds.borderColor}" opacity="0.88"/>`;
        });
      });
    } else {
      svgInner += gridLines.map((f) => {
        const y = padT + (1 - f) * plotH;
        return `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(20,24,31,0.1)" stroke-width="1"/>
                <text x="${padL - 8}" y="${y + 3}" text-anchor="end" font-family="var(--font-mono)" font-size="10" fill="#68707C">${Math.round(f * maxV)}</text>`;
      }).join('');
      labels.forEach((lbl, i) => {
        const x = n === 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW;
        svgInner += `<text x="${x}" y="${H - 12}" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="#68707C">${esc(lbl.slice(0, 18))}</text>`;
      });
      if (style === 'bar') {
        const groupW = plotW / n;
        const barW = Math.max(6, Math.min(20, (groupW * 0.65) / Math.max(1, datasets.length)));
        labels.forEach((_, i) => {
          const cx = n === 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW;
          const startX = cx - (datasets.length * (barW + 2)) / 2;
          datasets.forEach((ds, si) => {
            const val = ds.data[i];
            if (typeof val !== 'number' || !Number.isFinite(val)) return;
            const bh = Math.max(2, (val / maxV) * plotH);
            const y = padT + plotH - bh;
            svgInner += `<rect x="${startX + si * (barW + 2)}" y="${y}" width="${barW}" height="${bh}" rx="2" fill="${ds.borderColor}" opacity="0.88"/>`;
          });
        });
      } else {
        datasets.forEach((ds) => {
          const pts = [];
          ds.data.forEach((val, i) => {
            if (typeof val !== 'number' || !Number.isFinite(val)) return;
            const x = n === 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW;
            const y = padT + (1 - val / maxV) * plotH;
            pts.push({ x, y, val });
          });
          if (pts.length > 0) {
            const dLine = pts.map((p, idx) => `${idx === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
            if (style === 'area' && pts.length > 1) {
              const dArea = `${dLine} L${pts[pts.length - 1].x.toFixed(1)},${padT + plotH} L${pts[0].x.toFixed(1)},${padT + plotH} Z`;
              svgInner += `<path d="${dArea}" fill="${ds.borderColor}" fill-opacity="0.16"/>`;
            }
            svgInner += `<path d="${dLine}" fill="none" stroke="${ds.borderColor}" stroke-width="2.5"/>`;
            pts.forEach((p) => {
              svgInner += `<circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#FBF8F1" stroke="${ds.borderColor}" stroke-width="2"/>`;
            });
          }
        });
      }
    }

    const legend = datasets.map((ds) => `
      <span class="mono-num" style="display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--ink-paper);">
        <span style="width:10px;height:10px;border-radius:50%;background:${ds.borderColor};display:inline-block;"></span>
        ${esc(ds.label)}
      </span>`).join('');

    wrap.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:282px;" role="img" aria-label="Mission telemetry trend chart">${svgInner}</svg>
      <div style="display:flex;justify-content:center;gap:18px;flex-wrap:wrap;margin-top:4px;">${legend}</div>`;
  }

  function renderHistoryChart(rows) {
    const canvas = document.getElementById('vitalsChart');
    const offlineWrap = document.getElementById('offlineSvgChartWrap');
    if (!canvas) return;

    const ordered = (rows || []).slice().sort((a, b) => {
      const ta = a && a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const tb = b && b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return ta - tb;
    });
    const labels = ordered.map((r, i) => {
      const cleanLabel = String(r.label || ('Check-in #' + (i + 1)))
        .replace(/Inspiration4\s+C001\s+/i, 'C001 ')
        .replace(/ISS\s+Circadian\s+/i, 'ISS ')
        .replace(/Solar\s+Particle\s+Radiation\s+Event/i, 'Solar Rad Event')
        .replace(/Rover\s+Scrubber\s+CO2\s*\/\s*Hypoxia/i, 'Rover CO2 Alert')
        .slice(0, 20);
      const parsed = r.timestamp ? new Date(r.timestamp) : null;
      const shortDt = parsed && !Number.isNaN(parsed.getTime())
        ? parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : '';
      return shortDt ? `${cleanLabel} (${shortDt})` : cleanLabel;
    });
    const groupCfg = METRIC_GROUPS[activeGroup] || METRIC_GROUPS.readiness;
    const hintEl = document.getElementById('chartHintText');
    if (hintEl) hintEl.textContent = groupCfg.hint || '';

    const isBar = activeStyle === 'bar' || activeStyle === 'hbar';
    const isHbar = activeStyle === 'hbar';
    const isArea = activeStyle === 'area';

    const datasets = groupCfg.series.map((spec, idx) => {
      const color = CHART_PALETTE[idx % CHART_PALETTE.length];
      const wantsSecondAxis = spec.yAxisID === 'y1';
      return {
        label: spec.label,
        xAxisID: isHbar ? (wantsSecondAxis ? 'x1' : 'x') : 'x',
        yAxisID: isHbar ? 'y' : (spec.yAxisID || 'y'),
        unitSuffix: spec.unit || '',
        data: ordered.map((e) => {
          const v = spec.extract(e);
          return typeof v === 'number' && Number.isFinite(v) ? Number(v.toFixed(2)) : null;
        }),
        borderColor: color,
        backgroundColor: isBar ? color + 'CC' : isArea ? color + '2E' : color + '18',
        borderWidth: isBar ? 1.5 : 2.5,
        borderRadius: isBar ? 4 : 0,
        fill: isArea ? 'origin' : false,
        pointRadius: isBar ? 0 : 5,
        pointHoverRadius: isBar ? 0 : 7,
        tension: 0.25,
        spanGaps: true
      };
    });

    if (typeof global.Chart !== 'function') {
      canvas.classList.add('hidden');
      if (offlineWrap) {
        offlineWrap.classList.remove('hidden');
        renderOfflineSvgChart(offlineWrap, labels, datasets, activeStyle);
      }
      return;
    }

    canvas.classList.remove('hidden');
    offlineWrap?.classList.add('hidden');

    const usesSecondAxis = groupCfg.series.some((s) => s.yAxisID === 'y1');
    const scales = isHbar
      ? {
          x: {
            type: 'linear',
            position: 'bottom',
            beginAtZero: true,
            title: { display: Boolean(groupCfg.leftTitle), text: groupCfg.leftTitle, font: { family: 'B612 Mono, monospace', size: 11 } },
            ticks: { font: { family: 'B612 Mono, monospace', size: 11 } }
          },
          y: {
            type: 'category',
            ticks: { font: { family: 'B612 Mono, monospace', size: 11 } }
          }
        }
      : {
          x: { ticks: { font: { family: 'B612 Mono, monospace', size: 11 } } },
          y: {
            type: 'linear',
            position: 'left',
            title: { display: Boolean(groupCfg.leftTitle), text: groupCfg.leftTitle, font: { family: 'B612 Mono, monospace', size: 11 } },
            ticks: { font: { family: 'B612 Mono, monospace', size: 11 } }
          }
        };
    if (usesSecondAxis && isHbar) {
      scales.x1 = {
        type: 'linear',
        position: 'top',
        beginAtZero: true,
        grid: { drawOnChartArea: false },
        title: { display: Boolean(groupCfg.rightTitle), text: groupCfg.rightTitle, font: { family: 'B612 Mono, monospace', size: 11 } },
        ticks: { font: { family: 'B612 Mono, monospace', size: 11 } }
      };
    } else if (usesSecondAxis) {
      scales.y1 = {
        type: 'linear',
        position: 'right',
        grid: { drawOnChartArea: false },
        title: { display: Boolean(groupCfg.rightTitle), text: groupCfg.rightTitle, font: { family: 'B612 Mono, monospace', size: 11 } },
        ticks: { font: { family: 'B612 Mono, monospace', size: 11 } }
      };
    }

    if (chartInstance) chartInstance.destroy();
    chartInstance = new global.Chart(canvas.getContext('2d'), {
      type: isBar ? 'bar' : 'line',
      data: { labels, datasets },
      options: {
        indexAxis: isHbar ? 'y' : 'x',
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        layout: {
          padding: {
            bottom: 28,
            left: 10,
            right: 14,
            top: 10
          }
        },
        interaction: { mode: 'index', axis: isHbar ? 'y' : 'x', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { usePointStyle: true, padding: 16, font: { family: 'B612 Mono, monospace', size: 11.5 } }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const suffix = ctx.dataset.unitSuffix || '';
                const val = ctx.parsed && Number.isFinite(isHbar ? ctx.parsed.x : ctx.parsed.y)
                  ? (isHbar ? ctx.parsed.x : ctx.parsed.y)
                  : '--';
                return ` ${ctx.dataset.label.split(' (')[0]}: ${val}${suffix}`;
              }
            }
          }
        },
        scales
      }
    });
  }

  function exportHistory() {
    if (!global.BioShell) return;
    const csv = global.BioShell.exportHistoryCsv();
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bio_astro_lab_history_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    global.BioShell.showToast('Exported sanitized mission history CSV', 'nominal');
  }

  function bootstrapHistory() {
    if (global.BioShell) {
      global.BioShell.renderShellChrome({ activeRoute: 'history.html', showFooter: true });
    }
    const crewFilterEl = document.getElementById('historyCrewFilter');
    if (crewFilterEl && global.BioShell && typeof global.BioShell.getCrewProfiles === 'function') {
      const esc = global.BioShell.escapeHtml;
      const profiles = global.BioShell.getCrewProfiles();
      crewFilterEl.innerHTML = '<option value="all">All Crew Members</option>' +
        profiles.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
      crewFilterEl.addEventListener('change', () => {
        activeCrewFilter = crewFilterEl.value || 'all';
        renderHistoryTable();
      });
    }
    renderHistoryTable();

    document.querySelectorAll('[data-chart-group]').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeGroup = btn.getAttribute('data-chart-group') || 'readiness';
        document.querySelectorAll('[data-chart-group]').forEach((b) => b.classList.toggle('active', b === btn));
        renderHistoryChart(getFilteredRows());
      });
    });

    document.querySelectorAll('[data-chart-style]').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeStyle = btn.getAttribute('data-chart-style') || 'line';
        document.querySelectorAll('[data-chart-style]').forEach((b) => b.classList.toggle('active', b === btn));
        renderHistoryChart(getFilteredRows());
      });
    });

    document.getElementById('exportCsvBtn')?.addEventListener('click', exportHistory);
    document.getElementById('resetSeedBtn')?.addEventListener('click', () => {
      global.BioShell?.resetHistoryToSeed();
      renderHistoryTable();
      global.BioShell?.showToast('Reset logs to NASA baseline seed', 'nominal');
    });

    renderTrainingAchievementChart();
  }

  let trainingChartInstance = null;

  function renderTrainingAchievementChart() {
    const canvas = document.getElementById('trainingProgressChart');
    if (!canvas || typeof global.Chart === 'undefined') return;

    // 8-Sol microgravity exercise mission data
    const labels = ['Sol 35', 'Sol 37', 'Sol 39', 'Sol 41', 'Sol 43', 'Sol 45', 'Sol 47', 'Sol 48'];
    const completionRate = [80, 85, 100, 75, 100, 90, 100, 75]; // %
    const durationMinutes = [75, 80, 110, 60, 105, 95, 115, 65]; // Active minutes

    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)';
    const textColor = isLight ? '#4B5563' : '#8A99AD';

    if (trainingChartInstance) trainingChartInstance.destroy();

    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 260);
    grad.addColorStop(0, isLight ? 'rgba(40, 176, 116, 0.35)' : 'rgba(0, 229, 255, 0.35)');
    grad.addColorStop(1, isLight ? 'rgba(40, 176, 116, 0.02)' : 'rgba(0, 229, 255, 0.02)');

    trainingChartInstance = new global.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Mission Completion Rate (%)',
            data: completionRate,
            borderColor: isLight ? '#1C7C54' : '#00E5FF',
            backgroundColor: grad,
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointBackgroundColor: isLight ? '#1C7C54' : '#00E5FF',
            pointRadius: 4.5,
            pointHoverRadius: 6,
            yAxisID: 'y'
          },
          {
            label: 'Active Exercise Duration (mins)',
            data: durationMinutes,
            type: 'bar',
            backgroundColor: isLight ? 'rgba(43, 108, 163, 0.45)' : 'rgba(56, 149, 223, 0.45)',
            borderColor: isLight ? '#2B6CA3' : '#3895DF',
            borderWidth: 1,
            borderRadius: 3,
            yAxisID: 'y1'
          },
          {
            label: 'NASA Baseline (85% Target)',
            data: [85, 85, 85, 85, 85, 85, 85, 85],
            borderColor: '#E29322',
            borderWidth: 1.8,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
            yAxisID: 'y'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              boxWidth: 12,
              font: { size: 11, family: 'Space Grotesk, sans-serif' },
              color: textColor
            }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.raw}${ctx.dataset.yAxisID === 'y' ? '%' : ' min'}`
            }
          }
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: textColor, font: { size: 10.5, family: 'Space Grotesk, monospace' } }
          },
          y: {
            min: 0,
            max: 110,
            grid: { color: gridColor },
            ticks: {
              stepSize: 25,
              color: textColor,
              font: { size: 10.5, family: 'Space Grotesk, monospace' },
              callback: (v) => `${v}%`
            },
            title: { display: true, text: 'Completion (%)', color: textColor, font: { size: 10.5 } }
          },
          y1: {
            position: 'right',
            min: 0,
            max: 140,
            grid: { drawOnChartArea: false },
            ticks: {
              stepSize: 30,
              color: textColor,
              font: { size: 10.5, family: 'Space Grotesk, monospace' },
              callback: (v) => `${v}m`
            },
            title: { display: true, text: 'Duration (mins)', color: textColor, font: { size: 10.5 } }
          }
        }
      }
    });
  }

  global.historyPage = {
    renderTable: renderHistoryTable,
    renderChart: () => renderHistoryChart(getFilteredRows())
  };

  global.app = Object.assign(global.app || {}, {
    renderHistoryTable,
    exportHistory
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapHistory);
  } else {
    bootstrapHistory();
  }
})(typeof window !== 'undefined' ? window : globalThis);
