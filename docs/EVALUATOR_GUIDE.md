# Evaluator & Judge Walkthrough Guide — CASCADE 4.1
## Demonstrating On-Chain Governance Accountability on Ethereum Sepolia

> **Target Network:** Ethereum Sepolia (Chain ID `11155111`)  
> **Public Artifact:** [`docs/proof.json`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/docs/proof.json)  
> **Web UI Route:** `http://127.0.0.1:5173` (Audit Explorer)  
> **Estimated Demo Duration:** 5 – 7 minutes  

---

## 1. Quick Summary: What This Evaluates

Traditional DAO governance relies on off-chain forums and PDF grant descriptions, but on-chain execution executes arbitrary bytecode hex strings. Attackers exploit this gap through **calldata parameter substitution**, **unauthorized treasury drains**, and **hidden proxy upgrade backdoors**.

CASCADE 4.1 bridges this gap by enforcing a deterministic chain of custody from human evidence to smart contract execution:
1. **Human Evidence & Grounded Claims:** Text from proposal PDFs and forum posts is parsed and verified as exact character substrings.
2. **Canonical Manifest & On-Chain Hashing:** Confirmed claims produce deterministic cryptographic commitments (`versionHash`, `actionHash`, `evidenceRoot`) committed to `GovernanceRegistry.sol`.
3. **Deterministic Rule Verification (R1–R7, R9):** Submitted calldata is decoded and simulated off-chain against strict invariant rules. The LLM never decides execution verdicts.
4. **Guarded Single-Use Execution:** `GuardedExecutor.sol` checks the EIP-712 attestation signature, enforces one-time execution, verifies action binding, and routes the transaction through `Treasury.sol`.

---

## 2. 5–7 Minute Live Demonstration Script

Follow this step-by-step sequence when presenting the project to evaluators.

### Step 1: Open the Audit Explorer (0:00 – 0:45)
1. Navigate to the workbench at `http://127.0.0.1:5173`.
2. Click the **"Audit Explorer"** button in the TopBar (or select the Audit tab).
3. **Point out the Network Banner:**
   - Shows `Ethereum Sepolia (11155111)`.
   - RPC Health: `healthy` with live block number.
   - Proof Badge: `PROOF MODE · Real EVM Tx`.
4. **Point out Core Contracts Card:**
   - Four verified contracts on Ethereum Sepolia:
     - `MockToken (USDC)`
     - `GovernanceRegistry`
     - `Treasury`
     - `GuardedExecutor`
   - Notice the green **`has code`** bytecode verification badges on all four contracts.
   - Note the **Read-Only Wallet Viewer** in the TopBar displaying connection status without requesting private keys.

---

### Step 2: Live On-Chain Balances & Freshness (0:45 – 1:30)
1. Direct the evaluator's attention to the **"Protocol Roles & Treasury Live Balances"** card.
2. Note the native Sepolia ETH balances for the operational roles: `proposer`, `governance`, `verifier`, and `attacker`.
3. Point out the Treasury balance:
   - Initial funding: `1,000,000 USDC`.
   - Post-execution live balance: `0.00 USDC` (transferred to legitimate recipient Alice).
4. Click the **"Refresh"** button:
   - Notice the `"Last refreshed: [time]"` timestamp updating in real-time.
   - Live on-chain RPC state queries `MockToken.balanceOf(Treasury)`.

---

### Step 3: Walk the Verification Lifecycle Timeline (1:30 – 3:30)
Scroll to the **"On-Chain Verification Lifecycle Timeline"**. This visual timeline displays all five sequential transactions published and mined on Ethereum Sepolia:

| Step # | Event / Action | Actor | Outcome | On-Chain Effect |
| :---: | :--- | :--- | :---: | :--- |
| **1** | `commitVersion` | Proposer | `SUCCESS (Status 1)` | Commits `versionHash`, `actionHash`, and `evidenceRoot` to `GovernanceRegistry`. |
| **2** | `approve` | Governance | `SUCCESS (Status 1)` | Governance signs approval for the latest version. |
| **3** | **B1 Adversarial Substitution** | Attacker | `BLOCKED (Status 0)` | Attacker attempts to divert 2,000,000 USDC to attacker address. Execution immediately reverts with **`action mismatch`**. |
| **4** | **Valid Guarded Execution** | Proposer / Verifier | `SUCCESS (Status 1)` | Legitimate transaction passes all rules, presents valid EIP-712 attestation, transfers 1,000,000 USDC to Alice. |
| **5** | **Replay Attack Blocked** | Anyone / Attacker | `BLOCKED (Status 0)` | Attacker attempts to replay the executed proposal. Execution immediately reverts with **`already executed`**. |

Point out that:
- Every transaction displays its **Mined Block Number**, **Gas Used**, and **Transaction Fee (ETH)**.
- Reverted transactions clearly explain why on-chain execution halted before state could change.

---

### Step 4: Verify Receipts on Etherscan (3:30 – 4:45)
1. **Inspect Legitimate Guarded Execution:**
   - In Step 4 of the timeline, click the clickable transaction link `https://sepolia.etherscan.io/tx/<hash>`.
   - Point out to the evaluator:
     - **Status:** `Success`
     - **To:** `GuardedExecutor`
     - **Logs / Events:** `ExecutionSucceeded(proposalId, recipient, amount)`
     - **Token Transfer:** 1,000,000 USDC from `Treasury` to Alice (`0x90F7...`).
