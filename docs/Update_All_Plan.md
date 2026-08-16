# Update All — Backup, Refresh, Verify, Decide

**Status:** Specification. Not built.
**Date:** 2026-08-16

---

## 1. The problem

Refreshing site data currently takes about a dozen clicks across six cards in
`admin.html`, in an order that is not written down anywhere and lives in
whoever is clicking. Each button is independently safe, but the sequence is
not enforced, it is easy to skip a step, and there is no way back if a data
source returns something wrong.

The last part is the real exposure. Every one of these operations writes
straight to the live table. If Yahoo returns a bad month, or a ticker
silently starts returning nothing, the damaged data is on the site
immediately and the only recovery is to reload full history from the same
source that just produced the bad data.

## 2. What one click does

**Update All** runs five phases and then stops and waits for a human.

```
  1  SNAPSHOT   copy every in-scope table to its backup table
  2  UPDATE     run the routine operations, one at a time, in fixed order
  3  VERIFY     compare current against backup, run the check suite
  4  REPORT     present findings, ranked by severity, with a recommendation
  5  DECIDE     admin picks:  Keep new data   |   Restore backup
```

Phase 5 is never automatic. A clean report recommends keeping; it does not
commit on its own. The run sits in `AWAITING_DECISION` until a person acts,
and survives the browser being closed.

## 3. Scope — which tables are in, and which are deliberately out

### In scope (snapshotted, compared, restorable)

| Table | Written by |
|---|---|
| `monthly_prices` | Yahoo — new tickers, incremental, current month |
| `dividends` | Yahoo — new tickers, incremental, current month |
| `spy_daily_prices` | Yahoo — daily prices, missing days |
| `oef_daily_prices` | Yahoo — daily prices, missing days |
| `etf_directory_monthly_history` | ETF directory — missing months |
| `monthly_mm_rates` | FRED — incremental |
| `annual_mm_rates` | FRED — incremental |
| `damodaran_annual_returns` | Damodaran sync |

### Out of scope — never snapshotted, never restored

| Table | Why |
|---|---|
| `saved_simulations` | **User data.** A run takes minutes. If someone saves a simulation during that window, a restore would silently delete it. |
| `user_logins` | Same. Activity that happened during the run is real and must survive a rollback. |
| `api_request_logs` | Same. |
| `user_admin` | Access control. Must never be reverted by a data operation. |
| `stack_earn_savings_tiers` | Hand-edited via Rate Management. The routine does not write it. |
| `stack_earn_goal_tiers` | Same. |
| `shiller_market_data` | One-time historical load. The routine does not write it. |
| `tickers` | The routine reads it, never writes it. Snapshotting it would mean a rollback could erase a ticker added during the run. |

This split is the reason the feature is safe. A rollback must only be able to
undo what the run itself did. Anything the run did not write, it must not be
able to destroy.

### Excluded operations

**Reload All Tickers** (`POST /api/batch/full`) is not part of Update All. It
is minutes of rate-limited API calls across every ticker's full history, and
it is the wrong shape for a routine. It stays a separate, explicitly confirmed
action — see §12, which also corrects what that button actually does today.

## 4. Phase 1 — Snapshot

One backup table per in-scope table, single generation, replaced at the start
of every run:

```
zz_bak_monthly_prices
zz_bak_dividends
zz_bak_spy_daily_prices
...
```

Dialect differs and both are live (SQL Server locally, PostgreSQL on Railway):

```sql
-- SQL Server
DROP TABLE IF EXISTS zz_bak_monthly_prices;
SELECT * INTO zz_bak_monthly_prices FROM monthly_prices;

-- PostgreSQL
DROP TABLE IF EXISTS zz_bak_monthly_prices;
CREATE TABLE zz_bak_monthly_prices AS SELECT * FROM monthly_prices;
```

Backups are kept after a successful commit and overwritten by the next run,
so there is always one generation of safety net sitting there for free.

Phase 1 must complete for every table or the run aborts before writing
anything. A partial snapshot is worse than no snapshot — it produces a
restore that half-works.

**Storage note:** on Railway this roughly doubles the market-data footprint
during a run. Current sizes should be measured before this ships.

## 5. Phase 2 — Update sequence

Fixed order, one at a time, next step starts only when the previous reports
success. This is the sequence the buttons already imply; writing it down is
half the value of the feature.

