const API = "/api";
const $ = id => document.getElementById(id);

/* ========== NO-AUTH MODE ========== */

/* authFetch is just plain fetch on no-auth branch */
async function authFetch(url, options = {}) {
  return fetch(url, options);
}

/* ========== DATA ========== */
let sectorData = null;
let currentView = 'returns'; // 'returns' or 'dividends'
let yearStart = 2005, yearEnd = 9999; // yearEnd clamped to latest available year in populateYearSelectors()

// Preferred display order
const SECTOR_ORDER = [
  'XLK', 'XLV', 'XLF', 'XLE', 'XLY', 'XLP',
  'XLI', 'XLB', 'XLU', 'XLC', 'XLRE', 'VTI'
];

async function loadData() {
  try {
    const resp = await authFetch(API + '/sector-performance');
    sectorData = await resp.json();
    populateYearSelectors();
    render();
  } catch (e) {
    console.error('Failed to load sector data:', e);
    $('content').innerHTML = '<div style="text-align:center;padding:60px;color:var(--text3)">Failed to load data. Please try again.</div>';
  }
}

function populateYearSelectors() {
  // Find min/max years across all sectors
  let allYears = new Set();
  for (const sym of SECTOR_ORDER) {
    if (!sectorData[sym]) continue;
    for (const y of Object.keys(sectorData[sym].data)) allYears.add(+y);
  }
  const sorted = [...allYears].sort((a, b) => a - b);
  if (sorted.length === 0) return;

  const startSel = $('yearStart'), endSel = $('yearEnd');
  startSel.innerHTML = '';
  endSel.innerHTML = '';
  for (const y of sorted) {
    startSel.innerHTML += `<option value="${y}"${y === Math.max(sorted[0], yearStart) ? ' selected' : ''}>${y}</option>`;
    endSel.innerHTML += `<option value="${y}"${y === Math.min(sorted[sorted.length - 1], yearEnd) ? ' selected' : ''}>${y}</option>`;
  }
  yearStart = +startSel.value;
  yearEnd = +endSel.value;
}

/* ========== RENDERING ========== */

function getReturnClass(val) {
  return val >= 0 ? 'growth-pos' : 'growth-neg';
}

function getDividendClass(val) {
  return val > 0 ? 'growth-gold' : 'growth-na';
}

const MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// True if any sector has a partial (YTD) figure for this year
function yearIsPartial(y) {
  for (const sym of SECTOR_ORDER) {
    const d = sectorData[sym] && sectorData[sym].data[String(y)];
    if (d && d.partial) return true;
  }
  return false;
}

function render() {
  if (!sectorData) return;
  renderQuilt();
  renderStats();
}

