/* ==========================================
   SHARED ANALYTICS JS
   Common API layer + utilities for all analytics pages
   ========================================== */

const API = "/api";
const $ = id => document.getElementById(id);

/* No-auth fetch */
async function authFetch(url, options = {}) {
  return fetch(url, options);
}

/* Sector order & colors */
const SECTOR_ORDER = [
  'XLK', 'XLV', 'XLF', 'XLE', 'XLY', 'XLP',
  'XLI', 'XLB', 'XLU', 'XLC', 'XLRE', 'VTI'
];

const SECTOR_COLORS = {
  XLK: '#3b82f6', XLV: '#10b981', XLF: '#f59e0b', XLE: '#ef4444',
  XLY: '#8b5cf6', XLP: '#06b6d4', XLI: '#f97316', XLB: '#84cc16',
  XLU: '#ec4899', XLC: '#14b8a6', XLRE: '#a855f7', VTI: '#e2e8f0'
};

/* ========== SHARED API CALLS ========== */

let _sectorCache = null;
async function getSectorPerformance() {
  if (_sectorCache) return _sectorCache;
  try {
    const resp = await authFetch(API + '/sector-performance');
    if (!resp.ok) throw new Error('API returned ' + resp.status);
    _sectorCache = await resp.json();
    return _sectorCache;
  } catch (e) {
    console.error('getSectorPerformance failed:', e);
    throw e;
  }
}

let _monthlyCache = null;
async function getMonthlyPrices() {
  if (_monthlyCache) return _monthlyCache;
  try {
    const resp = await authFetch(API + '/sector-monthly');
    if (!resp.ok) throw new Error('API returned ' + resp.status);
    _monthlyCache = await resp.json();
    return _monthlyCache;
  } catch (e) {
    console.error('getMonthlyPrices failed:', e);
    throw e;
  }
}

/* ========== UTILITY FUNCTIONS ========== */

function formatPct(val, decimals = 1) {
  const sign = val >= 0 ? '+' : '';
  return sign + val.toFixed(decimals) + '%';
}

function formatDollar(val) {
  return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

/* Pearson correlation between two arrays */
function pearsonCorrelation(x, y) {
  const n = Math.min(x.length, y.length);
  if (n < 2) return null;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += x[i]; sumY += y[i];
    sumXY += x[i] * y[i];
    sumX2 += x[i] * x[i]; sumY2 += y[i] * y[i];
  }
  const num = n * sumXY - sumX * sumY;
  const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : num / den;
}

/* Standard deviation */
function stdDev(arr) {
  const n = arr.length;
  if (n < 2) return 0;
  const mean = arr.reduce((a, b) => a + b, 0) / n;
  const variance = arr.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (n - 1);
  return Math.sqrt(variance);
}

/* Compute total return for a year from sector data */
function totalReturn(d) {
  if (!d || d.prev_close <= 0) return null;
  return ((d.close - d.prev_close + d.dividend) / d.prev_close) * 100;
}

/* Tooltip helpers */
function showTooltipAt(e, html) {
  const tooltip = $('tooltip');
  if (!tooltip) return;
  tooltip.innerHTML = html;
  tooltip.classList.add('show');
  moveTooltip(e);
}

function moveTooltip(e) {
  const tooltip = $('tooltip');
  if (!tooltip) return;
  const pad = 16;
  let x = e.clientX + pad, y = e.clientY + pad;
  const rect = tooltip.getBoundingClientRect();
  if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - pad;
  tooltip.style.left = x + 'px';
  tooltip.style.top = y + 'px';
}

function hideTooltip() {
  const tooltip = $('tooltip');
  if (tooltip) tooltip.classList.remove('show');
}

/* ========== PAGE VIEW TRACKING (self-hosted, zero cost) ========== */
(function() {
  try {
    var pg = location.pathname || '/';
    var ref = document.referrer || '';
    navigator.sendBeacon('/api/track/pageview', JSON.stringify({ page: pg, referrer: ref }));
  } catch(e) { /* fire-and-forget */ }
})();