| # | Operation | Endpoint |
|---|---|---|
| 1 | Load new tickers (full history for anything newly added) | `POST /api/batch/full-new` |
| 2 | Refresh recent data (incremental prices + dividends) | `POST /api/batch/incremental` |
| 3 | Load current month — all sources | `POST /api/batch/current-month` |
| 4 | Daily prices — SPY, missing days | `POST /api/batch/daily-prices/SPY/incremental` |
| 5 | Daily prices — OEF, missing days | `POST /api/batch/daily-prices/OEF/incremental` |
| 6 | ETF directory — missing months | `POST /api/batch/etf-history/incremental` |
| 7 | FRED — incremental | `POST /api/batch/fred-incremental` |
| 8 | Damodaran — sync latest | `POST /api/admin/damodaran-returns/sync` |

Each step records start time, end time, rows written, and any error. If a
step fails, the run stops there, moves to `FAILED`, and offers the same two
choices — keep what landed, or restore. It does not continue past a failure
and it does not roll back on its own.

**Concurrency:** batch jobs already run on a background thread guarded by a
single global status with a 409 on overlap. Update All extends that guard to
cover the whole orchestrated run, not just one step.

## 6. Phase 3 — Verification

Four families of check. Severity drives the recommendation, never the action.

### A. Structural — BLOCKER

| ID | Check |
|---|---|
| A1 | No in-scope table has zero rows |
| A2 | Row count did not decrease |
| A3 | No duplicate primary keys |
| A4 | `MIN(date)` did not move forward — history was not truncated from the front |

### B. Historical immutability — BLOCKER

| ID | Check |
|---|---|
| B1 | For every row present in both backup and current under the same key, all value columns are identical — **excluding** rows in the current, still-incomplete month, which are expected to change |

**This is the check that matters most.** March 2019's closing price has no
legitimate reason to change. Row counts and date ranges catch a truncated
table; only this catches a silent rewrite of settled history, which is the
failure that would otherwise reach the site looking completely normal.

### C. Continuity — BLOCKER

| ID | Check |
|---|---|
| C1 | `MAX(date)` advanced or is unchanged, never regressed |
| C2 | No new gaps — no period missing between min and max that was present in the backup |
| C3 | No individual ticker lost rows |

### D. Plausibility — WARNING

These flag rows for a human to look at. They never block, because every one
of them has a legitimate real-world cause.

| ID | Check |
|---|---|
| D1 | New monthly close differs from the prior month by more than the configured threshold (start at 35%) |
| D2 | Any price null, zero, or negative |
| D3 | New dividend more than 5× the trailing median for that ticker |
| D4 | A ticker returned zero new rows while its peers updated — the signature of a delisted or broken feed |
| D5 | FRED rate outside 0–25% |

D1 will fire in a genuine crash month and D3 fires on special dividends. That
is correct behaviour. They are prompts to look, not verdicts.

## 7. Phase 4 — The report

Per table: rows before, rows after, delta, date range before and after, and
the status of each check.

Then the findings, blockers first, each naming the table, the key, the
backup value and the current value. Long lists cap at 50 rows with a total
count, so a broadly broken load produces a readable page rather than fifty
thousand lines.

The recommendation is stated plainly and is only ever advice:

- Any blocker → **"Recommend restoring the backup."**
- Warnings only → **"Recommend keeping. N rows flagged for review."**
- Clean → **"No issues found. Recommend keeping."**

## 8. Phase 5 — Decision

Two buttons. No default, no timeout, no auto-commit.

**Keep new data** — run marked `COMMITTED`. Backups stay until the next run
overwrites them.

**Restore backup** — for each in-scope table, inside a single transaction:

```sql
DELETE FROM monthly_prices;
INSERT INTO monthly_prices SELECT * FROM zz_bak_monthly_prices;
```

All tables restore or none do. Identity and sequence columns need explicit
handling (`IDENTITY_INSERT` on SQL Server, sequence resync on PostgreSQL) —
this is the fiddliest part of the build and the part most worth testing
against both engines before trusting it.

After a restore the run is marked `ROLLED_BACK` and the backups are left in
place, so a restore can be re-run if it is interrupted.

## 9. State

```
IDLE → BACKING_UP → UPDATING → VERIFYING → AWAITING_DECISION
                                              ├→ COMMITTED
                                              └→ ROLLED_BACK
   any phase can → FAILED (which also offers keep / restore)
```

