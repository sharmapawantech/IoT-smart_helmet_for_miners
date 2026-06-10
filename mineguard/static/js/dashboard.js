/* ═══════════════════════════════════════════════════════════
   MineGuard — Dashboard JS  v3
   Field mapping (your ThingSpeak channel):
     field1 = methane   (MQ4,     ppm)
     field2 = temp      (DHT22,   °C)
     field3 = humidity  (DHT22,   %)
     field4 = fall flag (MPU6050, 1=fall / 0=ok)
   Refresh: every 10 seconds
═══════════════════════════════════════════════════════════ */

const REFRESH_MS = 10000;

// ── Thresholds — UPDATE THESE WHEN YOU CHANGE config.py ──
const THR = {
  temp:    { warn: 42,  danger: 50  },
  hum:     { warn: 80,  danger: 95  },
  methane: { warn: 650, danger: 800 },
};

// ════════════════════════════════════════════════════════
//  DATE / TIME HELPERS
//  DB stores timestamps as UTC (no timezone info).
//  Appending 'Z' tells JavaScript it is UTC so it
//  automatically converts to the browser's local time.
// ════════════════════════════════════════════════════════

function toLocalDate(isoStr) {
  if (!isoStr) return new Date();
  // If string already has Z or +offset, leave as-is; otherwise add Z
  const s = /[Z+]/.test(isoStr.slice(-6)) ? isoStr : isoStr + 'Z';
  return new Date(s);
}

/** Full date + time: "29 Mar 2026, 04:35:12 PM" */
function fmtFull(isoStr) {
  return toLocalDate(isoStr).toLocaleString([], {
    day:    '2-digit',
    month:  'short',
    year:   'numeric',
    hour:   '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

/** Short time only: "04:35 PM" */
function fmtShort(isoStr) {
  return toLocalDate(isoStr).toLocaleTimeString([], {
    hour:   '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

// ════════════════════════════════════════════════════════
//  LEVEL HELPERS
// ════════════════════════════════════════════════════════

function levelOf(v, warn, danger) {
  if (v === null || v === undefined) return 'safe';
  if (v >= danger) return 'danger';
  if (v >= warn)   return 'warning';
  return 'safe';
}

const levelTemp    = v => levelOf(v, THR.temp.warn,    THR.temp.danger);
const levelHum     = v => levelOf(v, THR.hum.warn,     THR.hum.danger);
const levelMethane = v => levelOf(v, THR.methane.warn, THR.methane.danger);

// ════════════════════════════════════════════════════════
//  GAUGE FACTORY
// ════════════════════════════════════════════════════════

function makeGauge(canvasId, unit, min, max, warn, danger) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return null;

  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [0, max],
        backgroundColor: ['#16a34a', '#e5e0d8'],
        borderWidth: 0,
        circumference: 200,
        rotation: 260,
      }]
    },
    options: {
      cutout: '72%',
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 500 },
    },
    plugins: [{
      id: 'gaugeText',
      afterDraw(c) {
        const { ctx: cx, chartArea: { top, width, height } } = c;
        const x = width / 2;
        const y = top + height * 0.70;
        const v = c._val;
        cx.save();
        cx.textAlign = 'center';
        cx.fillStyle = '#111827';
        cx.font = `700 1.35rem 'IBM Plex Mono', monospace`;
        cx.fillText((v !== null && v !== undefined && !isNaN(v)) ? v.toFixed(1) : '--', x, y);
        cx.fillStyle = '#6b7280';
        cx.font = `500 0.68rem 'Inter', sans-serif`;
        cx.fillText(unit, x, y + 18);
        cx.restore();
      }
    }]
  });

  chart._warn = warn; chart._danger = danger;
  chart._min = min;   chart._max = max;
  return chart;
}

function updateGauge(chart, value) {
  if (!chart) return;
  const v         = value ?? 0;
  const clamped   = Math.max(chart._min, Math.min(chart._max, v));
  const remaining = chart._max - clamped;
  const color = (v >= chart._danger) ? '#dc2626'
              : (v >= chart._warn)   ? '#d97706'
              : '#16a34a';
  chart._val = value;
  chart.data.datasets[0].data            = [clamped, remaining];
  chart.data.datasets[0].backgroundColor = [color, '#e5e0d8'];
  chart.update('none');
}

const gaugeTemp = makeGauge('gaugeTemp', '°C',  0, 80,   THR.temp.warn,    THR.temp.danger);
const gaugeHum  = makeGauge('gaugeHum',  '%',   0, 100,  THR.hum.warn,     THR.hum.danger);
const gaugeGas  = makeGauge('gaugeGas',  'ppm', 0, 1000, THR.methane.warn, THR.methane.danger);

// ════════════════════════════════════════════════════════
//  LINE + BAR CHARTS
// ════════════════════════════════════════════════════════

let lineChart, gasLine, summaryBar;

