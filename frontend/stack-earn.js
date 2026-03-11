/* ==========================================
   Stack & Earn — Tiered Savings Calculator
   ========================================== */

(function () {
  'use strict';

  /* ---- State ---- */
  var savingsTiers = [];
  var goalTiers = [];
  var savingsPeriodYears = 5;
  var goalPeriodYears = 5;

  /* ---- Utilities ---- */
  function fmt$(n) {
    if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    return '$' + n.toFixed(2);
  }
  function fmt$exact(n) {
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  /* ---- Tab switching ---- */
  window.switchTab = function (tab) {
    document.getElementById('tabSavings').style.display = tab === 'savings' ? '' : 'none';
    document.getElementById('tabGoal').style.display = tab === 'goal' ? '' : 'none';
    document.getElementById('tabSavingsBtn').classList.toggle('active', tab === 'savings');
    document.getElementById('tabGoalBtn').classList.toggle('active', tab === 'goal');
  };

  /* ---- Period chip selection ---- */
  window.selectPeriod = function (which, years) {
    var chips = document.querySelectorAll('#' + which + 'PeriodChips .period-chip');
    chips.forEach(function (c) { c.classList.remove('active'); });
    var target = document.querySelector('#' + which + 'PeriodChips [data-years="' + years + '"]');
    if (target) target.classList.add('active');

    var customWrap = document.getElementById(which + 'CustomWrap');
    if (years === 'custom') {
      customWrap.classList.add('show');
      if (which === 'savings') savingsPeriodYears = null;
      else goalPeriodYears = null;
    } else {
      customWrap.classList.remove('show');
      if (which === 'savings') savingsPeriodYears = years;
      else goalPeriodYears = years;
    }
  };

  function getYears(which) {
    var chips = document.querySelectorAll('#' + which + 'PeriodChips .period-chip.active');
    if (!chips.length) return 5;
    var val = chips[0].getAttribute('data-years');
    if (val === 'custom') {
      var n = parseInt(document.getElementById(which + 'CustomYears').value, 10);
      return (n > 0 && n <= 50) ? n : 5;
    }
    return parseInt(val, 10);
  }

  /* ---- Core simulation ---- */
  function simulate(monthlyC, years, tiers) {
    /* tiers sorted by tier_number */
    var t = tiers;
    /* tier balance thresholds — Infinity when no upper bound */
    var lim1 = t[0] ? (t[0].max_amount != null ? t[0].max_amount : Infinity) : 1000;
    var lim2 = t[1] ? (t[1].max_amount != null ? t[1].max_amount : Infinity) : 10000;
    var r1 = t[0] ? t[0].annual_rate / 12 : 0;
    var r2 = t[1] ? t[1].annual_rate / 12 : 0;
    var r3 = t[2] ? t[2].annual_rate / 12 : 0;

    var balance = 0;
    var totalDeposited = 0;
    var yearRows = [];
    var months = years * 12;
    var yearT1Earn = 0, yearT2Earn = 0, yearT3Earn = 0;
    var yearDeposited = 0;

    for (var m = 1; m <= months; m++) {
      /* Deposit first */
      balance += monthlyC;
      totalDeposited += monthlyC;
      yearDeposited += monthlyC;

      /* Split running balance across tier thresholds, apply each rate */
      var b1 = Math.min(balance, lim1);
      var b2 = Math.max(0, Math.min(balance, lim2) - lim1);
      var b3 = Math.max(0, balance - lim2);

      var i1 = b1 * r1;
      var i2 = b2 * r2;
      var i3 = b3 * r3;

      balance += i1 + i2 + i3;
      yearT1Earn += i1;
      yearT2Earn += i2;
      yearT3Earn += i3;

      /* Year-end snapshot */
      if (m % 12 === 0) {
        yearRows.push({
          year: m / 12,
          deposited: yearDeposited,
          t1Earned: yearT1Earn,
          t2Earned: yearT2Earn,
          t3Earned: yearT3Earn,
          balance: balance,
          cumDeposited: totalDeposited,
        });
        yearT1Earn = 0; yearT2Earn = 0; yearT3Earn = 0;
        yearDeposited = 0;
      }
    }

    return {
      total: balance,
      totalDeposited: totalDeposited,
      interestEarned: balance - totalDeposited,
      yearRows: yearRows,
    };
  }

  /* ---- Render year table ---- */
  function renderTable(tbodyId, rows) {
    var tbody = document.getElementById(tbodyId);
    tbody.innerHTML = '';
    var showT2 = rows.some(function (r) { return r.t2Earned > 0; });
    var showT3 = rows.some(function (r) { return r.t3Earned > 0; });

    /* Sync thead columns */
    var thead = tbody.closest('table').querySelector('thead tr');
    if (thead) {
      thead.innerHTML =
        '<th>Year</th><th>Deposited</th><th>T1 Earned</th>' +
        (showT2 ? '<th>T2 Earned</th>' : '') +
        (showT3 ? '<th>T3 Earned</th>' : '') +
        '<th>Balance</th>';
    }

    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>Year ' + r.year + '</td>' +
        '<td>' + fmt$(r.cumDeposited) + '</td>' +
        '<td class="earn-val">+' + fmt$exact(r.t1Earned) + '</td>' +
        (showT2 ? '<td class="earn-val">+' + fmt$exact(r.t2Earned) + '</td>' : '') +
        (showT3 ? '<td class="earn-val">+' + fmt$exact(r.t3Earned) + '</td>' : '') +
        '<td><strong>' + fmt$(r.balance) + '</strong></td>';
      tbody.appendChild(tr);
    });
  }

  /* ---- Savings calculator ---- */
  window.runSavings = function () {
    var monthlyC = parseFloat(document.getElementById('savingsAmount').value);
    if (!monthlyC || monthlyC <= 0) { alert('Enter a valid monthly amount.'); return; }
    var years = getYears('savings');
    if (!savingsTiers.length) { alert('Tier data not loaded yet. Please try again.'); return; }

    var result = simulate(monthlyC, years, savingsTiers);

    /* Hero card */
    var hero = document.getElementById('savingsHero');
    hero.innerHTML =
      '<div class="result-label">Ending Balance</div>' +
      '<div class="result-amount">' + fmt$(result.total) + '</div>' +
      '<div class="result-subtitle">saving ' + fmt$exact(monthlyC) + '/mo for ' + years + ' year' + (years !== 1 ? 's' : '') + '</div>' +
      '<div class="result-pills">' +
        '<div class="result-pill"><span>' + fmt$(result.totalDeposited) + '</span> deposited</div>' +
        '<div class="result-pill">+<span>' + fmt$(result.interestEarned) + '</span> interest earned</div>' +
        '<div class="result-pill"><span>' + ((result.interestEarned / result.totalDeposited) * 100).toFixed(1) + '%</span> return on deposits</div>' +
      '</div>';

    renderTable('savingsTableBody', result.yearRows);
    document.getElementById('savingsResults').style.display = '';
  };

  /* ---- Goal calculator (binary search) ---- */
  window.runGoal = function () {
    var target = parseFloat(document.getElementById('goalAmount').value);
    if (!target || target <= 0) { alert('Enter a valid target amount.'); return; }
    var years = getYears('goal');
    if (!goalTiers.length) { alert('Tier data not loaded yet. Please try again.'); return; }

    /* Binary search for monthly contribution */
    var lo = 0, hi = target; /* hi is always enough since rate > 0 and hi*months > target */
    var found = lo;
    for (var i = 0; i < 60; i++) {
      var mid = (lo + hi) / 2;
      var res = simulate(mid, years, goalTiers);
      if (res.total < target) {
        lo = mid;
      } else {
        hi = mid;
        found = mid;
      }
    }

    /* Round up to nearest cent so we always meet or exceed target */
    found = Math.ceil(found * 100) / 100;
    var finalResult = simulate(found, years, goalTiers);

    /* Hero card */
    var hero = document.getElementById('goalHero');
    hero.innerHTML =
      '<div class="result-label">Required Monthly Contribution</div>' +
      '<div class="result-amount">' + fmt$exact(found) + '/mo</div>' +
      '<div class="result-subtitle">to reach ' + fmt$(target) + ' in ' + years + ' year' + (years !== 1 ? 's' : '') + '</div>' +
      '<div class="result-pills">' +
        '<div class="result-pill"><span>' + fmt$(finalResult.totalDeposited) + '</span> total deposited</div>' +
        '<div class="result-pill">+<span>' + fmt$(finalResult.interestEarned) + '</span> interest earned</div>' +
        '<div class="result-pill">Ending balance <span>' + fmt$(finalResult.total) + '</span></div>' +
      '</div>';

    renderTable('goalTableBody', finalResult.yearRows);
    document.getElementById('goalResults').style.display = '';
  };

  /* ---- Render tier rates table ---- */
  function renderTiers(savTiers) {
    var productName = (savTiers[0] && savTiers[0].product_type) ? savTiers[0].product_type : 'PurposeSaving';
    var anyRateVisible = savTiers.some(function (t) { return (t.display_rate !== 0); });

    var html = '<div style="font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--text3);margin-bottom:.5rem">' +
      productName + '</div>';
    html += '<table class="tiers-table"><thead><tr>' +
      '<th>Tier</th><th>Monthly Range</th>' +
      (anyRateVisible ? '<th style="text-align:right">Annual Rate</th>' : '') +
      '</tr></thead><tbody>';

    savTiers.forEach(function (t) {
      var showRate = (t.display_rate !== 0);
      var range;
      if (t.max_amount === null || t.max_amount === undefined) {
        range = fmt$(t.min_amount) + '+/mo';
      } else if (t.display_upto === 1) {
        range = 'Upto ' + fmt$(t.max_amount);
      } else {
        range = fmt$(t.min_amount === 0 ? 1 : t.min_amount) + ' – ' + fmt$(t.max_amount) + '/mo';
      }
      html += '<tr>' +
        '<td><span class="tier-badge">T' + t.tier_number + '</span></td>' +
        '<td>' + range + '</td>' +
        (anyRateVisible ? '<td>' + (showRate ? '<span class="tier-rate">' + (t.annual_rate * 100).toFixed(2) + '%</span>' : '') + '</td>' : '') +
        '</tr>';
    });
    html += '</tbody></table>';
    document.getElementById('tiersContent').innerHTML = html;
  }

  /* ---- Load tiers from API ---- */
  async function loadTiers() {
    try {
      var savRes = await fetch('/api/stack-earn/savings-tiers');
      var goalRes = await fetch('/api/stack-earn/goal-tiers');
      if (!savRes.ok || !goalRes.ok) throw new Error('API error');
      savingsTiers = await savRes.json();
      goalTiers = await goalRes.json();
      renderTiers(savingsTiers);
    } catch (e) {
      document.getElementById('tiersContent').innerHTML =
        '<div class="status-msg" style="color:var(--red)">Could not load tier rates.</div>';
    }
  }

  /* ---- Boot ---- */
  loadTiers();

  /* Pageview tracking */
  if (typeof trackPageView === 'function') trackPageView('stack-earn');

})();
