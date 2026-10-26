# PROGRESS.md — DAO Accountability Engine Frontend

Last updated: 2026-10-26

---

## Status: S1 COMPLETE ✅

### Completed stages

| Stage | Commit | Notes |
|-------|--------|-------|
| S0 — Audit | 125af5f | PROJECT-TRUTH.md, CORRECTION-AUDIT.md, QUESTIONS.md |
| S1 — Types, vocabulary, fixtures, routes | current | All corrections from CORRECTION-AUDIT.md applied |

### S1 changes (this session)

**Data model (types.ts)**
- Verdict: 4 values — VERIFIED, MISMATCH, UNSUPPORTED, UNCERTAIN (never allowed/blocked)
- VERDICT_PLAIN: plain language per §4
- RunResult: verdict + plainVerdict + attestation + diffs + failedRule + allRules + BalanceSnapshot
- BalanceSnapshot: Treasury, Honest recipient, Attacker (role labels, not fund/badActor)
- ScenarioId includes B2

**Fixtures (fixtures.ts)**
- All 5 scenarios: A, B1, B2, B3, C — real data from repo
- AMOUNT_RAW = 1000000000000 (1M USDC, 6 decimals) from runner.py
- RECIPIENT_ADDR, ATTACKER_ADDR from Anvil accounts
- Correct scenario C story: "reset, no payment"
- All rule results labelled "Demo data"
- Attestation present/absent correctly per scenario

**Routes (App.tsx)**
- /app/proposal (was /app/payment-request)
- /app/manifest (was /app/approved-plan)
- /app/audit (was /app/record)
- Legacy paths → redirect

**New pages**
- ProposalPage: sources, claims (GROUNDED/CONFLICTED/UNCERTAIN), conflicts, AI label "cached"
- ManifestPage: action sheet, version chain, chain-verified badge
- AuditPage: input hash, prompt hash, provider, model, rule-set version, cache status

**Updated pages**
- WorkbenchPage: 5 scenarios + B2, VerdictMark, Treasury/Honest recipient/Attacker labels, correct "Approved manifest" wording
- CoveragePage: correct limits from §9, Treasury (not "shared fund"), no invented quorum %
- CoveragePage removed: "98.4% quorum" claim

**Components**
- StatusMark → VerdictMark: all 4 verdicts with correct CSS classes
- RunResult: attestation badge, failed-rule banner, field diff table, rules section (collapsible)
- BalanceComparison: uses RoleBalance (Treasury/Honest recipient/Attacker)
- WorkbenchShell nav: correct page names

**CSS**
- Verdict mark colour coding: verified=green, mismatch=red, unsupported=amber, uncertain=grey
- Attestation present/absent banners
- Field diff table with changed cell highlighting
- Rule rows with pass/fail backgrounds
- Conflict block, sources list, version chain, audit card

**Tests**
- 28/28 passing
- data.test.ts: fully rewritten for new types
- pages.test.ts: rewritten (removed stale secondaryData checks, added scenario shape + VERDICT_PLAIN checks)
- workspaces.test.ts: outcome → verdict

**Build**: clean (474 modules, no errors)
**TypeScript**: clean (0 errors)

---

## BLOCKERS resolved

| # | Issue | Resolution |
|---|-------|------------|
| BLOCKER-01 | Page named "Payment request" | Renamed to "Proposal", redirects in place |
| BLOCKER-02 | Only 2 verdicts shown | VerdictMark shows all 4 |
| BLOCKER-03 | Scenario C story misleading | Correct story: "reset, no payment" |
| BLOCKER-04 | Invented SHA-256 digests | Removed; real addresses from repo |
| BLOCKER-05 | Nav said "Payment request" | Fixed to "Proposal" |
| BLOCKER-06 | "98.4% quorum" fabricated | Removed; Coverage page now says "Simulated governance" |
| BLOCKER-07 | "The shared fund" vocabulary | Fixed to "Treasury" everywhere |
| BLOCKER-08 | "The bad actor" label | Fixed to "Attacker" |
| BLOCKER-09 | B2 scenario missing | Added |

---

## Next: S2 (optional polish / backend integration)

- Connect real `/scenarios/{id}/run` when backend is online
- Add Proposal page: load from GET /sources and GET /claims/{pid}
- Add Manifest page: load from GET /manifest/{pid} and GET /versions/{pid}
- Add Audit page: load from GET /audit/{pid}
- Landing page at `/`
- Pitch walkthrough (keyboard-driven, 7-step)
