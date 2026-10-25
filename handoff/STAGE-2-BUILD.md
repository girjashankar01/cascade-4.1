# Stage 2 build handoff — workbench shell and data boundary

Date: 2026-10-26 (Asia/Calcutta)
Status: BUILD COMPLETE; INDEPENDENT STAGE 2 REVIEW PENDING.
Source baseline: a3973a8, independent Stage 1 PASS. Branch: abhigyan-frontend only.

## Scope change authorized by owner

The owner explicitly requested skipping the landing page and continuing. Root `/` now redirects to `/app`; there is no marketing landing, hero/story, mini-demo, pinned marketing scene or Lenis dependency. Stage 5 is marked skipped in PLAN.md. The style tile is development-only; its old production URL redirects to the workbench. This does not remove the workbench's later execution/pitch requirements.

## Built

- React Router shell with workspace tabs and per-session pages: Workbench, Payment request, Approved plan, Record of what happened, What this does and does not cover. Remaining pages currently use honest empty states, not invented content.
- Independent session state using Context/reducer: add, activate, rename, close; per-tab scenario/source/result/phase; close-last creates a fresh empty demo workspace. In-progress state guards block source change/reset/reselection/close. A data-layer global live-operation lock is shared across workspaces.
- Roving keyboard tabs: ArrowLeft/ArrowRight/Home/End. Active tab stays visible when the strip is resized or a new tab opens; contained strip overflow never causes page overflow. Rename uses a native dialog, blank-name validation, 40-character limit, Escape/cancel behavior and focus restoration.
- Desktop section rail that collapses to icons, expands on hover/focus, and can keep labels visible. Explicit expansion allocates layout space; hover/focus expansion is a floating overlay. Phones use a permanent bottom bar. Five sections: Scenario, Run, Result, Balances, Details.
- Scroll tracking, smooth section jumps, reduced-motion instant jumps, repeated same-anchor navigation, and correct selection when multiple final sections share the page-bottom scroll position. User scrolling resumes visibility-based tracking.
- A compact phone page selector keeps page navigation distinct from session tabs and section navigation.
- Shared theme/reduced-motion preference above routes. Router synchronizes source/theme query flags without replacing history metadata. Preference persistence is guarded; system reduced-motion CSS still applies independently. R1-02 is addressed in code and appended to STAGE-1-BUILD.md for re-review.
- Thin API boundary: client.ts alone fetches; api.ts owns endpoint paths/coordination; adapters.ts validates unknown payloads and returns clean view models. Demo mode never initializes the live client or calls the network, including when live configuration is invalid.
- Four authored fixture scenarios, exact raw token amounts/BigInt formatting, independent fixture sessions, full run/reset/balance services and immutable returned snapshots. C records prior fixture balances before restoring initial state; it is a reset, not a payment.
- Read-only live connection status with service/chain state separated, known local-chain gating, friendly fallback to demo data, retrying only the read, and sanitized developer-copy feedback. Unknown balances remain unavailable rather than guessed zeros.
- Live response validation, no POST retry, one shared operation lock, and persisted unconfirmed-operation marker where sessionStorage is available. Timeouts/errors after submission never silently unlock another live run or pretend a demo reset was live.
- CONTRACT-ASSUMPTIONS.md with exact response requirements, omissions, external backend risks and reset semantics. React Router and transitive notices added to LICENSES-AND-SOURCES.md and public/licenses.

Stage 2 is a shell/data review preview. Scenario selection and baseline demo balances work in the UI. Run remains explicitly unavailable; the actual progress/result/before-after/reset/drawer UI belongs to Stage 3. The full offline run/reset service is exercised by tests, not falsely presented as a completed UI flow.

## Files changed

| Area | Files |
|---|---|
| Routing/preferences | frontend/src/App.tsx, app/ThemeProvider.tsx, theme.ts, WorkspaceProvider.tsx, workspace-context.ts, workspaces.ts |
| Shell/navigation | components/layout/WorkbenchShell.tsx, WorkbenchShell.css, WorkspaceTabs.tsx, SectionRail.tsx; components/ui/Icon.tsx |
| Views | pages/WorkbenchPage.tsx, WorkspacePage.tsx; StyleTilePage.tsx shared preference follow-up |
| Data | data/types.ts, fixtures.ts, adapters.ts, client.ts, api.ts; hooks/useConnection.ts |
| Tokens/tooling | design/tokens.css, package.json/package-lock.json, tsconfig.tests.json, index.html |
| Tests | frontend/tests/data.test.ts, workspaces.test.ts |
| Notices/docs | public/licenses/{react-router-dom,react-router,cookie,set-cookie-parser}-MIT.txt; CONTRACT-ASSUMPTIONS.md; LICENSES-AND-SOURCES.md; frontend/README.md and DESIGN-SYSTEM.md; PLAN.md/DECISIONS.md; STAGE-1-BUILD.md follow-up; this handoff |
| Builder evidence | handoff/builder-evidence/stage-2/ screenshots and measurement/route/navigation JSON |

No backend, contract, root script, backend fixture or runtime database edits. No reviewer-owned file edits. Builder screenshots live in builder-evidence/, never the reviewer's screenshots/ folder.

## Run and review

From frontend/ (Node 24 recommended; tested 24.13.0):

