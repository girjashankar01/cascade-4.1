# Frontend redesign plan — Stage 0

Date: 2026-10-26 (Asia/Calcutta)
Status: Stage 0 approved/reviewed; Stage 1 PASS; Stage 2 built, pending independent review. Stage 0 itself changed no application code.
Scope update, 2026-10-26: the owner explicitly requested skipping the landing page. Marketing sections, hero/story, pinned landing sequence, mini-demo, landing-only Lenis and landing social assets are omitted. `/` now redirects directly to `/app`. Continue the workbench stages and their review gates. The original landing proposals below are historical context, superseded by this update.
Product: DAO Accountability Engine (existing repository name; no invented brand).
Repository: `https://github.com/girjashankar01/cascade-4.1.git`
Working checkout: `C:/Users/abhig/OneDrive/Desktop/Cascade 4.1/cascade-4.1`
Required branch for all commits and pushes: `abhigyan-frontend`. Never push to `main`, force-push, or stage the enclosing checkout's deletions.
Application baseline: `a135632` (`mvp`). Existing reviewer setup: `92d787d`. Preserve both histories.

## 1. Scope and review gate

Build the landing page and workbench in the existing React/TypeScript/Vite application. Backend, contracts, fixtures used by backend tests, and backend configuration remain untouched. This plan uses the builder prompt as the frontend workflow authority, the supplied design spec as visual guidance, and executable repository code as evidence of implemented backend behavior. The older backend stage numbering is separate from frontend stages 0–7.

After each stage, write `STAGE-N-BUILD.md` and stop. Read the independent `STAGE-N-REVIEW.md`, fix every BLOCKER/MAJOR, append fixes to the build file, and await re-review. Stage 1 requires human plan approval AND a passing Stage 0 review. Missing review is pending, never approval. Never write reviewer verdicts, screenshots, OPEN-ISSUES.md, REVIEWER-CHARTER.md, or FINAL-REVIEW.md.

## 2. Existing frontend inventory (complete)

| File / item | Current behavior | Treatment |
|---|---|---|
| `frontend/src/main.tsx` | React StrictMode, createRoot, global CSS import | Keep bootstrap and StrictMode |
| `frontend/src/App.tsx` / App | Single static page identifying the product, Stage 0 scaffold, trust-model footer | Replace after plan gate; retain factual product name and trust limitations |
| `frontend/src/App.css` | One narrow column, heading, badge, bordered section, footer | Replace with token-based component/layout styles |
| `frontend/src/index.css` | Inter/system stack, dark palette, basic reset | Replace; Inter violates the new brief |
| `frontend/index.html` | English, viewport, title, favicon, root | Keep HTML/bootstrap; update title/description/preview in Stage 5 |
| `frontend/public/favicon.svg`, `icons.svg` | Existing scaffold assets | Inspect/remove unused scaffold assets when replaced |
| `frontend/src/assets/hero.png`, `react.svg`, `vite.svg` | Unreferenced scaffold assets | Do not borrow as new product imagery |
| `frontend/vite.config.ts` | React plugin only, no API proxy | Keep Vite; introduce explicit API base configuration in adapter |
| TypeScript configs | Project references, noEmit, unused/fallthrough checks | Keep and run `tsc -b` |
| `.oxlintrc.json` | Oxlint with React/hooks/TypeScript rules | Keep; fix findings rather than disable checks |
| `package.json` / lockfile | React/ReactDOM 19; Vite 8; TypeScript 6; build includes typecheck; lint uses oxlint | Preserve toolchain; add only necessary frontend dependencies after approval |
| `frontend/README.md` | Scaffold commands only | Replace incrementally with accurate usage and pitch instructions |

Existing routes/pages: only App at the default Vite entry; no router or secondary pages. Existing components: App only. Existing API calls: NONE (no fetch, clients, hooks, or service calls). Existing frontend data shapes, state stores, fixtures, forms, or workspace logic: NONE. There is no working dashboard logic to preserve.

## 3. Repository and backend inventory

Inspected root README, handoff.md, decisions.md, both docs handoff/build-guide documents, all frontend source/configuration, backend routes/main/schema/database, scenario runner, verification/report/decoder/simulation interfaces and scenario tests. Reviewed the project source tree excluding vendored dependency internals, binary PDFs/images, caches and environments. No AGENTS.md was found in the workspace search.

