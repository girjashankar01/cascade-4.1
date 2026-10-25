# DAO Accountability Engine — Complete Project Handoff

**Event:** CASCADE ’26  
**Problem:** Problem 4.1  
**Working project name:** DAO Accountability Engine  
**Primary objective:** Build a working prototype that connects what DAO voters approve, the evidence behind the proposal, and what a smart contract actually executes.

**Time constraint:** 10–15 hours preferred; the revised build plan targets approximately 12–15 hours.

**Status:** Architecture and implementation plan defined. Actual implementation progress has not been verified in this handoff.

---

## 1. Executive summary

### The problem

A DAO (Decentralized Autonomous Organization) allows participants to propose and vote on decisions that may control a treasury, transfer tokens, grant permissions, or upgrade smart contracts.

Blockchain provides useful guarantees: transactions can be verified, proposal data can be hashed, and execution history can be inspected. However, those guarantees do not automatically establish that:

- The transaction's effects match what voters understood the proposal to authorize.
    
- The supporting evidence is consistent and trustworthy.
    
- Financial or conflict-of-interest disclosures are complete.
    
- The code being executed does only what the approved proposal permits.
    
- A suspicious action will actually be prevented rather than merely flagged by a dashboard.
    

A proposal can describe a routine treasury payment while the associated execution introduces a dangerous approval, grants a privileged role, or upgrades a proxy to malicious code.

An important nuance: modern governance systems such as OpenZeppelin Governor already bind a proposal to its transaction data. The gap is not simply that someone can arbitrarily replace calldata after a vote. The more interesting gap is that the **human-readable proposal and supporting evidence may not adequately describe or constrain the actual effects of the approved execution**.

### The solution

Build a DAO Accountability Engine that:

1. Ingests proposal documents and supporting evidence.
    
2. Extracts claims using an LLM, with source quotations and page references.
    
3. Detects contradictions and uncertain evidence.
    
4. Converts the approved intent into a structured, signed manifest.
    
5. Commits proposal versions and evidence hashes to a local EVM blockchain.
    
6. Decodes and simulates a proposed transaction.
    
7. Compares the transaction's observed effects against a deny-by-default policy.
    
8. Issues a cryptographic verifier attestation only when the transaction passes.
    
9. Uses an on-chain executor to reject mismatched or unattested actions.
    
10. Presents the evidence, execution differences, and verdict in an explainable dashboard.
    

The central chain of accountability is:

**Proposal text → Evidence → Approved manifest → Transaction → Observed effects → Verdict → Execution or rejection**

The LLM assists with understanding the evidence. Deterministic rules, simulation, cryptographic verification, and smart contracts enforce the safety conditions.

---

## 2. What is confirmed versus what remains uncertain?

### Established project direction

- The working project is the DAO Accountability Engine.
    
- The project needs a real EVM component, not a blockchain simulation implemented entirely in Python.
    
- The primary prototype should use a local Anvil chain.
    
- The first implementation should use a hosted LLM, with a provider-independent interface for later local inference.
    
- The frontend should be a proper interactive dashboard rather than a minimal chat interface.
    
- The main novelty should connect human-readable proposal intent to actual transaction effects.
    
- The executor should enforce approval and attestation requirements on-chain.
    
- Docker should not delay the native end-to-end vertical slice.
    
- The revised build budget is 12–15 hours, with strict cut-lines.
    

### Not yet confirmed

- Which hosted LLM provider has been selected and tested.
    
- Whether the actual repository has been created or which implementation stages are complete.
    
- Whether the event requires a public testnet or only a live local demo.
    
- The exact judging rubric and mandatory acceptance tests.
    
- The final machine specifications and local-model feasibility.
    
- Whether a full voting lifecycle is required or an explicitly simulated approval is sufficient.
    

Do not represent any of these unresolved items as already implemented.

---

## 3. The core technical idea

### 3.1 The proposal manifest

A manifest is a machine-readable description of what an approved proposal is allowed to do.

For example, a proposal might authorize transferring a particular quantity of a particular token to one recipient. Its manifest specifies the token, recipient, amount, and allowed effects.

The manifest should also bind to:

