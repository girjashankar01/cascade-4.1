# Component Inventory & Technical Specification

Extracted from Cascade 4.1 front end (`frontend/src/components/`, `frontend/src/features/`, and `frontend/src/design/components.css`).

All components are authored natively with standard HTML5 elements, CSS variables, and zero external widget libraries (no Radix, no Tailwind, no shadcn, no Mantine).

---

## Component Matrix Overview

| Component | Source File | CSS File | HTML Element | Key Props / Variants | Accessibility |
|---|---|---|---|---|---|
| **Button** | `src/components/ui/Button.tsx` | `design/components.css` | `<button>` | `variant`: `primary`, `secondary`, `quiet` | Focus-visible outline, disabled state, tap highlight reset, touch target ≥ 44px |
| **Icon** | `src/components/ui/Icon.tsx` | `design/components.css` | `<svg>` | `name`: 18 icon types | `aria-hidden="true"`, stroke 1.6, vector paths |
| **VerdictMark** | `src/components/ui/StatusMark.tsx` | `features/workbench/workbench.css` | `<span>` | `verdict`: `VERIFIED`, `MISMATCH`, `UNSUPPORTED`, `UNCERTAIN` | Plain language text paired with semantic icon |
| **StatusMark (Legacy)** | `src/components/ui/StatusMark.tsx` | `design/components.css` | `<span>` | `outcome`: `allowed`, `blocked` | Compatibility alias for VerdictMark |
| **ThemeToggle** | `src/components/ui/ThemeToggle.tsx` | N/A | `<Button>` (secondary) | N/A | `aria-label`, visible text label, persists in `localStorage` |
| **LockObject** | `src/components/lock/LockObject.tsx` | `design/components.css` | `<svg>` | `engaged`: boolean | Role `img`, dynamic `aria-label`, respects `reducedMotion` |
| **LazyLock** | `src/components/lock/LazyLock.tsx` | `design/components.css` | `<div>` wrapper | `engaged`: boolean | Code-split lazy chunk, error boundary fallback to static icon |
| **Radio & Checkbox** | Native elements | `design/components.css` | `<input type="radio/checkbox">` | Native checked state | Custom styled pseudo-elements, `forced-colors: active` support |
| **Text Input & Select** | Native elements | `components/layout/WorkbenchShell.css` | `<input type="text">`, `<select>` | Standard form controls | Focus ring, min-height 3rem (48px), 16px font prevents iOS zoom |
| **TechnicalDrawer** | `features/workbench/TechnicalDrawer.tsx` | `features/workbench/workbench.css` | `<dialog>` | `result`: `RunResult \| null` | Native `showModal()`, focus trap on Tab, Escape support, backdrop |
| **RenameDialog** | `components/layout/WorkbenchShell.tsx` | `components/layout/WorkbenchShell.css` | `<dialog>` | Form modal | Modal backdrop, focus trap, form actions |
| **ActionComparison** | `features/workbench/RunResult.tsx` | `features/workbench/workbench.css` | `<div>` / `<article>` | Side-by-side approved vs submitted | Diff highlighting on mismatch, tabular numeric amounts |
| **DiffTable** | `features/workbench/RunResult.tsx` | `features/workbench/workbench.css` | `<table>` | `diffs`: `FieldDiff[]` | Accessible table headers (`th scope="col"`), monospace values |
| **BalanceComparison** | `features/workbench/RunResult.tsx` | `features/workbench/workbench.css` | `<div>` (ARIA table) | `before`, `after`: `BalanceSnapshot` | Role `table`/`row`/`cell`/`columnheader`/`rowheader`, animated numbers |
| **AttestationBadge** | `features/workbench/RunResult.tsx` | `features/workbench/workbench.css` | `<div>` | Present vs Absent | Semantic messaging, colored indicator bar |
| **CheckSequence** | `WorkbenchShell.css`, `workbench.css` | `WorkbenchShell.css` | `<ol>` / `<li>` | Step sequence | Step current / complete / pending states |

---

## Detailed Component Specifications

### 1. Button

- **File**: `frontend/src/components/ui/Button.tsx`
- **CSS**: `frontend/src/design/components.css` (lines 2–8)
- **Props**:
  - `variant`: `'primary'` (default) | `'secondary'` | `'quiet'`
  - `type`: `'button'` (default) | `'submit'` | `'reset'`
  - `className`: string
  - Standard HTML button attributes & `ref`
