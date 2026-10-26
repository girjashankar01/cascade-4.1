# PROJECT TRUTH: DAO Accountability Engine (CASCADE '26, Problem 4.1)

Copy this file into the repo as `handoff/PROJECT-TRUTH.md`. It is the single source of facts for the front end. It was written from `dao-build-guide-final.md` and the Stage 3 `handoff.md`. Where something is an inference and not stated in those files, it is marked **ASSUMPTION** and must be confirmed by the backend owner.

If any front-end text, number, scenario, or wording contradicts this file, the front end is wrong.

---

## 1. What the product is

A system that proves that **what a DAO executes matches what voters were asked to approve**.

The real gap, stated carefully (do not overclaim on the landing page):
- An OpenZeppelin Governor's proposal ID already hashes the exact calldata, so calldata cannot be swapped after a vote.
- What can still mismatch is the **prose voters read** versus the **calldata that was proposed**, and the **behaviour of the code** the proposal runs (for example a contract upgrade).
- The product binds the prose to a structured manifest, commits it on-chain, verifies the submitted execution against it, and refuses to execute on mismatch.

Never write that the product "stops someone swapping a payment after a vote" as if that were the main threat. The honest framing is: voters approve text, the chain executes bytes, and this closes the gap between the two.

## 2. The pipeline in plain steps

1. **Sources**: proposal PDF, forum post and other evidence are uploaded. Only hashes go on-chain; documents stay off-chain.
2. **Claims**: an AI model extracts facts (amount, recipient and so on). Every claim must carry a quote that is actually found in the source, with page number. A quote that is not found is dropped. Numbers in the quote must match the claimed value.
3. **Conflicts**: if sources disagree on the same field (for example $5.0M in the forum post versus $5.8M in the PDF), a conflict is shown with both quotes. An unresolved conflict blocks manifest confirmation.
4. **Uncertainty**: weak or missing evidence is labelled UNCERTAIN and is never used silently.
5. **Manifest**: one action only, drafted from claims. A human confirms every field. The proposer signs it.
6. **Version chain**: each version has a version hash that includes the previous version hash, the proposal text hash and the evidence root. A new text revision with the same action produces a new version hash, so older approvals stop working.
7. **Commit and approve**: the proposer commits a version on-chain; governance (simulated) approves the latest committed version.
8. **Verify**: for a submitted transaction, the verifier recomputes everything, decodes it, simulates it, compares observed effects against the manifest envelope (deny by default), and applies rules.
9. **Attest**: the verifier signs an attestation only if the verdict is VERIFIED.
10. **Execute**: the GuardedExecutor contract re-checks on-chain (approved action hash, attestation signature, deadline, one execution per proposal) and either executes through the Treasury or reverts.

Important rule: **the AI never decides a verdict.** Hashes, decoding, simulation and rules decide. The AI only extracts and summarizes.

## 3. Roles and actors

| Role | Does |
|---|---|
| Proposer | signs and commits manifest versions |
| Governance (simulated) | approves a version |
| Verifier | signs attestations (single trusted key) |
| Executor (contract) | enforces on-chain, then calls Treasury |
| Attacker | demo adversary who submits a substituted action |
| Honest recipient | the intended payee |

The Treasury holds the funds and, in the upgrade scenario, owns the proxy. The token is a mock ERC-20 with 6 decimals that mimics USDC.

## 4. Verdicts (the front end must show these four, not just allowed or blocked)

| Verdict | Meaning | Attestation signed? |
|---|---|---|
| VERIFIED | everything matches | yes |
| MISMATCH | a rule failed; shows rule ID and a field-level diff | no |
| UNSUPPORTED | something cannot be checked; needs human review | no |
| UNCERTAIN | evidence quality problem | no |

Plain-language wording for non-technical readers:

| Technical | Plain wording |
|---|---|
| VERIFIED | Verified |
| MISMATCH | Does not match |
| UNSUPPORTED | Cannot be checked, needs review |
| UNCERTAIN | Evidence unclear |
| Manifest | Action sheet (exactly what will be done) |
| Version hash chain | Version history |
| Attestation | Verifier's signed OK |
| GuardedExecutor | The guarded executor |
| Simulated governance | Approval (simulated governance) |
| Envelope | Allowed limits |
| Watched state | The balances and settings we can observe |

Keep the real words "Proposal", "Evidence", "Treasury", and "Attacker". Do not rename "Proposal" to "Payment request".

Rule IDs (R1, R2, R7 and so on) appear in the technical drawer and as a small label next to the plain sentence, never as the only explanation.

**IMPORTANT CONFLICT TO RESOLVE WITH THE BACKEND OWNER:** the build guide lists rules as R1 version, R2 action, R3 token outflow, R4 unexpected balance increase, R5 allowance change, R6 implementation slot change, R7 undeclared selector, R9 owner or role change. The Stage 3 handoff lists a different seven-rule numbering for Stage 4. The front end must therefore not hard-code what any rule number means. It displays the rule ID and message text that the backend returns, and fixtures must say "demo data" until the backend rule list is final.

## 5. The scenarios (what really happens in each)

