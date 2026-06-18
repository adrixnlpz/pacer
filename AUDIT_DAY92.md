# PACER Day 92 QA + Polish Audit

Report-only audit. No app code was changed.

## Verification Pass

- Source read: `index.html` full 7,120 lines; `server.py` full 353 lines; `service-worker.js` and `manifest.json` read for runtime/cache contract.
- Browser stress pass: Playwright via installed Microsoft Edge against `http://127.0.0.1:8765/`.
- Viewports checked: desktop `1440x1100`; mobile `390x900`.
- Tabs clicked: live, history, optimize, yield, simulator, compare, codex, broker.
- Flows exercised: Tokemon sync, history CSV export, yield demo load/expand, simulator extreme values, compare custom profile prompts, codex log/export, broker demo/add intent.
- Browser results: no console errors, no page errors, no request failures, no horizontal overflow at 1440 or 390. CSV downloads fired for History and Codex.
- Motion/accessibility note: reduced-motion CSS exists, but tab/dialog ARIA/focus patterns are incomplete.
- GSAP/Three.js: skipped. PACER is a vanilla dashboard; no 3D or timeline motion is needed for this audit.

## Prioritized Findings

| ID | Sev | Tab / Feature | Exact Symptom | Reference | One-line Fix |
|---|---|---|---|---|---|
| F-01 | P1 | Compare / Add Custom | Non-numeric custom profile input renders `NaN%` for Avg / Day and Peak Day; confirmed with `weekly=abc`, `opus=999` at both 1440 and 390. | `index.html:5888-5896`, rendered `#cmpGrid` / `#cmp-card-custom-*` | Validate/clamp prompt values before `profiles.push`; reject non-finite values or default to bounded numeric values. |
| F-02 | P1 | Live / Backend offline | Clicking `UPDATE USAGE` when fetch fails opens the manual modal, then rethrows; button event has no `.catch()`, risking unhandled promise noise. | `index.html:3676`, `index.html:3818-3821` | Do not rethrow after opening fallback, or catch the promise in the click handler. |
| F-03 | P1 | Live / Recommendation snooze | Button says `1HR SNOOZE`, but snooze expires after 5 seconds. | `index.html:2735`, `index.html:4297-4312` | Change timeout to `3600000` or relabel the control as demo behavior. |
| F-04 | P1 | Live / Burn chart | Week projection is hardcoded to `80%`, `117%`, and `100% @ 10:42 PM THU`; live Tokemon sync can show different values, so chart and KPI can disagree. | `index.html:4225-4250` | Derive projection line, exhaustion marker, and `NOW` label from current live state instead of constants. |
| F-05 | P1 | Simulator / Apply to Live | `APPLY TO LIVE TAB` updates only a subset of Live fields; verdict text, marker, burn delta, target line, chart arrays, recommendation, and snapshot state can remain stale. | `index.html:4510-4525` | Route simulator values through `PACER.writeLiveValues(...)` and save a typed snapshot. |
| F-06 | P1 | Yield / CodeBurn Import | Imported sessions can produce `NaN` tokens because `c.tokens || c.input_tokens + c.output_tokens` is not guarded when either token field is missing; `pct` ignores the fallback sum. | `index.html:5100-5112` | Compute `tokens = Number(c.tokens) || ((Number(c.input_tokens)||0) + (Number(c.output_tokens)||0))`, then reuse it for `pct`. |
| F-07 | P1 | API / Server startup | `import anthropic` runs at module import, so `/api/data` and static serving fail if the optional recommendation dependency is missing. | `server.py:17`, `server.py:239-244` | Lazy-import `anthropic` inside `get_recommendation()` and return a recommendation-only error if unavailable. |
| F-08 | P1 | Service Worker / API freshness | Fetch handler caches every successful GET and falls back to `index.html`; in production this can cache dynamic same-origin API responses or return HTML for failed data requests. | `service-worker.js:23-36` | Bypass caching/fallback for `/api/*` and non-app asset requests; cache only app shell files. |
| F-09 | P2 | API / Health checks | `HEAD /api/data?range=7d` returns `404` because server implements only `do_GET`; basic uptime checks can report false failure. | `server.py:319-345` | Add `do_HEAD` for `/`, `/index.html`, and `/api/data`, or return `405` with `Allow: GET`. |
| F-10 | P2 | API / Tokemon history | Latest plan usage uses `history[-1]` without sorting; out-of-order Tokemon writes can display stale weekly/5-hour values. | `server.py:229-236` | Sort valid history entries by parsed timestamp before choosing latest. |
| F-11 | P2 | Broker / Rebalance | Rebalance rounds each unlocked intent independently; totals can land at 99% or 101%, causing reserve/overcommit drift after a "balanced" action. | `index.html:6260-6271` | Normalize the rounding remainder onto the largest unlocked intent so totals equal exactly `100 - lockedSum`. |
| F-12 | P2 | Broker / Mobile polish | At <=900px the table header is hidden, but rows still show raw controls with no row labels; mobile text reads like `income build explore ... DELMOVE`. | `index.html:2386-2550`, `index.html:6681-6699` | Render mobile-specific labeled rows or add visible field labels for priority, allocation, spent, status, and actions. |
| F-13 | P2 | Broker / Advisor freeze | Accepting `freeze_claude_unlocked` only toggles in-memory `frozenClaudeUnlocked`; refresh/tab rebuild loses the freeze. | `index.html:6475-6477`, `index.html:6533-6552` | Persist the freeze flag in broker UI state or encode it into affected Claude intents. |
| F-14 | P2 | Accessibility / Tabs | Tabs use `role="tablist"` / `role="tab"` but omit `aria-selected`, `aria-controls`, keyboard arrow navigation, and `tabpanel` wiring. | `index.html:2593-2618`, `index.html:3573-3608` | Add tab ids, panel ids/roles, `aria-selected`, roving tabindex, and arrow-key handling. |
| F-15 | P2 | Accessibility / Modals | Usage and Codex modals lack focus trap, Escape close, focus restoration, and `aria-describedby`; background remains keyboard reachable. | `index.html:3376-3404`, `index.html:3927-3938`, `index.html:6900-6914` | Add dialog focus management, Escape handling, restore opener focus, and description ids. |
| F-16 | P2 | Accessibility / Icon buttons | Delete/lock controls rely on glyph/title or short text; some generated Broker action buttons lack explicit accessible labels and context. | `index.html:6689-6698`, `index.html:7029` | Add `aria-label` values with intent/task names, e.g. `Delete PACER build intent`. |
| F-17 | P2 | Runtime resilience / Unguarded DOM | Several core methods assume static elements exist and assign directly; future locked-feature insertions could turn missing elements into crashes. | Examples: `index.html:3508-3511`, `index.html:3651-3653`, `index.html:6637-6639` | Use a tiny `must(id)`/`maybe(id)` helper or guard direct writes in shared runtime paths. |
| F-18 | P2 | UX copy / Language toggle | Language toggle persists `es` and changes `<html lang>`, but the UI copy remains English; toast says `Idioma: espanol` without Spanish text actually loading. | `index.html:2583-2585`, `index.html:3514-3544` | Either implement real Spanish labels for visible copy or relabel the control as a future bilingual mode. |

