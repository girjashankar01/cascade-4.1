# Frontend — design foundations (Stage 1)

React + TypeScript + Vite. Stage 1 implements the shared design system and an interactive style tile. The workbench, API adapters, payment runs, and landing story belong to later stages. Backend and contracts are unchanged.

From this directory:

```powershell
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm run build
npm run lint
npm run typecheck
npm run check:contrast
```

Open [the style tile](http://127.0.0.1:5173/style-tile?theme=light) and use the theme button to compare light/dark. `?theme=light` or `?theme=dark` takes precedence over the saved preference. Blocked browser storage does not stop the page rendering. `/` is a temporary review alias; the style tile will be removed from the shipped application before Stage 5.

Use **Engage the lock**, **Release the lock**, example radio choices, and **Reset preview**. These are visual controls; no payment is sent. **Reduce preview motion** makes transitions instant and scrolling native. The operating system reduced-motion preference is also respected. Reset restores the lock and example choice, while preserving accessibility preferences.

Production review:

```powershell
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Then open [the built style tile](http://127.0.0.1:4173/style-tile?theme=dark). There is no backend requirement for Stage 1. Fonts and assets are served locally; the initial dependency install requires registry access.

Shared values: `src/design/tokens.css`. Font faces: `src/design/fonts.css`. Reusable styles: `src/design/components.css`. The lock and Motion load as a separate chunk with a reserved-size static fallback. The technical monospace family is reserved but not loaded outside the future technical drawer.

See [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md), [licenses](../LICENSES-AND-SOURCES.md), and the builder's [Stage 1 handoff](../handoff/STAGE-1-BUILD.md). Reviewer-owned files are independent evidence and are never edited by the builder.