Backend modules: FastAPI routes/main; SQLite database; ingestion PDF/OCR; claims normalization/grounding/conflicts/coi; hosted/local/hybrid LLM routing and caching; manifest canonicalization/hashes/builder; chain client/attestation; verification decode/simulate/rules; scenario runner. Contracts currently contain MockToken, GovernanceRegistry, Treasury, GuardedExecutor and the Counter sample. Tests and fixture documents exist separately. Keep these as read-only integration sources.

### Available API inventory (not currently called by frontend)

| Method and path | Inputs / returned shape | Planned frontend use |
|---|---|---|
| GET `/health` | status, rpc_connected, chain_id, block_number, rpc_url | Separate backend/chain availability; technical fields only in drawer |
| POST `/sources` | Uploaded file or pasted content/filename/content_type; source_id and metadata | Payment request source intake if live integration is ready |
| GET `/sources` | Array of id, sha256, filename, content_type, storage_path, page_count, ocr_used, created_at | Source list with safe names |
| GET `/sources/{source_id}` | Metadata plus extracted_pages | Evidence quotation/page context |
| POST `/analyze/{pid}` | Optional source_ids/prompt; AnalysisResponse | Evidence analysis; safe status mapping |
| GET `/claims/{pid}` | proposal_id, claims[], conflicts[], cache_status | Payment request claims and contradictions |
| GET `/proposals/{pid}/coi` | Conflict-of-interest report from coi module | Out of main flow; no invented graph or identity claims |
| GET `/audit/{pid}` | Array of analysis records including provider/model/cache/fallback/errors/hashes | Plain-language record page; raw details drawer |
| POST `/manifest/{pid}` | token_address, decimals, version, text/source, previous hash; draft | Optional live draft flow; never expose key inputs |
| POST `/manifest/{pid}/confirm` | Draft inputs plus optional proposer_private_key; confirmed record | Do not build a private-key form or embed keys; use backend defaults only if validated |
| GET `/manifest/{pid}` | Optional version; manifest record and canonical_json | Approved plan and version metadata |
| POST `/commit/{pid}` | Optional version/registry/proposer key/RPC; commitment record | Optional explicit live action, not automatic on page load |
| POST `/approve/{pid}` | Optional version/registry/governance key/RPC; approval record | Explicit simulated approval only if included; never imply community voting |
| GET `/versions/{pid}` | Version records with commitments/approval/chain flags | Plain-language approved-plan history |
| POST `/verify-version/{pid}` | Optional manifest/text/evidence/version/registry/RPC; integrity report or tamper fields | Integrity status with honest uncertainty |
| POST `/verify`, `/verify/{pid}` | proposal_id, target, value, data, optional addresses/key/TTL/RPC; VerificationReport | Runner owns primary demo; no technical transaction form in default UI |
| POST `/execute`, `/execute/{pid}` | Action, verdict/deadline/signature and optional addresses/key/RPC; success, tx_hash, block_number, status | No automatic retry; prefer single runner action |
| GET `/verifications/{pid}` | Verification records with rules/diff/simulation/decoded_tx/attestation/execution fields | Result and record enrichment |
| GET `/deployments` | Deployment/role addresses and RPC | Technical drawer only; never treats addresses as connection proof |
| GET `/balances` | Optional rpc_url/recipient; connected, token_address, treasury/recipient/attacker objects | Before/after balances; raw integer strings are authoritative |
| POST `/scenarios/{name}/run` | Optional rpc_url/reset_first payload; scenario-specific result | Single scenario execution request, read balances before/after |

### Observed data contracts