function initCharts() {
  const grid = 'rgba(0,0,0,0.05)';

  // Temperature + Humidity — dual Y axis
  lineChart = new Chart(document.getElementById('lineChart').getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Temperature (°C)',
          data: [], yAxisID: 'y',
          borderColor: '#dc2626', backgroundColor: 'rgba(220,38,38,0.07)',
          tension: 0.4, fill: true, pointRadius: 2,
        },
        {
          label: 'Humidity (%)',
          data: [], yAxisID: 'y1',
          borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.07)',
          tension: 0.4, fill: true, pointRadius: 2,
        }
      ]
    },
    options: {
      responsive: true, animation: { duration: 400 },
      plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x:  { grid: { color: grid }, ticks: { maxTicksLimit: 8, maxRotation: 0, font: { size: 10 } } },
        y:  { grid: { color: grid }, position: 'left',  title: { display: true, text: '°C', font: { size: 10 } } },
        y1: { grid: { display: false }, position: 'right', title: { display: true, text: '%', font: { size: 10 } } },
      }
    }
  });

  // Methane over time with threshold lines drawn via plugin
  gasLine = new Chart(document.getElementById('gasLine').getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Methane (ppm)',
        data: [],
        borderColor: '#7c3aed', backgroundColor: 'rgba(124,58,237,0.07)',
        tension: 0.4, fill: true, pointRadius: 2,
      }]
    },
    options: {
      responsive: true, animation: { duration: 400 },
      plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { grid: { color: grid }, ticks: { maxTicksLimit: 6, maxRotation: 0, font: { size: 10 } } },
        y: { grid: { color: grid }, beginAtZero: true,
             suggestedMax: THR.methane.danger + 100 }
      }
    },
    // Draw horizontal threshold lines
    plugins: [{
      id: 'thresholdLines',
      afterDraw(chart) {
        const { ctx, chartArea: { left, right }, scales: { y } } = chart;
        const lines = [
          { value: THR.methane.warn,   color: '#d97706', label: `Warning ${THR.methane.warn}` },
          { value: THR.methane.danger, color: '#dc2626', label: `Danger ${THR.methane.danger}` },
        ];
        lines.forEach(({ value, color, label }) => {
          const yPos = y.getPixelForValue(value);
          ctx.save();
          ctx.setLineDash([6, 3]);
          ctx.strokeStyle = color;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(left, yPos);
          ctx.lineTo(right, yPos);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = color;
          ctx.font = '500 10px Inter, sans-serif';
          ctx.fillText(label, right - 70, yPos - 4);
          ctx.restore();
        });
      }
    }]
  });

  // ── Sensor Summary Bar — REPLACES useless pie chart ──
  // Shows current value of each sensor vs its warning and danger limits.
  // Immediately tells you how far each reading is from the threshold.
  summaryBar = new Chart(document.getElementById('pieChart').getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['Temp (°C)', 'Humidity (%)', 'Methane (ppm÷10)'],
      datasets: [
        {
          label: 'Current Value',
          data: [0, 0, 0],
          backgroundColor: ['#16a34a', '#16a34a', '#16a34a'],
          borderRadius: 6,
          borderSkipped: false,
        },
        {
          label: 'Warning Limit',
          data: [THR.temp.warn, THR.hum.warn, THR.methane.warn / 10],
          backgroundColor: 'rgba(217,119,6,0.15)',
          borderColor: '#d97706',
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false,
          type: 'bar',
        },
        {
          label: 'Danger Limit',
          data: [THR.temp.danger, THR.hum.danger, THR.methane.danger / 10],
          backgroundColor: 'rgba(220,38,38,0.10)',
          borderColor: '#dc2626',
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false,
          type: 'bar',
        }
      ]
    },
    options: {
      responsive: true, animation: { duration: 400 },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } },
        tooltip: {
          callbacks: {
            label(ctx) {
              const raw = ctx.raw;
              // Methane is divided by 10 for display scale — show real value
              if (ctx.dataIndex === 2 && ctx.datasetIndex === 0)
                return `Methane: ${(raw * 10).toFixed(0)} ppm`;
              return `${ctx.dataset.label}: ${raw}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: grid }, beginAtZero: true }
      }
    }
  });
}

// ════════════════════════════════════════════════════════
//  UI UPDATERS
// ════════════════════════════════════════════════════════

function updateCard(cardId, badgeId, level) {
  const card  = document.getElementById(cardId);
  const badge = document.getElementById(badgeId);
  if (!card || !badge) return;
  card.className    = `stat-card ${level}`;
  badge.className   = `stat-badge ${level}`;
  badge.textContent = level.toUpperCase();
}

function updateBanner(dangerLevel, fall) {
  const banner = document.getElementById('alertBanner');
  const text   = document.getElementById('bannerText');
  const icon   = document.getElementById('bannerIcon');
  if (!banner) return;
  if (dangerLevel === 'danger') {
    banner.className = 'alert-banner danger';
    icon.textContent = fall ? '🤸' : '🔴';
    text.textContent = fall
      ? 'FALL DETECTED on mining helmet — check miner immediately!'
      : 'DANGER: Critical sensor values — immediate action required!';
  } else if (dangerLevel === 'warning') {
    banner.className = 'alert-banner warning';
    icon.textContent = '⚡';
    text.textContent = 'WARNING: Elevated sensor readings — monitor closely.';
  } else {
    banner.classList.add('hidden');
  }
}

function renderInlineAlerts(alerts) {
  const el = document.getElementById('alertsList');
  if (!el) return;
  if (!alerts.length) {
    el.innerHTML = '<p class="muted-msg">No alerts yet.</p>';
    return;
  }
  el.innerHTML = alerts.slice(0, 6).map(a => {
    const icon = a.alert_type === 'fall'          ? '🤸'
               : a.alert_type === 'methane'       ? '💨'
               : a.alert_type === 'temperature'   ? '🌡️'
               : a.alert_type === 'humidity'      ? '💧'
               : a.alert_type === 'safe_recovery' ? '✅' : '⚠️';
    return `
      <div class="alert-inline ${a.level}">
        <span class="ai-icon">${icon}</span>
        <div>
          <span class="ai-msg">${a.message}</span>
          <span class="ai-time">${fmtFull(a.timestamp)}</span>
        </div>
      </div>`;
  }).join('');
}

function updateSummaryBar(temp, hum, methane) {
  if (!summaryBar) return;
  const colors = [
    levelTemp(temp)    === 'danger' ? '#dc2626' : levelTemp(temp)    === 'warning' ? '#d97706' : '#16a34a',
    levelHum(hum)      === 'danger' ? '#dc2626' : levelHum(hum)      === 'warning' ? '#d97706' : '#16a34a',
    levelMethane(methane) === 'danger' ? '#dc2626' : levelMethane(methane) === 'warning' ? '#d97706' : '#16a34a',
  ];
  summaryBar.data.datasets[0].data             = [temp ?? 0, hum ?? 0, (methane ?? 0) / 10];
  summaryBar.data.datasets[0].backgroundColor  = colors;
  summaryBar.update('none');
}

function updateHistoryCharts(history) {
  // fmtShort converts UTC timestamps to local time correctly
  const labels = history.map(r => fmtShort(r.timestamp));

  lineChart.data.labels            = labels;
  lineChart.data.datasets[0].data  = history.map(r => r.temperature);
  lineChart.data.datasets[1].data  = history.map(r => r.humidity);
  lineChart.update('none');

  gasLine.data.labels              = labels;
  gasLine.data.datasets[0].data    = history.map(r => r.methane);
  gasLine.update('none');
}

function setOnline(ok) {
  const pill = document.getElementById('livePill');
  if (!pill) return;
  pill.className = ok ? 'live-pill' : 'live-pill offline';
  pill.innerHTML = ok ? '<span class="pulse-dot"></span> Live' : '● Offline';
}

// ════════════════════════════════════════════════════════
//  MAIN POLL — runs every 10 seconds
// ════════════════════════════════════════════════════════

async function poll() {
  try {
    const pollRes = await fetch('/api/poll', { method: 'POST' });
    if (!pollRes.ok) throw new Error(`HTTP ${pollRes.status}`);
    const data = await pollRes.json();
    setOnline(true);

    const temp    = data.temperature  ?? null;
    const hum     = data.humidity     ?? null;
    const methane = data.methane      ?? null;
    const fall    = data.fall_detected ?? false;

    // Stat card values
    document.getElementById('val-temp').textContent = temp    !== null ? temp.toFixed(1)    : '--';
    document.getElementById('val-hum').textContent  = hum     !== null ? hum.toFixed(1)     : '--';
    document.getElementById('val-gas').textContent  = methane !== null ? methane.toFixed(0) : '--';
    document.getElementById('val-fall').textContent = fall ? '⚠️ FALL' : '✓ OK';

    // Stat card colours
    updateCard('card-temp', 'badge-temp', levelTemp(temp));
    updateCard('card-hum',  'badge-hum',  levelHum(hum));
    updateCard('card-gas',  'badge-gas',  levelMethane(methane));
    updateCard('card-fall', 'badge-fall', fall ? 'danger' : 'safe');

    // Gauges
    updateGauge(gaugeTemp, temp);
    updateGauge(gaugeHum,  hum);
    updateGauge(gaugeGas,  methane);

    // Alert banner
    updateBanner(data.danger_level, fall);

    // History charts (correct local time labels)
    const histRes = await fetch('/api/history?limit=50');
    if (histRes.ok) updateHistoryCharts(await histRes.json());

    // Sensor summary bar (replaces pie)
    updateSummaryBar(temp, hum, methane);

    // Inline alerts with correct local timestamps
    const alertRes = await fetch('/api/alerts?limit=6');
    if (alertRes.ok) renderInlineAlerts(await alertRes.json());

  } catch (err) {
    console.error('[MineGuard] Poll error:', err);
    setOnline(false);
  }
}

// Boot
initCharts();
poll();
setInterval(poll, REFRESH_MS);
