/* ==========================================
   ETF HOME — default landing layout (/)

   Builds the ETF directory shown on the landing page:
     - Range period chips (1y/5y/10y/max) re-render every row at once, so
       there is no per-ticker click and no hover dependency.
     - Always-on sparkline per row.
     - Filled position-in-range bar instead of a dot marker.
     - Skeleton placeholders while fetches are in flight.
     - History is fetched once and cached in sessionStorage -- it only
       changes when the monthly load runs, so back/forward navigation
       re-paints instantly with no network call. Live quotes are NOT
       cached; those stay fresh on every visit.

   Ticker data comes from etf-groups.js (loaded first).
   ========================================== */

const PERIODS = [
  { key: '1y', label: '1Y' },
  { key: '5y', label: '5Y' },
  { key: '10y', label: '10Y' },
  { key: 'max', label: 'Max' },
];

const HISTORY_CACHE_KEY = 'etf_history_summary_v1';
const HISTORY_CACHE_TTL_MS = 12 * 60 * 60 * 1000; // 12h — history only changes on monthly load

let _activePeriod = '10y';
let _history = {};      // ticker -> {periods: {...}}
let _quotes = {};       // ticker -> {price, week52_low, week52_high}

const ALL_TICKERS = ETF_GROUPS.flatMap(g => g.rows.map(r => r[1]));

/* ---------- rendering ---------- */

function renderChips() {
  const el = $('rangeChips');
  el.innerHTML =
    '<span class="range-chips-label">Range</span>' +
    PERIODS.map(p =>
      `<button class="range-chip${p.key === _activePeriod ? ' active' : ''}" data-period="${p.key}">${p.label}</button>`
    ).join('');

  el.querySelectorAll('.range-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      _activePeriod = btn.dataset.period;
      renderChips();
      ALL_TICKERS.forEach(renderHistoryCells);
    });
  });
}

