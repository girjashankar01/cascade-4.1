# CASCADE 4.1 — Technical Deep Dive & Judge Defense Q&A

**System:** CASCADE 4.1 DAO Accountability Engine  
**Event:** CASCADE ’26, Problem 4.1  
**Target:** Presenters, Lead Engineers, Hackathon Judges  
**File Location:** `docs/project-explanation-and-judge-qa.md`

---

## 1. End-to-End Execution Story: From Prose to On-Chain Transaction

### Plain English Summary
When a DAO voter reads a proposal, they see a human-written document (e.g. *"Grant $1,000,000 USDC to Alice for security research"*). Traditional governance systems only verify that the hash of the submitted transaction calldata matches what was voted on. They cannot verify that the calldata **actually does what the human text promised**.

CASCADE transforms governance from an honor system into a verifiable, deterministic pipeline:
1. The human text is digested and its claims are extracted.
2. The claims are verified against the document coordinates (grounding).
3. Any cross-source contradictions lock the proposal.
4. Clean claims form a canonical manifest that is signed and committed on-chain.
5. When execution is requested, the transaction is simulated in an EVM sandbox.
6. A deterministic rule engine checks that the transaction does **only** what was approved.
7. A verifier issues a cryptographic EIP-712 attestation.
8. The on-chain `GuardedExecutor` contract enforces the attestation and dispatches the funds.

---

## 2. Division of Responsibilities: LLM vs Python vs Solidity

A fundamental architectural principle of CASCADE is **defense-in-depth with strict responsibility boundaries**:

```
+----------------------------------------------------------------------------------+
| LLM (Hosted / Local)                                                             |
| - Extracts candidate claims from unstructured PDF / forum prose                  |
| - Identifies potential fields: amount, token, recipient, purpose, assumptions     |
| - Provides quote snippets and page references                                    |
| * NEVER DECIDES VERDICTS. CANNOT APPROVE MANIFESTS. FAILS CLOSED.                |
+----------------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------+
| DETERMINISTIC PYTHON ENGINE (Backend Service)                                     |
| - Character-by-character substring quote verification (grounding)                |
| - Decimal monetary normalization and cross-source conflict detection             |
| - Canonical JSON serialization (canon.py) and cryptographic hashing              |
| - Anvil EVM snapshot simulation & differential state tracking                    |
| - Evaluates Rules R1-R7 and R9 against the manifest envelope                     |
| - Static EVM bytecode opcode scanner (PUSH4 candidate selector heuristic)        |
| - Signs EIP-712 typed data attestations with verifier private key                |
+----------------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------+
| SOLIDITY SMART CONTRACTS (On-Chain Trust Anchor)                                 |
| - GovernanceRegistry: sequential 1-indexed version chain; revokes prior approvals|
| - GuardedExecutor: single-use execution check; verifies EIP-712 typed signature; |
|   verifies deadline; checks actionHash == approvedAction                         |
| - Treasury: holds DAO USDC vault; callable exclusively by GuardedExecutor         |
| - UUPS Proxy: proxy storage slot protected; upgrades restricted to Treasury      |
+----------------------------------------------------------------------------------+
```

---

## 3. The 8 Deterministic Verification Rules (R1–R7, R9)

Section 5.6 of `docs/dao-build-guide-final.md` defines 8 deterministic rules. **Rule R8 is unassigned in the specification**:

### Rule R1: Approved Version and Governance Commitment
- **What it checks:** Reconstructs the canonical manifest from database records, recomputes `versionHash`, queries `GovernanceRegistry.approved(pid)` on-chain, and asserts that the recomputed `versionHash` and `evidenceRoot` match the on-chain approved governance tuple exactly. Verifies proposer signature.
- **Why it matters:** Prevents an off-chain database administrator from tampering with manifest terms after governance has voted.

### Rule R2: Action Hash and Decoded Transaction Parameters
- **What it checks:** Computes the submitted transaction's action hash:
  $$\text{actionHash} = \text{keccak256}(\text{abi.encode}(\text{target}, \text{value}, \text{keccak256}(\text{calldata})))$$
  Asserts equality with `manifest.actionHash`. Strictly decodes calldata parameters (target, value, selector, recipient, amount) and computes a field-level diff against `manifest.action`.
