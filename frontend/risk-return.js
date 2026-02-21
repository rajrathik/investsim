/* Risk vs Return Scatter Plot — pure canvas */
let data = null;
let yearStart = 2005, yearEnd = 2025;

async function loadData() {
  $('navLinks').innerHTML = navLinks();
  data = await getSectorPerformance();
  populateYears();
  render();
  window.addEventListener('resize', render);
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

function computeMetrics(sym) {
  if (!data[sym]) return null;
  const rets = [];
  const dataYears = [];
  for (let y = yearStart; y <= yearEnd; y++) {
    const d = data[sym].data[String(y)];
    const tr = totalReturn(d);
    if (tr !== null) { rets.push(tr); dataYears.push(y); }
  }
  if (rets.length < 2) return null;

  const vol = stdDev(rets);

  // Total CAGR
  let cagr = null;
  const firstD = data[sym].data[String(dataYears[0])];
  const lastD = data[sym].data[String(dataYears[dataYears.length - 1])];
  if (firstD && lastD && dataYears.length > 1) {
    let cumValue = 1.0;
    for (const y of dataYears) {
      const d = data[sym].data[String(y)];
      if (d && d.prev_close > 0) {
        const yearTR = (d.close - d.prev_close + d.dividend) / d.prev_close;
        cumValue *= (1 + yearTR);
      }
    }
    cagr = (Math.pow(cumValue, 1 / dataYears.length) - 1) * 100;
  }

  // Sharpe-like ratio (CAGR / vol) — simplified, no risk-free rate
  const sharpe = vol > 0 && cagr !== null ? cagr / vol : 0;

  return { sym, vol, cagr, sharpe, name: data[sym].name, years: dataYears.length };
}

function render() {
  const canvas = $('scatterCanvas');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  const W = rect.width - 48, H = 500;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';
  ctx.scale(dpr, dpr);

  const pad = { top: 30, right: 30, bottom: 50, left: 70 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  // Compute metrics for all sectors
  const points = [];
  for (const sym of SECTOR_ORDER) {
    const m = computeMetrics(sym);
    if (m && m.cagr !== null) points.push(m);
  }

  if (points.length === 0) return;

  // Determine axis ranges
  let minX = Math.min(...points.map(p => p.vol));
  let maxX = Math.max(...points.map(p => p.vol));
  let minY = Math.min(...points.map(p => p.cagr));
  let maxY = Math.max(...points.map(p => p.cagr));

  // Add padding
  const xPad = (maxX - minX) * 0.15 || 2;
  const yPad = (maxY - minY) * 0.15 || 2;
  minX = Math.max(0, minX - xPad); maxX += xPad;
  minY -= yPad; maxY += yPad;

  const xScale = v => pad.left + ((v - minX) / (maxX - minX)) * plotW;
  const yScale = v => pad.top + (1 - (v - minY) / (maxY - minY)) * plotH;

  // Grid
  ctx.strokeStyle = THEME.grid;
  ctx.lineWidth = 0.5;
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.fillStyle = THEME.axis;

  // Y-axis grid + labels
  const yTicks = 8;
  for (let i = 0; i <= yTicks; i++) {
    const val = minY + (maxY - minY) * (i / yTicks);
    const py = yScale(val);
    ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(pad.left + plotW, py); ctx.stroke();
    ctx.textAlign = 'right';
    ctx.fillText(formatPct(val), pad.left - 8, py + 4);
  }

  // X-axis grid + labels
  const xTicks = 6;
  for (let i = 0; i <= xTicks; i++) {
    const val = minX + (maxX - minX) * (i / xTicks);
    const px = xScale(val);
    ctx.beginPath(); ctx.moveTo(px, pad.top); ctx.lineTo(px, pad.top + plotH); ctx.stroke();
    ctx.textAlign = 'center';
    ctx.fillText(val.toFixed(1) + '%', px, H - pad.bottom + 20);
  }

  // Zero line for Y
  if (minY < 0 && maxY > 0) {
    const zy = yScale(0);
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = THEME.text2;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.left, zy); ctx.lineTo(pad.left + plotW, zy); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Axis labels
  ctx.fillStyle = THEME.text2;
  ctx.font = '11px "Space Grotesk", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('VOLATILITY (Std Dev of Annual Total Returns)', pad.left + plotW / 2, H - 5);
  ctx.save();
  ctx.translate(15, pad.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('TOTAL CAGR', 0, 0);
  ctx.restore();

  // Plot dots
  for (const p of points) {
    const px = xScale(p.vol);
    const py = yScale(p.cagr);
    const color = SECTOR_COLORS[p.sym] || THEME.text2;

    // Dot
    ctx.beginPath();
    ctx.arc(px, py, 8, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = THEME.bg;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Label
    ctx.fillStyle = color;
    ctx.font = 'bold 10px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText(p.sym, px + 12, py + 4);
  }

  // Hover handling via canvas mouse events
  canvas.onmousemove = e => {
    const bRect = canvas.getBoundingClientRect();
    const mx = e.clientX - bRect.left;
    const my = e.clientY - bRect.top;
    let found = null;
    for (const p of points) {
      const px = xScale(p.vol);
      const py = yScale(p.cagr);
      if (Math.hypot(mx - px, my - py) < 14) { found = p; break; }
    }
    if (found) {
      canvas.style.cursor = 'pointer';
      showTooltipAt(e, `
        <div><span class="tt-sym">${found.sym}</span><span class="tt-year">${found.name}</span></div>
        <div style="margin-top:6px">
          <div class="tt-row"><span class="tt-label">Total CAGR</span><span class="tt-val" style="color:${found.cagr >= 0 ? 'var(--accent)' : 'var(--red)'}">${formatPct(found.cagr, 2)}</span></div>
          <div class="tt-row"><span class="tt-label">Volatility</span><span class="tt-val">${found.vol.toFixed(1)}%</span></div>
          <div class="tt-row"><span class="tt-label">Return/Risk</span><span class="tt-val">${found.sharpe.toFixed(2)}</span></div>
          <div class="tt-row"><span class="tt-label">Data Years</span><span class="tt-val">${found.years}</span></div>
        </div>
      `);
    } else {
      canvas.style.cursor = 'default';
      hideTooltip();
    }
  };
  canvas.onmouseleave = hideTooltip;

  // Summary cards
  renderSummary(points);
}

function renderSummary(points) {
  // Sort by Sharpe-like ratio (best risk-adjusted return)
  const sorted = points.slice().sort((a, b) => b.sharpe - a.sharpe);
  let html = '';
  for (const p of sorted) {
    html += `
      <div class="card fade-up">
        <div style="font-size:15px;font-weight:700;color:${SECTOR_COLORS[p.sym]};font-family:'Space Grotesk',sans-serif">${p.sym}</div>
        <div style="font-size:10px;color:var(--text3);margin-bottom:10px">${p.name}</div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Total CAGR</span><span style="font-weight:600;color:${p.cagr >= 0 ? 'var(--accent)' : 'var(--red)'};font-family:'JetBrains Mono',monospace">${formatPct(p.cagr, 2)}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Volatility</span><span style="font-weight:600;color:var(--text1);font-family:'JetBrains Mono',monospace">${p.vol.toFixed(1)}%</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Return/Risk</span><span style="font-weight:600;color:var(--accent);font-family:'JetBrains Mono',monospace">${p.sharpe.toFixed(2)}</span></div>
        <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px"><span style="color:var(--text3)">Data Years</span><span style="font-weight:600;color:var(--text1);font-family:'JetBrains Mono',monospace">${p.years}</span></div>
      </div>
    `;
  }
  $('summaryCards').innerHTML = html;
}

document.addEventListener('DOMContentLoaded', loadData);
window.addEventListener('themechange', function() { if (typeof render === 'function') render(); });