- **Dimensions**:
  - `min-height`: `var(--control-height)` (3rem / 48px)
  - `padding`: `var(--space-3) var(--space-5)` (0.75rem 1.5rem / 12px 24px)
  - `gap`: `var(--space-3)` (0.75rem / 12px)
  - `border-radius`: `var(--radius-md)` (0.5rem / 8px)
  - `border-width`: `var(--border-width)` (1px)
  - `font-size`: `var(--text-sm)` (1rem / 16px)
  - `font-weight`: `var(--weight-semibold)` (600)
- **Variant Styling**:
  - **Primary**:
    - Background: `var(--color-action)` (#f2b35c)
    - Color: `var(--color-action-ink)` (#17231d)
    - Border: `var(--color-action-border)` (Light: #8a5a18, Dark: #f2b35c)
    - Shadow: `var(--shadow-control)` (Light: `0 2px 0 #6b420b`, Dark: `0 2px 0 #a67232`)
    - Hover: Background `var(--color-action-hover)` (Light: #e9a74a, Dark: #fac479)
    - Active: Background `var(--color-action-active)` (Light: #e4a044, Dark: #e9a74a), transform `translateY(var(--motion-press-y))` (1px), shadow `none`
  - **Secondary**:
    - Background: `transparent`
    - Color: `var(--color-text)`
    - Border: `var(--color-control-border)` (Light: #748278, Dark: #81988b)
    - Shadow: `none`
    - Hover / Active: Background `var(--color-recessed)`
  - **Quiet**:
    - Background: `transparent`
    - Color: `var(--color-text)`
    - Border: `transparent`
    - Shadow: `none`
    - Hover / Active: Background `var(--color-recessed)`
  - **Disabled (all variants)**:
    - Background: `var(--color-recessed)`
    - Color: `var(--color-muted)`
    - Border: `var(--color-control-border)`
    - Cursor: `not-allowed`

---

### 2. Icon

- **File**: `frontend/src/components/ui/Icon.tsx`
- **CSS**: `frontend/src/design/components.css` (line 1)
- **Props**:
  - `name`: `'arrow' | 'check' | 'stop' | 'sun' | 'moon' | 'lock' | 'unlock' | 'reset' | 'workspace' | 'plus' | 'edit' | 'close' | 'scenario' | 'run' | 'result' | 'balances' | 'details' | 'menu'`
  - `className`: string
- **Dimensions & SVGAttributes**:
  - ViewBox: `0 0 24 24`
  - `fill`: `none`
  - `stroke`: `currentColor`
  - `strokeWidth`: `1.6`
  - `strokeLinecap`: `round`
  - `strokeLinejoin`: `round`
  - `aria-hidden`: `true`
  - Default size: `var(--icon-size)` (1.25rem / 20px)
  - Brand header icon size: `var(--brand-size)` (2rem / 32px)
  - Large fallback lock size: `var(--lock-fallback-size)` (5rem / 80px)

---

### 3. VerdictMark / StatusMark

- **File**: `frontend/src/components/ui/StatusMark.tsx`
- **CSS**: `frontend/src/features/workbench/workbench.css` (lines 60–66) & `design/components.css` (lines 13–15)
- **Tokens & Variants**:
  - Container: `inline-flex`, items centered, gap `var(--space-2)` (0.5rem), border-radius `var(--radius-sm)` (0.25rem), font-size `var(--text-sm)` (1rem / 16px), font-weight `var(--weight-semibold)` (600), white-space `nowrap`.
  - **VERIFIED**:
    - Text: "Verified — matched the approved plan"
    - Icon: `check`
    - Color: `var(--color-success, #16a34a)`
    - Background: `color-mix(in srgb, var(--color-success, #16a34a) 12%, transparent)`
  - **MISMATCH**:
    - Text: "Mismatch — stopped before money moved"
    - Icon: `stop`
    - Color: `var(--color-danger, #dc2626)`
    - Background: `color-mix(in srgb, var(--color-danger, #dc2626) 12%, transparent)`
  - **UNSUPPORTED**:
    - Text: "Unsupported — requires manual review"
    - Icon: `details`
    - Color: `var(--color-attention, #ca8a04)`
    - Background: `color-mix(in srgb, var(--color-attention, #ca8a04) 12%, transparent)`
  - **UNCERTAIN**:
    - Text: "Uncertain — check details before retry"
    - Icon: `result`
    - Color: `var(--color-muted, #6b7280)`
    - Background: `color-mix(in srgb, var(--color-muted, #6b7280) 12%, transparent)`

---

### 4. Lock Illustration (LockObject & LazyLock)

- **File**: `frontend/src/components/lock/LockObject.tsx` & `LazyLock.tsx`
- **CSS**: `frontend/src/design/components.css` (lines 9–12)
- **Container**:
  - Class: `.lock-frame`
  - Width: `min(100%, var(--lock-width))` (23rem / 368px)
  - Aspect Ratio: `var(--lock-ratio)` (`360 / 390`)
- **Animation**:
  - Library: `motion/react` (`LazyMotion` with `domAnimation`, `m.g`)
  - Target: Shackle SVG `<m.g>` element
  - Y-position:
    - Unlocked / Open: `var(--lock-rest-y)` (-40px)
    - Engaged / Closed: `var(--lock-engaged-y)` (0px)
  - Transition:
    - Duration: `var(--motion-duration-explain)` (0.6s)
    - Easing: `cubic-bezier(0.2, 0, 0, 1)`
    - Reduced Motion: 0s duration (immediate snap)
- **Shading & Gradients**:
  - Steel shackle: 5-stop linear gradient (`--lock-steel-dark`, `--lock-steel-light`, `--lock-steel-mid`)
  - Metal body: 3-stop linear gradient (`--lock-metal-top`, `--lock-metal-mid`, `--lock-metal-bottom`)
  - Brass cylinder: 2-stop linear gradient (`--lock-brass-light`, `--lock-brass-dark`)
  - Contact shadow: SVG `<ellipse>` with `fill: var(--lock-shadow)` and `opacity: var(--lock-shadow-opacity)` (0.13 Light, 0.30 Dark)

---

### 5. Native Form Controls (Radio & Checkbox)

- **CSS**: `frontend/src/design/components.css` (lines 17–25)
- **Appearance**: `appearance: none;`
- **Radio**:
  - Circle `border-radius: 50%`
  - Unchecked: background `--color-canvas`, border `--color-control-border`
  - Checked: background `--color-action`, border `--color-action-border`
  - Indicator: `::before` pseudo-element dot, size `var(--radio-dot-size)` (0.5rem / 8px), color `--color-action-ink`
- **Checkbox**:
  - Square `border-radius: var(--radius-sm)` (0.25rem / 4px)
  - Unchecked: background `--color-canvas`, border `--color-control-border`
  - Checked: background `--color-action`, border `--color-action-border`
  - Indicator: `::before` pseudo-element checkmark: width `var(--check-width)` (0.375rem / 6px), height `var(--check-height)` (0.75rem / 12px), rotated 45deg, border color `--color-action-ink`
- **Accessibility**:
  - Focus ring: `outline: var(--focus-width) solid var(--color-focus); outline-offset: var(--focus-offset);`
  - Forced colors mode: `@media (forced-colors: active) { appearance: auto; }`

---

### 6. TechnicalDrawer & Modals

- **File**: `frontend/src/features/workbench/TechnicalDrawer.tsx`
- **CSS**: `frontend/src/features/workbench/workbench.css` (lines 37–46)
- **HTML Element**: `<dialog className="technical-drawer">`
- **Properties**:
  - Position: `fixed; inset: 0 0 0 auto;` (slide-out right rail)
  - Width: `min(100%, var(--drawer-max))` (36rem / 576px)
  - Height: `100%`
  - Background: `var(--color-surface)`
  - Border: `border-left: var(--border-width) solid var(--color-control-border)`
  - Shadow: `var(--shadow-float)` (`0 12px 32px rgb(...)`)
  - Backdrop: `::backdrop { background: var(--dialog-backdrop); }` (`rgb(0 0 0 / 0.45)`)
- **Keyboard Handling**:
  - Custom Tab trap cycling inside active dialog buttons
  - Escape closes modal and returns focus to trigger button
  - Page scroll lock: `:root:has(.technical-drawer[open]) { overflow: hidden; }`

---

### 7. Balance Counter & Table

- **File**: `frontend/src/features/workbench/RunResult.tsx` (lines 167–219)
- **Structure**: ARIA table using CSS Grid (`role="table"`, `role="row"`, `role="cell"`)
- **Animation**:
  - Animate number count from starting balance to end balance using Motion `animate(0, 1000, ...)`
  - Duration: `var(--motion-duration-explain)` (0.6s)
  - Respects reduced motion (snaps immediately to formatted total)
  - Layout stability: invisible `.balance-reserve` element reserves maximum text width to prevent layout jitter while numbers tick up/down
  - Font styling: `font-variant-numeric: tabular-nums;`
