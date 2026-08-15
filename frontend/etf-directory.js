/* ==========================================
   ETF DIRECTORY
   Static curated list for now (category/fund/ticker/link) -- some of this
   is expected to move into the database later. Price + 52-week range are
   live, fetched from our own backend (GET /api/quotes), not a third-party
   client-side proxy.
   ========================================== */

const ETF_GROUPS = [
  {
    title: 'Market Cap & Style ETFs',
    rows: [
      ['Total US Market', 'ITOT', 'iShares Core S&P Total U.S. Stock Market ETF', 'https://www.ishares.com/us/products/239724/ishares-core-sp-total-us-stock-market-etf'],
      ['Mega-Cap', 'OEF', 'iShares S&P 100 ETF', 'https://www.ishares.com/us/products/239723/ishares-sp-100-etf'],
      ['Large-Cap Blend', 'VOO', 'Vanguard S&P 500 ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/voo'],
      ['Large-Cap Growth', 'QQQ', 'Invesco QQQ Trust', 'https://www.invesco.com/us/en/financial-products/etfs/invesco-qqq-trust-series-1.html'],
      ['Large-Cap Value', 'VTV', 'Vanguard Value ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vtv'],
      ['Mid-Cap Blend', 'IJH', 'iShares Core S&P Mid-Cap ETF', 'https://www.ishares.com/us/products/239763/ishares-core-sp-midcap-etf'],
      ['Mid-Cap Growth', 'VOT', 'Vanguard Mid-Cap Growth ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vot'],
      ['Mid-Cap Value', 'VOE', 'Vanguard Mid-Cap Value ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/voe'],
      ['Small-Cap Blend', 'IWM', 'iShares Russell 2000 ETF', 'https://www.ishares.com/us/products/239710/ishares-russell-2000-etf'],
      ['Small-Cap Growth', 'VBK', 'Vanguard Small-Cap Growth ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vbk'],
      ['Small-Cap Value', 'VBR', 'Vanguard Small-Cap Value ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vbr'],
    ],
  },
  {
    title: 'Factor & Strategy ETFs',
    rows: [
      ['Momentum', 'MTUM', 'iShares MSCI USA Momentum Factor ETF', 'https://www.ishares.com/us/products/251614/ishares-msci-usa-momentum-factor-etf'],
      ['Dividend Growth', 'DGRO', 'iShares Core Dividend Growth ETF', 'https://www.ishares.com/us/products/264623/ishares-core-dividend-growth-etf'],
      ['High Dividend Yield', 'HDV', 'iShares Core High Dividend ETF', 'https://www.ishares.com/us/products/239563/ishares-core-high-dividend-etf'],
      ['Dividend & Buybacks', 'DIVB', 'iShares Core Dividend ETF', 'https://www.ishares.com/us/products/291387/ishares-core-dividend-etf'],
    ],
  },
  {
    title: 'Global & Country ETFs',
    rows: [
      ['Total Intl (Ex-US)', 'VXUS', 'Vanguard Total International Stock ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vxus'],
      ['Developed Markets', 'VEA', 'Vanguard FTSE Developed Markets ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vea'],
      ['Emerging Markets', 'VWO', 'Vanguard FTSE Emerging Markets ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vwo'],
      ['Europe (Broad)', 'VGK', 'Vanguard FTSE Europe ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vgk'],
      ['Japan', 'EWJ', 'iShares MSCI Japan ETF', 'https://www.ishares.com/us/products/239665/ishares-msci-japan-etf'],
      ['Germany', 'EWG', 'iShares MSCI Germany ETF', 'https://www.ishares.com/us/products/239650/ishares-msci-germany-etf'],
      ['France', 'EWQ', 'iShares MSCI France ETF', 'https://www.ishares.com/us/products/239648/ishares-msci-france-etf'],
      ['United Kingdom', 'EWU', 'iShares MSCI United Kingdom ETF', 'https://www.ishares.com/us/products/239690/ishares-msci-united-kingdom-etf'],
      ['Canada', 'EWC', 'iShares MSCI Canada ETF', 'https://www.ishares.com/us/products/239615/ishares-msci-canada-etf'],
      ['Australia', 'EWA', 'iShares MSCI Australia ETF', 'https://www.ishares.com/us/products/239607/ishares-msci-australia-etf'],
      ['China', 'MCHI', 'iShares MSCI China ETF', 'https://www.ishares.com/us/products/239619/ishares-msci-china-etf'],
      ['India', 'INDA', 'iShares MSCI India ETF', 'https://www.ishares.com/us/products/239659/ishares-msci-india-etf'],
      ['Global Mega-Cap', 'IOO', 'iShares Global 100 ETF', 'https://www.ishares.com/us/products/239737/ishares-global-100-etf'],
    ],
  },
  {
    title: 'Broad Sector ETFs (U.S.)',
    rows: [
      ['Technology', 'XLK', 'Technology Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/state-street-technology-select-sector-spdr-etf-xlk'],
      ['Financials', 'XLF', 'Financial Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-financial-select-sector-spdr-fund-xlf'],
      ['Healthcare', 'XLV', 'Health Care Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-health-care-select-sector-spdr-fund-xlv'],
      ['Consumer Discretionary', 'XLY', 'Consumer Discretionary Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-consumer-discretionary-select-sector-spdr-fund-xly'],
      ['Consumer Staples', 'XLP', 'Consumer Staples Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-consumer-staples-select-sector-spdr-fund-xlp'],
      ['Energy', 'XLE', 'Energy Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-energy-select-sector-spdr-fund-xle'],
      ['Industrials', 'XLI', 'Industrial Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-industrial-select-sector-spdr-fund-xli'],
      ['Utilities', 'XLU', 'Utilities Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-utilities-select-sector-spdr-fund-xlu'],
      ['Real Estate', 'XLRE', 'Real Estate Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-real-estate-select-sector-spdr-fund-xlre'],
      ['Materials', 'XLB', 'Materials Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-materials-select-sector-spdr-fund-xlb'],
      ['Communication Services', 'XLC', 'Communication Services Select Sector SPDR', 'https://www.ssga.com/us/en/intermediary/etfs/the-communication-services-select-sector-spdr-fund-xlc'],
    ],
  },
  {
    title: 'Global Sector ETFs',
    rows: [
      ['Technology (Global)', 'IXN', 'iShares Global Tech ETF', 'https://www.ishares.com/us/products/239750/ishares-global-tech-etf'],
      ['Healthcare (Global)', 'IXJ', 'iShares Global Healthcare ETF', 'https://www.ishares.com/us/products/239744/ishares-global-healthcare-etf'],
      ['Energy (Global)', 'IXC', 'iShares Global Energy ETF', 'https://www.ishares.com/us/products/239741/ishares-global-energy-etf'],
      ['Consumer Staples (Global)', 'KXI', 'iShares Global Consumer Staples ETF', 'https://www.ishares.com/us/products/239740/ishares-global-consumer-staples-etf'],
      ['Real Estate (Global)', 'REET', 'iShares Global REIT ETF', 'https://www.ishares.com/us/products/268752/ishares-global-reit-etf'],
      ['Industrials (Global)', 'EXI', 'iShares Global Industrials ETF', 'https://www.ishares.com/us/products/239745/ishares-global-industrials-etf'],
      ['Materials (Global)', 'MXI', 'iShares Global Materials ETF', 'https://www.ishares.com/us/products/239748/ishares-global-materials-etf'],
    ],
  },
  {
    title: 'Subsector & Industry ETFs',
    rows: [
      ['Semiconductors', 'SMH', 'VanEck Semiconductor ETF', 'https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/'],
      ['Software', 'IGV', 'iShares Expanded Tech-Software Sector ETF', 'https://www.blackrock.com/us/individual/products/239771/ishares-north-american-techsoftware-etf'],
      ['Robotics & AI', 'BOTZ', 'Global X Robotics & Artificial Intelligence ETF', 'https://www.globalxetfs.com/funds/botz/'],
      ['Cloud Computing', 'SKYY', 'First Trust Cloud Computing ETF', 'https://www.ftportfolios.com/Retail/Etf/EtfSummary.aspx?Ticker=SKYY'],
      ['Internet', 'FDN', 'First Trust Dow Jones Internet Index Fund', 'https://www.ftportfolios.com/Retail/Etf/EtfSummary.aspx?Ticker=FDN'],
      ['Cybersecurity (Broad)', 'CIBR', 'First Trust NASDAQ Cybersecurity ETF', 'https://www.ftportfolios.com/Retail/Etf/EtfSummary.aspx?Ticker=CIBR'],
      ['Cybersecurity (Pure-Play)', 'BUG', 'Global X Cybersecurity ETF', 'https://www.globalxetfs.com/funds/bug/'],
      ['Fintech', 'FINX', 'Global X FinTech ETF', 'https://www.globalxetfs.com/funds/finx/'],
      ['Biotechnology', 'XBI', 'SPDR S&P Biotech ETF', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-biotech-etf-xbi'],
      ['Medical Devices', 'IHI', 'iShares U.S. Medical Devices ETF', 'https://www.ishares.com/us/products/239516/ishares-us-medical-devices-etf'],
      ['Regional Banks', 'KRE', 'SPDR S&P Regional Banking ETF', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-regional-banking-etf-kre'],
      ['Insurance', 'KIE', 'SPDR S&P Insurance ETF', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-insurance-etf-kie'],
      ['Oil & Gas E&P', 'XOP', 'SPDR S&P Oil & Gas Exploration & Production ETF', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-oil-gas-exploration-production-etf-xop'],
      ['Clean Energy', 'ICLN', 'iShares Global Clean Energy ETF', 'https://www.ishares.com/us/products/239738/ishares-global-clean-energy-etf'],
      ['Retail', 'XRT', 'SPDR S&P Retail ETF', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-retail-etf-xrt'],
      ['Homebuilders', 'XHB', 'SPDR S&P Homebuilders ETF', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-homebuilders-etf-xhb'],
      ['Infrastructure', 'PAVE', 'Global X U.S. Infrastructure Development ETF', 'https://www.globalxetfs.com/funds/pave/'],
      ['Aerospace & Defense', 'ITA', 'iShares U.S. Aerospace & Defense ETF', 'https://www.ishares.com/us/products/239502/ishares-us-aerospace-defense-etf'],
      ['Transportation', 'IYT', 'iShares U.S. Transportation ETF', 'https://www.ishares.com/us/products/239501/ishares-transportation-average-etf'],
      ['Gold Miners', 'GDX', 'VanEck Gold Miners ETF', 'https://www.vaneck.com/us/en/investments/gold-miners-etf-gdx/'],
      ['Airlines', 'JETS', 'U.S. Global Jets ETF', 'https://usglobaletfs.com/fund/u-s-global-jets-etf/'],
      ['Uranium & Nuclear', 'URA', 'Global X Uranium ETF', 'https://www.globalxetfs.com/funds/ura'],
      ['Water', 'PHO', 'Invesco Water Resources ETF', 'https://www.invesco.com/us/en/financial-products/etfs/invesco-water-resources-etf.html'],
      ['Agribusiness', 'MOO', 'VanEck Agribusiness ETF', 'https://www.vaneck.com/us/en/investments/agribusiness-etf-moo/'],
    ],
  },
  {
    title: 'Commodities & Alternatives',
    rows: [
      ['Physical Gold', 'GLD', 'SPDR Gold Shares', 'https://www.ssga.com/us/en/intermediary/etfs/spdr-gold-shares-gld'],
      ['Physical Silver', 'SLV', 'iShares Silver Trust', 'https://www.ishares.com/us/products/239855/ishares-silver-trust-fund'],
      ['Broad Commodities', 'PDBC', 'Invesco Optimum Yield Diversified Commodity Strategy', 'https://www.invesco.com/us/en/financial-products/etfs/invesco-optimum-yield-diversified-commodity-strategy-no-k-1-etf.html'],
      ['Real Estate (Broad)', 'VNQ', 'Vanguard Real Estate Index ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/vnq'],
      ['Long-Term Treasuries', 'TLT', 'iShares 20+ Year Treasury Bond ETF', 'https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf'],
      ['Bitcoin (Spot)', 'IBIT', 'iShares Bitcoin Trust', 'https://www.ishares.com/us/products/333011/ishares-bitcoin-trust'],
    ],
  },
  {
    title: 'Fixed Income & Bond ETFs',
    rows: [
      ['Broad U.S. Aggregate', 'AGG', 'iShares Core U.S. Aggregate Bond ETF', 'https://www.ishares.com/us/products/239458/ishares-core-us-aggregate-bond-etf'],
      ['World Bond (Ex-US)', 'BNDX', 'Vanguard Total International Bond ETF', 'https://investor.vanguard.com/investment-products/etfs/profile/bndx'],
      ['U.S. Government / Treasury', 'IEF', 'iShares 7-10 Year Treasury Bond ETF', 'https://www.ishares.com/us/products/239456/ishares-710-year-treasury-bond-etf'],
      ['Inv. Grade Corporate', 'LQD', 'iShares iBoxx $ Inv Grade Corporate Bond ETF', 'https://www.ishares.com/us/products/239566/ishares-iboxx-investment-grade-corporate-bond-etf'],
      ['High Yield Corporate', 'HYG', 'iShares iBoxx $ High Yield Corporate Bond ETF', 'https://www.ishares.com/us/products/239565/ishares-iboxx-high-yield-corporate-bond-etf'],
    ],
  },
];

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

  const { ten_yr_low, ten_yr_high, oldest_month, price_then, change_pct, months_covered } = tenYr;
  const livePrice = _latestQuotes[ticker]?.price;
  const currentPrice = livePrice != null ? livePrice : tenYr.price_now;

  const pct = ten_yr_high > ten_yr_low
    ? Math.max(0, Math.min(100, ((currentPrice - ten_yr_low) / (ten_yr_high - ten_yr_low)) * 100))
    : 50;

  const spanLabel = months_covered < 120 ? `${months_covered}mo` : '10yr';
  const changeSign = change_pct >= 0 ? '+' : '';

  cell.innerHTML = `
    <div class="range-labels"><span>$${ten_yr_low.toFixed(2)}</span><span>$${ten_yr_high.toFixed(2)}</span></div>
    <div class="range-track"><div class="range-marker ten-yr-marker" style="left:${pct}%"></div></div>
    <div class="ten-yr-compare">${spanLabel} since ${oldest_month}: $${price_then.toFixed(2)} &rarr; ${changeSign}${change_pct.toFixed(1)}%</div>
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