function renderGroups() {
  $('groupsContainer').innerHTML = ETF_GROUPS.map(group => `
    <details class="etf-group" open>
      <summary>${group.title}<span class="etf-count">${group.rows.length}</span></summary>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Fund</th>
              <th class="r">Price</th>
              <th>Trend</th>
              <th>Position in range</th>
              <th class="r">Change</th>
            </tr>
          </thead>
          <tbody>
            ${group.rows.map(([category, ticker, name, url]) => `
              <tr data-ticker="${ticker}">
                <td>${category}</td>
                <td class="fund-name"><a href="${url}" target="_blank" rel="noopener">${name}</a><span class="fund-ticker">${ticker}</span></td>
                <td class="r price-cell" id="price-${ticker}"><span class="sk sk-price"></span></td>
                <td class="spark-cell" id="spark-${ticker}"><span class="sk sk-spark"></span></td>
                <td class="pos-cell" id="pos-${ticker}"><span class="sk sk-bar"></span></td>
                <td class="r chg-cell" id="chg-${ticker}"><span class="sk sk-chg" style="margin-left:auto"></span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </details>
  `).join('');
}

function setAllGroups(open) {
  document.querySelectorAll('.etf-group').forEach(el => { el.open = open; });
}

function sparklineSvg(path) {
  if (!path || path.length < 2) return '<span class="quote-na">—</span>';

  const W = 78, H = 22, pad = 2;
  const min = Math.min(...path), max = Math.max(...path);
  const span = max - min || 1;
  const stepX = W / (path.length - 1);

  const pts = path.map((v, i) => {
    const x = i * stepX;
    const y = pad + (1 - (v - min) / span) * (H - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const last = pts.split(' ').pop().split(',');

  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${pts}"/>
    <circle class="spark-dot" cx="${last[0]}" cy="${last[1]}" r="1.8"/>
  </svg>`;
}

/* Label the actual span covered, not the requested one. A ticker with less
   history than the selected period (IBIT under 10Y, say) would otherwise be
   labelled "10Y ago" next to a date only ~3 years back. */
const PERIOD_MONTHS = { '1y': 12, '5y': 60, '10y': 120 };

function periodSpanLabel(monthsCovered) {
  const requested = PERIOD_MONTHS[_activePeriod];
  if (requested && monthsCovered >= requested) {
    return PERIODS.find(x => x.key === _activePeriod).label;
  }
  if (monthsCovered < 24) return `${monthsCovered}mo`;
  const yrs = monthsCovered / 12;
  return `${yrs.toFixed(yrs % 1 < 0.05 ? 0 : 1)}yr`;
}

/* The history-driven cells (sparkline, position bar, change) all key off
   the currently selected period, so they re-render together on a chip click. */
function renderHistoryCells(ticker) {
  const sparkEl = $('spark-' + ticker);
  const posEl = $('pos-' + ticker);
  const chgEl = $('chg-' + ticker);
  if (!sparkEl || !posEl || !chgEl) return;

  const p = _history[ticker]?.periods?.[_activePeriod];
  if (!p) {
    sparkEl.innerHTML = '<span class="quote-na">—</span>';
    posEl.innerHTML = '<span class="quote-na">no history loaded</span>';
    chgEl.innerHTML = '<span class="quote-na">—</span>';
    return;
  }

  sparkEl.innerHTML = sparklineSvg(p.path);

  /* Prefer the live quote for "where it sits right now"; fall back to the
     last monthly close when quotes are unavailable. */
  const current = _quotes[ticker]?.price ?? p.price_now;
  const pct = p.high > p.low
    ? Math.max(0, Math.min(100, ((current - p.low) / (p.high - p.low)) * 100))
    : 50;

  const spanLabel = periodSpanLabel(p.months_covered);

  posEl.innerHTML = `
    <div class="pos-labels"><span>$${p.low.toFixed(2)}</span><span>$${p.high.toFixed(2)}</span></div>
    <div class="pos-track">
      <div class="pos-fill" style="width:${pct}%"></div>
      <div class="pos-tick" style="left:calc(${pct}% - 1px)"></div>
    </div>
    <div class="pos-meta">${spanLabel} ago (${p.oldest_month}): $${p.price_then.toFixed(2)}</div>
  `;

  chgEl.textContent = p.change_pct == null
    ? '—'
    : (p.change_pct >= 0 ? '+' : '') + p.change_pct.toFixed(1) + '%';
}

function renderQuote(ticker) {
  const priceEl = $('price-' + ticker);
  if (!priceEl) return;
  const q = _quotes[ticker];
  priceEl.innerHTML = q ? '$' + q.price.toFixed(2) : '<span class="quote-na">n/a</span>';
}

/* ---------- data ---------- */

function readHistoryCache() {
  try {
    const raw = sessionStorage.getItem(HISTORY_CACHE_KEY);
    if (!raw) return null;
    const { at, tickers, data } = JSON.parse(raw);
    if (Date.now() - at > HISTORY_CACHE_TTL_MS) return null;
    // Invalidate if the curated list changed since the cache was written.
    if (tickers !== ALL_TICKERS.join(',')) return null;
    return data;
  } catch (e) { return null; }
}

function writeHistoryCache(data) {
  try {
    sessionStorage.setItem(HISTORY_CACHE_KEY, JSON.stringify({
      at: Date.now(), tickers: ALL_TICKERS.join(','), data,
    }));
  } catch (e) { /* quota or private mode — cache is optional */ }
}

async function loadHistory() {
  const cached = readHistoryCache();
  if (cached) {
    _history = cached;
    ALL_TICKERS.forEach(renderHistoryCells);
    return;
  }

  try {
    const resp = await authFetch(API + '/etf-directory/history-summary?symbols=' + ALL_TICKERS.join(','));
    if (!resp.ok) throw new Error('API returned ' + resp.status);
    _history = await resp.json();
    writeHistoryCache(_history);
  } catch (e) {
    console.error('loadHistory failed:', e);
    _history = {};
  }
  ALL_TICKERS.forEach(renderHistoryCells);
}

async function loadQuotes() {
  const statusEl = $('statusLine');
  try {
    const resp = await authFetch(API + '/quotes?symbols=' + ALL_TICKERS.join(','));
    if (!resp.ok) throw new Error('API returned ' + resp.status);
    _quotes = await resp.json();
    statusEl.textContent = `Live price loaded for ${Object.keys(_quotes).length} of ${ALL_TICKERS.length} funds.`;
  } catch (e) {
    console.error('loadQuotes failed:', e);
    _quotes = {};
    statusEl.textContent = 'Could not load live price data.';
  }
  ALL_TICKERS.forEach(renderQuote);
  // Position marker uses the live price, so refresh those cells once quotes land.
  if (Object.keys(_history).length) ALL_TICKERS.forEach(renderHistoryCells);
}

document.addEventListener('DOMContentLoaded', () => {
  renderGroups();
  renderChips();
  // Fire both together: history usually wins from cache, quotes always hit the network.
  loadHistory();
  loadQuotes();
});