| Scenario | Story | Expected verdict | What the user should see |
|---|---|---|---|
| A | Valid payout, submitted action equals approved action | VERIFIED | attestation signed, execution succeeds, recipient balance rises by exactly the approved amount |
| B1 | Substituted payout: attacker recipient and/or larger amount | MISMATCH (action rule, with decoded field diff) | approved versus submitted side by side, no attestation, on-chain revert, balances unchanged |
| B3 | Malicious upgrade: proposal text describes a benign V2 in jargon, voters approve, the submitted implementation contains an undeclared function (a hidden sweep). The implementation address matches what was approved, so voters were fooled; the check looks at what the code is | MISMATCH (undeclared selector rule) | no attestation, on-chain revert, implementation slot unchanged afterwards. Control case: a benign V2 upgrade is VERIFIED and executes |
| C | **ASSUMPTION, confirm with owner:** the guide lists C in the scenario runner but never defines it. The Stage 3 handoff shows the disputed proposal ($5.0M versus $5.8M) blocking manifest confirmation, so C is probably the conflicting-evidence case | stopped before a manifest can be confirmed | both quotes side by side, the conflict, why confirmation is blocked |

Scenario runner endpoint: `POST /scenarios/{name}/run` with A, B1, B3, C.

## 6. The pages the product actually has

From the build guide (Stage 5):
1. **Proposal**: sources, claims with quote popups and page numbers, conflicts, uncertainty labels, and a label on every AI result saying "cached" or "generated now".
2. **Manifest and versions**: the manifest, the version hash chain, a "chain-verified" badge, approval status.
3. **Execution**: approved action beside submitted action, observed effects, the failed rule, verdict, attestation, transaction result. **This page is the centrepiece.**
4. **Audit**: input hashes, model and provider, rule-set version.

Plus a plain "What this does and does not cover" page, and the technical drawer.

## 7. Real data to use (no invented numbers)

- Proposal ID format: `PROP-001`.
- Main demo proposal: $5M payout; token has 6 decimals; raw amount `5000000000000`. Show raw amount, human token amount and USD **separately**. Show USD only with a stated valuation source and time; otherwise omit USD.
- Conflicting forum post: $5.8M.
- Clean test proposals (from the Stage 3 handoff): `clean_proposal_v1` and `clean_proposal_v2`, $1.0M to `0x9965507D1a55BCC6475675304Ca994970De97744`, v2 being a text revision of the same action.
- Anvil accounts: 0 deployer, 1 proposer, 2 governance, 3 verifier, 4 attacker, 5 honest recipient.
- For balances and addresses, read the actual values from the repo's seed script and fixtures. Do not make numbers up. Anything not read from the repo is labelled "Demo data".

## 8. Backend status (from the Stage 3 handoff, dated 2026-10-25)

Implemented and tested: contracts (token, registry, treasury, executor), canonical manifest, hashes, manifest builder with eligibility and conflict gates, version commit and approval, tamper detection, and these routes: `POST /manifest/{pid}`, `POST /manifest/{pid}/confirm`, `GET /manifest/{pid}`, `POST /commit/{pid}`, `POST /approve/{pid}`, `GET /versions/{pid}`, `POST /verify-version/{pid}`. Earlier stages built sources, claims, conflicts and the LLM router; confirm the exact route names by reading `backend/app/api/routes.py`.

Not yet built (Stage 4 and later): simulation, the verification rules, `POST /verify`, `POST /execute`, and likely `/audit` and `/scenarios/{name}/run`. The front end must run the Execution page, scenarios and audit from fixtures until those exist, using an adapter so real endpoints can replace fixtures later. Anvil state is in memory: after a restart the seed script must be re-run. Reset is the seed script, not an API route.

## 9. Honest limits (must appear on the landing page and the coverage page)

- One executable action per proposal version.
- Only two action kinds are supported: ERC-20 payout and proxy upgrade. Anything else is UNSUPPORTED.
- Governance is simulated.
- The verifier is a single trusted key.
- The code scan is heuristic evidence. It is not a proof.
- Verification covers defined, watched state only.
- The version chain proves which text version was committed and referenced by the vote. It does not prove that each voter read it.
- The AI never produces a verdict.

## 10. The 5-minute demo story (the pitch walkthrough must follow this)

1. Problem (30 s): voters approve text; the chain executes bytes.
2. Evidence (90 s): upload the PDF and the conflicting forum post; show claims with quotes, the $5.0M versus $5.8M conflict, uncertainty labels, cached versus generated.
3. Commit and approve (30 s): confirm manifest, sign, commit version 2, approve; show the version chain; tamper one byte and show the failure.
4. Scenario A (45 s): valid payout simulated, attested, executed.
5. Scenario B1 (60 s): substituted recipient or amount; approved versus submitted side by side, the failed rule, no attestation, on-chain revert.
6. Scenario B3 (60 s): obfuscated upgrade; implementation hash matches but code exposes an undeclared function; MISMATCH; revert; slot unchanged.
7. Honest limits (15 s).

The failed transaction is the centrepiece: the expected recipient beside the substituted one, the exact rule, and proof the executor refused.

## 11. Things the front end must never do

- Claim the product detects calldata swaps that the governor already prevents.
- Say or imply that AI decides anything about approval.
- Show invented customers, metrics, savings or "trusted by" claims.
- Show raw JSON, raw hashes or stack traces outside the technical drawer.
- Imply real money or a public testnet. Everything is a local demo chain.
- Hard-code rule meanings (see the IMPORTANT note in section 4).
