# CASCADE 4.1 — Complete Frontend & UI Reference Guide

**System:** CASCADE 4.1 DAO Accountability Engine  
**Target:** Presenters, Developers, and Evaluators  
**File Location:** `docs/frontend-ui-reference.md`  
**Frontend URL:** `http://127.0.0.1:5173`  
**Backend API:** `http://127.0.0.1:8000`

---

## 1. Global Navigation & Layout Shell

The frontend uses a persistent dark workbench aesthetic ([`#080A0D`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/styles/tokens.css)) with mint accents ([`#7CE0BE`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/styles/tokens.css)) and an animated traveling grid background.

```
+----------------------------------------------------------------------------------------------------+
| SIDEBAR               | TOPBAR: [Page Title]   PID: [Dropdown v]      [Run Scenarios]  [Refresh]   |
| [Shield] CASCADE      +----------------------------------------------------------------------------+
|                       |                                                                            |
| (•) Overview          |                                                                            |
| ( ) Execution         |                              CONTENT AREA                                  |
| ( ) Proposals         |                         (Active Page Rendered)                             |
| ( ) Manifest          |                                                                            |
| ( ) Audit             |                                                                            |
|                       |                                                                            |
| API: Online (:8000)   |                                                                            |
| Chain: Anvil (#142)   |                                                                            |
+----------------------------------------------------------------------------------------------------+
```

### 1.1 Persistent Sidebar ([`Sidebar.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/layout/Sidebar.tsx))
- **Brand Symbol & Title:** "CASCADE — DAO Accountability".
- **Navigation Tabs:**
  - `Overview` (`onSelectTab('overview')`)
  - `Execution Workbench` (`onSelectTab('execution')`)
  - `Proposals & Evidence` (`onSelectTab('proposals')`)
  - `Manifests & Versions` (`onSelectTab('manifest')`)
  - `Audit Explorer` (`onSelectTab('audit')`)
- **Status Indicators (Footer):**
  - `API: Online (:8000)` / `API: Offline`: Green/red dot driven by `isBackendHealthy`.
  - `Chain: Anvil (31337) · #<blockNumber>` / `Disconnected`: Real-time Anvil block height from `/health`.

### 1.2 Persistent TopBar ([`TopBar.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/layout/TopBar.tsx))
- **Page Title:** Displays active view title.
- **Proposal Selector Dropdown:**
  - Options:
    - `PROP-002`: Clean 1M USDC grant (Scenario A baseline).
    - `PROP-001`: $5.0M PDF vs $5.8M forum post genuine conflict.
    - `PROP-B1`: Substituted payout attack.
  - Trigger: `onChange={(e) => onSelectProposal(e.target.value)}`. Updates `proposalId` globally in `AppShell`.
- **"Run Scenarios (A / B1 / C)" Button:**
  - Opens the interactive [`ScenarioModal`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/scenarios/ScenarioModal.tsx).
- **Refresh Button:**
  - Spins and triggers `refreshState()`, re-fetching `/health`, `/deployments`, and `/manifest/{pid}`.

---

## 2. Key Status Badges & Terminology Dictionary

| Badge / Label | Color / Style | Plain-English Meaning & Enforcement Reality |
| :--- | :---: | :--- |
| **`VERIFIED`** | Mint (`#34d399`) | All 8 deterministic rules (R1–R7, R9) passed. EIP-712 execution attestation is cryptographically signed and issued by the verifier key. |
| **`MISMATCH`** | Red (`#f87171`) | At least one deterministic rule failed (e.g. wrong amount, wrong recipient, undeclared backdoor selector). Attestation is strictly withheld (`attestation_sig: null`). |
| **`UNSUPPORTED`** | Yellow (`#fbbf24`) | Calldata contains a top-level selector other than supported methods (`transfer`, `approve`, `upgradeToAndCall`). |
| **`UNCERTAIN`** | Orange (`#fb923c`) | Claim has conflicting values across sources, low OCR confidence, or unverified numbers. Manifest drafting is blocked. |
| **`ELIGIBILITY_ERROR`** | Red Alert Box | Backend API error (HTTP 422). Returned when attempting to draft or confirm a manifest for a proposal with unresolved conflicts. |
| **`CONFIRMED`** | Mint Badge | Manifest has been drafted, confirmed, and signed by the proposer key. |
| **`DRAFTED`** | Blue Badge | Manifest drafted from claims but awaiting proposer confirmation signature. |
| **`Active Approval`** | Mint Badge | Proposal version currently recorded in on-chain `GovernanceRegistry._approved[pid]`. |
| **`Committed Only`** | Grey Badge | Proposal version committed to `GovernanceRegistry` history but not currently approved by governance. |
| **`Seeded Demo Graph`** | Grey Tag | Explicitly informs judges that wallet provenance and transfer paths are seeded demonstration data, not a live mainnet indexer. |
| **`Simulated Governance`** | Notice Banner | Explains that governance approvals use a designated key (`PK_GOVERNANCE`) to simulate multi-day DAO voting periods. |

