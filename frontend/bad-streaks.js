(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  let _data = null;
  let _n = 5;

  function fmt$(v) {
    return '$' + Math.round(v).toLocaleString();
  }

  function fmtPct(v) {
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  }

  function recStr(v) {
    if (v === null || v === undefined) return '<span class="rec-na">—</span>';
    const cls = v >= 0 ? 'c-rec-pos' : 'c-rec-neg';
    return `<span class="${cls}">${fmtPct(v)}</span>`;
  }

  function selectN(val) {
    _n = val;
    document.querySelectorAll('#nChips .ctrl-chip').forEach(b => {
      b.classList.toggle('active', +b.dataset.val === val);
    });
    if (_data) render();
  }

  function render() {
    const periods = _data.periods.slice(0, _n);

    // ── summary cards ──
    const worst  = periods[0];
    const rec1s  = periods.filter(p => p.recovery_yr1.available).map(p => p.recovery_yr1.return_pct);
    const rec2s  = periods.filter(p => p.recovery_yr2.available).map(p => p.recovery_yr2.return_pct);
    const avgRec1 = rec1s.length ? rec1s.reduce((a, b) => a + b, 0) / rec1s.length : null;
    const avgRec2 = rec2s.length ? rec2s.reduce((a, b) => a + b, 0) / rec2s.length : null;
    const posRec1 = rec1s.filter(v => v > 0).length;
    const posRec2 = rec2s.filter(v => v > 0).length;

    $('streakSummary').innerHTML = `
      <div class="streak-card sc-red">
        <div class="sc-icon">📉</div>
        <div class="sc-lbl">Worst 5-year period</div>
        <div class="sc-val c-worst">${fmtPct(worst.return_pct)}</div>
        <div class="sc-sub">${worst.start_year}–${worst.end_year} · $10K → ${fmt$(worst.end_value)}</div>
      </div>
      <div class="streak-card sc-green">
        <div class="sc-icon">📈</div>
        <div class="sc-lbl">Avg recovery (Yr +1)</div>
        <div class="sc-val ${avgRec1 !== null ? (avgRec1 >= 0 ? 'c-best' : 'c-worst') : ''}">${avgRec1 !== null ? fmtPct(avgRec1) : '—'}</div>
        <div class="sc-sub">${posRec1} of ${rec1s.length} periods had positive Yr +1</div>
      </div>
      <div class="streak-card sc-blue">
        <div class="sc-icon">🔄</div>
        <div class="sc-lbl">Avg recovery (Yr +2)</div>
        <div class="sc-val ${avgRec2 !== null ? (avgRec2 >= 0 ? 'c-best' : 'c-worst') : ''}">${avgRec2 !== null ? fmtPct(avgRec2) : '—'}</div>
        <div class="sc-sub">${posRec2} of ${rec2s.length} periods had positive Yr +2</div>
      </div>`;

    // ── panel sub ──
    $('panelSub').textContent = `Non-overlapping · ranked by 5-year total loss · showing ${_n}`;

    // ── table rows ──
    $('streaksBody').innerHTML = periods.map(p => {
      const pills = p.years_detail.map(y => {
        const cls = y.return_pct < 0 ? 'neg' : 'pos';
        return `<span class="yr-pill ${cls}">${y.year}: ${fmtPct(y.return_pct)}</span>`;
      }).join('');

      const recombCls = p.recovery_combined_pct !== null
        ? (p.recovery_combined_pct >= 0 ? 'c-rec-pos' : 'c-rec-neg')
        : '';

      return `<tr>
        <td class="td-rank">${p.rank}</td>
        <td class="td-period">
          ${p.start_year}–${p.end_year}
          <div class="yr-pills">${pills}</div>
        </td>
        <td class="td-r c-worst">${fmtPct(p.return_pct)}</td>
        <td class="td-r c-worst">${fmt$(p.end_value)}</td>
        <td class="td-rec">${recStr(p.recovery_yr1.available ? p.recovery_yr1.return_pct : null)}</td>
        <td class="td-rec">${recStr(p.recovery_yr2.available ? p.recovery_yr2.return_pct : null)}</td>
        <td class="td-rec">
          ${p.recovery_combined_pct !== null
            ? `<span class="${recombCls}">${fmtPct(p.recovery_combined_pct)}</span>`
            : '<span class="rec-na">—</span>'}
        </td>
      </tr>`;
    }).join('');

    $('results').style.display = '';
  }

  async function init() {
    document.querySelectorAll('#nChips .ctrl-chip').forEach(b => {
      b.addEventListener('click', () => selectN(+b.dataset.val));
    });

    $('statusMsg').textContent = 'Loading…';
    $('statusMsg').style.display = '';

    try {
      const res = await fetch('/api/sp500-bad-streaks?n=10');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      _data = await res.json();
      $('statusMsg').style.display = 'none';
      render();
    } catch (e) {
      $('statusMsg').textContent = 'Failed to load data. Please try again later.';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
