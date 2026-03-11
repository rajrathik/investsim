/* ==========================================================
   sp500-history.js
   Decade heatmap for Shiller S&P 500 annual returns
   ========================================================== */

let _data = null;

// ---- Boot ------------------------------------------------

async function init() {
  try {
    const resp = await fetch('/api/sp500-annual-returns');
    if (!resp.ok) throw new Error('API error ' + resp.status);
    _data = await resp.json();

    renderStats(_data.stats);
    $('statStrip').style.display = '';

    renderContent(_data.annual);

    window.addEventListener('themechange', () => {
      if (_data) renderHeatmap(_data.annual);
    });

  } catch (e) {
    $('content').innerHTML =
      `<div class="loading">Could not load data: ${e.message}</div>`;
  }
}

// ---- Stats strip -----------------------------------------

function renderStats(s) {
  if (!s || !s.total_years) return;

  $('statYears').textContent    = s.total_years;
  $('statPositive').textContent = s.pct_positive + '%';

  const med = $('statMedian');
  med.textContent = (s.median >= 0 ? '+' : '') + s.median + '%';
  med.style.color = s.median >= 0 ? 'var(--accent)' : 'var(--red)';
  $('statMeanSub').textContent = 'mean ' + (s.mean >= 0 ? '+' : '') + s.mean + '%';

  $('statBest').textContent    = '+' + s.best_return + '%';
  $('statBestSub').textContent = s.best_year;

  $('statWorst').textContent    = s.worst_return + '%';
  $('statWorstSub').textContent = s.worst_year;
}

// ---- Heatmap content wrapper -----------------------------

function renderContent(annual) {
  $('content').innerHTML =
    '<h2 class="section-title" style="margin-bottom:8px">Annual Returns by Decade</h2>' +
    '<p class="page-desc" style="margin-bottom:16px">' +
      'Rows are decades. Columns are the year within the decade (0–9). ' +
      'Hover any cell for exact return. Color fades from neutral toward dark green (gain) or dark red (loss).' +
    '</p>' +
    '<div class="hm-wrap"><div class="hm-grid" id="heatmapGrid"></div></div>';

  renderHeatmap(annual);
}

// ---- Heatmap coloring ------------------------------------

function heatBg(ret, isDark) {
  const neutral   = isDark ? [17, 24, 39]  : [241, 245, 249];
  const posTarget = [6, 78, 59];    // #064e3b — dark forest green
  const negTarget = [120, 28, 28];  // #781c1c — dark burgundy

  const target = ret >= 0 ? posTarget : negTarget;
  const t      = Math.min(1, Math.abs(ret) / (ret >= 0 ? 50 : 40));

  const r = Math.round(neutral[0] + (target[0] - neutral[0]) * t);
  const g = Math.round(neutral[1] + (target[1] - neutral[1]) * t);
  const b = Math.round(neutral[2] + (target[2] - neutral[2]) * t);
  return `rgb(${r},${g},${b})`;
}

function heatFg(ret, isDark) {
  const t = Math.min(1, Math.abs(ret) / 50);
  if (isDark) {
    if (t < 0.08) return '#64748b';
    if (ret >= 0) return t > 0.35 ? '#a7f3d0' : '#86efac';
    return t > 0.35 ? '#fca5a5' : '#fda4af';
  } else {
    if (t < 0.1)  return '#94a3b8';
    if (t > 0.45) return '#ffffff';
    return ret >= 0 ? '#065f46' : '#7f1d1d';
  }
}

// ---- Heatmap render --------------------------------------

function renderHeatmap(annual) {
  const grid = $('heatmapGrid');
  if (!grid) return;
  const isDark = document.documentElement.dataset.theme !== 'light';

  const decades = {};
  for (const [yr, ret] of Object.entries(annual)) {
    const year   = parseInt(yr);
    const decade = Math.floor(year / 10) * 10;
    if (!decades[decade]) decades[decade] = {};
    decades[decade][year % 10] = ret;
  }
  const sortedDecades = Object.keys(decades).map(Number).sort((a, b) => a - b);

  let html = '';

  // Column header row
  html += '<div class="hm-row">';
  html += '<div class="hm-decade-label" style="color:var(--text3)">Decade</div>';
  for (let i = 0; i <= 9; i++) {
    html += `<div class="hm-col-header">&thinsp;+${i}</div>`;
  }
  html += '</div>';

  for (const decade of sortedDecades) {
    html += '<div class="hm-row">';
    html += `<div class="hm-decade-label">${decade}s</div>`;
    for (let i = 0; i <= 9; i++) {
      const ret  = decades[decade][i];
      const year = decade + i;
      if (ret === undefined || ret === null) {
        html += '<div class="hm-cell hm-empty"></div>';
      } else {
        const bg   = heatBg(ret, isDark);
        const fg   = heatFg(ret, isDark);
        const sign = ret >= 0 ? '+' : '';
        html +=
          `<div class="hm-cell" style="background:${bg};color:${fg}"` +
          ` onmouseenter="hmTooltip(event,${year},${ret})"` +
          ` onmousemove="hmMoveTooltip(event)"` +
          ` onmouseleave="hmHide()">` +
          `${sign}${ret.toFixed(1)}</div>`;
      }
    }
    html += '</div>';
  }

  grid.innerHTML = html;
}

// ---- Heatmap tooltip -------------------------------------

function hmTooltip(e, year, ret) {
  const tt = $('tooltip');
  if (!tt) return;
  const sign  = ret >= 0 ? '+' : '';
  const color = ret >= 0 ? 'var(--accent)' : 'var(--red)';
  tt.innerHTML =
    `<div class="tt-sym" style="color:${color}">${year}</div>` +
    `<div class="tt-row" style="margin-top:6px">` +
      `<span class="tt-label">Annual Return</span>` +
      `<span class="tt-val" style="color:${color}">${sign}${ret.toFixed(2)}%</span>` +
    `</div>`;
  tt.style.left = (e.clientX + 16) + 'px';
  tt.style.top  = (e.clientY - 36) + 'px';
  tt.classList.add('show');
}

function hmMoveTooltip(e) {
  const tt = $('tooltip');
  if (!tt) return;
  tt.style.left = (e.clientX + 16) + 'px';
  tt.style.top  = (e.clientY - 36) + 'px';
}

function hmHide() {
  const tt = $('tooltip');
  if (tt) tt.classList.remove('show');
}

// ---- Start -----------------------------------------------
init();