- The exact proposal-text version.
    
- The supporting evidence.
    
- The previous version, if one exists.
    
- The permitted transaction effects.
    
- The declared actions and relevant security constraints.
    

A simplified conceptual example:

```
{
  "proposalId": "PROP-001",
  "version": 1,
  "proposalTextHash": "0x...",
  "evidenceRoot": "0x...",
  "actions": [
    {
      "kind": "erc20_payout",
      "token": "0x...",
      "recipient": "0x...",
      "amountRaw": "5000000000000",
      "decimals": 6
    }
  ],
  "envelope": {
    "allowApprovals": false,
    "allowRoleChanges": false,
    "allowImplChange": false,
    "allowNewContracts": false
  }
}
```

This is illustrative, not a final schema.

The LLM can propose a manifest from the evidence, but a human must review and confirm it. The proposer then signs the approved manifest.

**The LLM must never silently decide what the DAO has authorized.**

### 3.2 Proposal version commitments

Canonicalize the manifest and calculate a cryptographic hash. Store the version hash and evidence commitment on-chain.

Conceptually:

`versionHash = keccak256(canonicalManifest || previousVersionHash)`

This creates a verifiable history of proposal versions.

If someone modifies the document or manifest, recomputing the hash should reveal the discrepancy.

The design should distinguish between:

- A document being stored off-chain.
    
- A document's integrity being checked using its hash.
    
- A document being proven true.
    

A hash proves neither truth nor authenticity by itself. It establishes a cryptographic relationship to particular bytes.

### 3.3 Transaction verification

The proposed transaction is decoded, analyzed, and simulated.

The engine compares the observed effects with the approved effects envelope. Examples of effects include:

- Token transfers and balance changes.
    
- Native-token transfers.
    
- Allowance changes.
    
- Role or ownership changes.
    
- Proxy implementation changes.
    
- New contract deployments.
    
- Unexpected nested calls.
    

The principle is:

**Observed effects must be a subset of the explicitly permitted effects.**

Anything outside the supported and permitted scope must not be silently approved.

### 3.4 Enforcement

The proposed architecture uses a custom `GuardedExecutor` and a treasury that only permits this executor to move funds.

The executor checks that:

- The transaction action matches the approved action hash.
    
- The verifier attestation is valid.
    
- The attestation refers to the correct proposal and evidence.
    
- The verdict is `VERIFIED`.
    
- The attestation has not expired.
    
- The proposal has not already been executed.
    

The signature should use EIP-712 typed data, with the chain ID and verifying contract bound through the domain separator. Replay protection and consistent Python/Solidity encoding are essential.

The important distinction is that a suspicious result should not merely turn a dashboard card red. It must prevent the protected execution path from proceeding.

---

## 4. Architecture and technology stack

|Layer|Selected direction|Purpose|
|---|---|---|
|Frontend|React + TypeScript, preferably Vite for speed|Proposal review, evidence, manifest, execution diff and verdict|
|Backend|Python + FastAPI|APIs, ingestion, orchestration, verification|
|Database|SQLite|Metadata, analyses, audit records and cache|
|PDF extraction|PyMuPDF|Native PDF text and page-level provenance|
|OCR|RapidOCR, with OCR only where needed|Extract text from scanned pages|
|LLM|One hosted provider initially|Structured claim extraction and explanation|
|Local LLM|Ollama, later|Offline or confidential-source processing|
|Validation|Pydantic|Validate structured LLM output|
|Blockchain|Solidity + Foundry + Anvil|Real EVM execution and enforcement|
|Contract libraries|OpenZeppelin|Standard ERC-20, cryptographic and proxy components|
|Python/EVM integration|web3.py and eth-account|RPC, hashing, signatures and contract calls|
|Graph analysis|NetworkX|Wallet relationship analysis|
|Graph UI|Cytoscape.js or React Flow|Optional interactive wallet graph|
|Packaging|Docker Compose, later|Reproducible integrated environment|

### Why this stack?

It balances the time constraint with the need for a genuine blockchain security demonstration.

- Python makes document processing, OCR, LLM integration and analysis practical.
    
- React supports a polished, explainable UI.
    
