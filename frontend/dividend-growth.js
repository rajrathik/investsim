/* Dividend Growth Tracker — cards only, no table */
let data = null;
let yearStart = 2005, yearEnd = 2025;

async function loadData() {
  $('navLinks').innerHTML = navLinks();
  data = await getSectorPerformance();
  populateYears();
  render();
}

function populateYears() {
  let allYears = new Set();
  for (const sym of SECTOR_ORDER) {
    if (!data[sym]) continue;
    for (const y of Object.keys(data[sym].data)) allYears.add(+y);
  }
  const sorted = [...allYears].sort((a, b) => a - b);
  const startSel = $('yearStart'), endSel = $('yearEnd');
  startSel.innerHTML = ''; endSel.innerHTML = '';
  for (const y of sorted) {
    startSel.innerHTML += `<option value="${y}"${y === Math.max(sorted[0], yearStart) ? ' selected' : ''}>${y}</option>`;
    endSel.innerHTML += `<option value="${y}"${y === Math.min(sorted[sorted.length - 1], yearEnd) ? ' selected' : ''}>${y}</option>`;
  }
  yearStart = +startSel.value;
  yearEnd = +endSel.value;
}

function onYearChange() {
  yearStart = +$('yearStart').value;
  yearEnd = +$('yearEnd').value;
  if (yearStart > yearEnd) { const t = yearStart; yearStart = yearEnd; yearEnd = t; $('yearStart').value = yearStart; $('yearEnd').value = yearEnd; }
  render();
}

function render() {
  const years = [];
  for (let y = yearStart; y <= yearEnd; y++) years.push(y);
  const syms = SECTOR_ORDER.filter(s => data[s]);

  let html = '';
  for (const sym of syms) {
    const info = data[sym];
    const growthRates = [];
    let increases = 0, decreases = 0;
    let firstDiv = null, lastDiv = null, firstYear = null, lastYear = null;
    let totalDividends = 0;
    const decreaseYears = []; // track years with decline details

    for (const y of years) {
      const d = info.data[String(y)];
      const prevD = info.data[String(y - 1)];
      if (!d) continue;

      totalDividends += d.dividend;

      if (firstDiv === null && d.dividend > 0) { firstDiv = d.dividend; firstYear = y; }
      if (d.dividend > 0) { lastDiv = d.dividend; lastYear = y; }

      if (prevD && prevD.dividend > 0) {
        const g = ((d.dividend - prevD.dividend) / prevD.dividend) * 100;
        growthRates.push(g);
        if (g > 0) increases++;
        if (g < 0) {
          decreases++;
          decreaseYears.push({ year: y, from: prevD.dividend, to: d.dividend, change: g });
        }
      }
    }

    const avgGrowth = growthRates.length > 0 ? growthRates.reduce((a, b) => a + b, 0) / growthRates.length : null;
    let divCagr = null;
    if (firstDiv && lastDiv && firstYear && lastYear && lastYear > firstYear) {
      divCagr = (Math.pow(lastDiv / firstDiv, 1 / (lastYear - firstYear)) - 1) * 100;
    }

    const consistency = growthRates.length > 0 ? Math.round(increases / growthRates.length * 100) : 0;

    // Build the decrease detail rows (hidden by default)
    let decDetailHtml = '';
    if (decreaseYears.length > 0) {
      decDetailHtml = `<div class="dec-detail" id="dec-${sym}" style="display:none;margin-top:4px;padding:6px 0;border-top:1px solid var(--border)">`;
      for (const dy of decreaseYears) {
        decDetailHtml += `<div style="display:flex;justify-content:space-between;padding:2px 0;font-size:11px">
          <span style="color:var(--text3)">${dy.year}</span>
          <span style="font-family:'JetBrains Mono',monospace;color:var(--red)">$${dy.from.toFixed(2)} → $${dy.to.toFixed(2)} (${dy.change.toFixed(1)}%)</span>
        </div>`;
      }
      decDetailHtml += '</div>';
    }

    // Make decreases clickable only if there are any
    const decClickable = decreases > 0
      ? `<span style="font-weight:600;color:var(--red);font-family:'JetBrains Mono',monospace;cursor:pointer;text-decoration:underline;text-decoration-style:dotted" onclick="toggleDecDetail('${sym}')">${decreases}</span>`
      : `<span style="font-weight:600;color:var(--red);font-family:'JetBrains Mono',monospace">${decreases}</span>`;

    html += `
      <div class="card fade-up">
        <div style="font-size:15px;font-weight:700;color:var(--accent);font-family:'Space Grotesk',sans-serif">${sym}</div>
        <div style="font-size:10px;color:var(--text3);margin-bottom:10px">${info.name}</div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Total Dividends</span><span style="font-weight:600;color:var(--gold);font-family:'JetBrains Mono',monospace">$${totalDividends.toFixed(2)}</span></div>
        ${avgGrowth !== null ? `<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Avg Growth/Yr</span><span style="font-weight:600;color:${avgGrowth >= 0 ? 'var(--accent)' : 'var(--red)'};font-family:'JetBrains Mono',monospace">${avgGrowth >= 0 ? '+' : ''}${avgGrowth.toFixed(1)}%</span></div>` : ''}
        ${divCagr !== null ? `<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Dividend CAGR</span><span style="font-weight:600;color:${divCagr >= 0 ? 'var(--accent)' : 'var(--red)'};font-family:'JetBrains Mono',monospace">${divCagr >= 0 ? '+' : ''}${divCagr.toFixed(1)}%</span></div>` : ''}
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Increases</span><span style="font-weight:600;color:var(--accent);font-family:'JetBrains Mono',monospace">${increases}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Decreases</span>${decClickable}</div>
        ${decDetailHtml}
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Consistency</span><span style="font-weight:600;color:var(--text1);font-family:'JetBrains Mono',monospace">${consistency}%</span></div>
      </div>
    `;
  }
  $('summaryCards').innerHTML = html;
}

function toggleDecDetail(sym) {
  const el = document.getElementById('dec-' + sym);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

document.addEventListener('DOMContentLoaded', loadData);
