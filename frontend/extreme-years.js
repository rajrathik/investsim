(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  let _data = null;
  let _streaks = null;
  let _n = 10;
  let _sn = 5;  // streak count chip

  function fmt$(v) {
    return '$' + Math.round(v).toLocaleString();
  }

  function fmtPct(v) {
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  }

  // ── single-year panels ──────────────────────────────

  function selectN(val) {
    _n = val;
    document.querySelectorAll('#nChips .ctrl-chip').forEach(b => {
      b.classList.toggle('active', +b.dataset.val === val);
    });
    if (_data) render();
  }

  function buildRows(rows, isWorst, maxAbs) {
    const cls    = isWorst ? 'c-worst' : 'c-best';
    const barCls = isWorst ? 'bar-worst' : 'bar-best';
    return rows.slice(0, _n).map(r => {
      const barW = Math.min(100, Math.round(Math.abs(r.return_pct) / maxAbs * 100));
      return `<tr>
        <td class="td-rank">${r.rank}</td>
        <td class="td-date">${r.date}</td>
        <td class="td-ret ${cls}">${fmtPct(r.return_pct)}</td>
        <td class="td-val">
          <div class="val-wrap">
            <span class="val-num ${cls}">${fmt$(r.end_value)}</span>
            <div class="mini-bar ${barCls}" style="width:${barW}%"></div>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  function render() {
    const { worst, best } = _data;

    $('summaryGrid').innerHTML = `
      <div class="summary-card worst">
        <div class="sc-label">▼ Worst single year</div>
        <div class="sc-value c-worst">${fmt$(worst[0].end_value)}</div>
        <div class="sc-detail">${worst[0].date} &nbsp;·&nbsp; ${fmtPct(worst[0].return_pct)} &nbsp;·&nbsp; $10,000 turned into ${fmt$(worst[0].end_value)}</div>
      </div>
      <div class="summary-card best">
        <div class="sc-label">▲ Best single year</div>
        <div class="sc-value c-best">${fmt$(best[0].end_value)}</div>
        <div class="sc-detail">${best[0].date} &nbsp;·&nbsp; ${fmtPct(best[0].return_pct)} &nbsp;·&nbsp; $10,000 turned into ${fmt$(best[0].end_value)}</div>
      </div>`;

    $('worstSub').textContent = `Ranked by annual loss · showing top ${_n}`;
    $('bestSub').textContent  = `Ranked by annual gain · showing top ${_n}`;

    $('worstBody').innerHTML = buildRows(worst, true,  Math.abs(worst[0].return_pct));
    $('bestBody').innerHTML  = buildRows(best,  false, Math.abs(best[0].return_pct));

    $('results').style.display = '';
  }

  // ── worst 5-year streaks ────────────────────────────

  function selectSN(val) {
    _sn = val;
    document.querySelectorAll('#streakChips .ctrl-chip').forEach(b => {
      b.classList.toggle('active', +b.dataset.val === val);
    });
    if (_streaks) renderStreaks();
  }

  function recClass(v) {
    if (v === null || v === undefined) return 'rec-na';
    return v >= 0 ? 'c-rec-pos' : 'c-rec-neg';
  }

  function recStr(v) {
    if (v === null || v === undefined) return '<span class="rec-na">—</span>';
    return `<span class="${recClass(v)}">${fmtPct(v)}</span>`;
  }

  function renderStreaks() {
    const periods = _streaks.periods.slice(0, _sn);

    // ── summary cards ──
    const worstP = periods[0];
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
        <div class="sc-val c-worst">${fmtPct(worstP.return_pct)}</div>
        <div class="sc-sub">${worstP.start_year}–${worstP.end_year} · $10K → ${fmt$(worstP.end_value)}</div>
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

    $('streaksSection').style.display = '';
  }

  // ── init ────────────────────────────────────────────

  async function init() {
    document.querySelectorAll('#nChips .ctrl-chip').forEach(b => {
      b.addEventListener('click', () => selectN(+b.dataset.val));
    });
    document.querySelectorAll('#streakChips .ctrl-chip').forEach(b => {
      b.addEventListener('click', () => selectSN(+b.dataset.val));
    });

    $('statusMsg').textContent = 'Loading…';
    $('statusMsg').style.display = '';

    try {
      const [extRes, streakRes] = await Promise.all([
        fetch('/api/sp500-extreme-years?n=20'),
        fetch('/api/sp500-bad-streaks?n=10'),
      ]);
      if (!extRes.ok) throw new Error(`HTTP ${extRes.status}`);
      if (!streakRes.ok) throw new Error(`HTTP ${streakRes.status}`);
      _data    = await extRes.json();
      _streaks = await streakRes.json();
      $('statusMsg').style.display = 'none';
      render();
      renderStreaks();
    } catch (e) {
      $('statusMsg').textContent = 'Failed to load data. Please try again later.';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