```powershell
npm ci --ignore-scripts --no-audit --no-fund
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Open `http://127.0.0.1:4173/app?mode=demo` (production) or port 5173 (development). Both loopback servers were left running for review; restart if needed. No backend is required for demo mode. `?mode=live` requests read-only status from the configured local service. No live POST or reset was started during browser QA.

## Verification performed

| Check | Actual result |
|---|---|
| Production build | PASS; TypeScript project build + Vite 8.3.5 |
| Lint | PASS, no warnings/errors after fixing synchronous effect-state resets by keying async state to the current request |
| Typecheck | PASS, app/build projects plus a separate strict TypeScript check of the tests and core data/reducer modules |
| Native Node tests | PASS, 16 tests: all four fixture outcomes/conservation/reset, no demo network calls, isolation, busy/reset guards, unknown/mismatched/contradictory responses, unavailable balances, exact formatting, local-chain gating, sanitized errors, shared live lock, timeout/no retry, tab isolation and close-last behavior |
| Contrast | PASS, existing 46 semantic pairs. No new text/status colors; new controls use measured tokens |
| Responsive | Full-page screenshots and DOM measurements at 360/390/768/1280/1920 in both themes; 0 main overflow, page scroll width <= viewport width, active tab visible in every case. Representative phone/tablet/desktop screenshots visually inspected in both themes |
| Tab state | Browser observed first tab A and second tab B1 after keyboard switching; rename validation/Save/focus restoration; last tab close produced a new ID, one tab, no selection and demo source |
| Preferences | Reduced-motion override survived route change and reload; CSS read auto/zero duration. Restored the test preference to false. Toggling preference does not jump to a stale section anchor |
| Desktop rail | Selected Balances remains selected at page bottom even while Details is also visible; same-anchor Scenario click returns to its target after manual scrolling; wheel scrolling resumed view-based tracking |
| Expanded rail | Pinned rail does not overlap main content; switching that pinned state to a phone viewport still has a fixed bottom bar and no page overflow |
| Phone routing | Labelled page selector opens Record page; bottom Scenario link returns to the workbench, preserving the selected scenario |
| Error/fallback | Actual unreachable local service displayed a plain sentence and Use demo data control; unavailable live balances were not shown as zero |
| Route checks | Trailing-slash Payment request deep link renders; unknown route has a usable return link; `/` and production `/style-tile` both redirect to the workbench |
| Console | Clean new production demo session across route checks returned no warn/error entries. The intentional unreachable-live check produces expected browser network-failure diagnostics, not an uncaught application error or a raw on-page trace |
| Integrity | Backend/contract/root script/backend fixture paths unchanged relative to baseline; no reviewer-file edits. git whitespace checks run before commit |

Production output is about 292 kB entry JS (92.8 kB gzip), 22.4 kB CSS (4.9 kB gzip), and 44.66 kB of Latin WOFF2 fonts. No landing/style-tile/Motion lock chunk is shipped in this production stage. These are build sizes, not measured load-time or frame-rate claims.

## Evidence

`builder-evidence/stage-2/` contains the ten light/dark full-page layout captures and measurements.json; live-fallback.jpg; rename-dialog.jpg; section-navigation.jpg; mobile-sections.jpg; route-checks.json; navigation-checks.json; final preview capture. Full-page mobile screenshots capture the fixed bottom bar at the first viewport boundary; inspect mobile-sections.jpg or the live page for its actual viewport behavior.

The navigation issue discovered during self-review (a clicked Balances item being replaced with Details at a clamped page-bottom position) was fixed and reproduced successfully in the production browser. Repeated same-anchor clicks and preference toggles were checked as part of that repair. The initial fixture-concurrency test awaited a rejected second run before checking reset, inadvertently allowing the first run to finish; assertion order was corrected to check reset while the first promise was still pending. No failed check is left unresolved.

## Known limits / deliberately not done

- Stage 3 execution UI, technical drawer, animated balance comparisons and visible demo reset are not implemented yet. Stage 4 pages are intentionally empty shells. No live transaction or backend repair was performed.
- Backend deployment/upgrade dependencies remain missing; live runner integration is unverified. The backend can suppress partial balance-read errors, so live balances are reported rather than independently verified. See CONTRACT-ASSUMPTIONS.md.
- An uncertain live run stays blocked until its real record/backend state is reconciled; there is no invented job-status endpoint or generic automatic unlock. A second browser application session is not a shared frontend coordinator; backend concurrency protection remains necessary.
- Workspace sessions are in memory; reload creates a new session. User preferences persist where storage is permitted. No cross-window preference synchronization is claimed.
- True OS/browser media emulation, screen-reader auditory testing, axe/Impeccable detectors and physical-device performance testing were not available/run. Manual override, keyboard/DOM checks, contrast and screenshots were used. The system media rules remain in source.
- No full browser network-blocking offline harness was run. Fixture tests explicitly assert zero network calls; fonts/assets are locally bundled. Initial dependency install requires registry access.
- R1-01 monospace remains deferred until the actual technical drawer. Landing-only work is omitted by owner instruction, not silently deferred.

## Next gate

Independent reviewer: write STAGE-2-REVIEW.md; re-verify R1-02 and ownership/integrity; check tabs, modes, rail, mobile selector and contract assumptions. Do not treat the unavailable Stage 3 run button as a working execution flow. No Stage 3 code has started. Proceed only after the Stage 2 verdict satisfies the staged review rules.
