/* ==========================================
   SHARED AUTH — optional Auth0 sign-in for public pages
   Loaded AFTER shared-analytics.css.  Skipped on admin.html
   (admin has its own isolated auth flow).

   - Uses localStorage to cache user info across pages
   - Injects a welcome bar below the header when signed in
   - Injects a "Sign In" link in the header when signed out
   ========================================== */

(function () {
  'use strict';

  /* Skip on admin page — admin has its own auth */
  if (location.pathname.includes('admin')) return;

  var AUTH_CACHE_KEY = 'pub_auth_user';   // {email, name, sub}
  var auth0Client = null;
  var _user = null;

  /* ---- cached user from localStorage (instant, no network) ---- */
  function getCachedUser() {
    try { return JSON.parse(localStorage.getItem(AUTH_CACHE_KEY)); } catch (e) { return null; }
  }
  function setCachedUser(u) {
    localStorage.setItem(AUTH_CACHE_KEY, JSON.stringify(u));
  }
  function clearCachedUser() {
    localStorage.removeItem(AUTH_CACHE_KEY);
  }

  /* ---- UI injection ---- */

  function injectSignInLink() {
    /* Add a small "Sign In" link to the header nav area */
    var header = document.querySelector('.header') || document.querySelector('.hero');
    if (!header) return;
    var link = document.createElement('a');
    link.href = 'javascript:void(0)';
    link.id = 'pubSignInLink';
    link.textContent = 'Sign In';
    link.className = 'pub-signin-link';
    link.onclick = function () { doPublicLogin(); };
    header.appendChild(link);
  }

  function injectWelcomeBar(user) {
    if (!user || !user.email) return;
    /* Remove sign-in link if present */
    var sl = document.getElementById('pubSignInLink');
    if (sl) sl.remove();

    /* Don't duplicate */
    if (document.getElementById('pubWelcomeBar')) return;

    var name = user.name || user.email.split('@')[0];
    var bar = document.createElement('div');
    bar.id = 'pubWelcomeBar';
    bar.className = 'pub-welcome-bar';
    bar.innerHTML =
      '<span class="pub-welcome-text">Welcome, <strong>' + escHtml(name) + '</strong></span>' +
      '<button class="pub-signout-btn" onclick="window._pubSignOut()">Sign Out</button>';

    /* Insert right after .header or at top of body */
    var header = document.querySelector('.header') || document.querySelector('.hero');
    if (header && header.nextSibling) {
      header.parentNode.insertBefore(bar, header.nextSibling);
    } else {
      document.body.prepend(bar);
    }
  }

  function removeWelcomeBar() {
    var bar = document.getElementById('pubWelcomeBar');
    if (bar) bar.remove();
  }

  function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  /* ---- Auth0 flow ---- */

  async function initPublicAuth() {
    /* Show cached state immediately (no flash) */
    var cached = getCachedUser();
    if (cached) {
      _user = cached;
      injectWelcomeBar(cached);
    } else {
      injectSignInLink();
    }

    /* Load Auth0 config from backend */
    try {
      var config = await fetch('/api/auth/config').then(function (r) { return r.json(); });
      if (!config.domain) return; // Auth0 not configured — stay anonymous
    } catch (e) {
      return; // backend unreachable — stay anonymous
    }

    /* Wait for Auth0 SDK to be available */
    if (typeof auth0 === 'undefined') return;

    var authParams = {
      redirect_uri: window.location.origin + '/',
      scope: 'openid profile email',
    };
    if (config.audience) authParams.audience = config.audience;

    auth0Client = await auth0.createAuth0Client({
      domain: config.domain,
      clientId: config.clientId,
      authorizationParams: authParams,
      cacheLocation: 'localstorage',
    });

    /* Handle redirect callback */
    var query = window.location.search;
    if (query.includes('code=') && query.includes('state=')) {
      await auth0Client.handleRedirectCallback();
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    var isAuth = await auth0Client.isAuthenticated();
    if (isAuth) {
      var u = await auth0Client.getUser();
      _user = { email: u.email, name: u.name, sub: u.sub };
      setCachedUser(_user);
      removeWelcomeBar();
      /* Remove sign-in link before injecting bar */
      var sl = document.getElementById('pubSignInLink');
      if (sl) sl.remove();
      injectWelcomeBar(_user);

      /* Log login event to backend (fire-and-forget) */
      fetch('/api/auth/login-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auth0_user_id: u.sub, email: u.email, name: u.name }),
      }).catch(function () {});

      /* Notify page-specific scripts that auth is ready */
      window.dispatchEvent(new CustomEvent('pubauth', { detail: _user }));
    } else {
      /* Not authenticated — clear stale cache */
      clearCachedUser();
      _user = null;
      removeWelcomeBar();
      if (!document.getElementById('pubSignInLink')) injectSignInLink();
    }
  }

  async function doPublicLogin() {
    if (!auth0Client) return;
    await auth0Client.loginWithRedirect({
      authorizationParams: { redirect_uri: window.location.origin + '/' }
    });
  }

  /* Expose sign-out globally for the onclick handler */
  window._pubSignOut = async function () {
    clearCachedUser();
    _user = null;
    if (auth0Client) {
      auth0Client.logout({ logoutParams: { returnTo: window.location.origin + '/' } });
    } else {
      removeWelcomeBar();
      injectSignInLink();
    }
  };

  /* Expose authenticated fetch for other scripts (e.g. save simulation) */
  window._pubAuthFetch = async function (url, options) {
    if (!auth0Client) throw new Error('Not signed in');
    var token = await auth0Client.getTokenSilently();
    var headers = Object.assign({}, options && options.headers, { 'Authorization': 'Bearer ' + token });
    return fetch(url, Object.assign({}, options, { headers: headers }));
  };

  /* Check if a user is currently signed in (cached) */
  window._pubIsSignedIn = function () {
    return !!getCachedUser();
  };

  /* ---- Boot ---- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPublicAuth);
  } else {
    initPublicAuth();
  }
})();
