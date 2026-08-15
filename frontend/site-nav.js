/* ==========================================
   SITE NAV — top nav bar + category submenus, shared across every page.

   SINGLE SOURCE OF TRUTH FOR THE MENU: edit the SITE_NAV array below to
   reorder categories, reorder tools within a category, move a tool from
   one category to another, rename a label, or add/remove a page. Nothing
   else in the codebase needs to change -- every page picks this up
   automatically on next load.
   ========================================== */

/* Page names here are the canonical ones -- every page <title>, <h1>, and
   any link elsewhere should match these exactly. Names used to drift
   between the directory and the pages themselves (Sector Returns Quilt vs
   Sector Performance, $10K Growth Chart vs $10,000 Growth). */
var SITE_NAV = [
  {
    label: 'Portfolio',
    items: [
      { label: 'Portfolio Simulator', href: '/portfolio-simulator.html' },
      { label: 'S&P 500 Historical Simulator', href: '/sp500-simulate.html' },
      { label: 'Monte Carlo Simulator', href: '/montecarlo.html' },
    ],
  },
  {
    label: 'Market History',
    items: [
      { label: 'S&P 500 History', href: '/sp500-history.html' },
      { label: 'Rolling Returns', href: '/sp500-rolling-returns.html' },
      { label: 'Best & Worst Years', href: '/extreme-years.html' },
      { label: 'Best & Worst Months', href: '/extreme-months.html' },
      { label: 'Market Downturns & Recovery', href: '/bad-streaks.html' },
    ],
  },
  {
    label: 'Sectors',
    items: [
      { label: 'Sector Performance', href: '/sector-performance.html' },
      { label: 'Sector Rotation', href: '/sector-rotation.html' },
      { label: 'Sector Correlation', href: '/correlation.html' },
      { label: 'Dividend Growth', href: '/dividend-growth.html' },
      { label: '$10,000 Growth', href: '/growth-chart.html' },
      { label: 'Risk vs Return', href: '/risk-return.html' },
      { label: 'Drawdown Analysis', href: '/drawdown.html' },
      { label: 'ETF Directory (classic table)', href: '/etf-directory.html' },
    ],
  },
  {
    label: 'Learn',
    items: [
      { label: 'How the Simulator Works', href: '/simulator-guide.html' },
    ],
  },
  {
    label: 'Member',
    memberOnly: true,
    items: [
      { label: 'Saved Simulations', href: '/saved-simulations.html' },
      { label: 'Stack & Earn', href: '/stack-earn.html' },
    ],
  },
];

var SITE_HOME = { label: 'Browse ETFs', href: '/#etf-directory' };

(function () {
  'use strict';

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function isActive(href) {
    var path = location.pathname.replace(/\/index\.html$/, '/');
    if (href === '/') return path === '/';
    return path === href;
  }

  function renderMenu() {
    var html = '';
    SITE_NAV.forEach(function (group, i) {
      html += '<div class="site-nav-group' + (group.memberOnly ? ' site-nav-member-only' : '') + '" data-i="' + i + '">' +
        '<button type="button" class="site-nav-top">' + esc(group.label) + ' <span class="chev">&#9662;</span></button>' +
        '<div class="site-nav-drop">' +
        group.items.map(function (it) {
          return '<a href="' + it.href + '"' + (isActive(it.href) ? ' class="active"' : '') + '>' + esc(it.label) + '</a>';
        }).join('') +
        '</div></div>';
    });
    html += '<a href="' + SITE_HOME.href + '" class="site-nav-top site-nav-home">' + esc(SITE_HOME.label) + '</a>';
    html += '<a href="/admin.html" class="site-nav-top site-nav-admin" id="siteNavAdmin" style="display:none">Admin</a>';
    return html;
  }

  function mount() {
    var root = document.getElementById('siteNavRoot');
    if (!root) return;
    root.className = 'header site-nav';
    root.innerHTML =
      '<a href="/" class="site-nav-brand">Clarity Capital Tools</a>' +
      '<nav class="site-nav-menu" id="siteNavMenu">' + renderMenu() + '</nav>' +
      '<a href="https://claritycapitaltools.com/about.html" class="site-nav-top site-nav-about">About</a>' +
      '<button type="button" class="site-nav-toggle" id="siteNavToggle" aria-label="Menu">&#9776;</button>';

    /* Mobile hamburger */
    var toggle = document.getElementById('siteNavToggle');
    var menu = document.getElementById('siteNavMenu');
    toggle.addEventListener('click', function () {
      menu.classList.toggle('show');
    });

    /* Touch-friendly category open/close (hover still works via CSS on desktop) */
    root.querySelectorAll('.site-nav-group').forEach(function (g) {
      var btn = g.querySelector('.site-nav-top');
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var wasOpen = g.classList.contains('open');
        root.querySelectorAll('.site-nav-group.open').forEach(function (o) { o.classList.remove('open'); });
        if (!wasOpen) g.classList.add('open');
      });
    });
    document.addEventListener('click', function () {
      root.querySelectorAll('.site-nav-group.open').forEach(function (o) { o.classList.remove('open'); });
    });

    refreshMemberAndAdmin();
    window.addEventListener('pubauth', refreshMemberAndAdmin);
  }

  function refreshMemberAndAdmin() {
    var signedIn = !!(window._pubIsSignedIn && window._pubIsSignedIn());
    document.querySelectorAll('.site-nav-member-only').forEach(function (el) {
      el.style.display = signedIn ? '' : 'none';
    });

    var adminLink = document.getElementById('siteNavAdmin');
    if (!adminLink) return;
    if (!signedIn) {
      adminLink.style.display = 'none';
      localStorage.removeItem('_admin_hint');
      return;
    }
    if (localStorage.getItem('_admin_hint') === '1') {
      adminLink.style.display = '';
      return;
    }
    if (window._pubAuthFetch) {
      window._pubAuthFetch('/api/admin/verify').then(function (r) {
        if (r.ok) {
          localStorage.setItem('_admin_hint', '1');
          adminLink.style.display = '';
        }
      }).catch(function () {});
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