- **Why it matters:** Defends against calldata tampering attacks (Scenario B1) where an adversary substitutes an attacker-controlled recipient address or alters payout amounts.

### Rule R3: Token Outflow Envelope Compliance
- **What it checks:** Evaluates EVM simulation balance deltas for the Treasury and Recipient. Asserts that Treasury token outflow $\le \text{manifest.envelope.maxAllowedOutflow}$ and Recipient token inflow $\ge \text{manifest.action.amountRaw}$.
- **Why it matters:** Prevents hidden draining attacks where a transaction transfers more funds than approved or siphons money to unintended parties.

### Rule R4: Prohibited Balance Increases
- **What it checks:** Scans all watched addresses across the simulation. Asserts that zero unexpected balance increases occurred on non-recipient addresses (e.g. attacker wallets, intermediaries).
- **Why it matters:** Catches complex reentrancy or side-effect transfers that siphon tokens to secondary accounts.

### Rule R5: Allowance and Approval Modifications
- **What it checks:** Diffs token allowances (`allowance(treasury, *)`) before and after simulation. Asserts that allowances remain strictly unchanged unless `manifest.envelope.allowApprovals == true`.
- **Why it matters:** Prevents an approved transaction from sneaking in an `approve(attacker, MAX_UINT256)` call that allows draining the Treasury in a subsequent block.

### Rule R6: Implementation Slot Immutability
- **What it checks:** Diffs the EIP-1967 implementation storage slot (`0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`) of all watched proxies. For payout proposals, asserts zero slot modifications. For upgrade proposals, asserts that the slot changes strictly to `manifest.action.newImpl`.
- **Why it matters:** Prevents payout proposals from silently upgrading protocol logic, and ensures upgrade proposals only point to the authorized implementation contract.

### Rule R7: Selector Whitelist / Scope (Bytecode Static Scan)
- **What it checks:** Inspects the runtime bytecode of the new implementation contract using `scan_bytecode`. Extracts candidate 4-byte selectors discovered via `PUSH4` instructions in Solidity dispatchers. Asserts that all candidate selectors are elements of $\text{baselineSelectors} \cup \text{declaredSelectors}$.
- **Why it matters:** Catches hidden backdoors (Scenario B3). When `BoxEvil` exposes an undeclared `sweep()` backdoor (`0x35faa416`), Rule R7 immediately fails with `MISMATCH` and withholds the attestation.

### Rule R9: Owner and Access Control Role Immutability
- **What it checks:** Inspects contract ownership (`owner()`) and access control roles across watched contracts before and after simulation. Asserts zero unauthorized ownership transfers.
- **Why it matters:** Prevents proposals from hijacking protocol governance by transferring contract ownership to an attacker address.

---

## 4. Storage Architecture: SQLite vs On-Chain

| Data Entity | Storage Location | Mutability | Security Invariant |
| :--- | :--- | :--- | :--- |
| **Ingested Evidence Files** | Filesystem (`data/sources/`) & SQLite | Immutable | Verified via SHA-256 and `evidenceRoot` Keccak hash. |
| **Grounded Claims & Conflicts** | SQLite (`claims`, `conflicts`) | Mutable during draft | Verified via substring matching against extracted text. |
| **Canonical Manifests** | SQLite (`manifests`) | Immutable once confirmed | Verified via `versionHash` and Proposer ECDSA signature. |
| **Version Hash Chain** | On-Chain (`GovernanceRegistry.sol`) | Append-only sequential | Sequential 1-indexed; revision invalidates prior approvals. |
| **Governance Approval Tuple** | On-Chain (`GovernanceRegistry.sol`) | Governance key only | Holds active `(versionHash, actionHash, evidenceRoot)`. |
| **EIP-712 Execution Attestation** | SQLite (`verifications`) & Ephemeral | Signed once per run | Bound to verifier key, chain ID, contract address, and deadline. |
| **Single-Use Replay State** | On-Chain (`GuardedExecutor.sol`) | Immutable once `true` | `executed[pid] = true` set before external execution. |
| **DAO Vault USDC Balance** | On-Chain (`MockToken.sol`) | Controlled by Treasury | Transfers callable exclusively by `GuardedExecutor`. |
| **Proxy Implementation Slot** | On-Chain (`ERC1967Proxy.sol`) | Upgraded via Treasury | Slot modification checked in simulation and guarded on-chain. |