- Solidity and Anvil demonstrate actual EVM behavior and transaction rejection.
    
- SQLite avoids unnecessary database infrastructure.
    
- A local chain gives reproducible scenarios without faucet, testnet or network dependencies.
    

### What should not be added initially?

Do not introduce a vector database, microservices, a production database, Kubernetes, a public blockchain dependency, or a full general-purpose governance framework unless a demonstrated requirement justifies it.

The proposal evidence can initially be stored and retrieved using ordinary files, SQLite metadata and straightforward text lookup.

---

## 5. Blockchain architecture choice

Three options were considered.

### Option A — Registry and Python verifier only

This can commit hashes and display findings, but does not convincingly demonstrate that a suspicious execution is actually blocked.

**Verdict:** Too weak as the complete prototype.

### Option A-plus — Registry, treasury and guarded executor

Use:

- `MockToken`
    
- `GovernanceRegistry`
    
- `Treasury`
    
- `GuardedExecutor`
    
- A small approval or voting simulation
    
- A verifier that signs passing execution attestations
    

This preserves real EVM semantics while limiting implementation complexity.

**Verdict: Recommended for the core prototype.**

### Option B — Full Governor, Timelock and governance lifecycle

This is more realistic, but introduces voting periods, quorum, roles, timelock delays and additional integration work.

**Verdict:** Add only after Option A-plus works end to end.

### Other options

Forking a real DAO can provide real-world data but adds infrastructure and does not itself provide enforcement. A Python-only simulated chain is not an acceptable substitute for the on-chain requirement.

### Important trust limitation

The proposed verifier uses a signing key. If that key is compromised, or the verifier incorrectly approves a malicious transaction, the system may be compromised.

Document this trust assumption clearly. Multi-verifier signatures or threshold attestation can be future work.

---

## 6. Core features and novelty

### Feature 1 — Evidence-grounded intelligence

The LLM returns structured claims, for example:

```
{
  "field": "requested_amount",
  "value": "5000000",
  "quote": "The proposal requests $5M...",
  "source_id": "proposal.pdf",
  "page": 3
}
```

The backend validates the schema and verifies that the quotation actually occurs in the source text, allowing whitespace normalization.

A number in a claim must be consistent with the supporting quotation.

Fabricated or ungrounded claims should be rejected and logged.

### Feature 2 — Cross-document conflict detection

Compare claims across documents and sources.

Example:

- Governance proposal: $5 million.
    
- Supporting document: $5.8 million.
    

The dashboard should show both values, their sources and quotations, and a `CONFLICT` finding.

This should be deterministic after extraction. The LLM should not be the sole authority deciding whether the figures agree.

### Feature 3 — Evidence and proposal version integrity

Create canonical manifests and cryptographic commitments for the proposal text and evidence.

A changed document should fail verification against the earlier commitment.

Display version history and verification results.

### Feature 4 — Execution-effects verification

Compare expected effects with actual simulated state changes.

For a payout, verify the token, recipient and amount. A modified recipient or excessive amount must fail.

For an upgrade, inspect the proxy's implementation slot and compare the new implementation against the approved intent.

### Feature 5 — On-chain execution guard

Only a valid, correctly bound and attested transaction should pass through the protected executor.

This is stronger than a dashboard warning because the executor rejects the transaction.

### Feature 6 — Conflict-of-interest analysis

Build a wallet graph from seeded or available transaction history.

Represent relationships such as transfers, shared funding and declared ownership. Search for paths connecting proposer-controlled wallets to recipients.

Labels must distinguish:

- `declared`: disclosed relationship.
    
- `observed`: directly observed on-chain relationship.
    
- `inferred`: a possible relationship suggested by graph analysis.
    

A graph connection does not prove that two wallets belong to the same person.

### Feature 7 — Explainable verdicts

Use a consistent verdict taxonomy:

- `VERIFIED`: supported action is within the approved effects envelope.
    
- `MISMATCH`: observed effects violate the approved intent.
    
- `UNSUPPORTED`: the action is outside the implemented verification scope.
    
- `UNCERTAIN`: evidence quality or extraction confidence is insufficient.
    