---

## 3. Page-by-Page Inventory & Controls

---

### Page 1: Overview Page
**Navigation:** Sidebar $\rightarrow$ **Overview**  
**Component:** [`frontend/src/pages/OverviewPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx)  
**Purpose:** Executive summary of system health, active proposal commitments, governance lifecycle progression, and one-click demo scenario launchpad.

#### Visible Sections & Cards
1. **Hero Header Banner:** Value proposition, tagline, and environment connectivity badges (API port, Anvil block height, Treasury address).
2. **Interactive Lifecycle Strip:** Visual 8-step progression:
   `1. Evidence` $\rightarrow$ `2. Claims` $\rightarrow$ `3. Manifest` $\rightarrow$ `4. Approval` $\rightarrow$ `5. Simulation` $\rightarrow$ `6. Verification` $\rightarrow$ `7. Attestation` $\rightarrow$ `8. Execution`.
   Clicking any stage navigates directly to the relevant workbench page.
3. **Active Governance Intent Card:**
   - Displays Proposal ID, Manifest version (`v1`), Approved payout amount (`1,000,000 USDC`), Recipient address, `actionHash`, and `versionHash`.
   - Action Button: `"Open in Execution Workbench"` $\rightarrow$ switches tab to `execution`.
4. **Automated Demo Scenarios Card:**
   - One-click launchpad cards for **Scenario A** (Valid Payout), **Scenario B1** (Substituted Blocked), and **Scenario C** (Clean Reset & Seed).

#### Controls & Actions Table
| UI element | Meaning | User action | Code / Handler | API / Backend Effect | Expected Result | Caveat |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Lifecycle Stage Button** | Navigates to corresponding workflow page | Click on any step (1 to 8) | `handleStageSelect(stage)` in `OverviewPage.tsx` | Local tab state change | Switches tab to Proposals, Manifest, or Execution | Steps 1, 2, 5, 7, 8 use simplified boolean props in Overview |
| **"Open in Execution Workbench"** | Transitions to execution analysis | Click button | `onNavigate('execution')` | Local tab state change | Switches to Execution Workbench | Requires manifest to exist |
| **"Run A" Button** | Launches Scenario A modal | Click button | `onOpenScenario('A')` | Opens `ScenarioModal` with Tab A active | Modal opens ready to execute Scenario A | Runs against active Anvil instance |
| **"Run B1" Button** | Launches Scenario B1 modal | Click button | `onOpenScenario('B1')` | Opens `ScenarioModal` with Tab B1 active | Modal opens ready to execute Scenario B1 | Demonstrates R2 mismatch defense |
| **"Reset C" Button** | Launches Scenario C reset | Click button | `onOpenScenario('C')` | Opens `ScenarioModal` with Tab C active | Modal opens ready to redeploy & reseed | Destructive reset of demo tables |

*Presenter Script:*  
> *"The Overview dashboard shows the active proposal's cryptographic commitments and live chain health. The lifecycle strip tracks the full chain of custody from ingested PDF evidence to on-chain execution. We can launch any scenario with a single click."*

---

### Page 2: Execution Workbench
**Navigation:** Sidebar $\rightarrow$ **Execution Workbench**  
**Component:** [`frontend/src/pages/ExecutionPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/ExecutionPage.tsx)  
**Purpose:** The central technical workbench. Compares approved manifests against submitted calldata, inspects predicted EVM simulation deltas, evaluates deterministic rules R1–R7 and R9, reviews EIP-712 attestations, and triggers guarded execution.

