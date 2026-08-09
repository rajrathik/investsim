/* ==========================================================
   sp500-simulate.js  v2
   Historical DCA simulator using Shiller S&P 500 data
   ========================================================== */

// ---- Historical era presets -----------------------------------------

const PRESETS = [
  { id: 'gilded',      label: 'Gilded Age',            start: 1872, end: 1899 },
  { id: 'progressive', label: 'Progressive Era & WWI', start: 1900, end: 1919 },
  { id: 'roaring',     label: 'Roaring Twenties',      start: 1920, end: 1929 },
  { id: 'depression',  label: 'Great Depression',      start: 1929, end: 1939 },
  { id: 'wwii',        label: 'WWII Recovery',         start: 1939, end: 1945 },
  { id: 'postwar',     label: 'Post-War Boom',         start: 1945, end: 1965 },
  { id: 'stagflation', label: 'Stagflation Era',       start: 1968, end: 1982 },
  { id: 'reagan',      label: 'Reagan Bull Market',    start: 1982, end: 1999 },
  { id: 'dotcom',      label: 'Dot-Com Boom & Bust',   start: 1995, end: 2002 },
  { id: 'lost',        label: 'Lost Decade',           start: 2000, end: 2009 },
  { id: 'gfc',         label: 'Financial Crisis',      start: 2007, end: 2013 },
  { id: 'bull',        label: 'Post-Crisis Bull Run',  start: 2009, end: 2019 },
  { id: 'covid',       label: 'COVID Era',             start: 2020, end: 2024 },
];

let _activePreset = null;
let _currentMode  = 'era'; // 'era' | 'custom'

function setMode(mode) {
  _currentMode = mode;
  document.getElementById('panelEra').style.display    = mode === 'era'    ? '' : 'none';
  document.getElementById('panelCustom').style.display = mode === 'custom' ? '' : 'none';
  document.getElementById('modeEraBtn').classList.toggle('active',    mode === 'era');
  document.getElementById('modeCustomBtn').classList.toggle('active', mode === 'custom');
  if (mode === 'custom') {
    // Deselect any active chip
    _activePreset = null;
    document.querySelectorAll('.preset-chip').forEach(el => el.classList.remove('active'));
    updateSimDuration();
  }
}

function updateSimDuration() {
  const s   = parseInt(document.getElementById('ctrlStart').value);
  const e   = parseInt(document.getElementById('ctrlEnd').value);
  const yrs = e > s ? e - s + 1 : '—';
  const el  = document.getElementById('simDurationDisplay');
  if (el) el.innerHTML = `Simulating <strong>${yrs} year${yrs !== 1 ? 's' : ''}</strong> &nbsp;(${s} – ${e})`;
}

function renderPresetChips() {
  const container = document.getElementById('presetChips');
  container.innerHTML = PRESETS.map(p =>
    `<button class="preset-chip" data-id="${p.id}" onclick="selectPreset('${p.id}')">
       <span class="chip-name">${p.label}</span>
       <span class="chip-years">${p.start}–${p.end}</span>
     </button>`
  ).join('');
}

function selectPreset(id) {
  const p = PRESETS.find(x => x.id === id);
  if (!p) return;
  _activePreset = p;

  // Highlight selected chip
  document.querySelectorAll('.preset-chip').forEach(el =>
    el.classList.toggle('active', el.dataset.id === id)
  );

  // Keep dropdowns in sync (used by runSim even when hidden)
  document.getElementById('ctrlStart').value = p.start;
  document.getElementById('ctrlEnd').value   = p.end;
}

// ---- Populate year selectors ----------------------------------------

(function initSelectors() {
  const startEl = document.getElementById('ctrlStart');
  const endEl   = document.getElementById('ctrlEnd');
  for (let y = 1872; y <= 2023; y++) {
    const o = document.createElement('option');
    o.value = y; o.textContent = y;
    startEl.appendChild(o);
  }
  for (let y = 1873; y <= 2024; y++) {
    const o = document.createElement('option');
    o.value = y; o.textContent = y;
    endEl.appendChild(o);
  }
  startEl.value = 1990;
  endEl.value   = 2024;

  // Update computed duration display when years change (custom mode)
  startEl.addEventListener('change', updateSimDuration);
  endEl.addEventListener('change', updateSimDuration);
})();