- Claim: id, proposal_id, canonical field (amount/token/recipient/purpose/assumptions), normalized value, display_value, quote, source_id, page, confidence, status GROUNDED/UNCERTAIN/REJECTED, validation_details.
- Conflict: same field with value/display/source/quote/page for A and B; status UNRESOLVED. AnalysisResponse adds proposal_id, status, claims/conflicts, provider/model/cache_status, optional summary.
- Approved plan: version plus single action (`erc20_payout` or `proxy_upgrade`), envelope, text/evidence/previous commitments; manifest API wraps status/signature/confirmation and version/action hashes.
- VerificationReport: proposal_id, version, verdict VERIFIED/MISMATCH/UNSUPPORTED/UNCERTAIN, all_passed, rules[], decoded_tx, diff, simulation, optional attestation_sig/deadline/verifier_address/error. Rules contain rule_id, name, status, explanation, evidence.
- DecodedTransaction: target/value/selector/method/support, token/recipient/spender/amount_raw, hashes, decoding_error/diff/matches_manifest. Simulation includes success/restoration, watched balance/allowance/implementation/owner changes; raw details stay hidden.
- A result: scenario/name/proposal_id/success/verdict, steps[], verification_report, execution_result (status/tx_hash/block/gas), state_deltas with raw treasury/recipient before/after.
- B1 result: success=true means runner completed, NOT payment allowed; blocked_as_expected/verdict/diff, null execution_result, defense_layers, revert_details, balances_verified.
- C result: scenario/name/proposal_id/success, steps[], deployments. NO verdict, verification report or payment execution. It resets selected demo database records and deploys/seeds a new environment; it is not an entire-chain wipe.
- B3 result: blocked_as_expected/verdict/diff, null execution_result, defense_layers, revert_details, slot_verified (slot_protected/current/rejected implementation). B2 also exists as benign-upgrade control, but is outside the requested four cards.
- Balance: connected and token_address; each role has address, token_balance (floating display number), token_balance_raw (integer string). Missing contracts or swallowed query errors can resemble zero balances: do not equate HTTP 200/connected=true with validated balances.
- Tables: sources, claims, conflicts, analyses, llm_cache, manifests, versions, verifications. Do not read SQLite directly from frontend.

## 4. Contradictions and defaults

1. Product placeholder resolved to repository/charter name, DAO Accountability Engine. No new logo beyond an original typographic mark and lock motif.
2. Scenario C resolved to **Clean reset and seed** by runner and reviewer charter. Show its expected mark as **Allowed · Reset**, with explanatory text that no payment is being approved. Result says **Reset complete**; money-stopped question is **Not applicable**. Do not fabricate a fourth attack.
3. There is no dedicated `/reset` route, but C is an existing reset operation. Live reset may explicitly call `/scenarios/C/run` only after backend readiness is verified. On failure/unavailability, offer switching to demo mode and resetting local fixtures. Never silently fake a live reset.
4. Prompt says run-response shape is unconfirmed; this checkout exposes actual result variants above. Adapters validate unknown responses at runtime; document fields in CONTRACT-ASSUMPTIONS.md before Stage 2. `reset_first` is declared in the route payload but ignored by its implementation: never rely on it.
5. Live runner imports `scripts/deploy_and_seed.py`, which is absent. Upgrade runner references BoxUUPS/BoxV2/BoxEvil artifacts, but their source contracts are absent. Live scenario execution is an external dependency risk, not verified working functionality. Backend owner supplies fixes; frontend remains fixture-complete.
6. README/handoff still describe backend Stage 3 while newer scenario/verification code exists. Do not translate historical test counts or later code presence into new verification claims. README's old enclosing-Git-root statement is stale for this nested checkout.
7. Final build guide wins over older project handoff on attestation safety, one action (not actions[]), and optional graph. New frontend brief wins on hiding raw data and scope of frontend stages. USD estimates are omitted without a valuation source/time; amounts are test tokens only.
8. The generic story must not claim OpenZeppelin Governor lets transaction data be swapped after voting. Copy: **Keep the payment sent within the plan people approved.** Supporting text: **Compare a payment with the approved plan. Stop changed recipients, changed amounts, and unsupported actions before protected execution.** Mention the prototype's custom protected path and simulated governance in honest limits.

## 5. Proposed routes and files

Routes: `/` landing; `/style-tile` Stage 1 visual review; `/app` current workspace; `/app/payment-request`; `/app/approved-plan`; `/app/record`; `/app/coverage`. The temporary style tile will be removed from the shipped application before Stage 5; Stage 1 uses `/` as a temporary alias for easy review. Invalid routes have a plain-language return link. Workbench section anchors: #scenario, #run, #result, #balances, #details. Route navigation and workspace selection are separate concerns.