function renderQuilt() {
  const years = [];
  for (let y = yearStart; y <= yearEnd; y++) years.push(y);

  let html = '<table class="quilt"><thead><tr><th>Sector</th>';
  for (const y of years) {
    const partialYr = yearIsPartial(y);
    html += `<th${partialYr ? ' class="partial-col"' : ''}>${y}${partialYr ? ' (YTD)' : ''}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const sym of SECTOR_ORDER) {
    if (!sectorData[sym]) continue;
    const info = sectorData[sym];
    html += `<tr><td><strong>${sym}</strong><span class="ticker-name">${info.name}</span></td>`;

    for (const y of years) {
      const d = info.data[String(y)];
      if (!d) {
        html += '<td></td>';
        continue;
      }

      const partialCls = d.partial ? ' partial' : '';
      if (currentView === 'returns') {
        const totalRet = d.prev_close > 0 ? ((d.close - d.prev_close + d.dividend) / d.prev_close) * 100 : d.return;
        const cls = getReturnClass(totalRet);
        const sign = totalRet >= 0 ? '+' : '';
        html += `<td class="${cls}${partialCls}" data-sym="${sym}" data-year="${y}">${sign}${totalRet.toFixed(1)}%${d.partial ? '*' : ''}</td>`;
      } else {
        const cls = getDividendClass(d.dividend);
        html += `<td class="${cls}${partialCls}" data-sym="${sym}" data-year="${y}">$${d.dividend.toFixed(2)}${d.partial ? '*' : ''}</td>`;
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  $('quiltContainer').innerHTML = html;

  // Attach hover listeners
  const cells = document.querySelectorAll('.quilt td[data-sym]');
  const tooltip = $('tooltip');
  cells.forEach(cell => {
    cell.addEventListener('mouseenter', e => showTooltip(e, cell));
    cell.addEventListener('mousemove', e => moveTooltip(e));
    cell.addEventListener('mouseleave', () => tooltip.classList.remove('show'));
  });
}

function showTooltip(e, cell) {
  const sym = cell.dataset.sym;
  const year = cell.dataset.year;
  const info = sectorData[sym];
  const d = info.data[year];
  if (!d) return;

  const tooltip = $('tooltip');
  const totalRet = d.prev_close > 0 ? ((d.close - d.prev_close + d.dividend) / d.prev_close) * 100 : d.return;
  const totalSign = totalRet >= 0 ? '+' : '';
  const totalColor = totalRet >= 0 ? 'var(--accent)' : 'var(--red)';
  const priceSign = d.return >= 0 ? '+' : '';
  const priceColor = d.return >= 0 ? 'var(--accent)' : 'var(--red)';
  const endLabel = d.partial ? `As of ${MONTH_NAMES[d.as_of_month]} ${year}` : 'Year End';
  tooltip.innerHTML = `
    <div><span class="tt-sym">${sym}</span><span class="tt-year">${info.name}</span></div>
    <div style="margin-top:6px">
      <div class="tt-row"><span class="tt-label">Year</span><span class="tt-val">${year}${d.partial ? ' (YTD)' : ''}</span></div>
      <div class="tt-row"><span class="tt-label">Total Return</span><span class="tt-val" style="color:${totalColor}">${totalSign}${totalRet.toFixed(2)}%</span></div>
      <div class="tt-row"><span class="tt-label">Price Return</span><span class="tt-val" style="color:${priceColor}">${priceSign}${d.return.toFixed(2)}%</span></div>
      <div class="tt-row"><span class="tt-label">Dividend (cash)</span><span class="tt-val" style="color:var(--gold)">$${d.dividend.toFixed(2)}</span></div>
      <div class="tt-row"><span class="tt-label">Year Begin</span><span class="tt-val">$${d.prev_close.toFixed(2)}</span></div>
      <div class="tt-row"><span class="tt-label">${endLabel}</span><span class="tt-val">$${d.close.toFixed(2)}</span></div>
    </div>
    ${d.partial ? '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:11px;color:var(--gold)">⚠ Partial year — will update as more months load</div>' : ''}
  `;
  tooltip.classList.add('show');
  moveTooltip(e);
}

function moveTooltip(e) {
  const tooltip = $('tooltip');
  const pad = 16;
  let x = e.clientX + pad, y = e.clientY + pad;
  const rect = tooltip.getBoundingClientRect();
  if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - pad;
  tooltip.style.left = x + 'px';
  tooltip.style.top = y + 'px';
}

function renderStats() {
  const years = [];
  for (let y = yearStart; y <= yearEnd; y++) years.push(y);

  let html = '';
  for (const sym of SECTOR_ORDER) {
    if (!sectorData[sym]) continue;
    const info = sectorData[sym];

    // Compute stats over selected year range
    const totalRets = [], divs = [], dataYears = [];
    for (const y of years) {
      const d = info.data[String(y)];
      if (d) {
        const tr = d.prev_close > 0 ? ((d.close - d.prev_close + d.dividend) / d.prev_close) * 100 : d.return;
        totalRets.push(tr);
        divs.push(d.dividend);
        dataYears.push(y);
      }
    }
    if (totalRets.length === 0) continue;

    const bestRet = Math.max(...totalRets);
    const worstRet = Math.min(...totalRets);
    const totalDiv = divs.reduce((a, b) => a + b, 0);
    const avgDiv = totalDiv / divs.length;
    const posYears = totalRets.filter(r => r > 0).length;

    // Compute price-only CAGR
    let cagr = null;
    const actualMinYr = dataYears[0];
    const actualMaxYr = dataYears[dataYears.length - 1];
    const firstYearData = info.data[String(actualMinYr)];
    const lastYearData = info.data[String(actualMaxYr)];
    if (firstYearData && lastYearData && actualMinYr !== actualMaxYr) {
      const startPrice = firstYearData.prev_close;
      const endPrice = lastYearData.close;
      const numYears = actualMaxYr - actualMinYr + 1;
      cagr = (Math.pow(endPrice / startPrice, 1 / numYears) - 1) * 100;
    }

    // Compute total return CAGR (price + dividends reinvested)
    let totalCagr = null;
    if (firstYearData && lastYearData && actualMinYr !== actualMaxYr) {
      // Simulate reinvesting dividends: compound through each year
      let cumValue = 1.0;
      for (const y of dataYears) {
        const d = info.data[String(y)];
        if (d && d.prev_close > 0) {
          const yearTotalReturn = (d.close - d.prev_close + d.dividend) / d.prev_close;
          cumValue *= (1 + yearTotalReturn);
        }
      }
      const numYears = dataYears.length;
      totalCagr = (Math.pow(cumValue, 1 / numYears) - 1) * 100;
    }

    const bestYear = dataYears[totalRets.indexOf(bestRet)];
    const worstYear = dataYears[totalRets.indexOf(worstRet)];

    // Show year range note if data doesn't cover full selected range
    const fullRange = (actualMinYr === yearStart && actualMaxYr === yearEnd);
    const rangeNote = fullRange ? '' :
      `<div class="s-range">(${actualMinYr}\u2013${actualMaxYr})</div>`;

    const delay = SECTOR_ORDER.indexOf(sym) * 0.05;
    html += `
      <div class="stat-card fade-up" style="animation-delay:${delay}s">
        <div class="s-sym">${sym}</div>
        <div class="s-name">${info.name}</div>
        ${rangeNote}
        ${cagr !== null ? `<div class="s-row"><span class="s-label">Price CAGR</span><span class="s-val ${cagr >= 0 ? 'pos' : 'neg'}">${cagr >= 0 ? '+' : ''}${cagr.toFixed(2)}%</span></div>` : ''}
        ${totalCagr !== null ? `<div class="s-row"><span class="s-label">Total CAGR</span><span class="s-val ${totalCagr >= 0 ? 'pos' : 'neg'}">${totalCagr >= 0 ? '+' : ''}${totalCagr.toFixed(2)}%</span></div>` : ''}
        <div class="s-row"><span class="s-label">Best Year</span><span class="s-val pos">+${bestRet.toFixed(1)}% (${bestYear})</span></div>
        <div class="s-row"><span class="s-label">Worst Year</span><span class="s-val neg">${worstRet.toFixed(1)}% (${worstYear})</span></div>
        <div class="s-row"><span class="s-label">Positive Years</span><span class="s-val">${posYears}/${totalRets.length}</span></div>
        <div class="s-row"><span class="s-label">Total Dividends</span><span class="s-val gold">$${totalDiv.toFixed(2)}</span></div>
        <div class="s-row"><span class="s-label">Avg Dividend/Yr</span><span class="s-val gold">$${avgDiv.toFixed(2)}</span></div>
      </div>
    `;
  }
  $('statsContainer').innerHTML = html;
}

/* ========== EVENT HANDLERS ========== */

function setView(view) {
  currentView = view;
  document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));
  document.querySelector(`.view-toggle button[data-view="${view}"]`).classList.add('active');
  render();
}

function onYearChange() {
  yearStart = +$('yearStart').value;
  yearEnd = +$('yearEnd').value;
  if (yearStart > yearEnd) {
    // Swap
    const tmp = yearStart;
    yearStart = yearEnd;
    yearEnd = tmp;
    $('yearStart').value = yearStart;
    $('yearEnd').value = yearEnd;
  }
  render();
}

/* ========== INIT ========== */
document.addEventListener('DOMContentLoaded', loadData);
