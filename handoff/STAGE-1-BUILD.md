# Stage 1 build handoff — design foundations

Date: 2026-10-26 (Asia/Calcutta)
Status: BUILD COMPLETE; independent Stage 1 review PASS in a3973a8.
Branch: `abhigyan-frontend` only. Source baseline: `a7c786a` (independent Stage 0 PASS WITH NOTES).

## What was built

- A complete responsive style tile at `/style-tile` with `/` as a temporary alias. Palette, typography, primary/secondary/disabled buttons, native choice controls, outcome marks, and an original tactile metal lock are reviewable together.
- Central design tokens for both themes, typography, spacing, size, radius, focus, shadows, artwork materials, and motion. Shared component styles are separate from page layout.
- Light/dark theme control with guarded saved preference and explicit `?theme=light` / `?theme=dark` overrides. Defaults are configurable by ThemeProvider for later route needs.
- Space Grotesk 500 and Source Sans 3 400/600, self-hosted as three Latin WOFF2 assets with swap/fallbacks. IBM Plex Mono is reserved/installed but not imported into this page.
- Original SVG lock with a user-triggered shackle movement. The open state has a visibly lifted right leg; the engaged state seats it into the body. Lazy chunk, fixed-size loading fallback, render/chunk error boundary, and state-specific fallback symbols preserve the page.
- System reduced-motion support plus an explicit Reduce preview motion checkbox. Zero-duration transforms and native scrolling; text never depends on an entrance animation.
- Accessible labels, skip-to-main navigation, keyboard radio selection, visible focus, native disabled Run payment button with explanation, and an announced lock status. Reset preview restores the example choice and lock without changing accessibility preferences.
- Actual installed font/runtime license notices shipped under public/licenses and recorded in LICENSES-AND-SOURCES.md. Original icons/favicon, no borrowed component kit, no stock imagery.
- R0 plan improvements and appended fixes, without modifying reviewer-owned files.

This is a visual foundation. It makes no backend calls, sends no payment, and shows no live results. The two choice examples are labelled Demo data · test tokens and Expected outcome.

## Files changed