```text
frontend/src/
  app/{AppRouter,ThemeProvider,WorkspaceProvider}.tsx
  design/{tokens.css,global.css,motion.ts}
  components/
    ui/{Button,StatusMark,ThemeToggle,Dialog,TechnicalDrawer,CopyButton}.tsx
    lock/{LockObject,LazyLock}.tsx
    layout/{Header,WorkspaceTabs,SectionRail,WorkbenchShell}.tsx
  features/
    workbench/{ScenarioPicker,ActionPreview,RunSequence,RunBar,ResultComparison,
               BalanceTable,ResetControl,WorkspaceEmptyState}.tsx
    landing/{Hero,ProblemReceipts,HowItWorks,MiniDemo,Outcomes,Audience,
             HonestLimits,Roadmap,FinalAction,StoryDialog}.tsx
    pitch/{PitchController,PresenterHints}.tsx
  pages/{LandingPage,WorkbenchPage,PaymentRequestPage,ApprovedPlanPage,
         RecordPage,CoveragePage,StyleTilePage,NotFoundPage}.tsx
  data/{types,client,adapters,api,fixtureService,errors}.ts
  data/fixtures/{scenarios,evidence,records}.ts
  hooks/{useRun,useSectionTracking,useReducedMotionPreference}.ts
  tests/{adapters,fixtures,workspace}.test.ts
frontend/public/{fonts/,social-preview.svg,favicon.svg}
LICENSES-AND-SOURCES.md
CONTRACT-ASSUMPTIONS.md
handoff/{PLAN.md,DECISIONS.md,STAGE-0-BUILD.md,...STAGE-7-BUILD.md}
```

Names are a concrete starting structure; combine trivial modules if splitting adds no value. Keep endpoint strings/fetch/runtime response parsing under data/. Components receive only view models. Lazy-load landing sections, pages and lock; keep text/functional fallbacks visible while chunks load.

### State, workspaces and view models

- React Context + reducer, no extra state library initially. Workspace holds id, editable name, selected scenario, mode, lifecycle phase, immutable completed run snapshot, error, and per-workspace records. Tabs support add/close/rename and keyboard access; closing final tab opens a fresh empty workspace.
- Live chain is shared across tabs: only one live operation globally. Explain that tabs retain previous run records, not isolated chains. A live reset refreshes availability/balances and marks older live records as historical.
- `Scenario`: id A/B1/C/B3, title, story, expected outcome/kind, approved preview. `ActionSummary`: payout/upgrade/reset discriminated union with safe labels; no raw fields.
- `RunResult`: run id, source demo/live, scenario, outcome allowed/blocked/reset/needs-review, safe reason, approved/submitted summaries, differences, optional balance snapshots, paymentStopped yes/no/not-applicable/unknown, step states, record items. TechnicalEvidence is separate and consumed only by the one shared technical drawer.
- Exact values use integer strings/BigInt with explicit decimals, never floating arithmetic. Unknown balances show unavailable; never infer missing values as zero. A passed verification is not execution success. UNSUPPORTED/UNCERTAIN stay needs-review; response contradictions fail closed with a retry/return-to-demo action.
- Timeout/abort ends waiting, not necessarily a backend transaction. Do not retry a live POST automatically or let another live run start until status has been reconciled. In-app route changes preserve in-flight operation state.

## 6. Data, demo mode and reset

Default `?mode=demo`; settings allow demo/live. `VITE_API_BASE_URL` defaults to documented local `http://127.0.0.1:8000` when live is explicitly selected. Deployment override is public config, never secrets. No API/network calls in demo mode. No remote fonts or assets required at runtime.

Fixtures cover scenarios, preview, all step states, result, three-role balances, source claims/quotes/conflicts, approved versions, record, reset, and pitch. Label every fixture surface **Demo data · test tokens**; never present timed animation as an observed backend step. Live requests use indeterminate waiting followed by actual response-derived steps; demo runs may stage Read/Lock/Check/Enforce.

The proposed story fixture is `StoryFrame[]`, each with `id`, `step` (problem/read/lock/check/enforce/result), `label`, `durationMs`, `transcript`, and optional `scenarioId` (A/B1) and visual state. Frame durations total 60,000ms. Playback position, pause/restart and transcript derive from this one typed sequence, isolated from live workspaces and served locally. This is a proposed frontend contract, not an observed backend response.

Initial fixture balances: shared fund 1,000,000 test USDC; recipient 0; bad actor 0. A moves exactly 1,000,000 to recipient; B1 attempts 2,000,000 to bad actor and moves none; B3 moves none and leaves implementation unchanged. C restores the initial fixture state and approved plan. These are explicitly authored demo examples based on runner constants/charter, not recorded live results. Each fixture run begins from its documented starting snapshot so repeated sessions are deterministic; show that reset before replay rather than disguising continuity.

