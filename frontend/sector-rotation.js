/* Sector Rotation / Ranking by Year */
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

function getRankClass(rank, total) {
  if (total <= 1) return '';
  // Map rank to color: 1=best(green), last=worst(red)
  const pct = (rank - 1) / (total - 1); // 0 to 1
  if (pct <= 0.08) return 'rank-1';
  if (pct <= 0.17) return 'rank-2';
  if (pct <= 0.25) return 'rank-3';
  if (pct <= 0.33) return 'rank-4';
  if (pct <= 0.42) return 'rank-5';
  if (pct <= 0.50) return 'rank-6';
  if (pct <= 0.58) return 'rank-7';
  if (pct <= 0.67) return 'rank-8';
  if (pct <= 0.75) return 'rank-9';
  if (pct <= 0.83) return 'rank-10';
  if (pct <= 0.92) return 'rank-11';
  return 'rank-12';
}

function render() {
  const years = [];
  for (let y = yearStart; y <= yearEnd; y++) years.push(y);
  const syms = SECTOR_ORDER.filter(s => data[s]);

  // For each year, rank sectors by total return
  const rankings = {}; // year -> [{sym, ret, rank}]
  for (const y of years) {
    const entries = [];
    for (const sym of syms) {
      const d = data[sym].data[String(y)];
      const tr = totalReturn(d);
      if (tr !== null) entries.push({ sym, ret: tr });
    }
    entries.sort((a, b) => b.ret - a.ret); // best first
    entries.forEach((e, i) => e.rank = i + 1);
    rankings[y] = entries;
  }

  // Build table: rows = rank positions (1st, 2nd, ...), columns = years
  // Each cell shows the sector that held that rank
  const maxRanks = syms.length;

  let html = '<table class="data-table"><thead><tr><th>Rank</th>';
  for (const y of years) html += `<th>${y}</th>`;
  html += '</tr></thead><tbody>';

  for (let rank = 1; rank <= maxRanks; rank++) {
    html += `<tr><td><strong>#${rank}</strong></td>`;
    for (const y of years) {
      const entry = (rankings[y] || []).find(e => e.rank === rank);
      if (!entry) { html += '<td></td>'; continue; }
      const total = (rankings[y] || []).length;
      const cls = getRankClass(rank, total);
      const sign = entry.ret >= 0 ? '+' : '';
      html += `<td class="${cls}" data-sym="${entry.sym}" data-year="${y}" data-ret="${entry.ret.toFixed(1)}" data-rank="${rank}">
        <strong>${entry.sym}</strong><br><span style="font-size:10px;opacity:0.8">${sign}${entry.ret.toFixed(1)}%</span>
      </td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  $('tableContainer').innerHTML = html;

  // Tooltips
  document.querySelectorAll('.data-table td[data-sym]').forEach(cell => {
    cell.addEventListener('mouseenter', e => {
      const sym = cell.dataset.sym;
      showTooltipAt(e, `
        <div><span class="tt-sym">${sym}</span><span class="tt-year">${data[sym].name}</span></div>
        <div style="margin-top:6px">
          <div class="tt-row"><span class="tt-label">Year</span><span class="tt-val">${cell.dataset.year}</span></div>
          <div class="tt-row"><span class="tt-label">Rank</span><span class="tt-val">#${cell.dataset.rank}</span></div>
          <div class="tt-row"><span class="tt-label">Total Return</span><span class="tt-val" style="color:${+cell.dataset.ret >= 0 ? 'var(--accent)' : 'var(--red)'}">${+cell.dataset.ret >= 0 ? '+' : ''}${cell.dataset.ret}%</span></div>
        </div>
      `);
    });
    cell.addEventListener('mousemove', moveTooltip);
    cell.addEventListener('mouseleave', hideTooltip);
  });

  // Leadership cards
  renderLeaderCards(rankings, years, syms);
}

function renderLeaderCards(rankings, years, syms) {
  const counts = {};
  for (const s of syms) counts[s] = { first: 0, top3: 0, bottom3: 0, total: 0 };

  for (const y of years) {
    const entries = rankings[y] || [];
    const n = entries.length;
    for (const e of entries) {
      counts[e.sym].total++;
      if (e.rank === 1) counts[e.sym].first++;
      if (e.rank <= 3) counts[e.sym].top3++;
      if (e.rank > n - 3) counts[e.sym].bottom3++;
    }
  }

  // Sort by #1 finishes, then top3
  const sorted = syms.slice().sort((a, b) => counts[b].first - counts[a].first || counts[b].top3 - counts[a].top3);

  let html = '';
  for (const sym of sorted) {
    const c = counts[sym];
    html += `
      <div class="card fade-up">
        <div style="font-size:15px;font-weight:700;color:var(--accent);font-family:'Space Grotesk',sans-serif">${sym}</div>
        <div style="font-size:10px;color:var(--text3);margin-bottom:10px">${data[sym].name}</div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">#1 Finishes</span><span style="font-weight:600;color:var(--accent);font-family:'JetBrains Mono',monospace">${c.first}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Top 3 Finishes</span><span style="font-weight:600;color:var(--accent);font-family:'JetBrains Mono',monospace">${c.top3}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Bottom 3 Finishes</span><span style="font-weight:600;color:var(--red);font-family:'JetBrains Mono',monospace">${c.bottom3}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Years Ranked</span><span style="font-weight:600;color:var(--text1);font-family:'JetBrains Mono',monospace">${c.total}</span></div>
      </div>
    `;
  }
  $('leaderCards').innerHTML = html;
}

document.addEventListener('DOMContentLoaded', loadData);