## Readiness Notes For Locked Features

### Two-profile onboarding: Newbie / Expert, expert first

- Best insertion point: run before `PACER.init()` finishes state restoration, then store `pacer.profile.mode`.
- Expert-first default should preserve current dense dashboard with all 8 tabs visible.
- Newbie mode should hide or soften Broker/Codex/Yield until the user opts in, but must not delete localStorage state or alter calculations.
- Avoid broad rewrites: add a small profile gate around tab visibility, copy density, and default recommendation tone.
- Accessibility dependency: fix tab ARIA before hiding/reordering tabs so focus order remains predictable.

### Claude-code-budget auto-handoff + response-counter + context-% tracker

- Best fit: extend Broker + Codex, not Live. Live remains budget telemetry; Broker owns routing; Codex owns handoff logging.
- Data model should be explicit: `pacer.handoff.state` with `session_id`, `response_count`, `context_pct`, `budget_pct`, `handoff_status`, and `last_exported_at`.
- Do not overload `pacer.codex.state`; keep task logs separate from session handoff telemetry.
- Add import/export JSON before automation so Claude/Code/Codex can hand off safely without relying on DOM text.
- Service worker API bypass is a prerequisite if this becomes dynamic or backend-backed.

## TOP 10 — do these first

1. Fix Compare custom profile numeric validation (`F-01`).
2. Stop `UPDATE USAGE` from rethrowing after manual fallback (`F-02`).
3. Make snooze duration match `1HR SNOOZE` (`F-03`).
4. Replace hardcoded Live chart projection values with live-state values (`F-04`).
5. Route Simulator apply through `PACER.writeLiveValues(...)` (`F-05`).
6. Fix Yield import token fallback math (`F-06`).
7. Lazy-load `anthropic` so `/api/data` does not depend on recommendation dependencies (`F-07`).
8. Bypass service-worker caching for `/api/*` and non-shell requests (`F-08`).
9. Add tab ARIA state and roving keyboard navigation (`F-14`).
10. Add modal focus trap, Escape close, focus restoration, and descriptions (`F-15`).

