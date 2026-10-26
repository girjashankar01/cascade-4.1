# Font Inventory & Typographic Specification

All font files are self-hosted Latin WOFF2 subsets bundled directly in the distribution. No runtime requests are made to Google Fonts or external CDNs.

## 1. Font Inventory Table

| Family | Weight | Style | Format | File Name | File Size | Package Version | Upstream / Designer | License | Usage in Application |
|---|---|---|---|---|---|---|---|---|---|
| **Space Grotesk** | 500 (Medium) | Normal | WOFF2 | `space-grotesk-latin-500-normal.woff2` | 13,312 B (~13.3 KB) | `@fontsource/space-grotesk` 5.3.0 | Florian Karsten | SIL Open Font License 1.1 | Display headings (`h1`, `h2`, `h3`), Brand label, balance figures, step titles |
| **Source Sans 3** | 400 (Regular) | Normal | WOFF2 | `source-sans-3-latin-400-normal.woff2` | 15,696 B (~15.7 KB) | `@fontsource/source-sans-3` 5.3.1 | Adobe (Frank Grießhammer) | SIL Open Font License 1.1 | Primary body text, descriptions, table contents, inputs |
| **Source Sans 3** | 600 (Semibold) | Normal | WOFF2 | `source-sans-3-latin-600-normal.woff2` | 15,668 B (~15.7 KB) | `@fontsource/source-sans-3` 5.3.1 | Adobe (Frank Grießhammer) | SIL Open Font License 1.1 | Action buttons, active tabs, status marks, column labels |
| **IBM Plex Mono** | 400 (Regular) | Normal | WOFF2 | `ibm-plex-mono-latin-400-normal.woff2` | 14,708 B (~14.7 KB) | `@fontsource/ibm-plex-mono` 5.3.0 | IBM (Mike Abbink, Bold Monday) | SIL Open Font License 1.1 | Technical drawer codes, contract addresses, rule IDs, diff tables |

Total font payload: **59,384 bytes (~58.0 KB)** across all 4 files.

---

## 2. Font Declarations (@font-face)

Extracted from `frontend/src/design/fonts.css`:

```css
/* Only the WOFF2 Latin faces actually used. font-display keeps text visible. */
@font-face {
  font-family: 'IBM Plex Mono';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('./fonts/ibm-plex-mono-latin-400-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'Space Grotesk';
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url('./fonts/space-grotesk-latin-500-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'Source Sans 3';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('./fonts/source-sans-3/files/source-sans-3-latin-400-normal.woff2') format('woff2');
}
@font-face {
  font-family: 'Source Sans 3';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('./fonts/source-sans-3-latin-600-normal.woff2') format('woff2');
}
```

---

## 3. Fallback Stacks

| Token | Family Stack |
|---|---|
| `--font-display` | `'Space Grotesk', 'Segoe UI', sans-serif` |
| `--font-body` | `'Source Sans 3', 'Segoe UI', sans-serif` |
| `--font-technical` | `'IBM Plex Mono', Consolas, monospace` |

Note: Neither **Inter** nor **Geist** is used anywhere in the codebase.

---

## 4. Typographic Scale

| Token | CSS Value | Computed (Desktop default 16px root) | Usage |
|---|---|---|---|
| `--text-sm` | `1rem` | 16px | Buttons, badges, captions, labels, technical drawer |
| `--text-body` | `1.125rem` | 18px | Default body copy (`body` root font size) |
| `--text-lead` | `1.25rem` | 20px | Sub-headlines, card titles, intro lead |
| `--text-title` | `1.5rem` | 24px | Section titles, drawer headings, dialog titles |
| `--text-heading` | `clamp(1.75rem, 3vw, 2.25rem)` | 28px – 36px | Page titles (`h1`), section level-1 headings |
| `--text-display` | `clamp(2.75rem, 5.7vw, 4.75rem)` | 44px – 76px | Hero headlines |
| `--text-specimen` | `clamp(3rem, 7vw, 6rem)` | 48px – 96px | Design specimen / style tile displays |

---

## 5. Line Heights & Letter Spacing

| Token / Property | Value | Notes |
|---|---|---|
| `--leading-body` | `1.5` | Standard reading comfort for body copy |
| `--leading-heading` | `1.15` | Compact line height for titles & section headers |
| `--leading-display` | `1.05` | Ultra-compact line height for hero display type |
| `--tracking-heading` | `-0.035em` | Tight tracking for headings |
| `--tracking-display` | `-0.055em` | Tighter tracking for display scale |

---

## 6. Rendering & Text Wrapping Rules

```css
body {
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

h1, h2, h3 {
  text-wrap: balance;
}

p {
  text-wrap: pretty;
}
```
All tabular figures (numbers, amounts, balances, hashes) enforce:
`font-variant-numeric: tabular-nums;`
