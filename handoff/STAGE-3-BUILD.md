# Stage 3 build handoff — execution workbench

Date: 2026-10-26 (Asia/Calcutta)
Status: BUILD COMPLETE; INDEPENDENT STAGE 3 REVIEW PENDING.
Baseline: bbc7716, independent Stage 2 PASS. Branch: abhigyan-frontend only.

## Built

- All four fixture scenarios now run from the workbench: A transfers exactly 1,000,000 test USDC to the approved recipient; B1 stops the substituted recipient and doubled amount; B3 rejects the hidden software change without a payment; C restores the starting fixture environment and states that the money-stopped question is not applicable.
- Approved preview before running; a four-step illustrative demo sequence with token-derived timing; lazy original lock engaging as the plan locks. Live waiting is indeterminate and never presents timed demo steps as observed service progress.
- Provider-owned operations survive page/tab changes. A synchronous per-workspace pending guard prevents duplicate starts before React commits state. Busy workspaces cannot reselect, switch source, reset, run again or close. Independent demo workspaces may run separately; the existing global live coordinator still serializes live work and retains uncertain submitted operations without retry/unlock.
- Safe result comparison, explicit difference highlight, plain reason and money-stopped answer. Unsupported/uncertain results stay Needs review. Missing action details say Comparison incomplete. No live result uses fixture substitutes.
- Three-role before/after balance table. Motion interpolates exact BigInt amounts, with final accessible labels and reserved numeric width. No raw amount is converted to floating point. Manual/system reduced motion shows final values immediately. Missing readings remain unavailable and do not imply protection.
- Reset demo restores the current fixture, clears selection/result, and announces completion. Live reset explicitly invokes existing C, affects the shared local environment, and is disabled while unavailable or uncertain. Switching to demo remains explicit. Later live completions mark other live records historical.
- One closed native technical side drawer, with labelled heading, initial focus, explicit forward/backward Tab wrapping, Escape close, restored trigger focus, full-value copy and friendly copy feedback. Page scrolling is locked while open. Validated hashes/addresses are shortened; arbitrary response bodies, nested errors, credentials and invented fixture hashes never render.
- Local IBM Plex Mono Latin 400 WOFF2, used only in technical values. No new package dependency or borrowed component/artwork.
- Updated frontend README, design system, contract assumptions, source/license table, PLAN and DECISIONS. Landing remains skipped; no Stage 4/6/7 work is claimed complete.

## Files changed

- `frontend/src/app/{WorkspaceProvider.tsx,workspace-context.ts,workspaces.ts}`: persistent execution lifecycle, progress/reset state, cross-workspace historical records.
- `frontend/src/pages/WorkbenchPage.tsx`: run controls, guards, progress, error/fallback, result, balances/reset and drawer entry.
- `frontend/src/features/workbench/{RunResult.tsx,TechnicalDrawer.tsx,workbench.css}`: original result/balance/drawer presentation and responsive rules.
- `frontend/src/data/technical.ts`: strict display allowlist over retained evidence.
- `frontend/src/components/ui/Button.tsx`, `frontend/src/design/{fonts.css,tokens.css}`: React 19 ref support and shared drawer/lock/font values.
- `frontend/tests/{data.test.ts,workspaces.test.ts}`: allowlist, reset lifecycle, completion isolation and historical-record tests; existing adapter/concurrency tests retained.
- Documentation listed above and this build file; screenshots/measurements under `handoff/builder-evidence/stage-3/`. No reviewer-owned files changed.

## Run and review

From `frontend/`, install with `npm ci` if needed, then `npm run build` and `npm run preview -- --host 127.0.0.1 --port 4173 --strictPort`. Open `http://127.0.0.1:4173/app?mode=demo`. Existing local preview remains on port 4173; development server on 5173. No backend is required for fixtures.

Choose a scenario, inspect its plan, Run safety check, then inspect Result/Balances/Details. Compare A and B1 in two workspaces. Try C after A, repeat B1, and Reset demo. Toggle reduced motion and both themes. In Details, open the drawer, cycle Tab/Shift+Tab, copy a field, then Escape. Local service selection performs only a connection check until an explicit run/reset; no live changing operation was performed during this build.

## Checks actually run

