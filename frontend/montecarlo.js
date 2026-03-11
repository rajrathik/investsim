/* ============================================================
   montecarlo.js  v1
   Block-bootstrap Monte Carlo portfolio simulator
   1,000 simulations client-side — server only serves raw returns
   ============================================================ */

(function () {
  'use strict';

  const SIM_COUNT = 1000;

  /* ---- State ---- */
  let _returns = null;   // Float64Array of monthly nominal total returns
  let _bands   = null;   // computed percentile bands [{p10,p25,p50,p75,p90}, ...]
  let _params  = null;   // last-run params (for chart redraw)
  let _eventOn = false;

  /* ---- Chip selection ---- */
  window.selectChip = function (group, val) {
    document.querySelectorAll('#' + group + 'Chips .ctrl-chip').forEach(function (c) {
      c.classList.toggle('active', c.dataset.val === String(val));
    });
    if (group === 'cycle') {
      var descs = {
        1: 'Draws 1-year return blocks — each year is independent',
        3: 'Draws 3-year return blocks — preserves bull/bear market clustering',
        5: 'Draws 5-year return blocks — preserves full market cycle structure',
      };
      document.getElementById('cycleDesc').textContent = descs[val] || '';
    }
  };

  function getChip(group) {
    var active = document.querySelector('#' + group + 'Chips .ctrl-chip.active');
    return active ? parseInt(active.dataset.val, 10) : null;
  }

  /* ---- One-time event toggle ---- */
  window.toggleEvent = function () {
    _eventOn = !_eventOn;
    var panel  = document.getElementById('eventPanel');
    var toggle = document.getElementById('eventToggle');
    panel.classList.toggle('show', _eventOn);
    toggle.textContent = _eventOn
      ? '− Remove one-time cash event'
      : '＋ Add one-time cash event (bonus, inheritance, large withdrawal…)';
  };

  /* ---- Formatting helpers ---- */
  function fmtK(v) {
    if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    if (Math.abs(v) >= 1e3) return Math.round(v / 1e3) + 'K';
    return Math.round(v).toString();
  }
  function fmt$(v) { return '$' + fmtK(v); }
  function fmtFull(v) { return '$' + Math.round(v).toLocaleString(); }

  /* ---- Status helpers ---- */
  function showStatus(msg) {
    var el = document.getElementById('simStatus');
    el.textContent = msg;
    el.style.display = '';
  }
  function hideStatus() { document.getElementById('simStatus').style.display = 'none'; }
  function hideResults() { document.getElementById('results').style.display = 'none'; }

  /* ============================================================
     CORE: Block-bootstrap Monte Carlo
     returns   — Float64Array of monthly returns (chronological)
     params    — { initial, monthly, years, blockYears, lumpSum, lumpSumYear }
     ============================================================ */
  function monteCarlo(returns, params) {
    var initial      = params.initial;
    var monthly      = params.monthly;
    var years        = params.years;
    var blockYears   = params.blockYears;
    var lumpSum      = params.lumpSum || 0;
    var lumpSumYear  = params.lumpSumYear || 0;

    var months    = years * 12;
    var blockSize = blockYears * 12;
    var n         = returns.length;
    var maxStart  = n - blockSize;   // last valid block start

    // yearBalances[yearIdx] = array of SIM_COUNT final balances for that year
    var yearBalances = [];
    for (var i = 0; i < years; i++) {
      yearBalances.push(new Float64Array(SIM_COUNT));
    }

    var ruinCount = 0;

    for (var trial = 0; trial < SIM_COUNT; trial++) {
      var balance  = initial;
      var ruined   = false;
      var blockPos = blockSize;   // force new block on first month
      var blockStart = 0;

      for (var m = 0; m < months; m++) {
        // Refresh block when exhausted
        if (blockPos >= blockSize) {
          blockStart = Math.floor(Math.random() * (maxStart + 1));
          blockPos   = 0;
        }

        // One-time cash event: applied at the start of the specified year
        if (lumpSum !== 0 && lumpSumYear > 0 && m === (lumpSumYear - 1) * 12) {
          balance += lumpSum;
        }

        var ret = returns[blockStart + blockPos];
        blockPos++;

        // Monthly cash flow then compound
        balance = (balance + monthly) * (1.0 + ret);

        if (balance <= 0) {
          balance = 0;
          if (!ruined) { ruinCount++; ruined = true; }
        }

        // Year-end snapshot
        if ((m + 1) % 12 === 0) {
          yearBalances[(m + 1) / 12 - 1][trial] = balance;
        }
      }
    }

    // Compute percentiles for each year
    var bands = yearBalances.map(function (arr) {
      var sorted = Array.from(arr).sort(function (a, b) { return a - b; });
      function pct(p) { return sorted[Math.min(Math.floor(p / 100 * SIM_COUNT), SIM_COUNT - 1)]; }
      return { p10: pct(10), p25: pct(25), p50: pct(50), p75: pct(75), p90: pct(90) };
    });

    return { bands: bands, ruinCount: ruinCount };
  }

  /* ---- Build cumulative deposited array (for chart) ---- */
  function buildDeposits(params) {
    var arr = [];
    for (var y = 1; y <= params.years; y++) {
      var d = params.initial + params.monthly * 12 * y;
      if (params.lumpSum && params.lumpSumYear > 0 && y >= params.lumpSumYear) {
        d += params.lumpSum;
      }
      arr.push(d);
    }
    return arr;
  }

  /* ============================================================
     RENDER: Stat strip
     ============================================================ */
  function renderStats(bands, params, ruinCount) {
    var last    = bands[bands.length - 1];
    var pctRuin = Math.round(ruinCount / SIM_COUNT * 100);
    var pctAbove = (function () {
      // count how many trials ended above initial
      // approximate via percentile position of initial in last year's bands
      // simple: if p10 > initial → >90%, if p50 > initial → >50%, etc.
      if (last.p10  > params.initial) return '>90%';
      if (last.p25  > params.initial) return '>75%';
      if (last.p50  > params.initial) return '>50%';
      if (last.p75  > params.initial) return '>25%';
      if (last.p90  > params.initial) return '>10%';
      return '<10%';
    })();

    var html =
      '<div class="stat-card"><div class="stat-label">Median Outcome</div>' +
        '<div class="stat-value stat-accent">' + fmt$(last.p50) + '</div>' +
        '<div class="stat-sub">P50 after ' + params.years + ' years</div></div>' +

      '<div class="stat-card"><div class="stat-label">Best 10% Reach</div>' +
        '<div class="stat-value stat-accent">' + fmt$(last.p90) + '</div>' +
        '<div class="stat-sub">P90 outcome</div></div>' +

      '<div class="stat-card"><div class="stat-label">Worst 10% End At</div>' +
        '<div class="stat-value stat-warn">' + fmt$(last.p10) + '</div>' +
        '<div class="stat-sub">P10 outcome</div></div>';

    if (params.monthly < 0) {
      // Withdrawal mode — show survival rate
      var survPct = 100 - pctRuin;
      var survCls = survPct >= 80 ? 'stat-accent' : survPct >= 50 ? '' : 'stat-warn';
      html +=
        '<div class="stat-card"><div class="stat-label">Portfolio Survival</div>' +
          '<div class="stat-value ' + survCls + '">' + survPct + '%</div>' +
          '<div class="stat-sub">of simulations didn\'t run out</div></div>';
    } else {
      html +=
        '<div class="stat-card"><div class="stat-label">Beat Starting Value</div>' +
          '<div class="stat-value">' + pctAbove + '</div>' +
          '<div class="stat-sub">of simulations</div></div>';
    }

    document.getElementById('statStrip').innerHTML = html;
  }

  /* ============================================================
     RENDER: Info banner
     ============================================================ */
  function renderBanner(params) {
    var modeDesc = params.monthly >= 0
      ? 'Contributing <strong>' + fmtFull(params.monthly) + '/mo</strong>'
      : 'Withdrawing <strong>' + fmtFull(Math.abs(params.monthly)) + '/mo</strong>';
    var lumpDesc = (params.lumpSum && params.lumpSumYear)
      ? ' · One-time <strong>' + (params.lumpSum > 0 ? '+' : '') + fmtFull(params.lumpSum) + '</strong> at year ' + params.lumpSumYear
      : '';
    document.getElementById('infoBanner').innerHTML =
      '<strong>' + SIM_COUNT + '</strong> simulations · ' +
      'Starting <strong>' + fmtFull(params.initial) + '</strong> · ' +
      modeDesc +
      ' · <strong>' + params.years + '-year</strong> horizon' +
      ' · <strong>' + params.blockYears + '-year</strong> market blocks' +
      lumpDesc;
  }

  /* ============================================================
     RENDER: Percentile table
     ============================================================ */
  function renderTable(bands, deposits) {
    var html = '';
    bands.forEach(function (b, i) {
      var dep = (deposits && deposits[i] != null) ? fmt$(deposits[i]) : '—';
      html +=
        '<tr>' +
        '<td>Year ' + (i + 1) + '</td>' +
        '<td>' + dep + '</td>' +
        '<td class="pct-worst">' + fmt$(b.p10) + '</td>' +
        '<td>' + fmt$(b.p25) + '</td>' +
        '<td class="pct-median">' + fmt$(b.p50) + '</td>' +
        '<td>' + fmt$(b.p75) + '</td>' +
        '<td class="pct-best">' + fmt$(b.p90) + '</td>' +
        '</tr>';
    });
    document.getElementById('pctTableBody').innerHTML = html;
  }

  /* ============================================================
     RENDER: Fan chart
     ============================================================ */
  var _chartBands   = null;
  var _chartDeposits = null;
  var _chartParams  = null;

  function renderChart(bands, deposits, params) {
    _chartBands    = bands;
    _chartDeposits = deposits;
    _chartParams   = params;
    drawChart();
    window.addEventListener('themechange', drawChart);
    window.addEventListener('resize', drawChart);
  }

  function drawChart() {
    var canvas = document.getElementById('mcCanvas');
    if (!canvas || !_chartBands || !_chartBands.length) return;

    var dpr = window.devicePixelRatio || 1;
    var W   = canvas.offsetWidth || canvas.parentElement.clientWidth || 700;
    var H   = 300;
    canvas.width        = W * dpr;
    canvas.height       = H * dpr;
    canvas.style.height = H + 'px';

    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    var isDark  = document.documentElement.dataset.theme !== 'light';
    var accent  = '#10b981';
    var text3   = getComputedStyle(document.documentElement).getPropertyValue('--text3').trim() || '#64748b';
    var gridCol = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.07)';

    var pad = { top: 12, right: 20, bottom: 36, left: 76 };
    var cW  = W - pad.left - pad.right;
    var cH  = H - pad.top  - pad.bottom;
    var n   = _chartBands.length;

    // Y scale — cap at P90 final to avoid crazy outliers dominating
    var maxVal = Math.max.apply(null, _chartBands.map(function (b) { return b.p90; }));
    if (_chartDeposits && _chartParams.monthly >= 0) {
      maxVal = Math.max(maxVal, _chartDeposits[_chartDeposits.length - 1]);
    }
    maxVal = maxVal || 1;

    var xOf = function (i) { return pad.left + (i / (n - 1 || 1)) * cW; };
    var yOf = function (v)  { return pad.top  + cH - Math.max(0, v / maxVal) * cH; };

    // Grid lines + Y labels
    ctx.strokeStyle = gridCol;
    ctx.lineWidth   = 1;
    for (var t = 0; t <= 4; t++) {
      var yg  = pad.top + (t / 4) * cH;
      var val = maxVal * (1 - t / 4);
      ctx.beginPath(); ctx.moveTo(pad.left, yg); ctx.lineTo(pad.left + cW, yg); ctx.stroke();
      ctx.fillStyle = text3;
      ctx.font      = "10px 'JetBrains Mono', monospace";
      ctx.textAlign = 'right';
      ctx.fillText('$' + fmtK(val), pad.left - 6, yg + 3.5);
    }

    // Helper: fill a band between two percentile arrays
    function fillBand(loKey, hiKey, color) {
      ctx.beginPath();
      _chartBands.forEach(function (b, i) { i === 0 ? ctx.moveTo(xOf(i), yOf(b[hiKey])) : ctx.lineTo(xOf(i), yOf(b[hiKey])); });
      for (var i = n - 1; i >= 0; i--) { ctx.lineTo(xOf(i), yOf(_chartBands[i][loKey])); }
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    }

    // P10-P90 outer band (light)
    fillBand('p10', 'p90', isDark ? 'rgba(16,185,129,0.10)' : 'rgba(16,185,129,0.08)');

    // P25-P75 inner band (stronger)
    fillBand('p25', 'p75', isDark ? 'rgba(16,185,129,0.28)' : 'rgba(16,185,129,0.20)');

    // Total deposited dashed line (only in accumulation mode)
    if (_chartDeposits && _chartParams.monthly >= 0) {
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = text3;
      ctx.lineWidth   = 1.5;
      ctx.beginPath();
      _chartDeposits.forEach(function (d, i) {
        var x = xOf(i), yy = yOf(d);
        i === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
      });
      ctx.stroke();
      ctx.restore();
    }

    // P50 median line
    ctx.strokeStyle = accent;
    ctx.lineWidth   = 2.5;
    ctx.lineJoin    = 'round';
    ctx.setLineDash([]);
    ctx.beginPath();
    _chartBands.forEach(function (b, i) {
      var x = xOf(i), yy = yOf(b.p50);
      i === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
    });
    ctx.stroke();

    // X-axis year labels
    ctx.fillStyle = text3;
    ctx.font      = "10px 'JetBrains Mono', monospace";
    ctx.textAlign = 'center';
    var step = Math.max(1, Math.round(n / 8));
    _chartBands.forEach(function (_, i) {
      if (i % step === 0 || i === n - 1) {
        ctx.fillText('Yr ' + (i + 1), xOf(i), H - pad.bottom + 16);
      }
    });

    canvas._layout = { pad: pad, cW: cW, cH: cH, xOf: xOf, yOf: yOf };
  }

  // Chart hover tooltip
  document.getElementById('mcCanvas').addEventListener('mousemove', function (e) {
    if (!_chartBands || !this._layout) return;
    var rect = this.getBoundingClientRect();
    var mx   = e.clientX - rect.left;
    var layout = this._layout;
    var idx = Math.round(((mx - layout.pad.left) / layout.cW) * (_chartBands.length - 1));
    if (idx < 0 || idx >= _chartBands.length) { hideTip(); return; }
    var b   = _chartBands[idx];
    var tip = document.getElementById('chartTip');
    tip.innerHTML =
      '<div class="ct-year">Year ' + (idx + 1) + '</div>' +
      '<div class="ct-row"><span class="ct-lbl">Best 10%</span><span class="ct-val" style="color:var(--accent)">' + fmtFull(b.p90) + '</span></div>' +
      '<div class="ct-row"><span class="ct-lbl">75th Pct</span><span class="ct-val">' + fmtFull(b.p75) + '</span></div>' +
      '<div class="ct-row"><span class="ct-lbl">Median</span><span class="ct-val" style="color:var(--accent)">' + fmtFull(b.p50) + '</span></div>' +
      '<div class="ct-row"><span class="ct-lbl">25th Pct</span><span class="ct-val">' + fmtFull(b.p25) + '</span></div>' +
      '<div class="ct-row"><span class="ct-lbl">Worst 10%</span><span class="ct-val" style="color:var(--red)">' + fmtFull(b.p10) + '</span></div>';
    tip.style.left = (e.clientX + 16) + 'px';
    tip.style.top  = (e.clientY - 60) + 'px';
    tip.classList.add('show');
  });
  document.getElementById('mcCanvas').addEventListener('mouseleave', hideTip);

  function hideTip() {
    var t = document.getElementById('chartTip');
    if (t) t.classList.remove('show');
  }

  /* ============================================================
     MAIN: Run simulation
     ============================================================ */
  window.runMC = async function () {
    var initial   = parseFloat(document.getElementById('ctrlInitial').value) || 0;
    var monthly   = parseFloat(document.getElementById('ctrlMonthly').value) || 0;
    var years     = getChip('horizon') || 20;
    var blockYears = getChip('cycle')  || 3;
    var lumpSum   = _eventOn ? (parseFloat(document.getElementById('ctrlLumpSum').value) || 0) : 0;
    var lumpSumYear = _eventOn ? (parseInt(document.getElementById('ctrlLumpYear').value, 10) || 0) : 0;

    if (lumpSumYear > years) {
      alert('One-time event year (' + lumpSumYear + ') is beyond the horizon (' + years + ' years).');
      return;
    }

    var params = { initial: initial, monthly: monthly, years: years, blockYears: blockYears, lumpSum: lumpSum, lumpSumYear: lumpSumYear };

    var btn = document.getElementById('btnRun');
    btn.disabled = true;
    btn.textContent = 'Running…';
    hideResults();
    showStatus('Running ' + SIM_COUNT + ' simulations…');

    // Load returns once, cache them
    if (!_returns) {
      try {
        showStatus('Loading return data…');
        var resp = await fetch('/api/shiller-monthly-returns');
        if (!resp.ok) throw new Error('API error ' + resp.status);
        var arr = await resp.json();
        _returns = new Float64Array(arr);
      } catch (e) {
        showStatus('Error loading data: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Run Simulation';
        return;
      }
    }

    showStatus('Running ' + SIM_COUNT + ' simulations…');

    // Yield to browser so "Running…" renders before we block the thread
    await new Promise(function (resolve) { setTimeout(resolve, 10); });

    var result = monteCarlo(_returns, params);
    _bands  = result.bands;
    _params = params;

    var deposits = buildDeposits(params);

    // Show deposit legend only in accumulation mode
    document.getElementById('depositLegend').style.display = monthly >= 0 ? '' : 'none';

    hideStatus();
    document.getElementById('results').style.display = '';

    renderBanner(params);
    renderStats(_bands, params, result.ruinCount);
    renderTable(_bands, deposits);
    requestAnimationFrame(function () { renderChart(_bands, deposits, params); });

    btn.disabled = false;
    btn.textContent = 'Run Simulation';
  };

  /* ---- Init: run default on page load ---- */
  window.addEventListener('DOMContentLoaded', function () {
    runMC();
  });

  /* Pageview tracking */
  if (typeof trackPageView === 'function') trackPageView('montecarlo');

})();