---

## 5. Comparison Matrix of the 5 Demonstration Scenarios

| Attribute | Scenario A | Scenario B1 | Scenario B2 | Scenario B3 | Scenario C |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Scenario Name** | Valid Approved Payout | Calldata Tampering | Benign Protocol Upgrade | Malicious Upgrade Defense | Clean Reset & Seed |
| **Proposal ID** | `PROP-002` | `PROP-B1` | `PROP-B2` | `PROP-B3` | `PROP-002` |
| **Proposal Kind** | `erc20_transfer` | `erc20_transfer` | `proxy_upgrade` | `proxy_upgrade` | Environment Setup |
| **Target Action** | Transfer 1M USDC to Alice | Divert 1M USDC to Attacker | Upgrade Proxy to `BoxV2` | Upgrade Proxy to `BoxEvil` | Deploy 8 Contracts & Seed |
| **Adversarial Vector** | None (Happy path) | Attacker substitutes calldata | None (Happy path upgrade) | Undeclared `sweep()` backdoor | Stale database / spent state |
| **Simulation Result** | 1M USDC Treasury outflow | 1M USDC Attacker inflow | Slot changes to `BoxV2` | Slot changes to `BoxEvil` | Fresh chain state |
| **Rule Failure** | None (All 8 Pass) | **Rule R2 Fails** (Action diff) | None (All 7 Pass) | **Rule R7 Fails** (`sweep()` found) | None |
| **Verdict** | `VERIFIED` | `MISMATCH` | `VERIFIED` | `MISMATCH` | — |
| **Attestation Status** | **Issued** (Signed EIP-712) | **Withheld** (`sig = null`) | **Issued** (Signed EIP-712) | **Withheld** (`sig = null`) | — |
| **On-Chain Result** | **Executed** in block # | **Reverted** (`action mismatch`) | **Executed** in block # | **Reverted** (`bad attestation`) | State reseeded in 1.5s |
| **Observed Balances** | Alice receives 1M USDC | Attacker receives 0 USDC | Storage preserved; v2.0.0 | Implementation slot protected | Treasury holds 1M USDC |

---

## 6. Judge Q&A: Bulletproof Technical Answers

### Q1: "Why not perform all of this verification inside Solidity smart contracts?"
**Answer:**
> *"Solidity is execution-bound and cost-constrained. Verifying natural-language PDF text, evaluating decimal grounding across dozens of claims, running differential EVM simulation across watchlists, and executing static EVM opcode scanning over runtime bytecode would require hundreds of millions of gas—far exceeding Ethereum block gas limits. 
> 
> Instead, CASCADE uses the **Rollup / Coprocessor Architecture**: computationally intensive verification, simulation, and static analysis are performed deterministically off-chain. The result is committed via a compact, standardized EIP-712 attestation. The on-chain `GuardedExecutor` contract enforces the cryptographic proof with minimal gas overhead (~108k gas), providing complete on-chain security without on-chain bloat."*

---

### Q2: "Can an attacker compromise or prompt-inject the LLM to get an unauthorized payout executed?"
**Answer:**
> *"No. The LLM has zero authority to issue verdicts or approve transactions. The LLM is strictly confined to extracting candidate strings from unstructured text. 
> 
> Even if an attacker successfully prompt-injected the LLM to output a fraudulent claim, the **deterministic Python grounding engine** requires the quote to be an exact character-by-character substring of the original ingested PDF. If it does not exist in the document, it is rejected. 
> 
> Furthermore, even if approved by voters, the transaction must pass the **EVM simulation and deterministic rule engine**, which independently diffs balances and checks envelopes. Finally, the **on-chain GuardedExecutor contract** checks the approved action hash and verifier signature. The LLM is completely isolated from the execution trust boundary."*

---