## Totals By Severity

- P0: 0
- P1: 8
- P2: 10
- Total: 18

## Day 92 — Data-source + deeper-bug investigation

Report-only addendum. No app code was changed.

### 1. `/api/data` trace and exact live-data root cause

`/api/data?range=7d` is served by `PACERHandler.do_GET`: it calls `parse_sessions(r)`, calls `get_plan_usage(r)`, attaches the plan block, and returns JSON. Evidence: `server.py:327-332`.

The response has two different data families:

- Real Claude Code transcript aggregates from `~/.claude/projects/**/*.jsonl`. `parse_sessions()` opens each JSONL file, filters assistant messages with usage, computes cost, daily totals, model mix, and tool counts. Evidence: `server.py:67-80`, `server.py:90-147`, `server.py:184-200`.
- Plan-percentage usage from Tokemon's local history file at `~/Library/Application Support/Tokemon/usage_history.json`. `get_plan_usage()` maps `primaryPercentage` to `primary_pct` and `sevenDayPercentage` to `seven_day_pct`, then returns `history`, `source`, and `updated_at`. Evidence: `server.py:202-237`.

The current hypothesis is only partially true:

- `import anthropic` is a real startup fragility because it runs at module load and can prevent the whole server from starting if the package is absent. Evidence: `server.py:17`.
- A missing Anthropic key does **not** kill `/api/data`; it is only checked inside `get_recommendation()`, which is used by `/api/recommend`. Evidence: `server.py:239-244`, `server.py:334-341`.
- On this machine, `import anthropic` succeeds (`anthropic 0.95.0`), and `/api/data` currently returns HTTP 200 with real Claude JSONL aggregate data.

Exact root cause for "live Claude data isn't showing": PACER's Live sync throws away almost everything real that `/api/data` returns and only reads `data.plan`. Evidence: `index.html:3762-3777`. The `plan` data is a stale Tokemon snapshot; local Tokemon history ends at `2026-06-12T10:47:31Z` with `primaryPercentage: 99` and `sevenDayPercentage: 61`, and PACER has no staleness guard before showing "Synced from Tokemon". Evidence: `server.py:229-236`, `index.html:3796-3815`. When the backend is unreachable, the frontend opens the manual usage popup and rethrows. Evidence: `index.html:3818-3821`. Separately, the Live projection chart still contains hardcoded forecast values, so even successful sync can disagree with the chart. Evidence: `index.html:4225-4250`.

