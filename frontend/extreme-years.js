(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  let _data = null;
  let _n = 10;

  function fmt$(v) {
    return '$' + Math.round(v).toLocaleString();
  }

  function fmtPct(v) {
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  }

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

  async function init() {
    document.querySelectorAll('#nChips .ctrl-chip').forEach(b => {
      b.addEventListener('click', () => selectN(+b.dataset.val));
    });

    $('statusMsg').textContent = 'Loading…';
    $('statusMsg').style.display = '';

    try {
      const res = await fetch('/api/sp500-extreme-years?n=20');
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
