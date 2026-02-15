# Auth0 Login Integration — Requirements & Implementation Plan

**Date:** February 2026
**Status:** Approved
**Branch:** `feature/auth0-login`

---

## Context

The portfolio simulator is currently open — anyone can use it. We need to gate access behind Auth0 authentication so only registered users can run simulations. All work happens on a new branch `feature/auth0-login` so `main` stays untouched and rollback is trivial.

---

## Rollback Instructions

```bash
git checkout main                          # switch back to clean state
git branch -D feature/auth0-login          # delete the branch entirely
```

---

## Files to Create/Modify

| File | Action | What |
|------|--------|------|
| `backend/.env` | MODIFY | Add AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE |
| `backend/app/config.py` | MODIFY | Add 4 Auth0 config vars via os.getenv() |
| `backend/app/auth.py` | CREATE | JWT verification, JWKS fetch, get_current_user dependency |
| `backend/app/models.py` | MODIFY | Add UserLogin model |
| `backend/app/api.py` | MODIFY | Add auth endpoints, protect 15 routes, serve frontend static files |
| `frontend/portfolio-simulator.html` | MODIFY | Add Auth0 SDK script, login overlay, header login/logout buttons |
| `frontend/portfolio-simulator.css` | MODIFY | Add auth overlay + auth section styles |
| `frontend/portfolio-simulator.js` | MODIFY | Auth0 init, authFetch wrapper, replace all fetch calls, initAuth() on load |
| `tools/create_user_logins.sql` | CREATE | SQL script to manually create user_logins table |

---

## Step-by-Step Implementation

### Step 1: Create branch
```bash
git checkout main
git checkout -b feature/auth0-login
```

### Step 2: Backend — Auth0 config
- Add to `backend/.env`: AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE, AUTH0_ALGORITHMS
- Add to `backend/app/config.py`: read those via os.getenv() (same pattern as DB config)
- Install: `pip install python-jose[cryptography]`

### Step 3: Backend — Create `backend/app/auth.py`
New file with:
- `get_jwks()` — fetch Auth0 JWKS (cached with @lru_cache)
- `get_token_from_header(request)` — extract Bearer token
- `verify_token(token)` — validate JWT against Auth0 public keys (RS256)
- `get_current_user(request)` — FastAPI Depends() function returning decoded user payload

### Step 4: Backend — UserLogin model
Add to `backend/app/models.py`:
- `UserLogin` class: id, auth0_user_id, email, name, login_time, ip_address, user_agent
- `auth0_user_id` is the stable user ID for future simulation storage
- Auto-created by init_db() since it inherits from Base

### Step 5: Backend — API changes in `backend/app/api.py`
- **New endpoint** `GET /api/auth/config` (unauthenticated) — returns domain + clientId for frontend SDK init
- **New endpoint** `POST /api/auth/login-event` (authenticated) — logs login to user_logins table
- **Protect 15 existing endpoints** by adding `user: dict = Depends(get_current_user)` parameter
- **Keep unprotected:** `/api/health` and `/api/auth/config`
- **Serve frontend** via `StaticFiles(directory=frontend, html=True)` mounted at the end of file
- **Tighten CORS** to `http://localhost:8000`

### Step 6: Frontend — HTML changes
- Add Auth0 SPA SDK CDN script in `<head>`
- Add auth overlay div (blocks simulator with lock icon + "Log In" button)
- Add login/logout buttons + user email display in header (right side)

### Step 7: Frontend — CSS changes
- `.auth-overlay` — fixed fullscreen backdrop with blur
- `.auth-overlay.hidden` — fade out when authenticated
- `.auth-card` — centered login prompt card

### Step 8: Frontend — JS changes
- Change `API` from `http://localhost:8000/api` to `/api` (relative, same origin)
- Add `auth0Client`, `currentUser` globals
- Add `initAuth()` — fetch config, create Auth0 client, handle redirect callback, check auth state
- Add `doLogin()` / `doLogout()` — call Auth0 SDK
- Add `onLoginSuccess()` — hide overlay, show user menu, log login event, then call `loadTickers()`
- Add `authFetch(url, options)` — wrapper that injects `Authorization: Bearer <token>` header
- Replace ALL `fetch(API+...)` calls with `authFetch(API+...)`
- Replace page-load ticker fetch with `initAuth()` call

### Step 9: SQL Script
Create `tools/create_user_logins.sql` for manual table creation.

---

## User Flow After Implementation

```
User opens http://localhost:8000/portfolio-simulator.html
  -> Sees lock screen overlay (simulator hidden)
  -> Clicks "Log In with Auth0"
  -> Auth0 hosted login page (email+password or Google)
  -> Redirected back -> overlay fades out
  -> Header shows "user@email.com | Log Out"
  -> Login event saved to user_logins table
  -> Simulator works normally (all API calls carry JWT)
  -> Close browser, come back -> still logged in (token in localStorage)
```

---

## Auth0 Dashboard Setup Required

User must configure in Auth0 before testing:
- Allowed Callback URLs: `http://localhost:8000/portfolio-simulator.html`
- Allowed Logout URLs: `http://localhost:8000/portfolio-simulator.html`
- Allowed Web Origins: `http://localhost:8000`

---

## Security Architecture

```
Browser                         Auth0                      FastAPI Backend
  |                               |                              |
  |-- Click "Log In" ------------>|                              |
  |                               |-- Login page (hosted) ------>|
  |                               |<-- email+password ---------- |
  |                               |-- Verify credentials         |
  |                               |-- Send verification email    |
  |<-- Redirect with JWT ---------|                              |
  |                                                              |
  |-- API call + Bearer token ---------------------------------->|
  |                                                              |-- Verify JWT via JWKS
  |                                                              |-- Extract user from token
  |                                                              |-- Process request
  |<-- JSON response -------------------------------------------|
```

- Auth0 stores all credentials (hashed, never plaintext)
- Your database never stores passwords
- JWT tokens verified against Auth0's public keys (RS256)
- Token expires after 24 hours by default
- MFA available via Auth0 dashboard toggle

---

## Database — user_logins Table

```sql
CREATE TABLE user_logins (
    id INT IDENTITY(1,1) PRIMARY KEY,
    auth0_user_id NVARCHAR(255) NOT NULL,    -- stable user ID (Auth0 "sub" claim)
    email NVARCHAR(255) NULL,
    name NVARCHAR(255) NULL,
    login_time DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    ip_address NVARCHAR(45) NULL,
    user_agent NVARCHAR(500) NULL
);
```

`auth0_user_id` is the key for future features (saving simulations per user).

---

## Verification Checklist

1. Start: `uvicorn app.api:app --reload` from backend/
2. Open: `http://localhost:8000/portfolio-simulator.html`
3. Verify: lock overlay appears, simulator hidden
4. Click "Log In" -> Auth0 login page -> sign up or log in
5. After redirect -> overlay gone, user email in header, simulator works
6. Check DB: `SELECT * FROM user_logins` — login event recorded
7. Click "Log Out" -> back to lock screen
8. Open a new incognito window -> should see lock screen (not logged in)

---

## Future Extensions

- **Save simulations per user** — new `user_simulations` table with `auth0_user_id` FK
- **MFA** — toggle on in Auth0 Dashboard > Security > Multi-factor Auth
- **Social login** — enable Google/Microsoft/GitHub in Auth0 Dashboard
- **Mobile app** — add Capacitor callback URLs to the same Auth0 app registration
- **Rate limiting** — add `slowapi` to FastAPI with per-user limits using `auth0_user_id`
