# CASCADE 4.1 — Live Demonstration Runbook & Workflow Trace

**System:** CASCADE 4.1 DAO Accountability Engine  
**Target:** Presenters, Hackathon Judges, Evaluators  
**File Location:** `docs/demo-runbook.md`  
**Prerequisites:** Anvil running on port 8545, FastAPI running on port 8000, Vite running on port 5173.

---

## 1. Quick Reference: Demo Timelines

CASCADE can be presented in two formats:
1. **The Fast Track (3–5 minutes):** Executive summary, PROP-001 conflict gate, Scenario A (valid payout execution), Scenario B1 (calldata tampering defense), Scenario B3 (malicious upgrade defense).
2. **The Technical Deep Dive (10–15 minutes):** Ingestion, quote grounding, canonical manifest serialization, on-chain hash chaining, EVM simulation deltas, Rule R1–R7 & R9 inspection, COI provenance trail, custom calldata testing, and clean-start reset.

---

## 2. Preflight Checklist & Initial Startup

Before taking the stage, verify the development environment:

```bash
# Terminal 1 — Start Local Anvil EVM (Chain 31337)
anvil --host 127.0.0.1 --silent

# Terminal 2 — Start FastAPI Backend (Port 8000)
cd backend
uv run uvicorn app.main:app --reload

# Terminal 3 — Start Frontend Dev Server (Port 5173)
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

### Health Verification
Open `http://127.0.0.1:5173` in your browser. Verify the Sidebar footer shows:
- `API: Online (:8000)` (green dot)
- `Chain: Anvil (31337) · #<blockNumber>` (green dot)

*Terminal Fallback Check:*
```bash
curl -s http://127.0.0.1:8000/health
# Expected: {"status":"ok","rpc_connected":true,"chain_id":31337,"block_number":...}
```

---

## 3. Fast Demo Path (3–5 Minutes)

### Step 1: Clean Baseline Setup (10 seconds)
- **Where to click:** TopBar $\rightarrow$ Click **"Run Scenarios (A / B1 / C)"** $\rightarrow$ Click **"Scenario C (Reset & Seed)"** tab $\rightarrow$ Click **"Execute Scenario"**.
- **Expected Result:** Steps complete in ~1.5s with green checkmarks:
  `Reset Database Tables` $\rightarrow$ `Deploy Fresh Contracts to Anvil` $\rightarrow$ `Fund Treasury Vault` $\rightarrow$ `Seed & Approve Proposal PROP-002`.
- **Presenter Script:**  
  > *"To ensure 100% reproducibility, we reset our local EVM and database to a known clean state. All 8 contracts are deployed, the Treasury is funded with 1,000,000 USDC, and clean proposal states are seeded."*

---

### Step 2: Ingestion, Grounding & Conflict Gating (45 seconds)
- **Where to click:** 
  1. TopBar $\rightarrow$ Select PID: **`PROP-001`**.
  2. Sidebar $\rightarrow$ Click **"Proposals & Evidence"**.
- **Expected Result:**
  - Notice the **Red Conflict Banner** at the top:  
    `Cross-Source Contradictions Detected (amount: $5.0M vs $5.8M) — Proposal Cannot Be Approved`.
  - In the Evidence Reader, click `clean_proposal_v1.pdf`: quote `"$5,000,000"` is highlighted.
  - In the Document List, click `forum_post.txt`: quote `"$5,800,000"` is highlighted.
  - Notice the status badge on the claims is `UNCERTAIN`.
- **Presenter Script:**  
  > *"Here we see CASCADE's decision intelligence in action. Proposal PROP-001 has conflicting numbers: the formal PDF asks for $5.0M, but the forum post claims $5.8M. The system flags this contradiction, marks the claim UNCERTAIN, and deterministically locks the manifest creation gate."*
- **On-Chain / API Verification (Show terminal if asked):**
  ```bash
  curl -s -X POST http://127.0.0.1:8000/manifest/PROP-001 -H "Content-Type: application/json" -d '{"token_address":"0x21dF544947ba3E8b3c32561399E88B52Dc8b2823"}'
  # Returns: HTTP 422 {"detail":{"error":"ELIGIBILITY_ERROR","message":"Proposal 'PROP-001' has unresolved conflicts..."}}
  ```

---

### Step 3: Scenario A — Valid Approved Payout Execution (60 seconds)
- **Where to click:**
  1. TopBar $\rightarrow$ Select PID: **`PROP-002`**.
  2. TopBar $\rightarrow$ Click **"Run Scenarios"** $\rightarrow$ Select **"Scenario A (Valid Payout)"** tab $\rightarrow$ Click **"Execute Scenario"**.
