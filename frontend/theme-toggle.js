/* ==========================================
   THEME TOGGLE — shared across all pages
   Loaded synchronously in <head> to prevent
   flash of wrong theme (FOUC).
   ========================================== */

// === IMMEDIATE: runs during <head> parse, before body renders ===
(function() {
  var t = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', t);
})();

// === THEME palette for Canvas-drawing JS ===
// Usage: ctx.strokeStyle = THEME.grid;
window.THEME = {
  get grid()  { return getComputedStyle(document.documentElement).getPropertyValue('--border').trim(); },
  get axis()  { return getComputedStyle(document.documentElement).getPropertyValue('--text3').trim(); },
  get bg()    { return getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(); },
  get text1() { return getComputedStyle(document.documentElement).getPropertyValue('--text1').trim(); },
  get text2() { return getComputedStyle(document.documentElement).getPropertyValue('--text2').trim(); },
  get card()  { return getComputedStyle(document.documentElement).getPropertyValue('--card').trim(); }
};

// === DEFERRED: inject toggle button after DOM is ready ===
document.addEventListener('DOMContentLoaded', function() {
  var btn = document.createElement('button');
  btn.id = 'themeToggle';
  btn.className = 'theme-toggle-btn';
  btn.setAttribute('aria-label', 'Toggle light/dark theme');
  btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '\u{1F319}' : '\u{2600}\u{FE0F}';

  btn.addEventListener('click', function() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    btn.textContent = next === 'dark' ? '\u{1F319}' : '\u{2600}\u{FE0F}';
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
  });

  document.body.appendChild(btn);
});
