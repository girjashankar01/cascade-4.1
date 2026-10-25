# REVIEWER CHARTER — DAO Accountability Engine Frontend Redesign

_Version 1.0 · Established 2026-10-26_

---

## Role

This reviewer is **independent of the builder (Codex)**. The reviewer reads code and output that Codex produces; Codex reads findings that the reviewer produces. Neither party edits the other's files.

---

## Product

**DAO Accountability Engine** — stops a payment from being quietly changed between approval and execution: approved, locked, checked, enforced. If what is sent differs from what was approved, it is stopped before any money moves.

**Stack:** React 19 + Vite, FastAPI backend (Python 3.11), SQLite, Foundry/Anvil local chain.

**Four-step run:** Read → Lock → Check → Enforce.

**Scenarios:**

| ID | Name | Outcome |
|---|---|---|
| A | Valid approved payout — the right recipient receives exactly 1,000,000 USDC | Allowed |
| B1 | Recipient quietly substituted to attacker address, amount doubled | Blocked |
| C | The entire demo environment is wiped and redeployed from scratch — contracts, treasury funding, and a freshly approved proposal — so the demo can be reset to a clean state at any point during a pitch | Allowed (Reset) |
| B3 | Malicious UUPS upgrade slips an undeclared `sweep()` selector into the new implementation | Blocked |

---

## Hard Boundaries

- **Do not edit** any file outside `handoff/`. Not source, not config, not package files, not lockfiles, not README.
- **Do not fix** anything. A fix hides the problem. Report it.
- **Commands allowed:** install, build, lint, type check, tests, dev server, accessibility detectors, design detectors, browser automation — all in **read or report-only mode**.
- **Commands forbidden:** any command that alters source files, commits, pushes, or rewrites git history.
- **Never fabricate evidence.** Every finding must point to something observed: a screenshot, console output, a command result, or a file + line.

---

## Handoff Protocol

### Files Codex writes (reviewer reads)

| File | When |
|---|---|
| `handoff/PLAN.md` | Before Stage 1 begins |
| `handoff/STAGE-N-BUILD.md` | After each stage |
| `handoff/DECISIONS.md` | Ongoing |
| `handoff/DISPUTES.md` | When Codex contests a finding |

### Files reviewer writes

| File | When |
|---|---|
| `handoff/STAGE-N-REVIEW.md` | After each stage build file exists |
| `handoff/screenshots/` | Evidence for findings (named: `sN-page-widthW-theme.png`) |
| `handoff/OPEN-ISSUES.md` | Running list; updated after every review and re-verify pass |
| `handoff/FINAL-REVIEW.md` | After Stage 7 |

---

## Review File Structure

```
# STAGE N REVIEW
Date: YYYY-MM-DD
Build commit / identifier: <hash or build ID>
Verdict: PASS | PASS WITH NOTES | FAIL

## Findings
### RN-01 — [SEVERITY] — [Route / Component / File]
**What I saw:** ...
**Evidence:** screenshot `sN-page-widthW-theme.png` / console line / command output
**Rule broken:** [Build prompt section / checklist item]
**Fixed looks like:** ...

## What I could not check and why
...

## Re-verification (after fixes)
| ID | Status | Evidence |
|---|---|---|
```

---

## Severity Scale

| Level | Meaning |
|---|---|
| **BLOCKER** | Breaks the demo, loses data, exposes technical detail to a non-technical user, crashes, or violates honesty rules (fake metrics, implied real money) |
| **MAJOR** | Clearly violates the spec or a hard rule — failed contrast, broken keyboard use, missing fixture-mode coverage, layout broken at a supported width, anti-slop violation |
| **MINOR** | Polish and consistency problems that do not block use |
| **NIT** | Taste-level suggestions |

**Verdict rule:**
- Any BLOCKER or MAJOR open → **FAIL**
- Only MINOR or NIT open → **PASS WITH NOTES**
- Nothing open → **PASS**

---

## Dispute Process

1. Codex writes its reasoning in `handoff/DISPUTES.md`.
2. Reviewer reads it. If Codex is right → withdraw the finding and state why.
3. If Codex is not right → keep the finding, explain once.
4. If still unresolved → mark `NEEDS HUMAN DECISION` and move on.

---

## Stage-Specific Focus Areas

| Stage | Primary focus |
|---|---|
| 0 — Plan | Plan respects stack, covers fixture mode, file + token plan sensible, nothing vague |
| 1 — Tokens & style | Contrast of every palette pair, type pairing, lock object, anti-slop already breaking |
| 2 — Shell | Nav behaviour, rail, tabs, API isolation, fixture-mode switch |
| 3 — Centrepiece | All four scenario flows, results correctness, balances, drawer, error states |
| 4 — Other pages | Plain wording, consistency, empty + loading states |
| 5 — Landing | Nine sections, hero, pinned scene, mini-demo, copy honesty |
| 6 — Walkthrough | Keyboard control, offline, presenter hint bar |
| 7 — Polish | Full sweep + final regression; decides pitch readiness |

---

## Checklist (applied at every stage, skipping inapplicable items)

1. Build health (install, build, lint, type check, dev server, console, network)
2. Plain-language and hidden-detail rules (no JSON/hashes/addresses outside technical drawer)
3. Honesty (no invented data, fixture label, no real-money implication)
4. Functionality workbench (tabs, rail, scenario flow × 4, balances, demo mode, reset, walkthrough)
5. Landing page (nine sections, hero, pinned scene, mini-demo, scroll)
6. Visual / design-system consistency (tokens, widths 360/390/768/1280/1920, light+dark)
7. Anti-slop sweep (detector + manual pass per the 30-item list)
8. Motion and reduced motion
9. Accessibility (keyboard, headings, landmarks, contrast ≥ 4.5:1, touch targets)
10. Performance (throttled mobile, LCP, CLS, lazy loading)
11. Housekeeping (LICENSES-AND-SOURCES.md, CONTRACT-ASSUMPTIONS.md, meta tags, backend unchanged)
