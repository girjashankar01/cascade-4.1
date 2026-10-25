# STAGE 0 REVIEW

**Date:** 2026-10-26
**Build files reviewed:** `handoff/PLAN.md`, `handoff/DECISIONS.md`, `handoff/STAGE-0-BUILD.md`
**Build identifier:** Commit `92d787d` (reviewer scaffold) + Codex plan files written at 03:13–03:16 IST; no application code commit yet
**Verdict: PASS WITH NOTES**

No BLOCKER or MAJOR findings. Three MINOR items and two NITs recorded below. Stage 1 may proceed once human plan approval is granted.

---

## Findings

### R0-01 — MINOR — `PLAN.md §5 / §9` — `scripts/deploy_and_seed.py` dependency risk not surfaced in the plan's file-structure section

**What I saw:** PLAN.md §5 lists the proposed `frontend/src/` tree and backend as read-only sources. `STAGE-0-BUILD.md` finding #2 correctly flags that `scripts/deploy_and_seed.py` and the BoxUUPS/BoxEvil contract sources are absent from the repository, making live runner execution an unverified external dependency. However, this risk is not reflected in §5's proposed route or page list — the four live scenario flows are described without a qualification that B3 and Scenario A's re-seed path cannot be validated until the backend owner resolves the missing file.

**Evidence:** `STAGE-0-BUILD.md` line 55–56; `backend/app/scenarios/runner.py` `from deploy_and_seed import deploy_and_seed` (lines 95, 514); `scripts/` directory contains `check_chain.py`, `dev-tools.ps1`, `install-foundry.ps1`, `make_fixtures.py` — no `deploy_and_seed.py` present (confirmed by directory listing).

**Rule broken:** Charter §11 "Backend files are unchanged … report any change"; Build prompt "Missing review is pending, never approval." — The plan should surface known integration blockers in the delivery section so the human approver is not surprised when live B3/re-seed fails.

**Fixed looks like:** A one-line note in PLAN.md §9 (stage delivery table, Stage 3 row) stating that live B3 and Scenario A re-seed require `scripts/deploy_and_seed.py` and upgrade contracts to be supplied by the backend owner before live integration can be verified.

---

### R0-02 — MINOR — `PLAN.md §7` — Font license not yet confirmed; plan treats this as a Stage 1 task but does not record where to look

**What I saw:** PLAN.md §7 proposes Space Grotesk, Source Sans 3, and IBM Plex Mono, self-hosted as WOFF2. The plan correctly defers license verification to Stage 1. DECISIONS.md line 16 repeats the deferral. Neither document records the expected license type or the authoritative source URL, so a Stage 1 reviewer cannot quickly confirm whether the check was done or skipped.

**Evidence:** `PLAN.md` §7 last paragraph: "verify font licenses and record sources before inclusion"; `DECISIONS.md` line 16.

**Rule broken:** Charter §11 "`LICENSES-AND-SOURCES.md` lists every borrowed component, font, and asset with source and licence." — The plan should name the licence expected (SIL OFL 1.1 for all three fonts) and the source (Google Fonts CDN or their respective GitHub repos) so Stage 1 can confirm rather than re-research.

**Fixed looks like:** A one-sentence addition in PLAN.md §7 naming the expected licence (SIL OFL 1.1) and canonical source for each font so Stage 1 can verify rather than discover. Stage 1 must still measure contrast and record confirmed licences in LICENSES-AND-SOURCES.md.

---

### R0-03 — MINOR — `PLAN.md §8` — "Watch the 60-second story" fixture animation is described but its fixture data structure is not in §3's data contracts

**What I saw:** PLAN.md §8 describes a narrated fixture-based animation with play/pause/restart, skip, and text transcript. This is a non-trivial fixture-driven feature. However, §3's observed data contracts list only scenario/result/claim/conflict/balance/manifest/verification shapes. There is no mention of what fixture data drives the narrated animation frames, step timing, or transcript text.

**Evidence:** `PLAN.md` §8 "Watch the 60-second story opens a fixture-based narrated animation"; §3 data contracts section does not mention story/frame/narration shape.

**Rule broken:** Charter Stage 2 focus: "API layer isolation (no component calling fetch directly), fixture-mode switch." A fixture feature whose data contract is unspecified risks ad-hoc implementation that bypasses the typed fixture boundary.

**Fixed looks like:** A brief addition to PLAN.md §3 or §6 naming the story fixture shape (e.g. a sequence of `{ step, label, durationMs, transcript }` objects), or an explicit statement that the story animation is entirely self-contained within the landing component and requires no separate fixture contract — whichever is accurate.

---

### R0-04 — NIT — `PLAN.md §5` — Route `/style-tile` listed as a reviewable page but is a builder-internal artefact

**What I saw:** The proposed routes include `/style-tile` for Stage 1 visual review. This is a builder convenience route that has no user function. If it persists into later stages it may appear in the final build as a stray route.

**Evidence:** `PLAN.md` §5 "Routes: `/` landing; `/style-tile` Stage 1 visual review; `/app` …"

**Fixed looks like:** A note that `/style-tile` will be removed before Stage 5 or is served only in development mode (e.g. behind `import.meta.env.DEV`).

---

### R0-05 — NIT — `PLAN.md §10` — Two open questions are answered with defaults but the plan does not record who answers them

**What I saw:** §10 lists two questions (pitch API URL, target device) with proposed defaults. Neither records whether the human owner has confirmed the default or whether it is still an open assumption. This could lead to Stage 7 surprises.

**Evidence:** `PLAN.md` §10.

**Fixed looks like:** The human owner either confirms defaults in a brief reply (which Codex records in DECISIONS.md) or supplies different values before Stage 1 begins.

---

## What I could not check and why

- **Contrast measurements:** No token values have been implemented. Stage 1 is the earliest point this can be checked.
- **Anti-slop detector (Impeccable):** No UI code exists yet. Not applicable at Stage 0.
- **Build health beyond baseline scaffold:** STAGE-0-BUILD.md reports the existing scaffold build passes (220 kB JS, 0.92 kB CSS, no lint/type errors). I accept this as claimed; I did not re-run the build myself. A fresh install and build is the first action at Stage 1.
- **Browser screenshots / responsive check:** No redesigned UI exists. The build file's spot-check of 360/768/1280 applies to the unchanged scaffold only.
- **Backend file integrity:** The build file states no backend files were changed. I confirmed by timestamp that `backend/` and `contracts/` timestamps are all prior to the plan files. A full diff against `a135632` was not run; I accept the claim.
- **Live scenario execution:** Not expected or possible at Stage 0.

---

## Re-verification

No findings from prior stages. This is the first review.

---

## Summary

The plan is thorough, honest about its gaps, and correctly scoped for Stage 0. The inventory of backend API shapes and scenario result variants is detailed and will make Stage 2–3 adapter work tractable. The honesty requirements, fixture/live boundary, and technical-drawer rules are clearly understood. The three MINOR items above are improvements to the plan document, not blockers to Stage 1 work — provided the human owner approves the plan and the open questions in §10 are acknowledged.

**Stage 1 gate:** Human approval of `handoff/PLAN.md` + no open BLOCKER/MAJOR in this review. Both conditions are met on the reviewer side. Human approval is still required.