Live flow: validate backend and chain separately, read verified initial balances and approved-plan metadata, POST runner once, adapt the response, read final balances and resolve execution evidence. B3 uses upgrade semantics rather than payment rows invented from a payout. C uses reset semantics. Any missing required metadata keeps the result incomplete with an honest next step. Do not issue a changing operation to discover whether an endpoint exists.

No dedicated reset endpoint is invented. C is offered as explicit **Reset demo environment** in live mode only if the integration works; a fallback changes the visible mode to Demo data and says **Live reset is unavailable. Demo data has been reset.** Unknown live reset completion remains unknown until checked.

## 7. Design system proposal

Direction: graphite/ink-green surfaces, editorial typography and generous spacing, one original physical lock built with inline SVG/CSS. No stock imagery, grid backgrounds, radial halos, neon, gradient headlines or decorative glass. Material shading stays within the lock object. Restrained glass only on genuinely overlapping rail/run bar/drawer. Scenario controls and main button get modest tactile pressed depth; no nested panels.

All shared values live in design/tokens.css (CSS variables), with motion.ts reading shared timing/easing definitions rather than divergent constants. Breakpoints are centralized/documented; layout values use tokens.

| Token family | Initial proposal |
|---|---|
| Light surfaces / text | background #f5f7f4; surface #ffffff; text #17231d; muted #53635a |
| Dark surfaces / text | background #111b18; surface #1b2723; text #f5f7f4; muted #b2beb6 |
| Amber attention/action | dark ink #17231d on #f2b35c; light attention #6b420b on #fbe9cc |
| Allowed only | light #22643c on #e1f0e6; dark #a6dfba on #153d29; paired check icon and word |
| Blocked only | light #9b302e on #f9e9e7; dark #ffc1bd on #4a2423; paired stop icon and word |
| Focus | separate dark/light amber outline with surface separation; measure nontext contrast |
| Fonts | Space Grotesk display; Source Sans 3 text; IBM Plex Mono technical drawer only; self-host WOFF2 with font-display swap and system fallbacks |
| Type | text 16/18/20; labels at least 16; headings 24/32/48/72 with responsive clamp; line-height 1.5 text, 1.08–1.2 display; tabular balances |
| Space | 4, 8, 12, 16, 24, 32, 48, 64, 96 px; readable measure 70ch; content max 1280px; touch target 44px |
| Radius | 4/8/12px; no extreme rounded containers |
| Depth | flat content; one modest interactive shadow and one floating-layer shadow; lock has its own material tokens |
| Motion | quick 120ms; enter 240ms; explain 600ms; cubic-bezier(.2,0,0,1); exits shorter; reduced movement duration 0 |

These are proposals, not verified contrast or license claims. Stage 1 measures every supported text/background pair (4.5:1 normal, 3:1 large), focus/control contrast, and disabled states before approval. Avoid green/red for decoration or generic connection states. Landing defaults dark; workbench defaults light; user override applies intentionally and remains switchable.

