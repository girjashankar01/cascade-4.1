# Design foundations

One CSS token file defines the palette, typography, spacing, radius, control sizes, artwork materials, depth and motion: src/design/tokens.css. Components refer to semantic variables. SVG coordinates are illustration geometry, not layout values. Structural zero/percentage values, SVG strokes/coordinates, and media-query thresholds are explicit where CSS variables cannot express them.

## Themes and type

The workbench defaults light; explicit query theme wins, then saved preference, then default. Theme switching is immediate, synchronized through React Router. Preference storage failures are non-fatal. The owner skipped the landing page, so no separate marketing theme or landing route is built. The design tile is development-only.

Space Grotesk 500 is used for display; Source Sans 3 400/600 for text and controls. All visible text is at least 16px, body 18px, with 1.5 line-height. Line length is constrained by the text's role: 70ch for long reading, 42ch for supporting columns. Balanced headings and pretty body wrapping avoid stranded words. Font-display swap preserves readable text while local WOFF2 assets load. IBM Plex Mono is reserved for technical details and is not imported in Stage 1.

## Surfaces and signals

Canvas, surface and recessed are neutral levels. Amber denotes an action, focus or selected choice. Green/Allowed and red/Blocked always carry a word and an icon and are never used for connection indicators. All supported normal text pairs exceed 4.5:1; focus/control boundaries exceed 3:1. See ../handoff/STAGE-1-CONTRAST.md for the actual token-derived measurements. Decorative dividers and the original metal illustration are not interactive boundaries or text.

No decorative glass, panels inside cards, neon, radial halos, backdrop grids, gradient typography, icon tiles, or infinite status animations. Material gradients exist only inside the original metal lock. Modest primary-button depth is attached to a pressable control. Cards use a clear outline and selected radio state without a shadow or accent stripe.

## Layout and inputs

Content max-width 80rem; gutter clamps from 20px to 64px. Breakpoints are documented in tokens.css and applied in page layout: 44rem stacks editorial columns; 68rem reduces palette columns and allows stacked choice headings. Above that the palette has six swatches. Below 44rem it has two.

Buttons have a 48px minimum height; clickable labels provide at least 44px hit targets around the native radio/checkbox elements. Their visual marks are styled with measured tokens, retaining native focus/keyboard semantics and reverting to native appearance in forced-colors mode. Focus uses a 3px outline and 4px offset. A skip link targets a focusable main landmark. Result-like lock state changes announce through role=status; example choices are explicitly expected outcomes using demo data.

## Motion and loading

The lock does not autoplay or oscillate. A user action moves the shackle using only transform with a 600ms settled ease. Duration/easing/position are read from CSS by design/motion.ts. Both system reduced-motion and a style-tile preview override set movement to zero and scrolling to auto. Content never starts invisible. LazyLock reserves illustration dimensions, provides open/closed static symbols while loading, and catches illustration render/chunk failure so page text and controls remain available.

The reduced-motion override is additional to, and cannot disable, the system preference. It now belongs to ThemeProvider and persists across route changes and reload (R1-02). True browser media emulation is not exposed by the current browser tool; manual override testing does not claim OS emulation.

## Review boundary

Stage 2 adds the routed workbench shell: scenario sessions in header tabs; per-session pages in text links or a phone selector; section jumps in a collapsed desktop rail or permanent phone bottom bar. Only section labels expand over content. Native dialog semantics handle renaming, with validation and focus restoration. Other pages have honest empty states until Stage 4.

The data boundary is separate from components. Demo runs/reset are available to the service/tests; the execution UI remains unavailable until Stage 3. The style tile is already excluded from the production application and its old URL redirects to /app. No marketing landing is built.
