/* Market Drawdown Analysis — with year filters */
let monthlyData = null;
let yearStart = null, yearEnd = null;

async function loadData() {
  try {
    monthlyData = await getMonthlyPrices();
    populateYears();
    render();
  } catch(e) {
    console.error('Failed to load data:', e);
    document.querySelector('.container').innerHTML = '<div style="text-align:center;padding:60px;color:var(--text3)">Failed to load data. Make sure the API server is running.</div>';
  }
}

function populateYears() {
  let minY = Infinity, maxY = -Infinity;
  for (const sym of SECTOR_ORDER) {
    if (!monthlyData[sym]) continue;
    for (const p of monthlyData[sym].monthly) {
      if (p.year < minY) minY = p.year;
      if (p.year > maxY) maxY = p.year;
    }
  }
  const startSel = $('yearStart'), endSel = $('yearEnd');
  startSel.innerHTML = ''; endSel.innerHTML = '';
  for (let y = minY; y <= maxY; y++) {
    startSel.innerHTML += `<option value="${y}">${y}</option>`;
    endSel.innerHTML += `<option value="${y}"${y === maxY ? ' selected' : ''}>${y}</option>`;
  }
  yearStart = minY;
  yearEnd = maxY;
}

function onFilterChange() {
  yearStart = +$('yearStart').value;
  yearEnd = +$('yearEnd').value;
  if (yearStart > yearEnd) {
    const t = yearStart; yearStart = yearEnd; yearEnd = t;
    $('yearStart').value = yearStart; $('yearEnd').value = yearEnd;
  }
  render();
}

function computeDrawdowns(prices) {
  let peak = -Infinity;
  let maxDD = 0, maxPeakDate = null, maxTroughDate = null;
  let curPeakDate = null;

  for (const p of prices) {
    if (p.close > peak) {
      peak = p.close;
      curPeakDate = `${p.year}-${String(p.month).padStart(2,'0')}`;
    }
    const dd = ((p.close - peak) / peak) * 100;
    if (dd < maxDD) {
      maxDD = dd;
      maxPeakDate = curPeakDate;
      maxTroughDate = `${p.year}-${String(p.month).padStart(2,'0')}`;
    }
  }

  // Find recovery
  let recoveryDate = null;
  let troughFound = false;
  let runPeak = -Infinity;
  let peakBeforeTrough = -Infinity;
  for (const pt of prices) {
    if (pt.close > runPeak) runPeak = pt.close;
    const key = `${pt.year}-${String(pt.month).padStart(2,'0')}`;
    if (key === maxTroughDate) { troughFound = true; peakBeforeTrough = runPeak; continue; }
    if (troughFound && pt.close >= peakBeforeTrough) {
      recoveryDate = key;
      break;
    }
  }

  return { maxDD, maxPeakDate, maxTroughDate, recoveryDate };
}

function render() {
  const results = [];
  for (const sym of SECTOR_ORDER) {
    if (!monthlyData[sym]) continue;
    const filtered = monthlyData[sym].monthly.filter(p => p.year >= yearStart && p.year <= yearEnd);
    if (filtered.length < 2) continue;
    const dd = computeDrawdowns(filtered);
    results.push({ sym, name: monthlyData[sym].name, ...dd });
  }

  results.sort((a, b) => a.maxDD - b.maxDD);
  const worstDD = Math.min(...results.map(r => r.maxDD));

  let html = '<div class="dd-card"><div class="dd-card-title">Maximum Drawdown by Sector (worst to best)</div>';
  for (const r of results) {
    const barWidth = worstDD !== 0 ? Math.abs(r.maxDD / worstDD) * 100 : 0;
    html += `
      <div class="dd-row">
        <span class="dd-sym">${r.sym}</span>
        <span class="dd-name">${r.name}</span>
        <div class="dd-bar-wrap">
          <div class="dd-bar" style="width:${barWidth}%;background:var(--text3);opacity:${0.35 + Math.abs(r.maxDD/100)*0.65}"></div>
        </div>
        <span class="dd-val">${r.maxDD.toFixed(1)}%</span>
        <span class="dd-period">${r.maxPeakDate || ''} → ${r.maxTroughDate || ''}</span>
      </div>
    `;
  }
  html += '</div>';

  html += '<h2 class="section-title" style="margin-top:32px">Drawdown Details</h2>';
  html += '<div class="cards-grid">';
  for (const r of results) {
    const recovery = r.recoveryDate ? r.recoveryDate : 'not recovered';
    let monthsToTrough = '';
    if (r.maxPeakDate && r.maxTroughDate) {
      const [py, pm] = r.maxPeakDate.split('-').map(Number);
      const [ty, tm] = r.maxTroughDate.split('-').map(Number);
      monthsToTrough = `${(ty - py) * 12 + (tm - pm)} months`;
    }
    let monthsToRecovery = '';
    if (r.maxTroughDate && r.recoveryDate) {
      const [ty, tm] = r.maxTroughDate.split('-').map(Number);
      const [ry, rm] = r.recoveryDate.split('-').map(Number);
      monthsToRecovery = `${(ry - ty) * 12 + (rm - tm)} months`;
    }

    html += `
      <div class="card fade-up">
        <div style="font-size:15px;font-weight:700;color:var(--accent);font-family:'Space Grotesk',sans-serif">${r.sym}</div>
        <div style="font-size:10px;color:var(--text3);margin-bottom:10px">${r.name}</div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Max Drawdown</span><span style="font-weight:600;color:var(--red);font-family:'JetBrains Mono',monospace">${r.maxDD.toFixed(1)}%</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Peak</span><span style="font-weight:600;font-family:'JetBrains Mono',monospace;color:var(--text1)">${r.maxPeakDate || '-'}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Trough</span><span style="font-weight:600;font-family:'JetBrains Mono',monospace;color:var(--text1)">${r.maxTroughDate || '-'}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Decline Duration</span><span style="font-weight:600;font-family:'JetBrains Mono',monospace;color:var(--text1)">${monthsToTrough}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Recovery</span><span style="font-weight:600;font-family:'JetBrains Mono',monospace;color:${r.recoveryDate ? 'var(--accent)' : 'var(--red)'}">${recovery}</span></div>
        ${monthsToRecovery ? `<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Recovery Time</span><span style="font-weight:600;font-family:'JetBrains Mono',monospace;color:var(--accent)">${monthsToRecovery}</span></div>` : ''}
      </div>
    `;
  }
  html += '</div>';
  $('content').innerHTML = html;
}

document.addEventListener('DOMContentLoaded', loadData);
