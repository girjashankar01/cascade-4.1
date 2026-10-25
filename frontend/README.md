# Frontend — workbench shell (Stage 2)

React + TypeScript + Vite. The owner skipped the marketing landing page; `/` opens `/app` directly. Stage 2 adds routing, workspace tabs, section navigation, the data/fixture boundary and shared preferences. The run button is still unavailable in this review preview; Stage 3 adds the execution UI. Remaining workspace pages currently show truthful empty states. Backend and contracts are unchanged.

From this directory:

```powershell
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm run build
npm run lint
npm run typecheck
npm run check:contrast
npm test
```

Open [the workbench](http://127.0.0.1:5173/app?mode=demo). Use New, Rename and Close to compare independent scenario workspaces. ArrowLeft/ArrowRight/Home/End switch workspace tabs. On phones, pages use a labelled selector and sections use a visible bottom bar. On desktop, the section rail expands on hover/focus and can keep its labels visible.

Theme and reduced-motion preference survive route changes and reload. Explicit `?theme=light` / `?theme=dark` takes precedence on initial load and stays synchronized through the router. `?mode=live` selects the local service for the initial workspace; new workspaces start in demo mode. The local-service check is read-only and offers demo data when unavailable. Demo mode makes no backend calls. No payment is sent by this preview.

Production review:

```powershell
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Then open [the built workbench](http://127.0.0.1:4173/app?mode=demo). The old `/style-tile` URL redirects to the workbench in production; the design tile remains available only on the development server. No backend is needed for demo mode. Fonts and assets are local; the initial dependency install requires registry access. Tests use Node 24's native TypeScript test runner (tested on 24.13.0).

Shared values: `src/design/tokens.css`. Font faces: `src/design/fonts.css`. Reusable styles: `src/design/components.css`. The original lock remains available for Stage 3 and is absent from the Stage 2 production bundle because the development tile is excluded. Technical monospace remains reserved for the future closed drawer.

Set public `VITE_API_BASE_URL` to change the service address (default http://127.0.0.1:8000). Never add keys or credentials. Read [CONTRACT-ASSUMPTIONS.md](../CONTRACT-ASSUMPTIONS.md) for response validation, exact balances, global live-operation locking and reset semantics. A timed-out submitted operation is not retried; uncertain live state stays blocked while demo work remains available.

See [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md), [licenses](../LICENSES-AND-SOURCES.md), and the builder's [Stage 2 handoff](../handoff/STAGE-2-BUILD.md). Reviewer-owned files are independent evidence and are never edited by the builder.