### 2. Tokemon source, schema, and PACER gap

Local Tokemon integration files found:

- `~/Library/Application Support/Tokemon/usage_history.json`
- `~/.tokemon/status.json`
- `~/.tokemon/statusline`
- `~/.tokemon/statusline-color`
- `~/.tokemon/oauth-debug.log`
- `~/.tokemon/tokemon-statusline.sh`

The Tokemon statusline helper documents the live files it expects Tokemon to write: `~/.tokemon/statusline`, `~/.tokemon/statusline-color`, and `~/.tokemon/status.json`. Evidence: `/Users/adrianlopez/.tokemon/tokemon-statusline.sh:35-40`. It also hides stale statusline data older than 5 minutes, which PACER does not do for `usage_history.json`. Evidence: `/Users/adrianlopez/.tokemon/tokemon-statusline.sh:67-71`.

Observed `usage_history.json` schema:

```json
{
  "source": "oauth",
  "timestamp": "2026-06-12T10:47:31Z",
  "id": "...",
  "primaryPercentage": 99,
  "sevenDayPercentage": 61
}
```

Observed `~/.tokemon/status.json` schema:

```json
{
  "reset_minutes": 172,
  "reset_time": "2026-06-12T13:40:00Z",
  "session_pct": 99,
  "updated": "2026-06-12T10:47:31Z",
  "weekly_pct": 61
}
```

The OAuth debug log shows Tokemon's mechanism is an OAuth-backed API fetch, not Claude transcript parsing: last local log entry says it had an access token and got API 200 with `5h=99.0%` at `2026-06-12T10:47:31Z`. PACER is reading the history schema correctly, but it reads the append-only history file instead of the fresher status JSON/statusline contract, and it does not reject stale data. Gap: PACER needs either a fresh Tokemon writer running or a direct read of `~/.tokemon/status.json` with the same 5-minute freshness rule used by Tokemon's shell helper.

### 3. CodeBurn / NPX data source for weekly + session usage

`codeburn` is local-log based. Its README says Codex sessions are stored at `~/.codex/sessions/` as JSONL rollout files and CodeBurn reads `token_count` events, attributing cost by project working directory. Evidence: `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:136`.

The useful commands/mechanisms are:

- `codeburn report --provider codex` for the interactive dashboard. Evidence: `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:136`.
- `codeburn status --format json --provider codex` for compact today/month JSON. Evidence: `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:77`, `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:348`.
- `codeburn export -f json --provider codex` for dashboard-panel JSON. Evidence: `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:78-79`, `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:341`.
- Local caches observed: `~/.cache/codeburn/daily-cache.json`, `~/.cache/codeburn/session-cache.json`, and `~/.cache/codeburn/codex-results.json`.

Important limitation: CodeBurn gives cost/tokens/calls/session analytics from local logs. It does not provide official ChatGPT/Codex subscription rate-limit percentages; those percentages are present in Codex rollout `token_count` events themselves.

### 4. Codex CLI usage/limit source PACER should read

There is no documented `codex usage` or `codex status` command in the installed CLI help. `codex doctor --json` reports state/auth locations, including:

- `CODEX_HOME`: `~/.codex`
- auth file: `~/.codex/auth.json`
- log DB: `~/.codex/logs_2.sqlite`
- state DB: `~/.codex/state_5.sqlite`
- rollout/session files: `~/.codex/sessions/**/*.jsonl`

The exact real source for current Codex usage and limits is the latest `event_msg` where `payload.type == "token_count"` in `~/.codex/sessions/**/*.jsonl`. These events include:

- `payload.info.total_token_usage.input_tokens`
- `payload.info.total_token_usage.cached_input_tokens`
- `payload.info.total_token_usage.output_tokens`
- `payload.info.total_token_usage.reasoning_output_tokens`
- `payload.info.model_context_window`
- `payload.rate_limits.primary.used_percent`
- `payload.rate_limits.primary.window_minutes`
- `payload.rate_limits.primary.resets_at`
- `payload.rate_limits.secondary.used_percent`
- `payload.rate_limits.secondary.window_minutes`
- `payload.rate_limits.secondary.resets_at`
- `payload.rate_limits.plan_type`