Expected font license is SIL OFL 1.1: [Space Grotesk](https://github.com/floriankarsten/space-grotesk/blob/master/OFL.txt), [Source Sans 3](https://github.com/adobe-fonts/source-sans/blob/release/LICENSE.md), and [IBM Plex Mono](https://github.com/IBM/plex/blob/master/LICENSE.txt). Stage 1 verifies the actual installed license notices and preserves them alongside shipped font assets.

Use Motion for animation, Lenis on landing only and disabled for reduced motion. Use React Router for routes and a small accessible dialog primitive if needed; confirm installed compatibility and exact licenses before adding. No broad UI kit. No database/design-tool requirement blocks work: the referenced UI UX Pro Max/Impeccable tools are not assumed installed. If unavailable, document that and perform measured/manual checks; never claim their detectors ran. Record all dependency/font/component sources and license files in LICENSES-AND-SOURCES.md. Use original UI components where practical.

## 8. Interaction, landing and pitch

Workbench rail tracks visible sections with IntersectionObserver. Icons always have accessible names; desktop labels expand on hover/focus plus an explicit expand control. Touch uses a visible bottom bar. Tabs get roving keyboard focus, accessible close labels, and explicit rename UI. Run disabled until selection; run/reset/mode switch disabled during work; live concurrency locked across tabs. Technical drawer closed on entry, no persisted open state, trap/restore focus, Escape closes; shortened hashes/addresses with full-value copy. Developer diagnostics are sanitized and contain no keys.

Landing sequence: hero request-to-lock object; paired problem receipts; one pinned How it works scene (static stacked sequence on phones/reduced motion); two-scenario independent mini-demo; one featured blocked outcome with three secondary rows (including honest Reset); short audience editorial blocks; plain honest limits; evidenced built/next roadmap; final demo link/footer. Alternate compositions. Watch the 60-second story opens a fixture-based narrated animation with play/pause/restart, skip and text transcript; no unavailable-video link or fabricated video. Heavy visuals lazy-load after readable text.

Pitch uses fixtures only, independent from live workspace state: problem → valid payout → substituted payout → lock stops it → balances unchanged. Next/previous/reset controls and ArrowRight/ArrowLeft/Home shortcuts, ignored in editable controls and when a dialog is open. Toggleable presenter hints, visible shortcut guidance, mobile controls, exit restoring focus, reduced-motion instant transitions.

Honest limits everywhere relevant: simulated governance; single trusted verifier; defined watched state only; heuristic upgrade scanning; supported action types; local test chain; demo outcomes are not proof about arbitrary contracts. No numeric security/latency/customer claims.

## 9. Stage delivery and verification

| Frontend stage | Deliverable and meaningful checks |
|---|---|
| 0 | This inventory/plan/decisions/build handoff; baseline install/build/lint/typecheck outcomes; STOP for human + independent review |
| 1 | Tokens, themes, source/license table, original lock, style tile; measured contrast, keyboard and widths in both themes; STOP |
| 2 | Router/shell/tabs/rail and typed fixture/live boundary; adapter unit tests for variant responses and malformed/unknown verdicts; per-tab state and global live lock; STOP |
| 3 | Four scenario flows, preview/progress/result/balances/reset/drawer; fixture invariants, repeat/reset, prevented duplicate runs, offline route interactions, technical-data hiding. Live B3 and A re-seed require the backend owner to supply missing scripts/deploy_and_seed.py and upgrade contracts before live integration can be verified; STOP |
| 4 | Request/plan/record/coverage pages; evidence/conflict/uncertainty/history plus loading/empty/error states and per-workspace context; STOP |
| 5 | SKIPPED by owner: no marketing landing, hero, 60-second story, pinned scene, mini-demo or landing-only dependencies. Root opens the workbench; style tile is development-only already |
| 6 | Fixture pitch, keyboard/navigation/hints, balanced state changes and restoration; offline rehearsal; STOP |
| 7 | Full regression, mobile/accessibility/performance/anti-slop sweep, truthful run/pitch docs; independent FINAL-REVIEW.md required |

At every implemented stage: npm run build (includes tsc -b), npm run lint, explicit typecheck; inspect localhost at 360/390/768/1280/1920 widths and both themes, reduced-motion, keyboard flow, console/network and overflow. Automated browser tests cover user behavior and critical adapter/fixture correctness, not mirrored CSS or snapshots of implementation details. Use accessible browser tooling and axe if available; identify unavailable tooling explicitly. No tests are claimed from source inspection.

Performance checks at final stage: production bundle breakdown, mobile-throttled page load, readable hero before visual chunk, LCP/CLS measurements and screen-size/device conditions recorded. No unmeasured performance promises or claimed real-device testing. Run actual offline request blocking to verify demo views/fonts/fixtures do not depend on network after local app load. Installed dependencies are required to serve/build locally; initial cold download is not promised offline.

## 10. Questions requiring owner input (defaults proposed)

1. Is local-only API hosting correct for the pitch, or is there a deployed backend URL? Default: explicit demo mode; live base `http://127.0.0.1:8000`, configurable via VITE_API_BASE_URL. Do not claim availability.
2. What is the target pitch device and event emphasis? Default: desktop laptop presentation at 1280px+, responsive 360px support; prioritize clear enforcement story, honest limits and deterministic fixtures. No public deployment until requested.

Product, scenario C, workspace semantics, rail behavior, stack and branch are already inferable; no redundant questions. These defaults allow planning; human approval and independent Stage 0 review remain mandatory before app code.

Owner status (2026-10-26): the human explicitly requested starting Stage 1 while review was in progress; the independent verdict has since arrived as PASS WITH NOTES, with no BLOCKER/MAJOR. That authorizes Stage 1. The reviewer marked R0-05 FIXED in afbd1fc following plan approval. Retain the proposed API/device defaults for planning and verify the actual event environment before final rehearsal; no deployed URL or device benchmark is claimed.
