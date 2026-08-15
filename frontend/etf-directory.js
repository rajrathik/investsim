/* ==========================================
   ETF DIRECTORY -- CLASSIC TABLE LAYOUT
   The original full-width table view, kept intact and reachable from
   Sector tools > ETF Directory (classic table). The default layout at /
   is built by etf-home.js instead.

   Ticker data comes from etf-groups.js (loaded first). Price + 52-week
   range are live from our own backend (GET /api/quotes).
   ========================================== */

function renderGroups() {
  const container = $('groupsContainer');
  container.innerHTML = ETF_GROUPS.map(group => `
    <details class="etf-group" open>
      <summary>${group.title}<span class="etf-count">${group.rows.length}</span></summary>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Fund</th>
              <th class="r">Price</th>
              <th>52W Range</th>
              <th>10Y Range</th>
              <th title="Bar length uses a compressed (square-root) scale, not linear -- returns here span -41% to +1500%+, so a linear scale would make everything except the single biggest winner look flat. Compressed scale keeps both ends visually comparable.">10Y Return</th>
            </tr>
          </thead>
          <tbody>
            ${group.rows.map(([category, ticker, name, url]) => `
              <tr data-ticker="${ticker}">
                <td>${category}</td>
                <td class="fund-name"><a href="${url}" target="_blank" rel="noopener">${name}</a><span class="fund-ticker">${ticker}</span></td>
                <td class="r price-cell" id="price-${ticker}"><span class="quote-na">…</span></td>
                <td class="range-cell" id="range-${ticker}"></td>
                <td class="range-cell ten-yr-cell" id="tenyr-${ticker}"><span class="quote-na">—</span></td>
                <td class="return-cell" id="return-${ticker}"><span class="quote-na">—</span></td>
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

let _latestQuotes = {};

function renderQuote(ticker, quote) {
  const priceCell = $('price-' + ticker);
  const rangeCell = $('range-' + ticker);
  if (!priceCell || !rangeCell) return;

  if (!quote) {
    priceCell.innerHTML = '<span class="quote-na">n/a</span>';
    rangeCell.innerHTML = '<span class="quote-na">n/a</span>';
    return;
  }

  const { price, week52_low, week52_high } = quote;
  priceCell.textContent = '$' + price.toFixed(2);

  const pct = week52_high > week52_low
    ? Math.max(0, Math.min(100, ((price - week52_low) / (week52_high - week52_low)) * 100))
    : 50;

  rangeCell.innerHTML = `
    <div class="range-labels"><span>$${week52_low.toFixed(2)}</span><span>$${week52_high.toFixed(2)}</span></div>
    <div class="range-track"><div class="range-marker" style="left:${pct}%"></div></div>
  `;
}

async function loadQuotes() {
  const allTickers = ETF_GROUPS.flatMap(g => g.rows.map(r => r[1]));
  const statusEl = $('statusLine');

  try {
    const resp = await authFetch(API + '/quotes?symbols=' + allTickers.join(','));
    if (!resp.ok) throw new Error('API returned ' + resp.status);
    const quotes = await resp.json();
    _latestQuotes = quotes;

    allTickers.forEach(ticker => renderQuote(ticker, quotes[ticker] || null));

    const found = Object.keys(quotes).length;
    statusEl.textContent = `Live price loaded for ${found} of ${allTickers.length} funds.`;
  } catch (e) {
    console.error('loadQuotes failed:', e);
    allTickers.forEach(ticker => renderQuote(ticker, null));
    statusEl.textContent = 'Could not load live price data.';
  }
}

function renderTenYear(ticker, tenYr) {
  const cell = $('tenyr-' + ticker);
  if (!cell) return;

  if (!tenYr) {
    cell.innerHTML = '<span class="quote-na">no history loaded</span>';
    return;
  }

  const { ten_yr_low, ten_yr_high, oldest_month, price_then, months_covered } = tenYr;
  const livePrice = _latestQuotes[ticker]?.price;
  const currentPrice = livePrice != null ? livePrice : tenYr.price_now;

  const pct = ten_yr_high > ten_yr_low
    ? Math.max(0, Math.min(100, ((currentPrice - ten_yr_low) / (ten_yr_high - ten_yr_low)) * 100))
    : 50;

  const spanLabel = months_covered < 120 ? `${months_covered}mo` : '10yr';

  cell.innerHTML = `
    <div class="range-labels"><span>$${ten_yr_low.toFixed(2)}</span><span>$${ten_yr_high.toFixed(2)}</span></div>
    <div class="range-track"><div class="range-marker ten-yr-marker" style="left:${pct}%"></div></div>
    <div class="ten-yr-compare">${spanLabel} ago (${oldest_month}): $${price_then.toFixed(2)}</div>
  `;
}

/* Diverging bar for the 10Y Return column. Returns here span roughly
   -41% to +1500%+ (verified against the real loaded data), so a plain
   linear scale would make every bar except the single biggest winner
   look flat. Signed-square-root compresses the tail just enough to
   keep both the bond/broad-market majority AND the outlier winners
   visually differentiated, instead of a hard cap that would make the
   top handful of tickers all look identical. Scale is computed fresh
   from whatever's actually loaded, so it stays calibrated as the
   underlying data changes over time. */
function computeReturnScale(ranges) {
  const pcts = Object.values(ranges).map(v => v.change_pct).filter(p => p != null);
  if (!pcts.length) return { maxPosSqrt: 1, maxNegSqrt: 1, zeroPct: 50 };

  const maxPos = Math.max(0, ...pcts);
  const maxNeg = Math.abs(Math.min(0, ...pcts));
  const maxPosSqrt = Math.sqrt(Math.max(maxPos, 1));
  const maxNegSqrt = Math.sqrt(Math.max(maxNeg, 1));

  // Zero-point sits proportionally between the two tails -- e.g. if the
  // worst loser is much smaller in magnitude than the best winner (true
  // here: bonds down ~40% max vs tech up ~1500%), zero sits close to the
  // left edge, giving most of the track's width to the positive side.
  const zeroPct = (maxNegSqrt / (maxNegSqrt + maxPosSqrt)) * 100;

  return { maxPosSqrt, maxNegSqrt, zeroPct };
}

function renderReturnBar(ticker, tenYr, scale) {
  const cell = $('return-' + ticker);
  if (!cell) return;

  if (!tenYr || tenYr.change_pct == null) {
    cell.innerHTML = '<span class="quote-na">no history loaded</span>';
    return;
  }

  const { change_pct } = tenYr;
  const { maxPosSqrt, maxNegSqrt, zeroPct } = scale;
  const signedSqrt = Math.sign(change_pct) * Math.sqrt(Math.abs(change_pct));

  let barLeft, barWidth;
  if (change_pct >= 0) {
    barWidth = maxPosSqrt > 0 ? (signedSqrt / maxPosSqrt) * (100 - zeroPct) : 0;
    barLeft = zeroPct;
  } else {
    barWidth = maxNegSqrt > 0 ? (Math.abs(signedSqrt) / maxNegSqrt) * zeroPct : 0;
    barLeft = zeroPct - barWidth;
  }

  const sign = change_pct >= 0 ? '+' : '';

  cell.innerHTML = `
    <div class="return-track">
      <div class="return-zero" style="left:${zeroPct}%"></div>
      <div class="return-bar" style="left:${barLeft}%; width:${barWidth}%"></div>
    </div>
    <div class="return-label">${sign}${change_pct.toFixed(1)}%</div>
  `;
}

async function loadTenYearRanges() {
  const allTickers = ETF_GROUPS.flatMap(g => g.rows.map(r => r[1]));

  try {
    const resp = await authFetch(API + '/etf-directory/10yr-range?symbols=' + allTickers.join(','));
    if (!resp.ok) throw new Error('API returned ' + resp.status);
    const ranges = await resp.json();

    const scale = computeReturnScale(ranges);
    allTickers.forEach(ticker => {
      const data = ranges[ticker] || null;
      renderTenYear(ticker, data);
      renderReturnBar(ticker, data, scale);
    });
  } catch (e) {
    console.error('loadTenYearRanges failed:', e);
    allTickers.forEach(ticker => {
      renderTenYear(ticker, null);
      renderReturnBar(ticker, null, null);
    });
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  renderGroups();
  await loadQuotes();
  loadTenYearRanges();
});