Concrete evidence from a local rollout file: `/Users/adrianlopez/.codex/sessions/2026/06/16/rollout-2026-06-16T18-03-37-019ed2e3-fe7a-7e23-91ae-c60967aa3d1b.jsonl:19` has a `token_count` event with `primary.used_percent: 1.0`, `secondary.used_percent: 0.0`, and `plan_type: "plus"`; line `430` in the same file has a later `token_count` event with `primary.used_percent: 40.0`, `secondary.used_percent: 6.0`.

PACER's Codex tab currently reads only its own localStorage task log and therefore shows task-derived numbers, not real Codex usage/limits. Evidence: `index.html:6874-6881`, `index.html:7066-7103`.

### 5. Analytics sections: real vs placeholder/gimmick/hardcoded

| Section | Classification | Evidence | Notes |
|---|---|---|---|
| Pattern detection engine | Placeholder / hardcoded | `index.html:5257-5299`, `index.html:5356-5382` | `PACER.history.weeks` and `patterns` are literal arrays; not connected to `/api/data.daily`. |
| Hidden cost audit | Placeholder / hardcoded | `index.html:2817-2826`, `index.html:4353-4363` | Static rows plus a button animation; no scan of JSONL/cache/tool data. |
| Circuit breaker | Placeholder / hardcoded | `index.html:2801-2812`, `index.html:4326-4350` | Threshold rows are static; reset button only changes UI text and rearms after 1.5s. |
| Reset alert | Placeholder / hardcoded | `index.html:2801-2812`, `index.html:4326-4350` | Same static alert table; no scheduled reset calculation beyond Live countdown helpers. |
| Yield analysis | Mixed, mostly placeholder | `index.html:5019-5030`, `index.html:5100-5115`, `index.html:5117-5228` | Demo sessions are hardcoded; import can read a `conversations` array, but ROI/verdict are generated with `Math.random()`. |
| Pacing simulator | Computed toy model, not live analytics | `index.html:4429-4436`, `index.html:4534-4582`, `index.html:4585-4628` | Computes from sliders; defaults/current comparison are hardcoded at `index.html:4482-4507`. |
| Profile compare | Hardcoded profiles with computed display | `index.html:5604-5664`, `index.html:5713-5785`, `index.html:5788-5904` | Archetypes are literal constants; comparison and radar math are real over those constants. |
| Optimize recommendations | Placeholder / hardcoded | `index.html:4738-4825`, `index.html:4984-5012` | Hardcoded recommendation cards; does not call `/api/recommend`. |
| Surface attribution / model mix | Placeholder / hardcoded despite real backend data | `index.html:2717-2796`, `server.py:198-199` | Static UI while `/api/data` already returns real `by_model` and `tools`. |
| History CSV/export | Placeholder / hardcoded export | `index.html:5257-5290`, `index.html:5584-5596`, `server.py:196-199` | Exports hardcoded week rows instead of backend `daily`, `by_model`, or `tools`. |

### 6. New deeper bugs beyond F-01 through F-18