Every verdict should display the rule that produced it and the evidence supporting the finding.

### Feature 8 — Reproducible audit trail

Record input hashes, extracted claims, provider and model versions, prompt hash, rule-set version, simulation results and verdict.

This supports reproducibility and makes the demonstration easier to defend.

### The strongest novelty claim

The project's central novelty is **binding the human-readable proposal and its evidence to a constrained execution policy, then checking actual transaction effects against that policy before execution**.

The individual ingredients—LLMs, hashes, transaction simulation and smart-contract guards—are not new by themselves. The contribution is their integration into an explainable accountability workflow.

---

## 7. Supported scope

The first release should explicitly support only a narrow, defensible set of operations.

### Core

- ERC-20 payout.
    
- Approved recipient and amount.
    
- Evidence-backed proposal manifest.
    
- Proposal version commitment.
    
- Valid verifier attestation.
    
- State-difference verification.
    
- Rejection of altered or unattested execution.
    

### High-value extension

- One proxy-upgrade scenario.
    
- Detection of an implementation change outside the manifest.
    
- Basic bytecode scanning for suspicious opcodes and undeclared selectors.
    
- One seeded wallet-graph investigation.
    

### Unsupported operations

Unknown selectors, complex nested calls, unrecognized contract patterns or effects the engine cannot reliably inspect should return `UNSUPPORTED` or require review.

Do not claim comprehensive smart-contract security. A heuristic bytecode scan is not a proof that code is malicious, and the absence of suspicious opcodes is not a proof that code is safe.

---

## 8. Implementation plan: 12–15 hours

The schedule below uses the revised core plan. Times are targets, not guarantees.

### Stage 0 — Environment and connectivity (0–1 hour)

Set up:

- Foundry and Anvil.
    
- Python environment.
    
- Node and frontend shell.
    
- FastAPI health endpoint.
    
- Basic backend connection to Anvil.
    

**Exit criterion:** All three processes start, and the backend reads the local chain.

### Stage 1 — Contracts and enforcement (1–3 hours)

Implement the token, registry, treasury and guarded executor.

Write Foundry tests for:

- Valid execution.
    
- Wrong recipient.
    
- Wrong amount.
    
- Missing attestation.
    
- Invalid attestation.
    
- Replayed execution.
    

Test the action-hash calculation in both Python and Solidity.

**Exit criterion:** Valid actions execute, and invalid actions revert.

If this stage is still broken at hour three, simplify the attestation fields and drop the upgrade scenario temporarily. Do not spend the whole project debugging a sophisticated contract.

### Stage 2 — Document extraction and grounding (3–5 hours)

Implement:

- PDF upload.
    
- File hashing and storage.
    
- PyMuPDF extraction with page numbers.
    
- One hosted LLM provider.
    
- Pydantic output validation.
    
- Grounding and numeric checks.
    
- Deterministic conflict detection.
    
- Cached fixture results.
    

**Exit criterion:** The sample documents produce grounded claims and a detectable contradiction.

### Stage 3 — Manifest and commitments (5–7 hours)

Implement:

- Canonical JSON serialization.
    
- Manifest creation and human confirmation.
    
- Proposal signature.
    
- Evidence commitment.
    
- Version hash chain.
    
- On-chain commitment and verification.
    

**Exit criterion:** A committed version can be read back and verified; tampering with the evidence is detected.

Introduce Docker only after the native path is working. Do not let container setup block the primary features.

### Stage 4 — Simulation and execution guard (7–10 hours)

Implement:

- Transaction decoding for supported actions.
    
- Anvil-based simulation.
    
- State snapshot and comparison.
    
- Effects-envelope validation.
    
- Verdict generation.
    
- Verifier attestation.
    
- Execution through the actual guarded executor.
    

**Exit criterion:** Scenario A executes successfully; a modified payout is rejected.

This is the highest-value and highest-risk stage.

### Stage 5 — Dashboard and wallet graph (10–12 hours)

Implement the core dashboard:

- Claims and source quotations.
    
- Conflicting evidence.
    
- Proposal manifest and version history.
    
- Expected-versus-observed effects.
    
- Verdict, attestation and transaction result.
    
