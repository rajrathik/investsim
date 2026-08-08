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

// ---- Heatmap render --------------------------------------
// Value coloring uses shared .growth-pos/.growth-neg text classes (ChartMill-style:
// plain background, text-only red/green) instead of a computed gradient fill.

function renderHeatmap(annual) {
  const grid = $('heatmapGrid');
  if (!grid) return;

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
  html += '<div class="hm-decade-label" style="border-bottom:2px solid var(--border)">Decade</div>';
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
        html += '<div class="hm-cell hm-empty">—</div>';
      } else {
        const cls  = ret >= 0 ? 'growth-pos' : 'growth-neg';
        const sign = ret >= 0 ? '+' : '';
        html +=
          `<div class="hm-cell ${cls}"` +
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
