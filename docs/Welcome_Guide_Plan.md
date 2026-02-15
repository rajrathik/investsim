# Welcome Guide Overlay + Documentation Updates

## Context
Auth0 login is working. After login, a concise "training manual" overlay is shown before the simulator loads. Helps users understand what the simulator does, how to use it, and what results mean. User clicks a single button to proceed. README.md and Architecture.md updated with auth + welcome guide info.

## Files Modified (5 files)

| File | Change |
|------|--------|
| `frontend/portfolio-simulator.css` | Add `.welcome-overlay`, `.welcome-card`, `.welcome-section` styles |
| `frontend/portfolio-simulator.html` | Add welcome guide overlay div between auth overlay and header |
| `frontend/portfolio-simulator.js` | Modify `onLoginSuccess()` → show guide; add `dismissWelcomeGuide()` |
| `README.md` | Add Authentication & Welcome Guide section, update Features list |
| `Architecture.md` | Add frontend user flow diagram, auth + welcome guide design decisions |

## Welcome Guide Content (4 short sections)
1. **What This Tool Does** — simulates monthly DCA investing, real historical prices, worst-case entry, dividends as cash
2. **How to Use It** — 4 steps: set amount/period → pick tickers → allocate to 100% → run
3. **What You'll See** — 6 summary tiles, interactive charts, monthly table (click cells), tax impact, annual returns
4. **Key Things to Know** — all values clickable, missing months redistributed, MMF column = benchmark

## User Flow
```
Auth0 login success
  → onLoginSuccess() hides auth overlay, shows welcome guide overlay (z-index 500)
  → User reads 4-section guide
  → Clicks "Got It — Let's Start"
  → dismissWelcomeGuide() hides welcome overlay, calls loadTickers()
  → Simulator is now usable
```

## Z-Index Layering
- Auth overlay: z-index 1000 (highest — blocks everything during login)
- Welcome guide: z-index 500 (shown after auth, before simulator)
- Modal overlay: z-index 200 (used during simulation results)

## Design Decisions
- Welcome guide uses same overlay pattern as auth screen (fixed position, backdrop blur, hidden via CSS class toggle)
- Content is concise and scannable — four sections with icons, short bullet lists
- Card is 640px max-width, scrollable on short screens (85vh max-height)
- Responsive: icons hidden on mobile (<600px) to save space
- Uses existing `fadeUp` animation and `.run` button class
- Guide shown every page load after login (no "show once" flag — keeps users oriented)
