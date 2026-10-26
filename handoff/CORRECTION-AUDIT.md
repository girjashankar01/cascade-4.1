# CORRECTION-AUDIT: Frontend vs. PROJECT-TRUTH.md

Date: 2026-10-26  
Branch: abhigyan-frontend  
Auditor: Self-check pass against PROJECT-TRUTH.md

---

## Summary

The previous front-end build was built from an **incorrect understanding of the product**. The core problems are:

1. Wrong terminology throughout ("Payment request" instead of "Proposal", "Allowed/Blocked" instead of four real verdicts)
2. Wrong page structure (secondary pages don't match what the product actually has)
3. Scenario C is wrong (implemented as "environment reset" — it IS actually an environment reset per the runner, but the front-end presentation was wrong)
4. Invented data not sourced from the repo
5. Missing concepts: Sources, Claims with quotes, Conflicts, Uncertainty, Version hash chain, Attestation, Audit records, four-verdict model

---

## S0.1 — Real Backend Routes (from `backend/app/api/routes.py`)

All these routes are LIVE in the backend:

| Route | Method | Status |
|---|---|---|
| `/sources` | POST | Live — upload/paste source document |
| `/sources` | GET | Live — list all sources |
| `/sources/{source_id}` | GET | Live — single source detail |
| `/analyze/{pid}` | POST | Live — LLM extraction + grounding + conflicts |
| `/claims/{pid}` | GET | Live — all claims and conflicts for a proposal |
| `/proposals/{pid}/coi` | GET | Live — conflict-of-interest analysis |
| `/audit/{pid}` | GET | Live — analysis audit trail |
| `/manifest/{pid}` | POST | Live — draft manifest |
| `/manifest/{pid}/confirm` | POST | Live — confirm + sign manifest |
| `/manifest/{pid}` | GET | Live — get manifest |
| `/commit/{pid}` | POST | Live — commit version on-chain |
| `/approve/{pid}` | POST | Live — governance approval |
| `/versions/{pid}` | GET | Live — version chain |
| `/verify-version/{pid}` | POST | Live — tamper check |
| `/verify` or `/verify/{pid}` | POST | Live — full verification pipeline |
| `/execute` or `/execute/{pid}` | POST | Live — guarded execution |
| `/verifications/{pid}` | GET | Live — all verification records |
| `/deployments` | GET | Live — contract addresses |
| `/balances` | GET | Live — treasury/recipient/attacker balances |
| `/scenarios/{name}/run` | POST | Live — run A, B1, B2, B3, C |
| `/health` | GET | Live — health check |

**Key finding:** The truth file said `/verify`, `/execute`, `/scenarios/{name}/run` were "not yet built" — but they ARE built and live in the code. This is a significant discrepancy in the truth file itself. Update QUESTIONS.md.

---

## S0.2 — Real Scenario Definitions (from `backend/app/scenarios/runner.py`)

| Scenario | Real backend description | Status |
|---|---|---|
| A | Valid approved payout → VERIFIED → attested → guarded execution | Correct in truth file |
| B1 | Substituted payout (attacker recipient / larger amount) → MISMATCH | Correct in truth file |
| B2 | **NEW: Not in truth file** — Benign V2 upgrade control → VERIFIED | Missing from front end entirely |
| B3 | Contested UUPS upgrade with undeclared sweep() selector → MISMATCH | Correct in truth file |
| C | Clean environment reset: redeploy contracts, fund treasury, seed PROP-002 | **Correct implementation (it IS a reset), but front-end must show it honestly** |

**PROP-002** is the proposal that gets seeded fresh in Scenario C (not PROP-001 which is the contested one).

**Real addresses from runner.py:**
- `RECIPIENT_ADDR = "0x9965507D1a55BCC6475675304Ca994970De97744"` (Anvil account 5)
- `ATTACKER_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"` (Anvil account 4)
- `DEFAULT_AMOUNT_RAW = 1_000_000 * 10**6 = 1000000000000` (raw int, 1M USDC at 6 decimals)

---

## S0.3 — Real Verification Rules (from `backend/app/verification/verify.py`)

Rules R1, R2, R3, R4, R5, R6, R7, R9 exist. Confirmed naming matches the build guide. No R8.

| Rule ID | Meaning (from code comments) |
|---|---|
| R1 | Approved version and live governance check |
| R2 | Action hash and calldata field match |
| R3 | Token outflow envelope check |
| R4 | Unexpected balance increase |
| R5 | Allowance change |
| R6 | Implementation slot change |
| R7 | Undeclared selector (whitelist / code hash) |
| R9 | Owner or role change |

Front end must NOT hard-code these — must display `rule_id` and `explanation` from the backend response.

---

## S0.4 — Every Contradiction Between Front End and PROJECT-TRUTH.md

### BLOCKER-01: "Payment request" page name
- **File:** `frontend/src/pages/PaymentRequestPage.tsx`, `frontend/src/components/layout/WorkbenchShell.tsx`
- **What is wrong:** Page is titled "Payment request" and route is `/app/payment-request`
- **What it should be:** "Proposal" — the truth file explicitly says "Do not rename 'Proposal' to 'Payment request'"
- **Fix:** Rename page, route, and all UI text

### BLOCKER-02: Two verdicts displayed (Allowed / Blocked) instead of four
- **Files:** `frontend/src/components/ui/StatusMark.tsx`, `frontend/src/data/types.ts`, `frontend/src/data/fixtures.ts`, `frontend/src/features/workbench/RunResult.tsx`
- **What is wrong:** Only `allowed` and `blocked` outcomes. No `MISMATCH`, `VERIFIED`, `UNSUPPORTED`, `UNCERTAIN` verdicts
- **What it should be:** Four verdicts: VERIFIED, MISMATCH, UNSUPPORTED, UNCERTAIN with correct plain-language text
- **Fix:** Redefine Outcome type, update all display logic

### BLOCKER-03: Scenario C described incorrectly
- **File:** `frontend/src/data/fixtures.ts`, `frontend/src/data/secondaryData.ts`
- **What is wrong:** Front end shows scenario C as "A clean start" with story "Restore the shared fund and the approved plan for another demonstration." — close but not honest about what it actually does (full redeploy + PROP-002 seed)
- **What it should be:** C is an environment reset that redeploys contracts, funds the treasury, and seeds a clean PROP-002 state. Show plainly "This resets the demo environment. No payment is executed."
- **Fix:** Update story and result text

### BLOCKER-04: Invented document digests in secondaryData.ts
- **File:** `frontend/src/data/secondaryData.ts`
- **What is wrong:** Lines like `digest: '0xce8e7cd2...'` are SHA-256 of arbitrary strings `"proposal-a"` etc., not real document hashes
- **What it should be:** Either real digests read from `expected_claims.json` / actual fixture files, or clearly labelled "Demo data"
- **Fix:** Remove invented digests; read from `expected_claims.json` or label as "Demo data"

### BLOCKER-05: "Payment request" label in WorkbenchShell pages nav
- **File:** `frontend/src/components/layout/WorkbenchShell.tsx` line 13
- **What is wrong:** `{ to: '/app/payment-request', name: 'Payment request' }`
- **What it should be:** `{ to: '/app/proposal', name: 'Proposal' }`
- **Fix:** Rename route

### MAJOR-01: Missing concepts — Sources, Claims, Conflicts page
- **File:** `frontend/src/pages/PaymentRequestPage.tsx` (replacement for Proposal page)
- **What is wrong:** No actual sources list, no claim-with-quote display, no conflict side-by-side view, no uncertainty labels, no cached/generated label on AI results
- **What it should be:** Proposal page shows sources, claims with page-number quotes, conflict pairs, uncertainty badges, and AI cache status
- **Fix:** Rewrite Proposal page (S3 priority)

### MAJOR-02: Missing Manifest / Version chain page
- **File:** `frontend/src/pages/ApprovedPlanPage.tsx`
- **What is wrong:** Shows "approved plan" concept but doesn't show version hash chain, chain-verified badge, proposer signature, or approval status from chain
- **What it should be:** "Manifest and versions" page with version chain, hashes in technical drawer, approval status
- **Fix:** Rewrite Approved Plan page as Manifest page (S3 priority)

### MAJOR-03: Missing Attestation in result view
- **File:** `frontend/src/features/workbench/RunResult.tsx`
- **What is wrong:** No attestation display. "Verifier's signed OK" is not shown at all
- **What it should be:** Show attestation status — "Verified and signed by the verifier" (VERIFIED) or "No attestation — verification refused" (MISMATCH)
- **Fix:** Add attestation field to RunResult view

### MAJOR-04: No rule ID display next to plain explanation
- **File:** `frontend/src/features/workbench/RunResult.tsx`
- **What is wrong:** No rule ID shown anywhere in the primary UI
- **What it should be:** Failed rule shown as plain sentence plus small rule ID label (R2, R7 etc.)
- **Fix:** Add rule result display

### MAJOR-05: "Allowed/Blocked" terminology in StatusMark
- **File:** `frontend/src/components/ui/StatusMark.tsx`
- **What is wrong:** `'Allowed'` and `'Blocked'` are shown. These are internal simplifications, not the four real verdicts
- **What it should be:** VERIFIED → "Verified", MISMATCH → "Does not match", UNSUPPORTED → "Cannot be checked, needs review", UNCERTAIN → "Evidence unclear"
- **Fix:** Replace StatusMark with VerdictMark showing all four

### MAJOR-06: "The shared fund" — wrong term
- **File:** `frontend/src/data/fixtures.ts`, multiple pages
- **What is wrong:** Balance holder is called "The shared fund" — the real term is "Treasury"
- **What it should be:** "Treasury" per the truth file ("Keep the real words: Treasury")
- **Fix:** Replace throughout

### MAJOR-07: Invented governance quorum numbers
- **File:** `frontend/src/data/secondaryData.ts`
- **What is wrong:** `governanceQuorum: 'Passed with 98.4% quorum agreement (Snapshot block #31337)'` — invented
- **What it should be:** "(Simulated governance)" — the truth file says governance is simulated
- **Fix:** Replace with "Approval (simulated governance)"

### MAJOR-08: "What was actually sent" — close but missing context
- **File:** Result display
- **What is wrong:** This is used but without the rule ID and field-level diff context that MISMATCH requires
- **What it should be:** Side-by-side with highlighted differences and the rule that caught the mismatch
- **Fix:** Add diff highlighting and rule reference

### MINOR-01: "Demo data · test tokens" label
- **File:** WorkbenchShell
- **What is wrong:** Correctly present but needs to be clearer — specifically "test USDC" not generic "test tokens"
- **Fix:** Minor wording clarification

### MINOR-02: B2 (Benign upgrade control) missing from front end entirely
- **Files:** All scenario-related files
- **What is wrong:** Scenario B2 (benign V2 upgrade → VERIFIED) exists in the backend but not shown in the front end
- **What it should be:** B2 should be included as the "control" scenario for B3 per the truth file
- **Fix:** Add B2 to scenario list (S2 priority)

### NIT-01: "Envelope" / "Watched state" not in glossary
- **File:** `frontend/src/pages/CoveragePage.tsx`
- **What is wrong:** Coverage page doesn't use these truth-file terms at all
- **Fix:** Incorporate these concepts

---

## S0.5 — Real Data Found in the Repo

From `fixtures/expected_claims.json`:
- Proposal ID: `PROP-001`
- Amount in proposal.pdf: `5000000` (display: `$5.0M`)
- Amount in forum_post.txt: `5800000` (display: `$5.8M`)
- Recipient: `0x9965507D1a55BCC6475675304Ca994970De97744`
- Conflict field: `amount`, status: `UNRESOLVED`
- Token: USDC

From `backend/app/scenarios/runner.py`:
- RECIPIENT_ADDR: `0x9965507D1a55BCC6475675304Ca994970De97744`
- ATTACKER_ADDR: `0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65`
- DEFAULT_AMOUNT_RAW: `1000000000000` (1,000,000 USDC at 6 decimals)

From `fixtures/forum_post.txt`:
- Quote: "revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC)"

---

## S0.6 — Priority Fix Plan

Stage S1 (immediately):
1. Fix all BLOCKER items: rename routes/pages, add four verdicts, fix vocabulary
2. Rebuild data layer types to match real concepts
3. Fix invented data — use only data sourced from repo

Stage S2 (execution centrepiece):
4. Execution page with all four verdicts, attestation, rule display, and field diff

Stage S3 (remaining pages):
5. Proposal page with sources/claims/conflicts/uncertainty
6. Manifest page with version chain
7. Audit page using `/audit/{pid}` endpoint shape

---

## S0.7 — Open Questions Updated

Q3 is now confirmed: `/scenarios/{name}/run` IS built and live. Update QUESTIONS.md.
Scenario B2 (benign upgrade) also exists — not in truth file. Add as Q6.
