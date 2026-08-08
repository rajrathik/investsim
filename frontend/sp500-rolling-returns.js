(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  let _rows = [];      // full dataset, ascending by year
  let _yearStart = null;
  let _yearEnd = null;

  function fmtPct(v) {
    if (v === null || v === undefined) return '<span class="c-na">—</span>';
    const cls = v >= 0 ? 'c-pos' : 'c-neg';
    const sign = v >= 0 ? '+' : '';
    return `<span class="${cls}">${sign}${v.toFixed(2)}%</span>`;
  }

  function populateYearSelectors() {
    const startSel = $('yearStart'), endSel = $('yearEnd');
    const years = _rows.map(r => r.year); // ascending
    startSel.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
    endSel.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
    startSel.value = years[0];
    endSel.value = years[years.length - 1];
    _yearStart = +startSel.value;
    _yearEnd = +endSel.value;

    startSel.addEventListener('change', onYearChange);
    endSel.addEventListener('change', onYearChange);
  }

  function onYearChange() {
    _yearStart = +$('yearStart').value;
    _yearEnd = +$('yearEnd').value;
    if (_yearStart > _yearEnd) {
      const tmp = _yearStart;
      _yearStart = _yearEnd;
      _yearEnd = tmp;
      $('yearStart').value = _yearStart;
      $('yearEnd').value = _yearEnd;
    }
    render();
  }

  function render() {
    const filtered = _rows
      .filter(r => r.year >= _yearStart && r.year <= _yearEnd)
      .slice()
      .sort((a, b) => b.year - a.year); // newest first

    $('rrBody').innerHTML = filtered.map(r => `
      <tr>
        <td>${r.year}</td>
        <td>${fmtPct(r.r1)}</td>
        <td>${fmtPct(r.r3)}</td>
        <td>${fmtPct(r.r5)}</td>
        <td>${fmtPct(r.r7)}</td>
        <td>${fmtPct(r.r10)}</td>
      </tr>
    `).join('');

    $('rowCount').textContent = `${filtered.length} year${filtered.length === 1 ? '' : 's'}`;
    $('rrPanel').style.display = '';
  }

  async function init() {
    $('statusMsg').style.display = '';

    try {
      const res = await fetch('/api/damodaran-forward-returns');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      _rows = data.years || [];
      if (!_rows.length) throw new Error('No data returned');

      $('statusMsg').style.display = 'none';
      populateYearSelectors();
      render();
    } catch (e) {
      $('statusMsg').textContent = 'Failed to load data. Please try again later.';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