### Q3: "Why use a single trusted verifier key instead of a multi-sig or consensus network?"
**Answer:**
> *"In this CASCADE 4.1 prototype, a single verifier key demonstrates the cryptographic trust anchor and EIP-712 attestation pipeline clearly. 
> 
> The architecture is designed to scale naturally to decentralized verification: the `GuardedExecutor.sol` contract can be trivially upgraded to require a $k$-of-$n$ threshold of verifier signatures, an EigenLayer AVS (Actively Validated Service), or a ZK-proof coprocessor. The EIP-712 typed digest structure remains identical."*

---

### Q4: "How does the system prevent front-running or calldata alteration during transaction broadcast?"
**Answer:**
> *"Through the cryptographic binding of `actionHash`. The EIP-712 attestation signed by the verifier commits to:
> $$\text{actionHash} = \text{keccak256}(\text{abi.encode}(\text{target}, \text{value}, \text{keccak256}(\text{calldata})))$$
> When `GuardedExecutor.execute()` is called on-chain, the contract recomputes the action hash from the broadcasted calldata and asserts that it matches `approvedAction` and the signed attestation digest. If an MEV bot or attacker alters a single byte of calldata in the mempool, the signature verification immediately fails on-chain, and the transaction reverts."*

---

### Q5: "What are the limitations of the PUSH4 static opcode scanner?"
**Answer:**
> *"We document this transparently in our codebase and UI: static opcode scanning is a defensive screening heuristic, not a formal verification proof. 
> 
> Our scanner (`scan_bytecode`) reliably avoids false positives by skipping the immediate data bytes of `PUSH1`..`PUSH32` instructions (so random 4-byte hash constants inside addresses or data are never misidentified as opcodes). It reliably catches standard Solidity function dispatch tables (`PUSH4 <selector> EQ ...`), which is how standard backdoors like `sweep()` are compiled. 
> 
> However, an adversary could theoretically construct dynamic jump tables, obfuscated bytecode, or compute selectors at runtime. For complete security, CASCADE relies on **defense-in-depth**: Rule R6 verifies that the EIP-1967 slot changes only to the approved implementation address, Rule R3 checks balance envelopes, and Treasury authorization prevents arbitrary calls."*

---

### Q6: "Is the Conflict of Interest (COI) graph live on-chain or seeded?"
**Answer:**
> *"It operates on a seeded demonstration graph, and we explicitly label it with a `Seeded Demo Graph` badge in the UI. 
> 
> It demonstrates the graph-theory algorithm: using NetworkX to build a directed graph of declared wallets, observed transfers, and shared funding sources, and finding shortest-path intermediary trails (Proposer $\rightarrow$ Horizon Labs $\rightarrow$ Alice). Building a live mainnet indexer was outside the time budget of CASCADE 4.1; our implementation demonstrates the exact data model and visualization ready to connect to an indexing provider like The Graph or Goldsky."*

---

### Q7: "Why do you use simulated governance instead of OpenZeppelin Governor?"
**Answer:**
> *"Standard Governor contracts require a multi-day voting period, quorum thresholds, and timelock delays before a proposal can be marked approved. To make the entire system testable in under five minutes and demonstrable in real-time, we simulated the governance approval link: a designated key (`PK_GOVERNANCE`) signs `GovernanceRegistry.approve(pid, versionHash)`. 
> 
> Crucially, **the GovernanceRegistry contract interface is identical** to what an OpenZeppelin Governor or TimelockController would invoke. In production, the Governor contract simply becomes the `msg.sender` authorized to call `approve()`."*

---

### Q8: "How does the version hash chain prevent governance rollback attacks?"
**Answer:**
> *"In `GovernanceRegistry.sol`, versions are strictly sequential and 1-indexed. Each version commit stores:
> $$\text{versionHash}_v = \text{keccak256}(\text{canonical\_json}_v \parallel \text{versionHash}_{v-1})$$
> Furthermore, whenever a new version is committed for a proposal, the contract executes `delete _approved[pid]`. This guarantees that if proposal text is modified or revised, any prior governance approval is automatically revoked. An adversary cannot pass a vote on Version 1, commit a malicious Version 2, and execute using Version 1's approval."*