- **Expected Result:**
  - Steps turn green: `Proposal & Governance Setup` $\rightarrow$ `EVM Simulation & Rule Verification` $\rightarrow$ `EIP-712 Attestation` $\rightarrow$ `Guarded Execution on Chain`.
  - Verdict badge: `VERIFIED`.
  - Transaction receipt: Mined in block #, hash shown.
  - State deltas: Treasury balance reduced by 1,000,000 USDC; Recipient received exactly 1,000,000 USDC.
- **Presenter Script:**  
  > *"For the valid grant proposal PROP-002, the submitted transaction is simulated against an Anvil snapshot. All 8 rules pass, zero diffs are detected, and the verifier issues a cryptographic EIP-712 attestation. The GuardedExecutor contract verifies the signature on-chain and dispatches the 1,000,000 USDC payout."*

---

### Step 4: Scenario B1 — Calldata Tampering Rejection (45 seconds)
- **Where to click:**
  - In the Scenario Modal, click the **"Scenario B1 (Substituted Payout)"** tab $\rightarrow$ Click **"Execute Scenario"**.
- **Expected Result:**
  - Execution halts at verification:
    - Verdict: `MISMATCH`.
    - Step `Static & Simulation Verification`: `Failed: Rule R2 failed: actionHash mismatch`.
    - Attestation: `Attestation strictly withheld. No signature issued`.
    - On-chain revert: `GuardedExecutor reverted execution on-chain`.
    - Defense proof: Treasury balance remained unchanged; Attacker received 0 tokens.
- **Presenter Script:**  
  > *"Now an adversary intercepts the transaction and modifies the recipient address to steal the funds. Notice the result: Rule R2 immediately catches the actionHash discrepancy. The verifier withholds the attestation, and any direct call to the GuardedExecutor contract reverts. No funds leave the treasury."*

---

### Step 5: Scenario B3 — Contested Upgrade & Backdoor Defense (60 seconds)
- **Where to click:**
  - In the Scenario Modal, click the **"Scenario B3 (Evil Upgrade Blocked)"** tab $\rightarrow$ Click **"Execute Scenario"**.
- **Expected Result:**
  - Verdict: `MISMATCH`.
  - Failure details: `Rule R7 failed: undeclared selector '0x35faa416' (sweep()) discovered in BoxEvil runtime bytecode`.
  - Attestation withheld.
  - Defensive proof: `Proxy implementation slot protected at BoxUUPS (BoxEvil rejected)`.
- **Presenter Script:**  
  > *"Finally, the most insidious attack: a contested protocol upgrade. Voters approved what seemed like a benign BoxV2 contract, but the proposed bytecode contains an undeclared sweep() backdoor. Our static bytecode scanner parses the EVM opcodes, identifies the undeclared function selector, fails Rule R7, and blocks the upgrade. The proxy implementation slot remains completely protected."*

---

## 4. Technical Deep-Dive Path (10–15 Minutes)

Use this expanded sequence when speaking with technical judges, smart contract auditors, or security engineers:

### Phase 1: Ingestion & Document Provenance
1. Navigate to **Proposals & Evidence**.
2. Click on `clean_proposal_v1.pdf`. Show that the document viewer displays native extracted text.
3. Show the **Conflict of Interest (COI) & Wallet Provenance** card at the bottom:
   - Highlight the **"Seeded Demo Graph"** badge.
   - Trace the visual provenance funding trail: `Proposer` $\rightarrow$ `Horizon Labs` $\rightarrow$ `Alice`.
   - Explain that this demonstrates graph-based multi-hop linkage analysis without making subjective accusations.

### Phase 2: Manifest Construction & Cryptographic Commitments
1. Navigate to **Manifests & Versions**.
2. Show the **Cryptographic Hash Commitments** grid:
   - Explain how `proposalTextHash` commits to voter prose.
   - Explain how `evidenceRoot` commits to sorted SHA-256 evidence digests.
   - Explain how `versionHash` links to previous versions via Keccak-256 chaining.
3. Click **"Verify Cryptographic Integrity"**:
   - The green banner appears: `Tamper Check Passed: All commitments match stored and on-chain records`.
4. Show the **On-Chain Version Hash Chain** card:
   - Show that Version 1 has an `Active Approval` badge on `GovernanceRegistry.sol`.

### Phase 3: The Execution Workbench & Rule Inspector
1. Navigate to **Execution Workbench**.
2. Show the **Side-by-Side Parameter Comparison**:
   - Point out how `target`, `value`, `method`, `recipient`, and `amount` are explicitly compared against the manifest.
3. Show the **EVM Simulation State Deltas** table:
   - Point out the simulation snapshot isolation: baseline state vs post-execution state.
4. Expand **Rule R7 (Selector Whitelist / Scope)**:
   - Show the candidate selector count and code hash.
   - Explain the heuristic opcode scanner: how `scan_bytecode` skips immediate push bytes (`PUSH1`..`PUSH32`) so hash constants are never confused with opcodes.