#### Visible Sections & Cards
1. **Workbench Top Bar:** Active Proposal ID, Target Contract, Calldata Hash, `"Run On-Demand Verification"` button, and `"Adversarial Calldata Workbench"` toggle button.
2. **Governance Model Banner:** Notice clarifying the simulated governance approval key model.
3. **Adversarial Calldata Workbench (Collapsible Drawer):** Allows entering custom target addresses, ETH values, and arbitrary calldata hex strings to test the rule engine against manual exploit payloads.
4. **Calldata & Parameter Comparison Card:** Side-by-side diff table comparing Approved Manifest fields (Target, Value, Method, Recipient, Amount) against Submitted Calldata fields, highlighting mismatches in red.
5. **EVM Simulation State Deltas Card:** Shows pre-state, post-state, and net $\Delta$ for Treasury and Recipient balances (USDC, ETH), allowance changes, implementation storage slots, and ownership changes.
6. **Deterministic Rule Inspector:** Evaluates the 8 rules (R1–R7, R9). Each row displays Rule ID, Name, Status Badge (`PASS` / `FAIL`), and Explanation. Clicking `"Inspect Details"` expands the raw diagnostic evidence JSON.
7. **EIP-712 Attestation & Guarded Execution Card:**
   - Displays Verifier Address, Attestation Deadline, EIP-712 Domain (`GuardedExecutor`, `v1`), and Status Badge (`VERIFIED`, `BLOCKED`, `EXECUTED`).
   - Button: `"Execute On-Chain via GuardedExecutor"` (opens confirmation modal).
8. **Confirmation Modal (`ConfirmModal.tsx`):** Displays execution parameters and requires a click on `"Confirm & Broadcast to GuardedExecutor"`.

#### Controls & Actions Table
| UI element | Meaning | User action | Code / Handler | API / Backend Effect | Expected Result | Caveat |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **"Run On-Demand Verification"** | Runs EVM simulation & rule engine | Click button | `handleRunVerification()` | `POST /verify` | Re-evaluates all 8 rules, updates diffs, signs attestation if verified | Uses reconstructed calldata from manifest |
| **"Adversarial Calldata" Toggle** | Opens custom payload tester | Click button | `setShowCustomTester(!showCustomTester)` | Local UI state toggle | Reveals custom target, value, and calldata inputs | For live adversarial testing |
| **"Run Custom Calldata Verification"** | Tests arbitrary calldata | Click button | `handleRunCustomVerification()` | `POST /verify` with custom `data` | Evaluates rule engine against custom payload | Will produce `MISMATCH` if altered |
| **Rule Row Expand Button** | Expands rule evidence | Click `"Inspect Details"` | `setExpandedRule(rule_id)` | Local UI state toggle | Displays formatted diagnostic JSON for that rule | Useful for showing judges R7 bytecode scan |
| **"Execute On-Chain" Button** | Triggers guarded execution | Click button | `setShowConfirmModal(true)` | Local UI modal toggle | Opens confirmation dialog with target & action details | Only enabled when attestation exists |
| **"Confirm & Broadcast"** | Broadcasts to `GuardedExecutor` | Click button | `handleExecute()` | `POST /execute` | Broadcasts transaction on-chain via Web3 | *Known issue:* UI passes `calldata_hash` instead of raw calldata; recommended to run execution via Scenario Modal |

*Presenter Script:*  
> *"Here in the Execution Workbench, we see the core innovation of CASCADE: calldata is not trusted on faith. The engine simulates the transaction in an EVM sandbox, diffs the state effects against the approved envelope, and evaluates 8 deterministic rules. Only if all rules pass does the verifier issue an EIP-712 attestation."*

---