Persisted in a new `data_refresh_runs` table: run id, state, phase timings,
per-step results, the findings payload, who decided and when. Server-side, so
closing the browser mid-run loses nothing and the decision can be made later
from anywhere.

**While a run is in `UPDATING`, `VERIFYING`, or `AWAITING_DECISION`, every
individual data button in admin is disabled.** A manual refresh during a
pending run corrupts the comparison and turns the restore from a correction
into a destructive act. The lock is not a convenience — it is what makes the
backup trustworthy.

## 10. Open questions

1. **Which database does this run against?** Data currently flows local SQL
   Server → Railway PostgreSQL via `tools/sync_sql_to_postgres.py`. If Update
   All runs against Railway, it operates on live data and the backup tables
   live in Railway. If it runs locally, the sync step needs to become part of
   the flow — and the decision point should sit *before* the sync, so bad
   data never reaches production at all. **This changes the design and should
   be settled first.**
2. Does `daily_quotes` belong in scope? It is in `models.py`; what writes it
   needs confirming.
3. Threshold values for D1 and D3 — the starting numbers above are guesses
   and should be set from a look at real historical volatility.
4. Backup retention — one generation as specified, or timestamped history?
   One generation is proposed for storage reasons.
5. Should a clean report with zero findings still require a click, or is that
   friction without value? Proposed: still require it. The click is the
   record of a human having looked.

## 11. Build order

1. `data_refresh_runs` table and the state machine, with no real work behind
   it — get resumability and the button lock right first.
2. Snapshot and restore, both dialects, tested by deliberately corrupting a
   table and restoring it.
3. The orchestrated update sequence, reusing the existing endpoints as-is.
4. Check suite A, B, C.
5. The report UI and the decision buttons.
6. Check suite D and its thresholds.

Steps 1 and 2 carry the risk. Everything after them is additive, and the
feature is genuinely useful from step 3 onward even before the checks exist.

---

## 12. Reload All Tickers — window it, and make it honest

This is separable from Update All and can ship first.

### What that button actually does today

Not what its name says. In `loader.load_prices()`, `mode="full"` **skips any
row that already exists**; only `mode="incremental"` updates one. So the
button downloads roughly thirty years of history for every active ticker —
the slow, rate-limited part — and then writes only the months that happened
to be missing. The card's fine print already concedes this ("existing data is
skipped, not overwritten"). The label is what misleads.

Two things follow.

**It cannot repair anything.** If a historical month is wrong, nothing in
admin can fix it. `full` skips it. `incremental` only reaches back N months.
The only route today is deleting rows by hand in the database. This is worth
stating plainly because it is the strongest argument for the backup half of
Update All: forward repair does not currently exist.

**The expensive part is the fetch, not the write.** Cost scales with history
depth × ticker count, and almost all of it is thrown away.

### What is being asked for

Default to reloading the last twelve months. Full history only on an explicit
request.

### It mostly already exists

`Refresh Recent Data` → `POST /api/batch/incremental` with `months` takes an
arbitrary window and upserts. Set it to 12 and that *is* "reload the last
twelve months for every ticker." No new endpoint is needed for the common
case. The work is defaults and guardrails.

### Proposed changes

| Control | Today | Proposed |
|---|---|---|
| Refresh Recent Data | `Months` defaults to 2 | Defaults to **12**. Behaviour unchanged — it already overwrites in-window. |
| Reload All Tickers | Single `confirm()`, then a ~30-year fetch that cannot overwrite | Rename **Rebuild Full History**. Typed confirmation, not a click-through. Switch to upsert so it can actually repair. |

On the API, `POST /api/batch/full` should require an explicit
`confirm_full_history: true` in the body and reject the request without it,
so the expensive path cannot be reached by an accidental or replayed call.

### The one real behaviour change

Making full-history mode upsert instead of skip converts the button from
"fill in gaps" to "trust the source and rewrite from it." That is what you
want after a bad load, and it is the only thing that makes forward repair
possible at all.

It is also the single most destructive operation in the admin dashboard, and
it would be pointed at the two largest tables. **It should not ship before
the snapshot/restore machinery in §4 and §8 exists**, and when it does ship
it should take a snapshot first — the same one Update All takes — regardless
of whether the rest of the verify/decide flow is built yet.

Sequencing follows from that: defaults and the typed confirmation can land
immediately; the upsert change waits for backups.
