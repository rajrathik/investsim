/* $10,000 Growth Chart — interactive crosshair, ticker picker */
let data = null;
let yearStart = 2005, yearEnd = 2025;
let activeSyms = new Set(['VTI']); // Start with VTI only
let allSeries = {};
let chartMeta = null; // stores scale info for crosshair

async function loadData() {
  $('navLinks').innerHTML = navLinks();
  data = await getSectorPerformance();
  populateYears();
  buildTickerPicker();
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

function buildTickerPicker() {
  let html = '';
  for (const sym of SECTOR_ORDER) {
    if (!data[sym]) continue;
    const active = activeSyms.has(sym) ? 'active' : '';
    const color = SECTOR_COLORS[sym];
    const borderColor = activeSyms.has(sym) ? color : 'var(--border)';
    const bgColor = activeSyms.has(sym) ? color + '22' : 'var(--bg)';
    html += `<span class="ticker-chip ${active}" data-sym="${sym}" style="border-color:${borderColor};background:${bgColor};${activeSyms.has(sym) ? 'color:' + color : ''}">${sym}</span>`;
  }
  $('tickerPicker').innerHTML = html;

  document.querySelectorAll('.ticker-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const s = chip.dataset.sym;
      if (activeSyms.has(s)) {
        if (activeSyms.size > 1) activeSyms.delete(s); // Keep at least 1
      } else {
        activeSyms.add(s);
      }
      buildTickerPicker();
      render();
    });
  });
}

function computeGrowth(sym) {
  if (!data[sym]) return [];
  const points = [];
  let value = null;
  for (let y = yearStart; y <= yearEnd; y++) {
    const d = data[sym].data[String(y)];
    if (!d) continue;
    if (value === null) {
      // First year with data — set starting point
      points.push({ year: y - 1, value: 10000 });
      value = 10000;
    }
    if (d.prev_close > 0) {
      const tr = (d.close - d.prev_close + d.dividend) / d.prev_close;
      value *= (1 + tr);
    }
    points.push({ year: y, value });
  }
  return points;
}

function render() {
  const canvas = $('chartCanvas');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  const W = rect.width - 48, H = 450;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';
  ctx.scale(dpr, dpr);

  const pad = { top: 20, right: 80, bottom: 40, left: 70 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  // Compute all series (even hidden ones for final values)
  allSeries = {};
  let globalMin = 10000, globalMax = 10000;

  for (const sym of SECTOR_ORDER) {
    if (!data[sym]) continue;
    allSeries[sym] = computeGrowth(sym);
    if (activeSyms.has(sym)) {
      for (const p of allSeries[sym]) {
        if (p.value < globalMin) globalMin = p.value;
        if (p.value > globalMax) globalMax = p.value;
      }
    }
  }

  const range = globalMax - globalMin || 1;
  globalMin = Math.max(0, globalMin - range * 0.05);
  globalMax = globalMax + range * 0.05;

  const years = [];
  for (let y = yearStart - 1; y <= yearEnd; y++) years.push(y);

  const xScale = y => pad.left + ((y - years[0]) / (years[years.length - 1] - years[0])) * plotW;
  const yScale = v => pad.top + (1 - (v - globalMin) / (globalMax - globalMin)) * plotH;

  // Store chart meta for crosshair
  chartMeta = { pad, plotW, plotH, W, H, years, xScale, yScale, globalMin, globalMax };

  // Grid lines
  ctx.strokeStyle = THEME.grid;
  ctx.lineWidth = 0.5;
  const yTicks = 6;
  for (let i = 0; i <= yTicks; i++) {
    const val = globalMin + (globalMax - globalMin) * (i / yTicks);
    const py = yScale(val);
    ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(pad.left + plotW, py); ctx.stroke();
    ctx.fillStyle = THEME.axis;
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'right';
    ctx.fillText('$' + Math.round(val).toLocaleString(), pad.left - 8, py + 4);
  }

  // X labels
  ctx.textAlign = 'center';
  for (const y of years) {
    if (y % 2 === 0 || years.length <= 12) {
      const px = xScale(y);
      ctx.fillStyle = THEME.axis;
      ctx.fillText(String(y), px, H - pad.bottom + 20);
      ctx.beginPath(); ctx.moveTo(px, pad.top); ctx.lineTo(px, pad.top + plotH); ctx.stroke();
    }
  }

  // $10K baseline
  const baseY = yScale(10000);
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = THEME.text2;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.left, baseY); ctx.lineTo(pad.left + plotW, baseY); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = THEME.text2;
  ctx.textAlign = 'left';
  ctx.fillText('$10,000', pad.left + plotW + 4, baseY + 4);

  // Draw lines for active syms
  for (const sym of SECTOR_ORDER) {
    if (!allSeries[sym] || !activeSyms.has(sym)) continue;
    const pts = allSeries[sym];
    const color = SECTOR_COLORS[sym];

    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const px = xScale(pts[i].year);
      const py = yScale(pts[i].value);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.stroke();

    // End label
    const last = pts[pts.length - 1];
    ctx.fillStyle = color;
    ctx.font = 'bold 11px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText(sym, xScale(last.year) + 6, yScale(last.value) + 4);
  }

  // Attach crosshair events
  canvas.onmousemove = handleCrosshair;
  canvas.onmouseleave = () => { $('crosshairInfo').style.display = 'none'; };

  renderFinalValues();
}

