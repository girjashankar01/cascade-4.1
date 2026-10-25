# Frontend redesign decisions

2026-10-26 — Work in nested cascade-4.1 checkout on abhigyan-frontend; user explicitly restricted GitHub pushes to this branch, and enclosing checkout has unrelated deletions.
2026-10-26 — Stage 0 creates documentation only; supplied builder prompt requires human plan approval and independent review before Stage 1.
2026-10-26 — Retain DAO Accountability Engine as product name; repository, backend and reviewer charter agree.
2026-10-26 — Scenario C means Clean reset and seed; show Allowed · Reset as expected mark and Reset complete as result, with payment comparison not applicable, matching runner semantics.
2026-10-26 — Do not describe C as an entire chain wipe; implementation clears selected demo records and deploys/seeds contracts.
2026-10-26 — Default to labelled offline demo data; live runner depends on absent deploy_and_seed.py and absent upgrade contract sources.
2026-10-26 — Local live API base proposed as http://127.0.0.1:8000 via public VITE_API_BASE_URL; README supplies address, not proof of uptime.
2026-10-26 — Reuse C as explicit live reset only after integration verification; never invent /reset, rely on ignored reset_first, or silently simulate live completion.
2026-10-26 — Preserve React/TypeScript/Vite/Oxlint toolchain and bootstrap; current App has no reusable workflow/API logic.
2026-10-26 — Propose Context/reducer plus React Router; isolated workspace records share one live chain and one global live-operation lock.
2026-10-26 — Treat success=true as runner completion, not allowance; adapt verdict/execution/reset separately and fail closed on missing or contradictory evidence.
2026-10-26 — Keep exact token amounts as integer strings/BigInt; do not infer unknown balances as zero or display unsourced USD valuations.
2026-10-26 — Propose graphite/ink-green and off-white with amber, green/red only for Allowed/Blocked; all theme pairs require measured contrast in Stage 1.
2026-10-26 — Propose self-hosted Space Grotesk, Source Sans 3 and drawer-only IBM Plex Mono; verify font licenses and record sources before inclusion.
2026-10-26 — Build original inline SVG/CSS lock, restrained Motion, landing-only Lenis; verify package compatibility/licenses before installation.
2026-10-26 — Use available measured/manual design checks if named external design databases/detectors are unavailable; never claim unrun tools.
2026-10-26 — Explain approved intent versus protected execution without implying OpenZeppelin Governor permits post-vote calldata substitution.
2026-10-26 — Keep reviewer-owned files untouched and preserve existing reviewer commits; builder handoffs carry actual checks and known weaknesses.
2026-10-26 — Owner explicitly requested Stage 1 while Stage 0 was under review; review a7c786a has since arrived as PASS WITH NOTES with no BLOCKER/MAJOR, so proceed within Stage 1 only.
2026-10-26 — Address R0-01/R0-02/R0-03 in PLAN.md by adding live-integration delivery dependency, canonical font-license links, and a typed StoryFrame sequence; request reviewer re-verification rather than close issues ourselves.
2026-10-26 — Address R0-04 by removing the temporary style tile before Stage 5; root is a temporary review alias until routing is built. Reviewer marked R0-05 FIXED in afbd1fc on human plan approval; retain defaults for planning and validate the actual event environment before rehearsal.
2026-10-26 — Ship Space Grotesk 500 and Source Sans 3 400/600 Latin WOFF2 only, with swap and local fallbacks; IBM Plex Mono is installed/reserved but not loaded until a technical drawer exists.
2026-10-26 — Verify installed OFL/MIT/0BSD runtime notices and copy them to public/licenses so deployment retains them; tslib 2.8.1 is 0BSD, verified from its installed notice and package metadata. No borrowed component library is needed.
2026-10-26 — Use native labelled radio/checkbox controls and original UI primitives, explicit focus outlines, no entrance-hidden content, and a lazy original SVG lock with a static fallback.
2026-10-26 — Lock motion occurs only after a user action; CSS is the single source of duration/easing/position tokens, with system reduced-motion rules and an additional style-tile preview override.
2026-10-26 — Use token-derived WCAG contrast calculation for supported semantic text/focus/control pairs and manual browser/DOM checks; do not claim unavailable Impeccable/axe/OS emulation ran.
2026-10-26 — Owner explicitly skipped the landing page; root redirects to /app, marketing/story/mini-demo/Lenis work is omitted, and the style tile is now development-only with production redirect to the workbench.
2026-10-26 — Stage 2 uses React Router 7.18.4 and Context/reducer workspace sessions; open/close/rename, per-tab selection/source/record state, roving tab keys, and a fresh demo tab when the last closes.
2026-10-26 — Fix R1-02 by moving reduced-motion override into the shared preference provider and persisting it across routes/reload; OS reduced motion still takes precedence through CSS/Motion. R1-01 monospace import remains deferred to the actual technical drawer.
2026-10-26 — On phones use a labelled workspace-page selector and a permanent bottom section bar, keeping page navigation distinct from workspace tabs and section jumps.
2026-10-26 — Components receive safe view models; only the client/data API knows fetch/paths. Health confirms service and local-chain state separately; missing balances/actions are unavailable, never fabricated zeros or fixture substitutes in live mode.
2026-10-26 — Use exact integer-string/BigInt demo amounts, per-workspace fixture services, explicit reset semantics and a global live lock; unconfirmed POST outcomes are not retried or automatically unlocked, including after reload where storage is available.
2026-10-26 — Stage 2 includes scenario selection and empty run/result/page surfaces for shell review; the run button stays explicitly unavailable until Stage 3, while the full fixture run/reset service is tested independently.
2026-10-26 — Use Node 24's native TypeScript test runner for meaningful adapter, fixture, concurrency and reducer invariants; no extra test framework or browser-runtime dependency is required.
2026-10-26 — Stage 2 reviewer PASS bbc7716 authorizes Stage 3. R2-01 is addressed by connecting Run to a provider-owned lifecycle that survives route/tab changes and prevents immediate duplicate requests.
2026-10-26 — Demo Read/Lock/Check/Enforce uses token-derived illustrative timing; live waits remain indeterminate. Reduced motion runs the authored sequence immediately; no intermediate service progress is fabricated.
2026-10-26 — Exact BigInt balance interpolation uses Motion with reserved numeric space and final accessible labels; no token amount passes through floating-point arithmetic.
2026-10-26 — R1-01 is addressed by loading local IBM Plex Mono Latin 400 WOFF2, used only in the technical drawer. Native modal semantics plus explicit bidirectional keyboard wrapping preserve focus; Escape closes and returns to the trigger.
2026-10-26 — Technical output is an allowlist of validated hashes/addresses and known fields, with full-value copy. No arbitrary response bodies, JSON, errors, credentials or invented fixture transaction hashes are displayed.
2026-10-26 — Reset demo clears selection/result and restores its fixture balances. Explicit live reset uses existing scenario C, affects the shared local environment and is disabled when unavailable or uncertain; switching to demo is always explicit.