| ID | Sev | Tab / Feature | Exact Symptom | Reference | One-line Fix |
|---|---|---|---|---|---|
| D-01 | P1 | Live / Data binding | Successful `/api/data` returns real `summary`, `daily`, `by_model`, and `tools`, but frontend uses only `data.plan`; all model/tool/history panels remain fake. | `server.py:184-200`, `index.html:3762-3777` | Bind Live/History/Model/Tool sections to the full `/api/data` payload, not just `plan`. |
| D-02 | P1 | Live / Tokemon freshness | PACER treats a stale Tokemon history entry from `2026-06-12T10:47:31Z` as live and shows a successful sync toast. | `server.py:229-236`, `index.html:3796-3815` | Reject or label plan data older than 5 minutes; prefer `~/.tokemon/status.json` if fresh. |
| D-03 | P1 | API / `/api/data` resilience | One unreadable Claude JSONL file can crash the whole `/api/data` response because `open(fpath)` is outside a per-file try/catch. | `server.py:76-80`, `server.py:327-332` | Wrap each file open/read loop in a per-file exception guard and continue. |
| D-04 | P1 | Optimize / API wiring | `/api/recommend` exists, but the Optimize tab never calls it and only renders static recommendation cards. | `server.py:334-341`, `index.html:4738-4825`, `index.html:4984-5012` | Add an explicit backend recommendation fetch path or remove the unused endpoint from the shipped flow. |
| D-05 | P1 | Yield / CodeBurn import | PACER expects `data.conversations`, but CodeBurn JSON export is dashboard-panel JSON; real `codeburn export -f json` will not populate rows as intended. | `index.html:5100-5115`, `/Users/adrianlopez/.npm/_npx/0bdd5f75ee65ad7b/node_modules/codeburn/README.md:341` | Support CodeBurn's exported panels/caches or provide a documented PACER import schema. |
| D-06 | P1 | Codex / Real usage | Codex tab persists only `pacer.codex.state` task entries; it never reads Codex rollout `token_count` events, so real primary/secondary limit percentages show as zeros or task-derived placeholders. | `index.html:6874-6881`, `index.html:7066-7103`, `/Users/adrianlopez/.codex/sessions/2026/06/16/rollout-2026-06-16T18-03-37-019ed2e3-fe7a-7e23-91ae-c60967aa3d1b.jsonl:19` | Add a backend reader for latest `~/.codex/sessions/**/*.jsonl` `token_count` rate limits. |
| D-07 | P2 | History / CSV export | History CSV export serializes hardcoded `PACER.history.weeks`, not real backend daily totals. | `index.html:5257-5290`, `index.html:5584-5596` | Populate `PACER.history.weeks` from `/api/data.daily` before rendering/exporting. |
| D-08 | P2 | Yield / KPIs | Yield table/chart update after demo/import, but the top KPI cards remain static. | `index.html:2996-3016`, `index.html:5117-5228` | Recompute `yAvgROI`, `yWasted`, `yBestUse`, and `yWorstUse` from active sessions. |
| D-09 | P2 | Live / Audit button state | `RUN FULL AUDIT` permanently changes to `AUDIT COMPLETE` after one click and has no reset/re-run state. | `index.html:4353-4363` | Restore the button label after a short success state or make it a real repeatable scan. |
| D-10 | P2 | Live / Optimize button state | `OPTIMIZE MIX` changes to `SEE OPTIMIZE TAB →` and never resets when the user returns to Live. | `index.html:4366-4377` | Reset transient call-to-action text on tab activation or after navigation. |

### Day 92 Investigation TOP 10 — do these first

1. Add freshness detection for Tokemon plan usage (`D-02`).
2. Bind Live/History/model/tool panels to the full `/api/data` payload (`D-01`).
3. Add a Codex backend reader for latest `~/.codex/sessions/**/*.jsonl` `token_count` rate limits (`D-06`).
4. Support CodeBurn's real export/cache schema in Yield import (`D-05`).
5. Guard `/api/data` against unreadable/corrupt Claude JSONL files (`D-03`).
6. Replace hardcoded History/export rows with `/api/data.daily` (`D-07`).
7. Wire Optimize to `/api/recommend` or remove that dead endpoint path (`D-04`).
8. Recompute Yield KPI cards from active sessions (`D-08`).
9. Reset `RUN FULL AUDIT` after its success state (`D-09`).
10. Reset `OPTIMIZE MIX` after navigation (`D-10`).

### New Findings Totals

- P0: 0
- P1: 6
- P2: 4
- New total: 10