function handleCrosshair(e) {
  if (!chartMeta) return;
  const canvas = $('chartCanvas');
  const bRect = canvas.getBoundingClientRect();
  const mx = e.clientX - bRect.left;
  const my = e.clientY - bRect.top;
  const { pad, plotW, plotH, years, xScale, yScale } = chartMeta;

  // Check if mouse is in plot area
  if (mx < pad.left || mx > pad.left + plotW || my < pad.top || my > pad.top + plotH) {
    $('crosshairInfo').style.display = 'none';
    return;
  }

  // Find closest year
  let closestYear = years[0];
  let closestDist = Infinity;
  for (const y of years) {
    const d = Math.abs(xScale(y) - mx);
    if (d < closestDist) { closestDist = d; closestYear = y; }
  }

  // Draw crosshair on canvas overlay (redraw)
  render(); // base render
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  ctx.save();
  ctx.scale(dpr, dpr);

  // Vertical line
  const cx = xScale(closestYear);
  ctx.setLineDash([3, 3]);
  ctx.strokeStyle = THEME.text2;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(cx, pad.top); ctx.lineTo(cx, pad.top + plotH); ctx.stroke();
  ctx.setLineDash([]);

  // Dots on lines
  let infoHtml = `<div class="ch-year">${closestYear}</div>`;
  for (const sym of SECTOR_ORDER) {
    if (!activeSyms.has(sym) || !allSeries[sym]) continue;
    const pt = allSeries[sym].find(p => p.year === closestYear);
    if (!pt) continue;
    const py = yScale(pt.value);
    const color = SECTOR_COLORS[sym];

    // Dot
    ctx.beginPath();
    ctx.arc(cx, py, 5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = THEME.bg;
    ctx.lineWidth = 2;
    ctx.stroke();

    const gain = ((pt.value / 10000 - 1) * 100).toFixed(1);
    const gainColor = pt.value >= 10000 ? 'var(--accent)' : 'var(--red)';
    infoHtml += `<div class="ch-row">
      <span class="ch-sym" style="color:${color}">${sym}</span>
      <span class="ch-val" style="color:${gainColor}">$${Math.round(pt.value).toLocaleString()} (${+gain >= 0 ? '+' : ''}${gain}%)</span>
    </div>`;
  }

  ctx.restore();

  // Remove recursive crosshair re-render
  canvas.onmousemove = handleCrosshair;

  const info = $('crosshairInfo');
  info.innerHTML = infoHtml;
  info.style.display = 'block';
}

function renderFinalValues() {
  const entries = [];
  for (const sym of SECTOR_ORDER) {
    if (!allSeries[sym] || !data[sym]) continue;
    const last = allSeries[sym][allSeries[sym].length - 1];
    entries.push({ sym, value: last.value, name: data[sym].name, active: activeSyms.has(sym) });
  }
  entries.sort((a, b) => b.value - a.value);

  let html = '';
  for (const e of entries) {
    if (!e.active) continue;
    const color = e.value >= 10000 ? 'var(--accent)' : 'var(--red)';
    const gain = ((e.value / 10000 - 1) * 100).toFixed(1);
    html += `
      <div class="fv-item">
        <div>
          <div class="fv-sym" style="color:${SECTOR_COLORS[e.sym]}">${e.sym}</div>
          <div style="font-size:9px;color:var(--text3)">${e.name}</div>
        </div>
        <div style="text-align:right">
          <div class="fv-val" style="color:${color}">${formatDollar(Math.round(e.value))}</div>
          <div style="font-size:10px;color:${color};font-family:'JetBrains Mono',monospace">${+gain >= 0 ? '+' : ''}${gain}%</div>
        </div>
      </div>
    `;
  }
  $('finalValues').innerHTML = html;
}

document.addEventListener('DOMContentLoaded', loadData);
window.addEventListener('themechange', function() { if (chartMeta) render(); });