5. Demonstrate the **Adversarial Calldata Workbench**:
   - Click the `"Adversarial Calldata"` toggle button.
   - Change the Calldata to `0xa9059cbb0000000000000000000000009965507d1a55bcc6475675304ca994970de9774400000000000000000000000000000000000000000000000000000000000f4240` (substituting 1 USDC instead of 1,000,000 USDC).
   - Click **"Run Custom Calldata Verification"**.
   - Show that Rule R2 and Rule R3 immediately flag the alteration and set the verdict to `MISMATCH`.

### Phase 4: Scenario B2 (Benign Upgrade Execution)
1. Open the **Scenario Modal**.
2. Select **"Scenario B2 (Benign Upgrade)"** $\rightarrow$ Click **"Execute Scenario"**.
3. Point out that all selectors (`increment()`, `version()`) were declared in the manifest.
4. Show that Rule R7 passes, attestation is issued, and the on-chain implementation slot updates to `BoxV2` ("2.0.0").

### Phase 5: The Audit Trail & Offline Verification
1. Navigate to **Audit Explorer**.
2. Filter by `ANALYSIS`: show prompt hashes, input hashes, and latency in milliseconds.
3. Filter by `VERIFICATION`: show execution receipts and simulation dumps.
4. Disclose the security limits truthfully: heuristic static scanning is a defensive filter against standard Solidity output; the trust anchor is the immutable `GuardedExecutor` contract on-chain.

---

## 5. End-to-End Technical Workflow Reference

The following table traces how every core operation flows across the UI, API, Python services, and Solidity contracts:

```
+-------------------------------------------------------------------------------------------------------------+
| WORKFLOW             | FRONTEND TRIGGER     | BACKEND ROUTE             | PYTHON MODULES   | CONTRACT CALLED|
+----------------------+----------------------+---------------------------+------------------+----------------+
| Ingest Evidence      | Proposals -> Upload  | POST /sources             | reader.py        | None           |
| Extract Claims       | Proposals -> Analyze | POST /analyze/{pid}       | router.py, llm   | None           |
| Ground Quotes        | Automatic in Analyze | claims/grounding.py       | grounding.py     | None           |
| Detect Conflicts     | Automatic in Analyze | claims/conflicts.py       | conflicts.py     | None           |
| Draft Manifest       | Manifest -> Draft    | POST /manifest/{pid}      | builder.py       | None           |
| Confirm Manifest     | Manifest -> Confirm  | POST /manifest/{pid}/conf | canon.py, hashes | None           |
| Commit Version       | Manifest -> Commit   | POST /commit/{pid}        | client.py        | Registry.commit|
| Approve Governance   | Manifest -> Approve  | POST /approve/{pid}       | client.py        | Registry.approv|
| EVM Simulation       | Execution -> Verify  | POST /verify              | simulate.py      | Treasury.exec  |
| Rule Evaluation      | Execution -> Verify  | verification/verify.py    | verify.py        | None           |
| Sign Attestation     | Execution -> Verify  | chain/attest.py           | attest.py        | None           |
| Guarded Execution    | Execution -> Execute | POST /execute             | routes.py        | Executor.exec  |
| Fast Clean-Start     | TopBar -> Scenario C | POST /scenarios/C/run     | deploy_and_seed  | All 8 Contracts|
+-------------------------------------------------------------------------------------------------------------+
```

---

## 6. Troubleshooting & Presenter Fallbacks

| Symptom | Cause | Solution / Presenter Action |
| :--- | :--- | :--- |
| **Sidebar shows "Chain: Disconnected"** | Anvil node was terminated or not started on port 8545. | Run `anvil --host 127.0.0.1 --silent` in Terminal 1, then click the TopBar Refresh button. |
| **Sidebar shows "API: Offline"** | FastAPI server was terminated. | Run `cd backend && uv run uvicorn app.main:app --reload` in Terminal 2. |
| **"Execute On-Chain" button reverts in Execution Page** | UI passes `calldata_hash` instead of raw calldata. | **Presenter note:** Execute Scenario A via the **Scenario Modal** ("Run Scenarios" pill), which uses the fully automated, verified runner. |
| **Scenario A reports "Proposal was already executed"** | Scenario A was run earlier; proposals are strictly single-use. | Run **Scenario C (Reset & Seed)** from the Scenario Modal. It redeploys fresh contracts and seeds a new clean baseline in 1.5 seconds. |
| **PROP-001 does not show in TopBar dropdown** | TopBar dropdown defaults to `PROP-002`. | Click the proposal dropdown in the TopBar and select `PROP-001 ($5.0M Conflict)`. |
| **Manifest Page shows "No Manifest Generated"** | Active proposal has not yet had a manifest confirmed. | Switch proposal selector to `PROP-002` or run Scenario C to seed the clean baseline manifest. |
