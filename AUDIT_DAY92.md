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