| Check | Result |
|---|---|
| Production build | PASS, TypeScript + Vite 8.3.5; final CSS-only scroll-lock repair rebuilt successfully |
| Lint | PASS, no warnings/errors |
| Type checks | PASS, application and strict test/data configuration |
| Native Node tests | PASS, 20 tests; exact fixture conservation/reset, no-network demo, strict response mapping, uncertain POST/timeout lock, concurrency, safe technical output, reset guards, tab isolation and historical records |
| Contrast | PASS, 46 supported semantic text/control/focus pairs; no semantic color changes |
| Browser scenarios | A, C after A, B1, repeated B1 and B3 all completed with correct plain outcomes and exact before/after labels; checks.json records outputs |
| Busy guards | Run/reset/source/radios disabled immediately during ordinary-motion A; navigation to Payment request and back retained completed A. Opening another tab during A preserved independent A/B1 records |
| Reset | Reset demo cleared selected radio and result, restored fund/recipient/bad actor to 1,000,000/0/0 and announced completion |
| Layout | Completed B1 result checked at 360, 390, 768, 1280, 1920 in both themes: zero horizontal page overflow; no technical code outside drawer; full-page captures saved |
| Motion | Ordinary A showed real intermediate displayed balances (902,000 fund and 98,000 recipient) with final accessible labels 0/1,000,000 and stable reserved width. Manual reduced motion completed all fixture outcomes without invisible/stuck content |
| Drawer | Forward/backward wrap verified, Escape restored trigger. Copy scenario feedback succeeded; IBM Plex Mono loaded. Final 360px drawer spans viewport with no overflow and background scroll hidden |
| Live fallback | Unavailable local service showed explicit demo fallback; live run/reset disabled. No live POST was sent |
| Integrity | Backend/contracts/root scripts/backend fixtures/data unchanged relative to bbc7716; no reviewer-file edits; Git whitespace check before commit |

The clean production demo console is captured in `console.json`; expected network failure from the separate deliberate unavailable-live check is not a demo application exception. Browser screenshots are manual/DOM-assisted verification, not a claimed automated Playwright regression suite.

Final production sizes: entry JS 370.99 kB / 121.01 kB gzip; lazy LockObject 35.60 kB / 12.44 kB gzip; runtime 0.59 kB / 0.36 kB gzip; CSS 27.88 kB / 5.66 kB gzip; four local WOFF2 fonts total 59.36 kB. These are bundle sizes, not measured device performance. Motion is now used by the execution interface as requested.

## Findings addressed / self-review repairs

- R2-01: Run now connects to the workspace lifecycle and actual fixture/live data service. The preview-only disabled run surface is removed.
- R1-01: technical monospace now has an actual local WOFF2 face and is used in the implemented drawer. Reviewer re-verification is requested; reviewer-owned issue statuses remain untouched.
- Native dialog Shift+Tab initially allowed focus to the browser chrome instead of wrapping to the last button. Added explicit bidirectional wrapping and reverified both ends and Escape restoration in the final build.
- The native dialog's default max-width initially narrowed the phone drawer and left two vertical scrollbars. Explicit maximum width and root scroll lock were added, rebuilt and rechecked at 360px.

## Known limitations / deliberately not done

- Stage 4 remaining pages still use honest empty shells. Pitch walkthrough is Stage 6. Stage 7 full regression/performance/polish and independent final verdict remain outstanding. Landing/Stage 5 stays omitted by owner instruction.
- Missing backend deployment script and upgrade contracts remain external dependencies. Live changing operations and reconciliation of uncertain live outcomes are not verified. The frontend does not invent a job-status endpoint, unlock a timed-out POST, or repair backend/contracts.
- The live service does not provide observable intermediate progress. Its action preview can be unavailable before a run; the interface says so and offers demo mode for a complete preview. No fixture evidence is passed off as live.
- The technical drawer intentionally displays only validated allowlisted fields, not a raw JSON dump. Fixtures have no invented transaction hashes/contract addresses. Detailed source/history pages arrive in Stage 4.
- Workspace records remain in memory. A full reload starts fresh workspaces; only preferences and the uncertain-live marker persist. Cross-browser-session chain coordination still requires backend protection.
- No actual browser network-blocking harness, OS media emulation, screen-reader auditory review, axe/Impeccable tooling, device throttling or physical-device benchmark was run. Existing no-network fixture tests and local assets support offline use; Stage 7 must record the available final checks honestly.
- Full-page screenshots show sticky/fixed bars at their capture scroll position. Phone drawer/balance viewport images and the live page are clearer evidence of those layers than the composited full-page image.

## Next gate

Independent reviewer: write `STAGE-3-REVIEW.md`, verify R1-01/R2-01, all four flows, duplicate-run prevention, route/tab persistence, reset, safe live fallback, numeric precision, reduced motion, technical-data hiding, drawer focus/copy and responsive layouts. No Stage 4 source has started. Proceed only after a passing Stage 3 verdict with no open BLOCKER/MAJOR, according to the supplied handoff protocol.