- Deterministic scenario buttons.
    

Add a small seeded wallet graph if time permits.

**Exit criterion:** A judge can run a scenario and understand the result without reading source code.

### Stage 6 — High-value extension and packaging (12–15 hours)

Prioritize:

1. One malicious proxy-upgrade scenario.
    
2. A seeded wallet graph.
    
3. Failure-path testing.
    
4. Docker Compose smoke test.
    
5. README and demo rehearsal.
    

Do not attempt to add every planned feature if the core flow is not stable.

---

## 9. Online-first, offline-later strategy

The online-first decision is about delivery speed, not making the entire system dependent on the internet.

### First: hosted LLM

Use one provider and a stable JSON schema. Test it against fixed fixtures. Do not spend hours comparing every provider.

Keep a small provider interface:

```
class LLMProvider:
    def extract_claims(self, sources):
        ...

    def summarize(self, claims):
        ...
```

The grounding checks, conflict detection, manifest logic and transaction verification should remain independent of the provider.

### Second: caching

Cache extraction results using the input hash, prompt hash and model identifier.

This makes the demonstration reproducible, reduces rate-limit risk and allows fixed scenarios to run without repeatedly calling the provider.

A cache hit is useful for a demo, but it is not evidence that the offline inference path works.

### Third: local inference

Add Ollama only after the core pipeline works.

Use the same structured-output schema and run the same fixtures through the hosted and local providers. Compare extraction quality, grounding success and conflict detection.

### Hybrid routing rules

- Public fixture: hosted provider permitted.
    
- Non-confidential source: hosted provider may be used if configured.
    
- Confidential source: local provider only.
    
- If local inference is unavailable for confidential material: return `LLM_UNAVAILABLE`.
    
- If a provider fails or returns invalid output: retry according to a bounded policy, then fall back if allowed or return an explicit failure.
    

**Never silently send confidential material to a hosted provider as a fallback.**

The offline mode requires more than a local model. It also requires the local blockchain, dependencies, cached fixtures, frontend assets and necessary model weights to be available.

---

## 10. Docker policy

Do not start by building the entire project inside Docker.

Use the native development loop first:

- Python virtual environment.
    
- Frontend development server.
    
- Anvil.
    
- Foundry tests.
    

Once the core path works, create a small Compose setup with frontend, backend and Anvil. Persist the SQLite database, uploads and cache through a volume.

Keep environment-specific configuration separate:

- Native RPC: `http://127.0.0.1:8545`
    
- Compose RPC: `http://anvil:8545`
    

Rebuild images when dependencies or system packages change, not after every source-code edit.

Before the final demonstration:

- Run a clean build.
    
- Reseed and redeploy the local chain.
    
- Run the scripted scenarios.
    
- Confirm persisted files are available.
    
- Freeze dependencies and avoid late infrastructure changes.
    

A working native prototype plus a tested Compose setup is better than a half-working Docker-first project.

---

## 11. Suggested repository structure

```
dao-integrity/
├── contracts/
│   ├── src/
│   │   ├── MockToken.sol
│   │   ├── GovernanceRegistry.sol
│   │   ├── Treasury.sol
│   │   ├── GuardedExecutor.sol
│   │   └── Box.sol
│   ├── test/
│   └── script/
├── backend/
│   └── app/
│       ├── ingestion/
│       ├── llm/
│       ├── claims/
│       ├── chain/
│       ├── graph/
│       ├── api/
│       └── main.py
├── frontend/
├── fixtures/
│   ├── pdf_digital.pdf
│   ├── pdf_scanned.pdf
│   ├── post.txt
│   └── expected/
├── scripts/
│   ├── seed_chain.py
│   └── run_scenarios.py
├── data/
├── .env.example
├── docker-compose.yml
└── README.md
```

This is a proposed structure, not a verified description of an existing repository. Keep the initial implementation simpler if necessary.

---

## 12. Five-minute demonstration

### 0:00–0:30 — Explain the gap

“Voters approve a proposal, but the system must also verify that the actual execution stays within the approved intent.”

### 0:30–2:00 — Show evidence intelligence

Upload the prepared proposal and supporting documents.