### Page 3: Proposals & Evidence Reader
**Navigation:** Sidebar $\rightarrow$ **Proposals & Evidence**  
**Component:** [`frontend/src/pages/ProposalsPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/ProposalsPage.tsx)  
**Purpose:** Inspect source evidence documents (PDFs and forum text), read extracted text with coordinate-highlighted quotes, review grounded claims, inspect cross-source conflict callouts, and explore wallet provenance trails.

#### Visible Sections & Cards
1. **Left Column (Evidence Documents & Ingestion):**
   - List of ingested documents showing filename, page count, extraction mode (`Native Text` or `OCR Fallback`), and SHA-256 hash.
   - Upload PDF/Text control (`<input type="file">`).
   - Paste Text Form: inputs for filename and text content with `"Save Pasted Evidence"` button.
2. **Right Column (Extracted Text Reader):**
   - Document title, page pagination pills (`Page 1`, `Page 2`, ...).
   - Text display panel showing extracted prose with amber highlight boxes over quotes linked to grounded claims.
3. **Claims Table Card:**
   - Filter pills (`ALL`, `GROUNDED`, `UNCERTAIN`, `REJECTED`).
   - Table displaying Canonical Field (`amount`, `token`, `recipient`), Value, Verbatim Quote, Page Number, Confidence Score, and Status Badge.
4. **Cross-Source Conflict Banner (Conditional):**
   - Renders when conflicting claims exist across sources for the active proposal (e.g. `PROP-001` $5.0M in PDF vs $5.8M in forum post). Explains that manifest drafting is blocked.
5. **Conflict of Interest (COI) & Wallet Provenance Card:**
   - Badge: `Seeded Demo Graph`.
   - Summary of detected entity relationships.
   - Visual Provenance Funding Trail: Proposer $\rightarrow$ Horizon Labs $\rightarrow$ Alice.
   - Undisclosed Counterparties list.

#### Controls & Actions Table
| UI element | Meaning | User action | Code / Handler | API / Backend Effect | Expected Result | Caveat |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Document List Button** | Selects active document | Click document card | `setSelectedSource(detail)` | `GET /sources/{id}` | Loads document pages into Extracted Text Reader | First document selected by default |
| **Page Pagination Pill** | Switches active page | Click page number | `setSelectedPage(pg)` | Local UI state change | Displays selected page text and highlights quotes | 1-indexed pages |
| **Upload PDF / Text** | Ingests new evidence | Select file from disk | `handleFileUpload(e)` | `POST /sources` (multipart) | File processed, SHA-256 stored, appears in list | Native PyMuPDF or RapidOCR |
| **"Save Pasted Evidence"** | Ingests pasted text | Click button | `handlePasteSubmit(e)` | `POST /sources` (JSON) | Pasted text saved, appears in document list | Useful for forum/Discourse text |
| **Claims Filter Pill** | Filters claims table | Click filter pill | `setFilterStatus(status)` | Local filter | Filters displayed rows to matching status | `ALL` shows all claims |

*Presenter Script:*  
> *"Every claim must be strictly grounded. Notice the highlighted quote in the text reader: the engine verifies that the quote is an exact substring of the PDF before it can ever be included in a manifest. When we switch to PROP-001, you see our conflict detector immediately catch the discrepancy between the $5.0M PDF and the $5.8M forum post."*

---

### Page 4: Manifests & Versions
**Navigation:** Sidebar $\rightarrow$ **Manifests & Versions**  
**Component:** [`frontend/src/pages/ManifestPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/ManifestPage.tsx)  
**Purpose:** Inspect the deterministic canonical manifest JSON, cryptographic hash commitments (`versionHash`, `actionHash`, `proposalTextHash`, `evidenceRoot`), run live tamper verification, and view the on-chain version hash chain.

