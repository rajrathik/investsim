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
      { label: 'Market Drawdown Analysis', href: '/drawdown.html' },
    ],
  },
  {
    /* Everything here is pulled from current market data rather than history,
       which is the one axis the other categories do not cover. One item today;
       the category exists so the next ones have somewhere to go. */
    label: 'Browse',
    items: [
      { label: 'ETF Directory', href: '/etf-directory.html' },
    ],
  },
  {
    label: 'Learn',
    /* atEnd: rendered after the tool categories rather than in sequence, so
       they stay together and Learn closes the bar. */
    atEnd: true,
    items: [
      { label: 'Learn from Market History', href: '/learn.html' },
      { label: 'How the Simulator Works', href: '/simulator-guide.html' },
      { label: 'About These Tools', href: '/about.html' },
    ],
  },
];

/* Personal items. These live under the signed-in user's own name rather than
   in the main bar: they are "your things", not a category of tool. Admin and
   Sign out are appended to this menu automatically. */
var USER_MENU = [
  { label: 'Saved Simulations', href: '/saved-simulations.html' },
];

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

  function renderLinks(items) {
    return items.map(function (it) {
      return '<a href="' + it.href + '"' + (isActive(it.href) ? ' class="active"' : '') + '>' + esc(it.label) + '</a>';
    }).join('');
  }

  function renderGroup(group, i) {
    return '<div class="site-nav-group" data-i="' + i + '">' +
      '<button type="button" class="site-nav-top">' + esc(group.label) + ' <span class="chev">&#9662;</span></button>' +
      '<div class="site-nav-drop">' + renderLinks(group.items) + '</div></div>';
  }

  /* Clicking a category opens it and closes any other. Used for the main bar
     and again for the user menu, which is re-rendered on every auth change. */
  function wireGroups(scope) {
    scope.querySelectorAll('.site-nav-group').forEach(function (g) {
      var btn = g.querySelector('.site-nav-top');
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var wasOpen = g.classList.contains('open');
        document.querySelectorAll('.site-nav-group.open').forEach(function (o) { o.classList.remove('open'); });
        if (!wasOpen) g.classList.add('open');
      });
    });
  }

  function renderMenu() {
    var html = '';
    /* Tool categories first, then anything marked atEnd. */
    SITE_NAV.forEach(function (group, i) {
      if (!group.atEnd) html += renderGroup(group, i);
    });
    SITE_NAV.forEach(function (group, i) {
      if (group.atEnd) html += renderGroup(group, i);
    });
    return html;
  }

  function mount() {
    var root = document.getElementById('siteNavRoot');
    if (!root) return;
    root.className = 'header site-nav';
    /* The brand is the parent company, so it leaves for the parent site.
       "Home" below is this site's own home. Previously both went to "/",
       which made the brand name look like a dead label. */
    root.innerHTML =
      '<a href="https://claritycapitaltools.com/" class="site-nav-brand">Clarity Capital Tools</a>' +
      '<nav class="site-nav-menu" id="siteNavMenu">' +
      '<a href="/" class="site-nav-top site-nav-item' + (isActive('/') ? ' active' : '') + '">Home</a>' +
      renderMenu() + '</nav>' +
      /* Everything personal -- saved work, Admin, Sign out -- collapses into
         one menu under the user's own name. About is not repeated here; it
         already lives under Learn. */
      '<div class="site-nav-user" id="siteNavUser"></div>' +
      '<button type="button" class="site-nav-toggle" id="siteNavToggle" aria-label="Menu">&#9776;</button>';

    /* Mobile hamburger */
    var toggle = document.getElementById('siteNavToggle');
    var menu = document.getElementById('siteNavMenu');
    toggle.addEventListener('click', function () {
      menu.classList.toggle('show');
    });

    /* Touch-friendly category open/close (hover still works via CSS on desktop) */
    wireGroups(root);
    document.addEventListener('click', function () {
      document.querySelectorAll('.site-nav-group.open').forEach(function (o) { o.classList.remove('open'); });
    });

    renderUser();
    window.addEventListener('pubauth', renderUser);
  }

  function firstName(user) {
    var raw = (user.name || user.email || '').trim();
    if (raw.indexOf('@') > -1 && !user.name) raw = raw.split('@')[0];
    return raw.split(/[\s.]+/)[0] || 'Account';
  }

  function renderUser() {
    var slot = document.getElementById('siteNavUser');
    if (!slot) return;

    if (!(window._pubIsSignedIn && window._pubIsSignedIn())) {
      localStorage.removeItem('_admin_hint');
      slot.innerHTML = '<a href="javascript:void(0)" class="site-nav-top site-nav-signin" id="siteNavSignIn">Sign In</a>';
      slot.querySelector('#siteNavSignIn').addEventListener('click', function () {
        if (window._pubSignIn) window._pubSignIn();
      });
      return;
    }

    var user = {};
    try { user = JSON.parse(localStorage.getItem('pub_auth_user')) || {}; } catch (e) {}
    var isAdmin = localStorage.getItem('_admin_hint') === '1';

    slot.innerHTML =
      '<div class="site-nav-group site-nav-usermenu">' +
        '<button type="button" class="site-nav-top">' + esc(firstName(user)) + ' <span class="chev">&#9662;</span></button>' +
        '<div class="site-nav-drop">' +
          renderLinks(USER_MENU) +
          (isAdmin ? '<div class="site-nav-sep"></div><a href="/admin.html"' + (isActive('/admin.html') ? ' class="active"' : '') + '>Admin</a>' : '') +
          '<div class="site-nav-sep"></div>' +
          '<a href="javascript:void(0)" id="siteNavSignOut">Sign out</a>' +
        '</div>' +
      '</div>';

    wireGroups(slot);
    slot.querySelector('#siteNavSignOut').addEventListener('click', function () {
      if (window._pubSignOut) window._pubSignOut();
    });

    /* Admin is invisible until verified server-side; the localStorage hint only
       avoids a round trip on later page loads. */
    if (!isAdmin && window._pubAuthFetch) {
      window._pubAuthFetch('/api/admin/verify').then(function (r) {
        if (r && r.ok) {
          localStorage.setItem('_admin_hint', '1');
          renderUser();
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