Show the grounded claims, a contradiction such as $5 million versus $5.8 million, and the evidence quotations.

### 2:00–2:30 — Show proposal integrity

Confirm the manifest, commit the version and show its on-chain hash. Modify a fixture and demonstrate the failed integrity check.

### 2:30–3:15 — Show a legitimate execution

Run the valid payout. Show the expected effects, observed effects, successful attestation and completed transfer.

### 3:15–4:30 — Show a malicious or mismatched execution

Attempt a modified payout or, if implemented, a malicious proxy upgrade.

Show the exact rule violation, state difference, absence of a valid attestation and the executor's rejection.

### 4:30–5:00 — Explain limitations

State the supported operation types, the verifier-key trust assumption and the limitations of heuristic analysis.

The demonstration should be deterministic and should not depend on live model calls completing at the right moment.

---

## 13. Critical risks and mitigations

|Risk|Mitigation|
|---|---|
|Blockchain learning consumes the schedule|Build and test the smallest real EVM path first|
|LLM fabricates claims|Require quotations, page references and deterministic grounding|
|Hosted provider fails|Cache fixtures and return explicit failure states|
|Simulation tooling is unreliable|Prefer state snapshots and differences over dependence on advanced trace APIs|
|Malicious effects evade simple amount checks|Deny by default; check allowances, roles and implementation changes|
|Attestation is trusted too broadly|Document the verifier trust assumption and bind signatures to context|
|Local-chain state disappears|Provide deterministic deployment and seeding scripts|
|Wallet graph implies unsupported accusations|Separate observed and inferred relationships|
|Too many features consume the schedule|Preserve the core execution path and use strict cut-lines|
|Docker consumes development time|Containerize after native end-to-end success|

---

## 14. Testing checklist

### Smart contracts

- Valid action executes.
    
- Modified recipient or amount reverts.
    
- Missing or invalid signature reverts.
    
- Expired attestation reverts.
    
- Wrong evidence root reverts.
    
- Replay is prevented.
    
- Python and Solidity action hashes match.
    

### Evidence pipeline

- Extracted quotations exist in the source.
    
- Fabricated quotations are rejected.
    
- Conflicting numbers are detected.
    
- Uncertain OCR results are marked uncertain.
    
- Provider failure does not create fake successful results.
    

### Integrity and simulation

- Modified manifest or evidence is detected.
    
- Observed effects outside the envelope fail verification.
    
- A failed verification cannot obtain an execution attestation.
    
- The executor rejects the malicious scenario.
    

### Delivery

- Fresh startup works.
    
- Anvil can be reseeded after restart.
    
- The dashboard runs all primary scenarios.
    
- Docker Compose passes the same smoke test if included.
    
- The demo works with the cached fixtures and does not require a live LLM response.
    

---

## 15. Immediate next actions

1. Read the DAO theory guide sections referenced by the build guide, especially the explanation of the proposal-text/calldata gap and execution verification.
    
2. Verify the event's exact acceptance criteria and whether a public testnet is required.
    
3. Confirm the local toolchain: Foundry, Anvil, Python and Node.
    
4. Create the minimal backend/frontend skeleton and establish chain connectivity.
    
5. Build and test the registry, treasury and guarded executor before adding the document intelligence pipeline.
    
6. Freeze the manifest schema and API contract once the basic end-to-end path works.
    
7. Implement the evidence pipeline and connect it to the manifest.
    
8. Complete simulation, attestation and dashboard integration.
    
9. Add the proxy-upgrade scenario and wallet graph only within the remaining budget.
    
10. Package, rehearse and document the working prototype.
    

### Final priorities

- **Never compromise:** real on-chain enforcement, correct cryptographic binding, evidence grounding, explicit uncertainty and reproducible tests.
    
- **Simplify first:** governance lifecycle, graph visualization, nested-call support and local-model tuning.
    
- **Add later:** full Governor/Timelock integration, threshold verification, broad contract analysis and production deployment.
    

The objective is not to claim that the system secures every DAO transaction. It is to demonstrate a credible, testable mechanism that connects approved intent to execution and prevents a defined class of unauthorized effects.