#### Visible Sections & Cards
1. **Header Action Bar:** Proposal ID title, `"Verify Cryptographic Integrity"` button, and `"Approve Latest Version"` button.
2. **Tamper Check Banner (Conditional):** Shows green checkmark if all recomputed hashes match stored and on-chain records; shows red alert if any field was tampered with.
3. **Cryptographic Hash Commitments Grid:**
   - `versionHash`: Keccak-256 hash over canonical JSON and previous version hash.
   - `actionHash`: Keccak-256 hash over ABI-encoded target, value, and calldata hash.
   - `proposalTextHash`: Keccak-256 hash over exact proposal prose seen by voters.
   - `evidenceRoot`: Keccak-256 hash over sorted SHA-256 evidence digests.
   - Proposer address and ECDSA signature.
4. **Canonical Manifest JSON Viewer:**
   - Syntax-highlighted deterministic UTF-8 JSON viewer with `"Copy JSON"` button.
5. **On-Chain Version Hash Chain Card:**
   - Displays all committed versions on `GovernanceRegistry.sol`, highlighting whether each version is `Active Approval` or `Committed Only`, along with commit and approve transaction hashes.

#### Controls & Actions Table
| UI element | Meaning | User action | Code / Handler | API / Backend Effect | Expected Result | Caveat |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **"Verify Cryptographic Integrity"** | Recomputes commitments | Click button | `handleVerifyIntegrity()` | `POST /verify-version/{pid}` | Verifies hashes match on-chain registry; shows green banner | Detects off-chain tampering |
| **"Approve Latest Version"** | Simulates governance approval | Click button | `handleApproveOnChain()` | `POST /approve/{pid}` | Calls `GovernanceRegistry.approve` on-chain; button changes to "Approved" | Disabled if already approved |
| **"Copy JSON"** | Copies canonical JSON | Click button | `navigator.clipboard.writeText` | Copies to clipboard | Tooltip confirms "Copied!" | Deterministic string without whitespace |

*Presenter Script:*  
> *"Here is the cryptographic backbone: the canonical manifest. The JSON is deterministically serialized with sorted keys and no whitespace, ensuring identical hashes across all platforms. Clicking 'Verify Cryptographic Integrity' recomputes the versionHash from scratch and validates it against the on-chain GovernanceRegistry."*

---

### Page 5: Audit Explorer
**Navigation:** Sidebar $\rightarrow$ **Audit Explorer**  
**Component:** [`frontend/src/pages/AuditPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/AuditPage.tsx)  
**Purpose:** Comprehensive chronological audit trail uniting LLM extraction events, prompt hashes, latency metrics, EVM verification runs, rule verdicts, and on-chain execution receipts.

#### Visible Sections & Cards
1. **Header & Filter Tabs:** Proposal title and filter pills (`ALL`, `ANALYSIS`, `VERIFICATION`).
2. **Persistent Verification & Execution Log Card:** Chronological list of recorded events.
   - `ANALYSIS` Events: Provider (`gemini`/`openai`), model, extraction latency in ms, prompt hash, input hash, cache status (`CACHED` / `GENERATED`).
   - `VERIFICATION` Events: Proposal version, rule verdict (`VERIFIED` / `MISMATCH`), target, recipient, transaction hash.
   - `"Inspect Details"` / `"Hide JSON"` button toggling raw JSON diagnostic dumps.

#### Controls & Actions Table
| UI element | Meaning | User action | Code / Handler | API / Backend Effect | Expected Result | Caveat |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Filter Tab (`ALL`/`ANALYSIS`/`VERIFICATION`)** | Filters timeline | Click pill | `setFilterType(f)` | Local state filter | Filters events list to matching event type | Retains chronological sort |
| **"Inspect Details" Button** | Toggles raw JSON view | Click button | `setExpandedId(id)` | Local state toggle | Expands complete JSON record including prompt and rules | Shows provider latency and hashes |

*Presenter Script:*  
> *"The Audit Explorer provides full provenance. For every LLM extraction, we store the prompt hash, input hash, latency, and whether it came from cache. For every verification, we preserve the exact simulation state and mined transaction receipt."*

---

### Interactive Modal: Scenario Runner
**Trigger:** TopBar $\rightarrow$ **"Run Scenarios (A / B1 / C)"**  
**Component:** [`frontend/src/components/scenarios/ScenarioModal.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/scenarios/ScenarioModal.tsx)  
**Purpose:** Step-by-step interactive runner for executing and demonstrating all 5 core scenarios.

