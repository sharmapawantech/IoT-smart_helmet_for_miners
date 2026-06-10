/* MineGuard — History Page JS  v3
   Timestamps: DB stores UTC naive → append 'Z' → JS converts to local time
*/

let histTempHum, histGas;

// ── Date helpers (same logic as dashboard.js) ────────────
function toLocalDate(isoStr) {
  if (!isoStr) return new Date();
  const s = /[Z+]/.test(isoStr.slice(-6)) ? isoStr : isoStr + 'Z';
  return new Date(s);
}

function fmtFull(isoStr) {
  return toLocalDate(isoStr).toLocaleString([], {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
  });
}

function fmtShort(isoStr) {
  return toLocalDate(isoStr).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

// ── Chart init ───────────────────────────────────────────
function initCharts() {
  const grid = 'rgba(0,0,0,0.05)';

  histTempHum = new Chart(document.getElementById('histTempHum').getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Temperature (°C)',
          data: [], yAxisID: 'y',
          borderColor: '#dc2626', backgroundColor: 'rgba(220,38,38,0.07)',
          tension: 0.4, fill: true, pointRadius: 1.5,
        },
        {
          label: 'Humidity (%)',
          data: [], yAxisID: 'y1',
          borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.07)',
          tension: 0.4, fill: true, pointRadius: 1.5,
        }
      ]
    },
    options: {
      responsive: true, animation: { duration: 300 },
      plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x:  { grid: { color: grid }, ticks: { maxTicksLimit: 10, maxRotation: 30, font: { size: 9 } } },
        y:  { grid: { color: grid }, position: 'left',  title: { display: true, text: '°C', font: { size: 10 } } },
        y1: { grid: { display: false }, position: 'right', title: { display: true, text: '%', font: { size: 10 } } },
      }
    }
  });

  histGas = new Chart(document.getElementById('histGas').getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Methane (ppm)',
        data: [],
        borderColor: '#7c3aed', backgroundColor: 'rgba(124,58,237,0.07)',
        tension: 0.4, fill: true, pointRadius: 1.5,
      }]
    },
    options: {
      responsive: true, animation: { duration: 300 },
      plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { grid: { color: grid }, ticks: { maxTicksLimit: 10, maxRotation: 30, font: { size: 9 } } },
        y: { grid: { color: grid }, beginAtZero: true }
      }
    }
  });
}

// ── Status cell HTML ─────────────────────────────────────
function statusCell(level) {
  return `<span class="td-${level}">${level.toUpperCase()}</span>`;
}

// ── Load and render history ──────────────────────────────
async function loadHistory() {
  const limit = document.getElementById('limitSelect').value;
  const res   = await fetch(`/api/history?limit=${limit}`);
  if (!res.ok) return;
  const data = await res.json();

  if (!data.length) {
    document.getElementById('histBody').innerHTML =
      '<tr><td colspan="6" style="text-align:center;padding:1rem;color:#6b7280">No data recorded yet.</td></tr>';
    return;
  }

  // Chart labels — short local time
  const labels = data.map(r => fmtShort(r.timestamp));

  histTempHum.data.labels            = labels;
  histTempHum.data.datasets[0].data  = data.map(r => r.temperature);
  histTempHum.data.datasets[1].data  = data.map(r => r.humidity);
  histTempHum.update('none');

  histGas.data.labels               = labels;
  histGas.data.datasets[0].data     = data.map(r => r.methane);
  histGas.update('none');

  // Table — full local date + time, newest first
  document.getElementById('histBody').innerHTML = data.slice().reverse().map(r => `
    <tr>
      <td>${fmtFull(r.timestamp)}</td>
      <td>${r.temperature !== null ? r.temperature.toFixed(1) : '—'}</td>
      <td>${r.humidity    !== null ? r.humidity.toFixed(1)    : '—'}</td>
      <td>${r.methane     !== null ? r.methane.toFixed(0)     : '—'}</td>
      <td>${r.fall_detected
           ? '<span class="td-danger">⚠️ YES</span>'
           : '<span class="td-safe">✓ NO</span>'}</td>
      <td>${statusCell(r.danger_level)}</td>
    </tr>
  `).join('');
}

initCharts();
loadHistory();