| Area | Files |
|---|---|
| Bootstrap | frontend/src/App.tsx, index.css; remove old App.css |
| Tokens and shared styles | frontend/src/design/tokens.css, fonts.css, global.css, components.css, motion.ts |
| Theme state | frontend/src/app/ThemeProvider.tsx, theme.ts |
| Primitives | frontend/src/components/ui/Button.tsx, Icon.tsx, StatusMark.tsx, ThemeToggle.tsx |
| Lock | frontend/src/components/lock/LockObject.tsx, LazyLock.tsx |
| Review page | frontend/src/pages/StyleTilePage.tsx, StyleTilePage.css |
| Packaging | frontend/package.json and package-lock.json; frontend/index.html; original public/favicon.svg; remove unused public/icons.svg; public/licenses/*.txt |
| Documentation | LICENSES-AND-SOURCES.md, frontend/README.md, frontend/DESIGN-SYSTEM.md, handoff/PLAN.md, DECISIONS.md, STAGE-0-BUILD.md fixes, this file, STAGE-1-CONTRAST.md |
| Builder evidence | handoff/builder-evidence/stage-1/*.jpg and measurements.json |

Backend, contract sources, backend fixtures and root scripts are unchanged (diff checked against a7c786a). Reviewer-owned STAGE-0-REVIEW.md, OPEN-ISSUES.md and REVIEWER-CHARTER.md are untouched. Builder screenshots are deliberately in builder-evidence/, not the reviewer's screenshots/ folder.

## How to run

From the nested repository's frontend/ directory:

```powershell
npm ci --ignore-scripts --no-audit --no-fund
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173/style-tile?theme=light` or `?theme=dark`.

Production:

```powershell
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Open `http://127.0.0.1:4173/style-tile`. Both loopback servers were left running for local review at handoff; restart with these commands if they stop. No public deployment was made.

## Verification performed

| Check | Actual result |
|---|---|
| Dependency installation | Exact Motion 14.6.0 and font package versions installed; npm dependency tree resolves without peer errors. Package manifests/lockfile updated; no new UI kit |
| Production build | PASS: npm run build (includes TypeScript project build), Vite 8.3.5 |
| Lint | PASS: npm run lint (Oxlint), no findings printed |
| Explicit typecheck | PASS: npm run typecheck, no errors printed |
| Contrast | PASS: npm run check:contrast; 46 semantic pairs, 0 failures. Text including disabled text >=4.5:1, focus/control borders >=3:1. Full ratios in STAGE-1-CONTRAST.md |
| Responsive/browser | Screenshots at 360, 390, 768, 1280, 1920 CSS-pixel widths in both themes. DOM overflow count 0, document scroll width equals viewport width in all 10 cases; checked phone/tablet/desktop layouts visually |
| Fonts | Browser document.fonts.check confirms display/body fonts; no remote element URLs; CSS imports local WOFF2 only. Three WOFF2 files in production output, total about 44.66 kB |
| Keyboard | Enter/Space engage the lock; arrow keys change the native radio group; Reset preview restores ready/valid state; focus outline observed on the card; skip link moves focus to main; theme button keyboard activation works |
| Theme persistence | Toggle to dark on URL without explicit theme, reload production page, observe dark theme retained. Explicit query overrides also observed and update when toggled |
| Reduced motion | Preview override checked in real browser; explanation duration reads 0s, scroll-behavior auto, lock state changes, 0 hidden headings. Repeated on production build; system preference was false and NOT emulated |
| Production runtime | Built app at 4173 loads with correct fonts/lock; keyboard choice/lock/reset and reduced preview controls work; Run payment stays disabled |
| Console | Dev and production warn/error log queries returned empty arrays after interactions |
| Content/honesty | No addresses, payloads, hashes, chain IDs or error traces in the page. Preview-only and test-token wording visible; no invented result or metric |
| Anti-slop | Manual source and rendered review: neutral base, bounded material gradients only inside lock, no decorative glass/halos/grids/neon/gradient text, no icon tiles/stripe cards/nested cards, no automatic looping motion |
| Integrity | git diff --check passed; backend/contracts/root scripts unchanged; reviewer files untouched |

Final build output (not a performance benchmark): entry JS 232.17 kB / 72.74 kB gzip; lazy lock + Motion chunk 88.34 kB / 30.91 kB gzip; CSS 17.79 kB / 4.21 kB gzip. The lock has its own chunk; main text remains present through loading. No frame-rate, LCP/CLS, throttled mobile or physical-device performance claim is made in this stage.

## Evidence and review path

- builder-evidence/stage-1/light-{360,390,768,1280,1920}.jpg and matching dark files: full-page layout matrix.
- measurements.json: exact viewport/overflow results and reduced-preview values.
- preview-light.jpg and preview-dark.jpg: production lock engaged state.
- keyboard-choice-dark.jpg: visible selected Recipient changed radio, amber focus outline and expected Blocked mark in production.
- reduced-motion-dark.jpg: production content with reduced preview enabled and lock engaged.

Suggested reviewer sequence: open light → dark → 360px → return to desktop → keyboard Engage → radio arrow keys → Reset → Reduce preview motion + Engage → inspect production build and contrast report. Check system media emulation independently if available.

## Known limits / not claimed

1. No Stage 2 router/workspaces/API layer, Stage 3 runner/balances/technical drawer, landing page or pitch mode. All paths currently reach this temporary visual page through Vite's fallback. Route handling belongs to Stage 2. Remove the shipped style tile before Stage 5 as recorded for R0-04.
2. No technical drawer exists yet, so the technical monospace face is not loaded or demonstrated outside one. No backend contracts are changed or live integrations verified.
3. The browser tool exposes viewport control but no prefers-reduced-motion emulation. The explicit preview override was exercised; system media CSS and Motion user preference support were source-reviewed. This is not a claim of true OS emulation.
4. Impeccable, UI UX Pro Max and axe were not available/run in this stage. Review used measured contrast, native semantics, DOM/keyboard checks and screenshots. No automated full accessibility certification or screen-reader auditory test is claimed.
5. Font-loading fallback and error-boundary code are present; the initial Suspense fallback was observed, but an intentionally rejected production chunk was not injected to test the error boundary.
6. The missing backend deploy_and_seed.py/upgrade sources remain external live-mode dependencies; API URL/pitch device are planning defaults to verify operationally before rehearsal. These do not affect this offline visual stage.
7. Fonts/assets are local, but no network-blocking offline harness was run. A cold dependency install still needs registry access.

## Stage 0 findings addressed for re-review

R0-01, R0-02, R0-03: plan additions implemented. R0-04: removal policy explicit. R0-05: reviewer marked FIXED in afbd1fc following human plan approval; actual event setup still needs operational verification before rehearsal. See the Fixes section in STAGE-0-BUILD.md. Only the reviewer may mark findings closed.

## Next gate

Please write `handoff/STAGE-1-REVIEW.md` and independently re-verify the Stage 0 plan fixes. Stage 2 has not started. The builder will address BLOCKER/MAJOR findings and request re-review before moving on, unless the human explicitly changes the staged workflow.

## Stage 2 follow-up fixes for re-review

R1-02: Reduced-motion override now belongs to ThemeProvider, with guarded persistence and a root CSS attribute. StyleTilePage consumes the shared preference and no longer deletes it on unmount. Browser checks confirmed it survives workbench route changes and reload, and changing it does not navigate to the current section anchor. Please re-verify and close this NIT if confirmed. R1-01 remains deliberately deferred until the Stage 3 technical drawer.