#### Controls & Tabs
- **Scenario Tabs:**
  - `Scenario A (Valid Payout)`: Happy path 1.0M USDC payout.
  - `Scenario B1 (Substituted Payout)`: Calldata tampering attack blocked.
  - `Scenario B3 (Evil Upgrade Blocked)`: UUPS backdoor `sweep()` blocked.
  - `Scenario B2 (Benign Upgrade)`: Benign V2 upgrade executed.
  - `Scenario C (Reset & Seed)`: Environment fast-reset.
- **"Execute Scenario" Button:**
  - Triggers `handleRun()`, calling `POST /scenarios/{name}/run`.
- **Live Output Panel:**
  - Shows real-time step progression (`COMPLETED`, `FAILED`), rule verdict badge, diffs, defensive proof, and transaction receipts.

---

## 4. Complete UI vs Terminal/API Workflow Matrix

| Operational Capability | Fully Available in UI? | UI Location / Action | Alternative Terminal / API Command |
| :--- | :---: | :--- | :--- |
| **System Startup & Health Probe** | Partial (Read-only) | Sidebar & Overview badges reflect live status | `curl -s http://127.0.0.1:8000/health` |
| **Fast Clean-Start & Reseed** | **Yes** | `TopBar` $\rightarrow$ Run Scenarios $\rightarrow$ `Scenario C` | `uv run --project backend python scripts/deploy_and_seed.py` |
| **Demonstrating Conflict Gate** | **Yes** | `TopBar` $\rightarrow$ PID: `PROP-001` $\rightarrow$ Proposals page | `curl -s -X POST http://127.0.0.1:8000/manifest/PROP-001 -H "Content-Type: application/json" -d '{"token_address":"0x..."}'` |
| **Ingesting New Evidence (PDF/Text)** | **Yes** | Proposals page $\rightarrow$ Ingest New Evidence | `curl -X POST http://127.0.0.1:8000/sources -F "file=@fixtures/clean_proposal_v1.pdf"` |
| **Inspecting Grounded Quotes** | **Yes** | Proposals page $\rightarrow$ Extracted Text Reader | `curl -s http://127.0.0.1:8000/claims/PROP-002` |
| **Reviewing COI Provenance** | **Yes** | Proposals page $\rightarrow$ COI Disclosure Card | `curl -s http://127.0.0.1:8000/proposals/PROP-002/coi` |
| **Drafting / Confirming Manifest** | Partial | Manifest page (Approve button) | `POST /manifest/{pid}` & `POST /manifest/{pid}/confirm` |
| **Running Scenario A (Valid Payout)** | **Yes** | Overview $\rightarrow$ "Run A" or Scenario Modal | `curl -s -X POST http://127.0.0.1:8000/scenarios/A/run` |
| **Running Scenario B1 (Tampering Defense)** | **Yes** | Overview $\rightarrow$ "Run B1" or Scenario Modal | `curl -s -X POST http://127.0.0.1:8000/scenarios/B1/run` |
| **Running Scenario B2 (Benign Upgrade)** | **Yes** | Scenario Modal $\rightarrow$ Tab `Scenario B2` | `curl -s -X POST http://127.0.0.1:8000/scenarios/B2/run` |
| **Running Scenario B3 (Backdoor Defense)** | **Yes** | Scenario Modal $\rightarrow$ Tab `Scenario B3` | `curl -s -X POST http://127.0.0.1:8000/scenarios/B3/run` |
| **Testing Custom Calldata Exploit** | **Yes** | Execution page $\rightarrow$ Adversarial Workbench | `curl -X POST http://127.0.0.1:8000/verify -d '{"target":"0x...","data":"0x..."}'` |
| **Tamper Verification** | **Yes** | Manifest page $\rightarrow$ "Verify Cryptographic Integrity" | `curl -s -X POST http://127.0.0.1:8000/verify-version/PROP-002` |
| **Inspecting Execution Receipts** | **Yes** | Audit page or Execution page receipt card | `curl -s http://127.0.0.1:8000/verifications/PROP-002` |