2. **Inspect Blocked Attack Transaction (Scenario B1):**
   - In Step 3 of the timeline, click the transaction link for the B1 attack attempt.
   - Point out to the evaluator:
     - **Status:** `Fail with error 'action mismatch'`
     - **Why it failed:** The attacker modified the recipient and amount in calldata. The on-chain `GuardedExecutor.sol` computed `keccak256(calldata)` and detected that it diverged from the `approvedAction` hash recorded in `GovernanceRegistry.sol`.
     - **Funds Impact:** Zero funds moved. Attacker received 0 tokens.

---

### Step 5: Before / After Financial Balance Delta (4:45 – 5:30)
Direct the evaluator to the **"Guarded Execution Balance Deltas"** table:
- **Treasury USDC:** $1,000,000 \rightarrow 0$ ($-1,000,000$ USDC delta)
- **Legitimate Recipient (Alice):** $0 \rightarrow 1,000,000$ ($+1,000,000$ USDC delta)
- **Attacker Address:** $0 \rightarrow 0$ ($0$ delta; attack completely prevented)

Click **"Download Proof Bundle"** to export the entire signed verification proof JSON, or click **"Export CSV"** to download the transaction log.

---

### Step 6: Honest Transparency on System Limits (5:30 – 6:30)
Walk through the **Verification Rules Coverage Matrix (R1 – R9)** table:
- **R1 (Version Binding):** Full on-chain check via `latestVersion`.
- **R2 (Action Binding):** Full on-chain check via `keccak256(calldata)`.
- **R3 (Envelope Limits):** Full check on transfer parameters.
- **R7 (Selector Scope):** Full static bytecode scanner (`PUSH4` analysis).
- **Reduced Rules (R4, R5, R6, R9):**
  - Explain clearly: On a live public testnet without debug cheat codes (`evm_snapshot`, `evm_revert`), observing arbitrary third-party account balance changes or dynamic storage slot diffs is evaluated via static calldata verification, selector inspection, and EIP-1967 view calls.
  - To execute full dynamic state diffs against Sepolia contracts, an evaluator can point `SIM_FORK_URL` to an Anvil fork (`anvil --fork-url "$AMOY_RPC" --port 8546`).
  - Scenarios A, B1, B2, B3, C can also be triggered interactively against local Anvil via the TopBar modal.

---

## 3. Frequently Asked Questions (Judge Q&A)

### Q1: Why test on a public testnet instead of only using Anvil?
> **Answer:** Local Anvil networks are isolated, synthetic sandboxes with zero latency, zero gas fee market volatility, and custom cheat codes (`anvil_impersonateAccount`, `evm_snapshot`). Operating on **Ethereum Sepolia** proves that:
> 1. The EIP-712 domain separator correctly recovers signers with the real public chain ID (`11155111`).
> 2. EIP-1559 type-2 gas pricing and dynamic tip estimation handle public mempool congestion.
> 3. Smart contract reverts (`action mismatch`, `already executed`) are genuinely enforced by Ethereum Virtual Machine consensus and recorded immutably on Etherscan.

### Q2: Why does `tx_hash` differ from `versionHash`?
> **Answer:** They serve completely different cryptographic purposes:
> - `tx_hash` is the standard Ethereum transaction hash: $\text{keccak256}(\text{RLP-encoded signed transaction})$. It identifies a specific transaction mined into a block.
> - `versionHash` is the CASCADE application-level provenance digest: $\text{keccak256}(\text{canonical\_manifest}_v \parallel \text{versionHash}_{v-1})$. It binds the sequential version of the proposal claims to the governance registry on-chain.

### Q3: What is a "Dry-Run" and how does it prevent gas waste?
> **Answer:** Running `make dry-run` executes the complete verification pipeline locally:
> 1. Builds the canonical manifest and calculates all hashes.
> 2. Signs the EIP-712 attestation using the verifier key.
> 3. Verifies cryptographic recovery against the public `GuardedExecutor` address.
> 4. Generates `docs/dryrun.json` containing simulated transactions and balances.
>
> **Zero transactions are broadcast to Ethereum Sepolia**, and zero gas is spent. This allows operators to verify attestation parameters before spending real testnet ETH.

### Q4: How is secret hygiene maintained?
> **Answer:** No private keys or API keys are ever committed to the repository, stored in database records, or returned by API endpoints. The frontend is strictly read-only: it queries blockchain state via JSON-RPC view calls and never handles private keys. The verification script `scripts/check_proof.py` scans `docs/`, `data/`, and database tables to ensure zero secret leakage.

---

## 4. Verification Check Commands for Evaluators

Evaluators can run these commands independently from the repository root:

```bash
# 1. Run full automated test suite (backend pytest, forge contracts, and frontend build)
make test

# 2. Independently validate public proof artifact against Ethereum Sepolia RPC
make check-proof

# 3. Verify smart contract on-chain bytecode and wiring
make verify-deploy
```
