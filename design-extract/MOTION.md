# Motion & Animation Specification

Extracted from Cascade 4.1 front end (`frontend/src/design/motion.ts`, `tokens.css`, `global.css`, `components.css`, `LockObject.tsx`, and `RunResult.tsx`).

---

## 1. Design Principles

1. **CSS as Source of Truth**: All motion durations, curves, and coordinates originate in CSS custom properties. TypeScript functions read tokens dynamically from `getComputedStyle(document.documentElement)` rather than hardcoding values.
2. **Intentional & Functional**: Motion is used exclusively for mechanical feedback (button press), state change communication (lock shackle engaging/disengaging), and numerical clarity (balance changes ticking up/down). No gratuitous floating, bouncing, pulsing, or parallax effects.
3. **Strict Accessibility First**: Full dual-tier reduced motion support via both system-level media query (`prefers-reduced-motion: reduce`) and manual user preference toggle (`data-reduce-motion="true"`). When reduced motion is active, durations collapse to `0s` and translations collapse to `0px`.

---

## 2. Motion Tokens

| Token | Normal Value | Reduced Motion Value | Purpose |
|---|---|---|---|
| `--motion-duration-quick` | `0.12s` (120ms) | `0s` | Micro-interactions: button hover, press feedback, color shifts |
| `--motion-duration-enter` | `0.24s` (240ms) | `0s` | Elements entering the viewport or revealing context |
| `--motion-duration-explain` | `0.6s` (600ms) | `0s` | Explanatory state changes: lock shackle closing, balance counter animation |
| `--motion-ease-points` | `0.2, 0, 0, 1` | `0.2, 0, 0, 1` | Raw bezier control points (shared between CSS and JavaScript) |
| `--motion-ease` | `cubic-bezier(0.2, 0, 0, 1)` | N/A | High-deceleration curve (fast out, smooth settle) |
| `--motion-press-y` | `1px` | `0px` | Tactile push depth on active buttons |
| `--lock-rest-y` | `-40` | `-40` | SVG Y coordinate offset for open/unlocked shackle |
| `--lock-engaged-y` | `0` | `0` | SVG Y coordinate offset for closed/locked shackle |

---

## 3. Motion Curves

The primary easing curve is:
$$\text{cubic-bezier}(0.2, 0, 0, 1)$$

Characteristics:
- **Initial acceleration**: Rapid rise (x1 = 0.2, y1 = 0)
- **Deceleration**: Long, gradual deceleration tail into the final position (x2 = 0, y2 = 1)
- **Zero overshoot**: Never bounces or oscillates past 1.0 (passes anti-slop check).

---

## 4. Component Implementations

### A. Lock Shackle Engagement (`LockObject.tsx`)

- **Trigger**: Safety check execution completes, outcome changes to locked / unlocked.
- **Library**: `motion/react` (utilizing `<LazyMotion features={domAnimation} strict>`).
- **Animation Target**: `<m.g>` containing the SVG shackle paths.
- **Motion Spec**:
  ```ts
  const timing = getLockMotion(Boolean(reduced))
  // returns:
  // {
  //   duration: reducedMotion ? 0 : 0.6,
  //   ease: [0.2, 0, 0, 1],
  //   openY: -40,
  //   closedY: 0
  // }
  ```
- **JSX Call**:
  ```tsx
  <m.g
    initial={false}
    animate={{ y: engaged ? timing.closedY : timing.openY }}
    transition={{ duration: timing.duration, ease: timing.ease }}
  >
  ```

### B. Balance Counter Animation (`RunResult.tsx`)

- **Trigger**: New run result loaded with changed balance figures.
- **Library**: `motion/react` imperative `animate()` API.
- **Spec**:
  ```ts
  const duration = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue('--motion-duration-explain')
  ) // 0.6s

  const control = animate(0, 1000, {
    duration,
    onUpdate: value => {
      if (number.current) {
        const current = start + (end - start) * BigInt(Math.floor(value)) / 1000n
        number.current.textContent = formatTokens(current.toString())
      }
    },
    onComplete: () => {
      if (number.current) number.current.textContent = label
    }
  })
  ```
- **Layout Stability**: An invisible `.balance-reserve` span with `visibility: hidden` renders the longest potential number string inside the same CSS grid cell, preventing horizontal layout shift during the count.

### C. Button Tactile Feedback (`components.css`)

- **Hover**:
  - `transition: transform var(--motion-duration-quick) var(--motion-ease), background-color var(--motion-duration-quick) var(--motion-ease);`
  - Background color shifts smoothly over 120ms.
- **Active Press**:
  - `transform: translateY(var(--motion-press-y));` (1px down)
  - `box-shadow: none;` (the 2px bottom shadow flattens out, simulating mechanical key travel)

### D. Scroll Behavior (`global.css`)

- **Default**: `html { scroll-behavior: smooth; scroll-padding-top: var(--space-6); }`
- **Reduced Motion**:
  ```css
  html[data-reduce-motion='true'] { scroll-behavior: auto; }
  @media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
  }
  ```

---

## 5. Reduced Motion Implementation

Both system preferences and in-app toggles are unified:
```css
:root[data-reduce-motion='true'],
@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-duration-quick: 0s;
    --motion-duration-enter: 0s;
    --motion-duration-explain: 0s;
    --motion-press-y: 0px;
  }
}
```
In JavaScript:
```ts
export function getLockMotion(reducedMotion: boolean) {
  const tokens = getComputedStyle(document.documentElement)
  const points = tokens.getPropertyValue('--motion-ease-points').split(',').map(Number)
  return {
    duration: reducedMotion ? 0 : parseFloat(tokens.getPropertyValue('--motion-duration-explain')),
    ease: points as [number, number, number, number],
    openY: Number(tokens.getPropertyValue('--lock-rest-y')),
    closedY: Number(tokens.getPropertyValue('--lock-engaged-y')),
  }
}
```
All animations instantly jump to final resting states without delay or intermediate interpolation.
