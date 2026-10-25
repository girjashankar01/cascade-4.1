# Frontend — execution workbench (Stage 3)

React + TypeScript + Vite. The owner skipped the marketing landing page; `/` opens `/app` directly. Stages 1 and 2 passed independent review. Stage 3 adds four runnable scenarios, progress, result comparisons, exact before/after balances, reset and a technical drawer. The remaining pages are Stage 4; pitch and final polish remain later stages. Backend and contracts are unchanged.

```powershell
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm run build
npm run lint
npm run typecheck
npm run check:contrast
npm test
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Open [the built workbench](http://127.0.0.1:4173/app?mode=demo), choose a scenario, read its plan, and select Run safety check. Demo data never calls the backend. A pays 1,000,000 test USDC to the approved recipient; B1 stops the changed recipient/amount; B3 rejects the hidden software change; C restores the starting state without approving a payment. The labelled demo sequence illustrates the fixture. Repeat payment/upgrade runs restore their starting balances, with an explicit note. Reset demo restores the current workspace and clears its selection/result.

Use New, Rename and Close for independent workspaces. ArrowLeft/ArrowRight/Home/End switch tabs. A run continues in its original workspace when navigating away. Run/reset, source switching, scenario changes and closing the busy workspace are guarded. Phones have a page selector and bottom section navigation. Theme and reduced motion persist across routes/reload; both manual and system reduced motion disable movement.

The result compares the plan and the submitted action and states whether money was stopped, unknown, or not applicable. Amounts are exact integer strings/BigInt. All amounts are test tokens. Show technical details opens the single native side drawer; Tab wraps, Escape closes and focus returns. Hash/address values are shortened there with full-value Copy; no invented transaction evidence is attached to fixtures.

`?mode=live` selects the local service for the initial workspace; new tabs start with demo data. `VITE_API_BASE_URL` is public config (default http://127.0.0.1:8000), never a key. Live run sends one explicit changing request after connection checks. Live reset runs existing scenario C and affects all live workspaces; older records are marked historical. A timed-out submitted operation is not retried or unlocked automatically. If unavailable, switch to Demo data and use Reset demo. Missing backend deployment/upgrade dependencies remain an external integration limitation; no real live run is claimed verified.

The initial dependency install requires registry access. Fonts/assets are local. Tests use Node 24's native TypeScript runner, verified on 24.13.0. The production `/style-tile` URL redirects to the workbench; the tile is development-only. The lock is a lazy chunk with a static fallback. Token/style files live in `src/design/`; runtime data boundaries live in `src/data/`. No component calls fetch.

See [Stage 3 build handoff](../handoff/STAGE-3-BUILD.md), [contract assumptions](../CONTRACT-ASSUMPTIONS.md), [design system](DESIGN-SYSTEM.md) and [licenses](../LICENSES-AND-SOURCES.md). Independent review is required before Stage 4.
