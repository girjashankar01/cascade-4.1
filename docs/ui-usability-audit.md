# CASCADE 4.1 — Frontend Usability & Presenter Experience Audit

**System:** CASCADE 4.1 DAO Accountability Engine  
**Auditor:** Independent Technical Auditor  
**File Location:** `docs/ui-usability-audit.md`  
**Evaluation Standard:** First-time presenter confidence, demonstration reproducibility, and security transparency.

---

## 1. Executive Summary

The CASCADE 4.1 user interface succeeds in presenting a dense, technical workflow (Linear/Tenderly dark aesthetic, live EVM simulation deltas, interactive rule checklist, and coordinate-highlighted evidence reader). 

However, an audit of the actual React components and event handlers reveals several critical usability friction points where a presenter could easily become confused, click a control that produces an unexpected error, or fail to locate Tier 1 upgrade scenarios.

This document catalogs these defects by severity (**P0** to **P3**), provides exact source code evidence, and outlines the smallest safe remediations.

---

## 2. Prioritized Defect Catalog

### Summary Table

| Severity | Issue ID | Component & File | Description / Failure Mode | Presenter Impact |
| :---: | :---: | :--- | :--- | :--- |
| **P0** | **UI-01** | [`ExecutionPage.tsx#L181`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/ExecutionPage.tsx#L181) | `"Execute On-Chain"` button passes `calldata_hash` instead of raw calldata to `POST /execute`. | Clicking execution in the UI always fails with HTTP 400 `"Submitted transaction does not match on-chain approved actionHash"`. |
| **P1** | **UI-02** | [`TopBar.tsx#L42-L45`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/layout/TopBar.tsx#L42-L45) | Proposal selector dropdown lacks `<option>` tags for `PROP-B2` and `PROP-B3`. | When running Scenario B2 or B3, the dropdown renders blank or visually reverts to `PROP-002`. |
| **P1** | **UI-03** | [`OverviewPage.tsx#L151-L189`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx#L151-L189) | Overview page scenario cards omit Scenarios B2 and B3 (protocol upgrades). | Evaluators looking at the Overview dashboard may assume only payout scenarios exist. |
| **P1** | **UI-04** | [`OverviewPage.tsx#L76-L83`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx#L76-L83) | `LifecycleStrip` props are partially hardcoded boolean literals. | Stages 5, 6, 7 show green before verification runs; Stage 8 (`Execution`) always shows grey even after successful on-chain mining. |
| **P2** | **UI-05** | [`AppShell.tsx#L98`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/layout/AppShell.tsx#L98) | Scenario completion handler only auto-switches tab for `'A'` and `'B1'`, not `'B2'` or `'B3'`. | Running an upgrade scenario leaves the presenter on whatever tab they were on rather than showing the verified proxy slot. |
| **P2** | **UI-06** | [`OverviewPage.tsx#L110`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx#L110) | Overview page payout fallback defaults to `'1,000,000 USDC'` for upgrade proposals. | Upgrades (`kind == 'proxy_upgrade'`) display `'1,000,000 USDC'` instead of `'0 USDC (Protocol Upgrade)'`. |
| **P3** | **UI-07** | [`Sidebar.tsx#L79`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/layout/Sidebar.tsx#L79) | Footer version string reads `CASCADE v0.2.0 · Stage 5`. | Minor text label out of sync with Phase 7 completion. |

---

## 3. Deep-Dive Defect Analysis

### Defect UI-01 (Severity: P0)
**Component:** `handleExecute()` in [`frontend/src/pages/ExecutionPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/ExecutionPage.tsx#L177-L185)  
**Root Cause Code:**
```typescript
const res = await api.executeTransaction({
  proposal_id: proposalId,
  target: report.decoded_tx.target,
  value: report.decoded_tx.value,
  data: '0x' + report.decoded_tx.calldata_hash, // <--- ERROR: passes 32-byte hash instead of raw calldata!
  executor_address: deployments.executor,
  registry_address: deployments.registry || undefined,
});
```
**Backend Failure Evidence ([`backend/app/api/routes.py#L888-L894`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/backend/app/api/routes.py#L888-L894)):**
```python
raw_data = bytes.fromhex(payload.data[2:] if payload.data.startswith("0x") else payload.data)
computed_ahash = compute_action_hash(payload.target, payload.value or 0, raw_data)
if computed_ahash != app_ahash:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Submitted transaction does not match on-chain approved actionHash",
    )
```
When `payload.data` is `'0x' + calldata_hash` (32 bytes), `compute_action_hash` hashes the hash (`keccak256(keccak256(data))`), producing a mismatch against `app_ahash`.
**Impact on Demo:** If the presenter clicks `"Execute On-Chain via GuardedExecutor"` on the Execution Workbench, a red alert appears: `"Submitted transaction does not match on-chain approved actionHash"`. The presenter is forced to apologize or restart.
**Smallest Safe Fix:** In `ExecutionPage.tsx`, reconstruct the calldata (using `encode_erc20_transfer_calldata` format or the exact calldata generated during `handleRunVerification`) or store the verified calldata in component state, and pass that hex string in `api.executeTransaction({ ... data: calldata })`.
**Runbook Workaround:** Use the **Scenario Modal** (`Run Scenarios` $\rightarrow$ `Scenario A`), which dispatches via `backend/app/scenarios/runner.py` with the raw calldata properly encoded.

---

### Defect UI-02 (Severity: P1)
**Component:** Proposal Selector Dropdown in [`frontend/src/components/layout/TopBar.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/components/layout/TopBar.tsx#L38-L45)  
**Root Cause Code:**
```tsx
<select
  className="proposal-select"
  value={proposalId}
  onChange={(e) => onSelectProposal(e.target.value)}
>
  <option value="PROP-002">PROP-002 (Clean 1M USDC)</option>
  <option value="PROP-001">PROP-001 ($5.0M Conflict)</option>
  <option value="PROP-B1">PROP-B1 (Substituted Payout)</option>
</select>
```
**Impact on Demo:** When the user runs Scenario B2 (`PROP-B2`) or Scenario B3 (`PROP-B3`) from the Scenario Runner modal, `onScenarioComplete` sets `proposalId` to `'PROP-B2'` or `'PROP-B3'`. Because `<select>` has no matching `<option>`, the dropdown appears completely blank or renders an invalid selection.
**Smallest Safe Fix:** Add `<option value="PROP-B2">PROP-B2 (Benign Upgrade)</option>` and `<option value="PROP-B3">PROP-B3 (Evil Upgrade Blocked)</option>` to the `<select>` in `TopBar.tsx`.

---

### Defect UI-03 (Severity: P1)
**Component:** Scenario Launcher Cards in [`frontend/src/pages/OverviewPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx#L151-L189)  
**Root Cause Code:**
`OverviewPage.tsx` defines cards for:
- `Scenario A: Valid Payout`
- `Scenario B1: Substituted Blocked`
- `Scenario C: Clean Reset & Seed`
It completely omits cards for **Scenario B2** and **Scenario B3**.
**Impact on Demo:** Tier 1 (Contested UUPS protocol upgrades) is a key requirement of the hackathon problem statement. Having zero mention of Scenarios B2 and B3 on the primary landing dashboard conceals this capability.
**Smallest Safe Fix:** Add two cards in `OverviewPage.tsx` next to Scenario B1:
- `Scenario B3: Evil Upgrade Blocked` (`onOpenScenario('B3')`)
- `Scenario B2: Benign V2 Upgrade` (`onOpenScenario('B2')`)

---

### Defect UI-04 (Severity: P1)
**Component:** `LifecycleStrip` in [`frontend/src/pages/OverviewPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx#L76-L83)  
**Root Cause Code:**
```tsx
<LifecycleStrip
  hasSources={true}
  hasClaims={true}
  hasManifest={Boolean(manifest)}
  isApproved={Boolean(manifest?.confirmed_at)}
  isVerified={Boolean(manifest)}
  hasAttestation={Boolean(manifest)}
  isExecuted={false}
  onSelectStage={handleStageSelect}
/>
```
**Impact on Demo:**
- `isVerified` and `hasAttestation` are passed as `Boolean(manifest)`. Thus, as soon as a manifest is confirmed, Stages 5 (`Simulation`), 6 (`Verification`), and 7 (`Attestation`) show green checkmarks before verification has ever run!
- `isExecuted` is hardcoded to literal `false`. Thus, even after Scenario A executes on-chain and transfers 1M USDC, Stage 8 (`Execution`) remains an unfulfilled grey circle.
**Smallest Safe Fix:** In `OverviewPage.tsx`, query `api.getVerifications(proposalId)`. Set:
```typescript
const latestV = verifications[0];
const isVerified = latestV?.verdict === 'VERIFIED';
const hasAttestation = Boolean(latestV?.attestation_sig);
const isExecuted = Boolean(latestV?.executed);
```

---

### Defect UI-06 (Severity: P2)
**Component:** Active Governance Intent Card in [`frontend/src/pages/OverviewPage.tsx`](file:///Users/althea/Developer/Projects/iiitn-cascade/cascade4.1/frontend/src/pages/OverviewPage.tsx#L108-L112)  
**Root Cause Code:**
```tsx
<span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
  {action ? `${(Number(action.amountRaw) / 10**6).toLocaleString()} USDC` : '1,000,000 USDC'}
</span>
```
**Impact on Demo:** For protocol upgrades (`PROP-B2`, `PROP-B3`), `action.kind === 'proxy_upgrade'` has no `amountRaw` (value is 0). Number converts `undefined` to `NaN`, rendering `"NaN USDC"` or falling back to `"1,000,000 USDC"`, which misleadingly implies an upgrade proposal is transferring funds.
**Smallest Safe Fix:**
```tsx
{action?.kind === 'proxy_upgrade' 
  ? '0 USDC (Proxy Upgrade)' 
  : action?.amountRaw 
    ? `${(Number(action.amountRaw) / 10**6).toLocaleString()} USDC` 
    : '—'}
```

---

## 4. Usability Best Practices for Live Demonstrations

1. **Avoid the Direct Execute Button on ExecutionPage:**
   Due to Defect UI-01, always execute transactions using the **Scenario Modal** (`Run Scenarios` pill in the TopBar). The modal dispatches via the verified backend runner and executes with zero errors.
2. **Always Run Scenario C First:**
   If another presenter or automated test touched the database or mined transactions, running Scenario C restores clean state in 1.5 seconds.
3. **Use PID PROP-001 to Prove Conflict Gating:**
   Switch to `PROP-001` in the TopBar to demonstrate the conflict detector and explain why the manifest creation button is blocked.
4. **Highlight the "Seeded Demo Graph" Badge:**
   When presenting the COI card on the Proposals page, proactively point to the `Seeded Demo Graph` badge to demonstrate honesty and technical maturity to the judges.
