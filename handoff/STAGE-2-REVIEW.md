# STAGE 2 REVIEW

**Date:** 2026-10-26  
**Build files reviewed:** `handoff/STAGE-2-BUILD.md`, `CONTRACT-ASSUMPTIONS.md`, `LICENSES-AND-SOURCES.md`, `handoff/DECISIONS.md`, `handoff/PLAN.md`  
**Build identifier:** Baseline commit `a3973a8` (independent Stage 1 PASS) + Stage 2 implementation; verified on production build (`dist/`)  
**Verdict: PASS**

All checklist criteria pass. Zero BLOCKER, zero MAJOR, zero MINOR issues. One NIT noted for Stage 3 planning.

---

## Checks Executed & Observations

### 1. Build Health & Unit Testing
- `npm run build`: **PASS** (Vite 8.3.5 production build transforms 45 modules cleanly).
  - Production footprint: `dist/assets/index-RLBjAvWS.js` (291.97 kB / 92.73 kB gzip); CSS `index-BLHtVhlm.css` (22.39 kB / 4.85 kB gzip); WOFF2 Latin fonts (44.66 kB).
- `npm run lint`: **PASS** (Oxlint checked 30 files across 116 rules; 0 warnings, 0 errors).
- `npm run typecheck`: **PASS** (both `tsconfig.app.json` and strict test suite `tsconfig.tests.json` pass with 0 errors).
- `npm test`: **PASS** (16 native Node test suites passed in 263ms).
  - Verified exact 6-decimal integer-string conservation across all 4 scenarios (A, B1, C, B3).
  - Verified zero network requests in demo mode even when configured with malformed live URLs.
  - Verified multi-tab state isolation and global live-operation lock.
  - Verified rejection of floating numbers, missing deployments, and ambiguous zero balances.
  - Verified safe failure and non-allowance on malformed/contradictory run responses.

### 2. API Layer Isolation & Boundary Enforcement
- Inspected the entire `frontend/src/` codebase for `fetch`:
  - **Zero components, hooks, or pages call `fetch` directly.**
  - Network requests are strictly confined to [`frontend/src/data/client.ts`](file:///c:/Users/abhig/OneDrive/Desktop/Cascade%204.1/cascade-4.1/frontend/src/data/client.ts) (with orchestration in `api.ts` and view model adaptation in `adapters.ts`).
  - Components consume only strongly-typed view models (`Scenario`, `ActionSummary`, `Connection`, `Balances`, `RunResult`).
  - No secret keys, private keys, or wallet credentials exist anywhere in the frontend code.

### 3. Shell Architecture, Workspace Tabs & Section Rail
- **Workspace Tabs ([`WorkspaceTabs.tsx`](file:///c:/Users/abhig/OneDrive/Desktop/Cascade%204.1/cascade-4.1/frontend/src/components/layout/WorkspaceTabs.tsx)):**
  - Full tab lifecycle: add new tab, switch tabs, rename (via accessible native modal `<dialog>` with focus trap and 40-character limit), and close.
  - Roving keyboard navigation: `ArrowRight`, `ArrowLeft`, `Home`, `End` verified with proper `aria-selected` and `tabIndex`.
  - Closing the final workspace safely returns a fresh empty demo workspace.
  - Contained tab strip overflow (`overflow-x: auto`) with `ResizeObserver` maintaining active tab visibility.
- **Section Rail ([`SectionRail.tsx`](file:///c:/Users/abhig/OneDrive/Desktop/Cascade%204.1/cascade-4.1/frontend/src/components/layout/SectionRail.tsx)):**
  - Five sections tracked: `Scenario`, `Run`, `Result`, `Balances`, `Details`.
  - Collapses to icons by default, expands on hover and focus. Has an explicit pin toggle button allocating layout space (`aria-pressed`).
  - Smooth/instant scrolling respects user and system reduced-motion preference.
  - Page bottom clamping logic correctly selects the terminal section.
  - Mobile adaptation: at viewports <= 44rem (704px), the rail seamlessly transforms into a permanent 5-column fixed bottom navigation bar reachable without hover or clipping.

### 4. Router & Scope Alignment
- Root `/` cleanly redirects to `/app?mode=demo`.
- Sub-pages properly routed: `/app/payment-request`, `/app/approved-plan`, `/app/record`, `/app/coverage`.
- `/style-tile` is strictly gated behind `import.meta.env.DEV` (redirects to `/app` in production).
- 404 route displays plain-language recovery ("This page is not available. Your workspaces are still here.") with a return link.
- Landing page skip authorized by human owner is properly reflected in `PLAN.md` and `DECISIONS.md`.

### 5. Plain Language, Honesty & Connection Resilience
- Glossary wording strictly adhered to:
  - "Payment request", "Approved plan", "Record of what happened", "What this does and does not cover"
  - "The shared fund", "Approved recipient", "The bad actor"
  - "Local demonstration. No real money."
- Unreachable live service produces a polite explanation ("The local service is available. The chain is not connected.") with a 1-click "Use demo data" fallback and sanitized developer diagnostic copy.
- Zero raw hashes or contract addresses displayed in default UI.
- [`CONTRACT-ASSUMPTIONS.md`](file:///c:/Users/abhig/OneDrive/Desktop/Cascade%204.1/cascade-4.1/CONTRACT-ASSUMPTIONS.md) created and matches adapter implementation.
- Backend, contract sources, scripts, and fixtures remain 100% untouched (`git diff HEAD -- backend/ contracts/ scripts/ fixtures/ data/` returns 0 changes).

---

## Findings

### R2-01 — NIT — `WorkbenchPage.tsx` — Preparation for Stage 3 Centerpiece Execution UI
**What I saw:** The execution button in the `#run` section is disabled with the label "Run safety check ->" and helper text "Payment runs are unavailable in this preview."  
**Analysis:** This is completely appropriate for the Stage 2 shell scope, as Stage 3 will introduce the full interactive execution runner, live simulation progress, before/after diffs, and drawer.  
**Fixed looks like:** In Stage 3, wire the Run button to the workspace execution lifecycle.

---

## Re-verification of Previous Findings

| ID | Short Description | Status | Evidence |
|---|---|---|---|
| R1-01 | Reserved monospace font unimported until Stage 3 technical drawer | **OPEN** | Remains deferred to Stage 3 as planned when the technical drawer is built. |
| R1-02 | Reduced-motion preference integrated into shared ThemeProvider | **FIXED** | Verified `ThemeContext` in `theme.ts` manages `reduceMotion` and `setReduceMotion`. Verified `WorkbenchShell.tsx` and `StyleTilePage.tsx` synchronize with this state and respect system `prefers-reduced-motion`. |

---

## Summary

Stage 2 establishes a rock-solid, accessible shell and a bulletproof, typed data boundary. The tests prove rigorous handling of concurrency, timeouts, and response validation.

**Verdict:** **PASS**. Codex is cleared to begin **Stage 3 (Centrepiece — Four Scenario Flows, Results, Balances, and Technical Drawer)**.