// ---- Run simulation -------------------------------------------------

let _simData   = null;
let _usedStart = null;
let _usedEnd   = null;

async function runSim() {
  const poolStart = parseInt(document.getElementById('ctrlStart').value);
  const poolEnd   = parseInt(document.getElementById('ctrlEnd').value);
  const initial   = parseFloat(document.getElementById('ctrlInitial').value) || 0;
  const monthly   = parseFloat(document.getElementById('ctrlMonthly').value) || 0;

  if (poolEnd <= poolStart) {
    showStatus('End year must be after start year.');
    return;
  }

  // Always simulate the full selected range (start→end)
  _usedStart = poolStart;
  _usedEnd   = poolEnd;

  const btn = $('btnRun');
  btn.disabled = true;
  btn.textContent = 'Running…';
  hideResults();
  showStatus('Simulating…');

  try {
    const url = `/api/sp500-simulate?start=${poolStart}&end=${poolEnd}&initial=${initial}&monthly=${monthly}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'API error ' + resp.status);
    }
    _simData = await resp.json();
    hideStatus();

    // Show results div BEFORE drawing chart so canvas has layout dimensions
    $('results').style.display = '';
    renderPeriodBanner(_simData.stats);
    renderSummary(_simData.stats);
    renderTable(_simData.years);
    // Defer chart until browser has laid out the newly visible canvas
    requestAnimationFrame(() => renderChart(_simData.years));

  } catch (e) {
    showStatus('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Simulation';
  }
}

// ---- Status helpers -------------------------------------------------

function showStatus(msg) {
  const el = $('simStatus');
  el.textContent = msg;
  el.style.display = '';
}
function hideStatus() { $('simStatus').style.display = 'none'; }
function hideResults() { $('results').style.display = 'none'; }

// ---- Period used banner ---------------------------------------------

function renderPeriodBanner(s) {
  const usedYears = s.num_years;
  $('periodBanner').innerHTML =
    `Using S&P 500 returns from <strong>${s.start_year}–${s.end_year}</strong> ` +
    `(${usedYears} year${usedYears !== 1 ? 's' : ''} of data) — forecasting future portfolio balances`;
}

// ---- Summary strip --------------------------------------------------

function renderSummary(s) {
  const fmt = n => '$' + Math.round(n).toLocaleString();

  $('sFinal').textContent    = fmt(s.final_balance);
  $('sFinalSub').textContent = `after ${s.num_years} years`;

  $('sContrib').textContent    = fmt(s.total_contributed);
  $('sContribSub').textContent =
    `$${Math.round(s.initial).toLocaleString()} + ${s.num_years * 12} mo × $${Math.round(s.monthly_contribution).toLocaleString()}`;

  const gainEl = $('sGain');
  gainEl.textContent = fmt(s.total_gain);
  gainEl.style.color = s.total_gain >= 0 ? 'var(--accent)' : 'var(--red)';
  $('sGainSub').textContent = (s.total_gain_pct >= 0 ? '+' : '') + s.total_gain_pct + '% on invested capital';

  $('sYears').textContent    = s.num_years;
  $('sYearsSub').textContent = `${s.start_year}–${s.end_year}`;
}

// ---- Chart ----------------------------------------------------------

let _chartYears = null;

function renderChart(years) {
  _chartYears = years;
  drawChart();
  window.addEventListener('themechange', drawChart);
  window.addEventListener('resize', drawChart);
}

function drawChart() {
  const canvas = document.getElementById('simCanvas');
  if (!canvas || !_chartYears || _chartYears.length === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const W   = canvas.offsetWidth || canvas.parentElement.clientWidth || 600;
  const H   = 260;
  canvas.width        = W * dpr;
  canvas.height       = H * dpr;
  canvas.style.height = H + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const isDark  = document.documentElement.dataset.theme !== 'light';
  const accent  = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()  || '#10b981';
  const text3   = getComputedStyle(document.documentElement).getPropertyValue('--text3').trim()   || '#64748b';
  const gridCol = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.07)';

  const pad = { top: 12, right: 20, bottom: 36, left: 72 };
  const cW  = W - pad.left - pad.right;
  const cH  = H - pad.top  - pad.bottom;

  const maxVal = Math.max(..._chartYears.map(y => y.end_balance), ..._chartYears.map(y => y.total_contributed));
  const range  = maxVal || 1;

  const xOf = i  => pad.left + (i / (_chartYears.length - 1 || 1)) * cW;
  const yOf = v  => pad.top  + cH - (v / range) * cH;

  // Grid lines + Y labels
  ctx.strokeStyle = gridCol;
  ctx.lineWidth   = 1;
  for (let t = 0; t <= 4; t++) {
    const yg  = pad.top + (t / 4) * cH;
    const val = maxVal * (1 - t / 4);
    ctx.beginPath(); ctx.moveTo(pad.left, yg); ctx.lineTo(pad.left + cW, yg); ctx.stroke();
    ctx.fillStyle  = text3;
    ctx.font       = `10px 'JetBrains Mono', monospace`;
    ctx.textAlign  = 'right';
    ctx.fillText('$' + fmtK(val), pad.left - 6, yg + 3.5);
  }

  // Total invested — dashed line
  ctx.save();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = text3;
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  _chartYears.forEach((y, i) => {
    const x = xOf(i), yy = yOf(y.total_contributed);
    i === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
  });
  ctx.stroke();
  ctx.restore();

  // Balance — area fill
  const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + cH);
  grad.addColorStop(0, isDark ? 'rgba(16,185,129,0.30)' : 'rgba(16,185,129,0.18)');
  grad.addColorStop(1, 'rgba(16,185,129,0.00)');
  ctx.beginPath();
  _chartYears.forEach((y, i) => {
    const x = xOf(i), yy = yOf(y.end_balance);
    i === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
  });
  ctx.lineTo(xOf(_chartYears.length - 1), pad.top + cH);
  ctx.lineTo(xOf(0), pad.top + cH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Balance — solid line
  ctx.strokeStyle = accent;
  ctx.lineWidth   = 2.5;
  ctx.lineJoin    = 'round';
  ctx.beginPath();
  _chartYears.forEach((y, i) => {
    const x = xOf(i), yy = yOf(y.end_balance);
    i === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
  });
  ctx.stroke();

  // X-axis labels — "Year 1", "Year 2", …
  ctx.fillStyle  = text3;
  ctx.font       = `10px 'JetBrains Mono', monospace`;
  ctx.textAlign  = 'center';
  const step = Math.max(1, Math.round(_chartYears.length / 8));
  _chartYears.forEach((_y, i) => {
    if (i % step === 0 || i === _chartYears.length - 1) {
      ctx.fillText('Yr ' + (i + 1), xOf(i), H - pad.bottom + 16);
    }
  });

  canvas._layout = { pad, cW, cH, xOf, yOf };
}

function fmtK(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
  if (v >= 1_000)     return Math.round(v / 1_000) + 'K';
  return Math.round(v).toString();
}

// Chart hover
document.getElementById('simCanvas').addEventListener('mousemove', function(e) {
  if (!_chartYears || !this._layout) return;
  const rect = this.getBoundingClientRect();
  const mx   = e.clientX - rect.left;
  const { pad, cW } = this._layout;
  const idx  = Math.round(((mx - pad.left) / cW) * (_chartYears.length - 1));
  if (idx < 0 || idx >= _chartYears.length) { hideTip(); return; }
  const y     = _chartYears[idx];
  const sign  = y.annual_return_pct >= 0 ? '+' : '';
  const color = y.annual_return_pct >= 0 ? 'var(--accent)' : 'var(--red)';
  const tip   = $('chartTip');
  tip.innerHTML =
    `<div class="ct-year">Year ${idx + 1}</div>` +
    `<div class="ct-row"><span class="ct-lbl">Balance</span><span class="ct-val">$${Math.round(y.end_balance).toLocaleString()}</span></div>` +
    `<div class="ct-row"><span class="ct-lbl">Invested</span><span class="ct-val">$${Math.round(y.total_contributed).toLocaleString()}</span></div>` +
    `<div class="ct-row"><span class="ct-lbl">Return</span><span class="ct-val" style="color:${color}">${sign}${y.annual_return_pct.toFixed(1)}%</span></div>`;
  tip.style.left = (e.clientX + 16) + 'px';
  tip.style.top  = (e.clientY - 36) + 'px';
  tip.classList.add('show');
});
document.getElementById('simCanvas').addEventListener('mouseleave', hideTip);

function hideTip() {
  const t = $('chartTip');
  if (t) t.classList.remove('show');
}

// ---- Year table -----------------------------------------------------

// Catchy comment + dollar market impact for the year
function yearComment(ret, dollarGain) {
  const sign = dollarGain >= 0 ? '+' : '-';
  const amt  = sign + '$' + Math.abs(Math.round(dollarGain)).toLocaleString();
  let label;
  if      (ret <= -30) label = 'Market crashed — stay invested';
  else if (ret <= -15) label = 'Painful drop — keep contributing';
  else if (ret <= -5)  label = 'Down year — DCA working for you';
  else if (ret <   0)  label = 'Tiny dip — barely a blip';
  else if (ret <   3)  label = 'Flat — contributions quietly building';
  else if (ret <   8)  label = 'Steady — compounding at work';
  else if (ret <  15)  label = 'Solid year — market on your side';
  else if (ret <  25)  label = 'Strong — wealth accelerating fast';
  else if (ret <  35)  label = 'Exceptional — big jump this year!';
  else                 label = 'Historic run — incredible gains!';
  return `${amt} &nbsp;·&nbsp; ${label}`;
}

let _tableYears   = null;
let _tableMonthly = 0;

function renderTable(years) {
  _tableYears   = years;
  _tableMonthly = _simData ? _simData.stats.monthly_contribution : 0;
  drawTable();
}

function drawTable() {
  if (!_tableYears) return;
  const years      = _tableYears;
  const monthly    = _tableMonthly;
  const maxAbsRet  = Math.max(...years.map(y => Math.abs(y.annual_return_pct)));

  $('yearTableBody').innerHTML = years.map((y, i) => {
    const ret        = y.annual_return_pct;
    const sign       = ret >= 0 ? '+' : '';
    const retCls     = ret >= 0 ? 'ret-pos' : 'ret-neg';
    const barW       = Math.round(Math.abs(ret) / (maxAbsRet || 1) * 48);
    // No red/green -- bar length shows magnitude, sign in the number shows direction.
    const bar        = `<span class="ret-bar-wrap"><span class="ret-bar" style="width:${barW}px;background:var(--text3)"></span></span>`;
    const dollarGain = y.end_balance - y.start_balance - monthly * 12;
    const comment    = yearComment(ret, dollarGain);

    return `<tr>
      <td>Year ${i + 1}</td>
      <td class="${retCls}">${sign}${ret.toFixed(1)}%${bar}</td>
      <td>$${Math.round(y.total_contributed).toLocaleString()}</td>
      <td style="font-weight:600">$${Math.round(y.end_balance).toLocaleString()}</td>
      <td style="text-align:left;font-size:11px">${comment}</td>
    </tr>`;
  }).join('');
}

// ---- Init -----------------------------------------------------------
window.addEventListener('DOMContentLoaded', () => {
  renderPresetChips();
  updateSimDuration();
  runSim();
});
