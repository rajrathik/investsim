/* Sector Correlation Matrix */
let data = null;
let yearStart = 2005, yearEnd = 2025;

async function loadData() {
  try {
    data = await getSectorPerformance();
    populateYears();
    render();
  } catch(e) {
    console.error('Failed to load data:', e);
    document.querySelector('.container').innerHTML = '<div style="text-align:center;padding:60px;color:var(--text3)">Failed to load data. Make sure the API server is running.</div>';
  }
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

function getReturns(sym) {
  if (!data[sym]) return [];
  const rets = [];
  for (let y = yearStart; y <= yearEnd; y++) {
    const d = data[sym].data[String(y)];
    const tr = totalReturn(d);
    if (tr !== null) rets.push({ year: y, ret: tr });
  }
  return rets;
}

function corrClass(val) {
  if (val === 1) return 'val-self';
  if (val >= 0.4) return 'growth-pos';
  if (val >= -0.1) return 'growth-gold';
  return 'growth-neg';
}

function render() {
  const syms = SECTOR_ORDER.filter(s => data[s]);

  // Build return arrays keyed by sym
  const retMap = {};
  for (const s of syms) retMap[s] = getReturns(s);

  // Compute correlation matrix
  let html = '<table class="data-table"><thead><tr><th></th>';
  for (const s of syms) html += `<th>${s}</th>`;
  html += '</tr></thead><tbody>';

  for (const s1 of syms) {
    html += `<tr><td><strong>${s1}</strong><span class="ticker-name">${data[s1].name}</span></td>`;
    for (const s2 of syms) {
      // Find overlapping years
      const r1map = {}, r2map = {};
      for (const r of retMap[s1]) r1map[r.year] = r.ret;
      for (const r of retMap[s2]) r2map[r.year] = r.ret;
      const commonYears = Object.keys(r1map).filter(y => y in r2map);
      const x = commonYears.map(y => r1map[y]);
      const yArr = commonYears.map(y => r2map[y]);

      const corr = pearsonCorrelation(x, yArr);
      if (corr === null) {
        html += '<td></td>';
      } else {
        const cls = corrClass(corr);
        html += `<td class="${cls}" data-s1="${s1}" data-s2="${s2}" data-corr="${corr.toFixed(3)}" data-n="${commonYears.length}">${corr.toFixed(2)}</td>`;
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  $('matrixContainer').innerHTML = html;

  // Tooltips
  document.querySelectorAll('.data-table td[data-s1]').forEach(cell => {
    cell.addEventListener('mouseenter', e => {
      const s1 = cell.dataset.s1, s2 = cell.dataset.s2;
      showTooltipAt(e, `
        <div><span class="tt-sym">${s1}</span> vs <span class="tt-sym">${s2}</span></div>
        <div style="margin-top:6px">
          <div class="tt-row"><span class="tt-label">Correlation</span><span class="tt-val">${cell.dataset.corr}</span></div>
          <div class="tt-row"><span class="tt-label">Common Years</span><span class="tt-val">${cell.dataset.n}</span></div>
          <div class="tt-row"><span class="tt-label">${data[s1].name}</span></div>
          <div class="tt-row"><span class="tt-label">${data[s2].name}</span></div>
        </div>
      `);
    });
    cell.addEventListener('mousemove', moveTooltip);
    cell.addEventListener('mouseleave', hideTooltip);
  });
}

document.addEventListener('DOMContentLoaded', loadData);
