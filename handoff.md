# Phase 7 handoff

Updated 2026-10-25. **Phase 7 complete.** System hardening, reproducibility & demo rehearsal delivered. Deterministic fast-reset and reseed automation (`scripts/deploy_and_seed.py` completing in ~1.5s), LLM network error shielding and rate-limit resilience with zero credential leakage and fail-closed security (`backend/app/llm/online.py`), offline-mode cached claim extraction validation, end-to-end 5-minute live demo rehearsal across all five scenarios (A, B1, B2, B3, C), and operational hardening across all components are fully implemented and verified.

## Pre-implementation verification findings (Phase 6 baseline)

1. Confirmed all 28 Foundry tests and 97 backend pytest tests passed prior to Phase 7 modifications.
2. Verified that local Anvil instance on port 8545 and FastAPI server on port 8000 run consistently without memory leaks.
3. Identified need for virtualenv auto-bootstrapping in `scripts/deploy_and_seed.py` when executed from workspace root or differing shell contexts.
4. Identified conflict status mismatch between seeding (`status = 'CONFLICT'`) and manifest gate (`status = 'UNRESOLVED'`), rectified by matching `status IN ('UNRESOLVED', 'CONFLICT')` in `manifest/builder.py`.

## Implemented files and functionality

- `scripts/deploy_and_seed.py`:
  - Enforces local development environment guard: checks loopback host (`127.0.0.1`, `localhost`), Anvil connection status, and `chain_id in {31337, 1337}`.
  - Implements automatic Python virtualenv bootstrapping to re-exec into `backend/.venv/bin/python` if `eth_account` or `web3` are missing in the invoking shell.
  - Idempotent clean-start: resets database tables (`claims`, `conflicts`, `manifests`, `versions`, `verifications`, `analyses`) specifically for demo proposals (`PROP-001`, `PROP-002`, `PROP-B1`, `PROP-B2`, `PROP-B3`).
  - Deploys all 8 contracts: `MockToken`, `GovernanceRegistry`, `Treasury`, `GuardedExecutor`, `BoxUUPS`, `ERC1967Proxy`, `BoxV2`, `BoxEvil`.
  - Configures Treasury executor, funds Treasury with 1,000,000 USDC test funds.
  - Seeds proposal `PROP-002` on-chain (clean Alice grant approved for 1,000,000 USDC).
  - Seeds proposal `PROP-001` with genuine conflict: `clean_proposal_v1.pdf` ($5.0M) vs `forum_post.txt` ($5.8M) with `ClaimStatus.UNCERTAIN` and conflict `status = 'CONFLICT'`.
  - Writes and synchronizes active `deployments.json` in both `data/` and `backend/data/`.
  - Completes full deployment and seeding in ~1.5 seconds.
- `backend/app/manifest/builder.py`:
  - Updated line 49 conflict query from `status = 'UNRESOLVED'` to `status IN ('UNRESOLVED', 'CONFLICT')`, ensuring seeded `PROP-001` conflicts deterministically block `POST /manifest/{pid}` and `POST /manifest/{pid}/confirm` with HTTP 422 `ELIGIBILITY_ERROR`.
- `backend/app/llm/online.py`:
  - Enhanced `OnlineLLMProvider.extract_claims` with robust error classification:
    - Parses HTTP 429 rate limits, extracting the `Retry-After` header to inform backoff without crashing.
    - Sanitizes HTTP 5xx responses without dumping raw response bodies or internal stack traces.
    - Captures `httpx.TimeoutException` and `httpx.ConnectError` cleanly.
    - Strips and redacts `self.api_key` if accidentally present in exception strings or messages.
    - Enforces fail-closed posture: network errors return empty claims or raise safe `RuntimeError` (`LLM_UNAVAILABLE`), which the manifest builder blocks with 422 `ELIGIBILITY_ERROR` rather than approving an ungrounded manifest.
- `backend/app/scenarios/runner.py`:
  - Updated Scenario C database purge query to clear records for all five demo proposal IDs (`PROP-001`, `PROP-002`, `PROP-B1`, `PROP-B2`, `PROP-B3`).
- `backend/tests/test_offline_and_resilience.py`:
  - Created 11 targeted resilience tests verifying:
    1. Missing credentials returns `LLM_UNAVAILABLE` cleanly without tracebacks.
    2. Timeout sanitization suppresses internal timeout details and hides keys.
    3. HTTP 429 with `Retry-After` header extraction and safe return.
    4. HTTP 503 service error shielding without dumping server internals.
    5. DNS/connect error handling returning `LLM_UNAVAILABLE`.
    6. Retry exhaustion and audit log recording.
    7. Offline cached extraction succeeding with network disconnected (`httpx.Client.post` mocked to fail).
    8. Cache invalidation on modified evidence hash (`prompt_hash` mismatch).
    9. Fail-closed eligibility gate blocking manifest drafting on missing or uncertain claims.
    10. Rejection of non-local RPC endpoints (`chain_id 1` and external host).
    11. Disconnected Anvil diagnostic reporting clear error guidance.

## Executed commands and outcomes

| Command | Directory | Outcome | Details |
| --- | --- | --- | --- |
| `forge test -vv` | `contracts/` | PASS | 28 tests passed across 4 test suites (100% pass) |
| `uv run pytest` | `backend/` | PASS | 108 tests passed across 19 test suites (100% pass) |
| `npm run build` | `frontend/` | PASS | Vite production build succeeded in 83ms (0 errors) |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 warnings and 0 errors across 20 files |
| `git diff --check` | repo root | PASS | 0 whitespace or formatting errors |

## Live demo rehearsal sequence & measured timing

Full end-to-end rehearsal executed live against Anvil on port 8545:

| Step | Operation | Method & Endpoint | Measured Duration | Result |
| --- | --- | --- | --- | --- |
| 1 | Deterministic Fast-Reset & Reseed | `python scripts/deploy_and_seed.py` | 1.51s | 8 contracts deployed, Treasury funded 1M USDC, PROP-002 approved, PROP-001 conflict seeded |
| 2 | Scenario C Live Reset & Seed | `POST /scenarios/C/run` | 1.85s | Database purged, contracts redeployed, Treasury funded, PROP-002 re-approved |
| 3 | Scenario A Valid Payout | `POST /scenarios/A/run` | 0.88s | `VERIFIED` verdict (8/8 rules pass), EIP-712 attestation signed, executed on-chain, 1M USDC transferred |
| 4 | Scenario B1 Calldata Tampering Defense | `POST /scenarios/B1/run` | 0.62s | `MISMATCH` verdict (Rule R2 fails), attestation withheld, on-chain execution reverted, balances protected |
| 5 | Scenario B2 Benign V2 Protocol Upgrade | `POST /scenarios/B2/run` | 0.74s | `VERIFIED` verdict (R1-R7 pass), attestation signed, executed on-chain, implementation slot updated to BoxV2 ("2.0.0") |
| 6 | Scenario B3 Malicious Backdoor Defense | `POST /scenarios/B3/run` | 0.65s | `MISMATCH` verdict (Rule R7 detects undeclared `sweep()` backdoor `0x35faa416`), attestation withheld, slot protected |
| 7 | Conflict Gate Enforcement | `POST /manifest/PROP-001` | 0.05s | HTTP 422 `ELIGIBILITY_ERROR`: "Proposal 'PROP-001' has unresolved conflicts ($5.0M vs $5.8M)" |
| **Total** | **Complete Demo Lifecycle** | — | **~6.30s** | **Fully completed in well under 5 minutes** |

## Security guarantees and operational boundaries

1. **Fail-Closed Security**:
   - The engine never approves a manifest or issues an EIP-712 execution attestation when external services fail.
   - Any LLM timeout, rate limit, HTTP 5xx, or network failure returns `LLM_UNAVAILABLE`. The manifest builder strictly rejects drafting or confirming proposals lacking grounded claims or containing conflicts (`status IN ('UNRESOLVED', 'CONFLICT')`).
2. **Zero Credential Exposure**:
   - All exception handling in `OnlineLLMProvider` actively redacts `self.api_key` and strips raw response dumps, preventing credential leaks in logs or API responses.
3. **Local Development Environment Bound**:
   - Both `deploy_and_seed.py` and `backend/app/scenarios/runner.py` enforce loopback host validation (`127.0.0.1`, `localhost`) and chain ID restrictions (`chain_id in {31337, 1337}`), preventing accidental state mutation on testnets or mainnet.

---

# Stage 6 handoff

Updated 2026-10-25. **Stage 6 complete.** Contested UUPS protocol upgrades (`BoxUUPS`, `BoxV2`, `BoxEvil`), static bytecode analysis for undeclared function selectors (Rule R7), EIP-1967 implementation slot tracking (Rule R6), Scenario B3 (Malicious Upgrade Blocked) and Scenario B2 (Benign V2 Upgrade Executed), conflict-of-interest (COI) wallet provenance foundation (`GET /proposals/{pid}/coi` and COI Disclosure Card), genuine evidence conflict seeding for `PROP-001` ($5.0M vs $5.8M), and all Stage 5 frontend edge case remediations are fully implemented and verified.

## Pre-implementation verification findings (Stage 5 baseline)

1. Confirmed all 24 Foundry tests and 84 Stage 5 pytest tests passed prior to Stage 6 modifications.
2. Verified OpenZeppelin UUPS contracts vendored at `contracts/lib/openzeppelin-contracts/contracts/proxy/utils/UUPSUpgradeable.sol` and `ERC1967Proxy.sol`.
3. Verified Solc 0.8.30 compiles cleanly with zero warnings.

## Implemented files and functionality

- `contracts/src/`:
  - `BoxUUPS.sol`: UUPS upgradeable contract behind ERC-1967 proxy, `owner` set to `Treasury`, `value` storage, `setValue`, `getValue`, `version() == "1.0.0"`, `_authorizeUpgrade` restricted to `onlyOwner`.
  - `BoxV2.sol`: Benign V2 implementation, preserves storage, `version() == "2.0.0"`, `increment()`.
  - `BoxEvil.sol`: Malicious implementation containing undeclared backdoor `sweep()` (`0x35faa416`) and extra `delegatecall` opcode.
- `contracts/test/Upgrade.t.sol`:
  - Comprehensive Foundry suite (4 tests) verifying ERC-1967 proxy deployment, direct unauthorized upgrade revert, Treasury-authorized benign upgrade to `BoxV2`, and Treasury-authorized evil upgrade.
- `backend/app/verification/`:
  - `decode.py`: Supported selector `0x4f1ef286` (`upgradeToAndCall(address,bytes)`), canonical address padding validation, and field-level diff for `proxy_upgrade` manifests.
  - `verify.py`: Implemented `scan_bytecode` EVM opcode scanner (PUSH4 candidate selector heuristic and control opcodes), Rule R6 (EIP-1967 implementation slot tracking & envelope `allowImplChange` policy), Rule R7 (whitelist check against `baselineSelectors ∪ declaredSelectors`). Undeclared `sweep()` fails Rule R7 with `MISMATCH` and withholds attestation.
- `backend/app/manifest/hashes.py`:
  - Implemented `encode_upgrade_to_and_call_calldata` and extended `compute_manifest_action_hash` to handle `kind == "proxy_upgrade"`.
- `backend/app/claims/coi.py`:
  - NetworkX-based conflict-of-interest and wallet provenance graph analyzer. Tracks declared wallets, observed on-chain transfers, shared funders, shortest path discovery, and undisclosed intermediary bridges.
- `backend/app/api/routes.py`:
  - Registered `GET /proposals/{pid}/coi` endpoint.
  - Added `decoded_tx` reconstruction in `get_verifications_for_proposal`.
  - Added `cache_status` in `get_claims_for_proposal`.
- `scripts/deploy_and_seed.py`:
  - Deploys `BoxUUPS`, `BoxV2`, `BoxEvil`, and `ERC1967Proxy` (owned by Treasury) to local chain and records in `deployments.json`.
  - Seeds `PROP-001` with genuine conflicting sources (`clean_proposal_v1.pdf` $5.0M vs `forum_post.txt` $5.8M) and persists conflict.
- `backend/app/scenarios/runner.py`:
  - Implemented `run_scenario_b3`: Seeds `PROP-B3`, submits `BoxEvil` upgrade, detects Rule R7 undeclared `sweep()` backdoor, withholds attestation, verifies on-chain execution revert, and proves proxy implementation slot remained protected.
  - Implemented `run_scenario_b2`: Seeds `PROP-B2`, verifies all candidate selectors declared, issues attestation, executes upgrade on-chain, and verifies proxy implementation slot updated to `BoxV2` with version "2.0.0".
- `frontend/src/`:
  - `pages/ProposalsPage.tsx`: Integrated Conflict-of-Interest (COI) Disclosure Card with provenance funding trail and undisclosed entity risk indicators; added cached vs generated analysis badge.
  - `pages/ExecutionPage.tsx`: Added Adversarial Calldata Simulation Workbench (safe custom calldata tester), single-key simulated governance approval notice banner, fixed snapshot revert badge styling, fixed blocked verdict status badge, and eliminated state-in-effect oxlint warning.
  - `components/scenarios/ScenarioModal.tsx`: Added interactive launchpad tabs for Scenario B3 and Scenario B2.
  - `pages/AuditPage.tsx`: Clarified immutability wording to "Persistent Verification & Execution Log", and ensured target/recipient fallbacks.

## Executed commands and outcomes

| Command | Directory | Outcome | Details |
| --- | --- | --- | --- |
| `forge test -vv` | `contracts/` | PASS | 28 tests passed across 4 test suites (100% pass) |
| `uv run pytest` | `backend/` | PASS | 97 tests passed across 18 test suites (100% pass) |
| `npm run build` | `frontend/` | PASS | Vite production build succeeded in 77ms (0 errors) |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 warnings and 0 errors across 20 files |
| `git diff --check` | repo root | PASS | 0 whitespace or formatting errors |

## Security guarantees and documented limitations

1. **Bytecode Static Scanner Guarantees & Limitations**:
   - `scan_bytecode` evaluates EVM instructions sequentially, skipping `1 + n` bytes for all `PUSH1`..`PUSH32` instructions (0x60 <= op <= 0x7F). This strictly ensures data constants (e.g. 0x63 inside hashes or addresses) are never misinterpreted as PUSH4 opcodes.
   - Truncated instructions at boundaries or EOF terminate safely without IndexError or false detections.
   - Candidate 4-byte constants discovered by `PUSH4` represent function selectors checked by Solidity function dispatchers (`PUSH4 <selector> EQ ...`), but can also capture 4-byte numeric constants.
   - Limitation: Heuristic static scanning is a defensive filter against standard Solidity compiler output; it does not constitute a formal verification proof of safety against arbitrary obfuscated bytecode, unaligned jumps, or dynamic delegatecall targets. Full safety relies on defense-in-depth: Rule R6 (EIP-1967 slot immutability & exact `newImpl` match), Rule R7 (whitelist check & code hash), and on-chain `GuardedExecutor`.
2. **Conflict-of-Interest (COI) Provenance Model**:
   - Analyzes directed provenance graphs over signed wallet disclosures and observed transfers.
   - Demonstrates 2-hop intermediary detection (Proposer -> Horizon Labs -> Beneficiary) on seeded proposal `PROP-002`.
   - Upgrade proposals without beneficiaries (`PROP-B2`, `PROP-B3`) correctly report `has_linkage = False` with zero undisclosed connections.
   - Limitation: Seeded/demonstration graph data only; does not implement a live full-node mainnet indexer. Provenance indicates financial proximity and linkage evidence, never subjective intent or proven wrongdoing.
3. **Governance Security Boundary**:
   - The engine uses a designated governance key (`PK_GOVERNANCE`) to simulate approvals (`governance.approve(pid, versionHash)`).
   - This single-key model is explicitly labeled as simulated governance in the UI and documentation. Production migration requires token-weighted OpenZeppelin Governor + TimelockController.
   - Strict local-chain safeguards reject any non-local RPC endpoint (`chain_id ∉ {31337, 1337}`).

---

# Stage 5 handoff

Updated 2026-10-25. **Stage 5 complete.** The complete interactive React/TypeScript/Vite frontend workbench, automated scenario runner service (`backend/app/scenarios/runner.py`), scenario execution API (`POST /scenarios/{name}/run`), auxiliary read endpoints (`GET /sources`, `GET /sources/{id}`, `GET /verifications/{pid}`, `GET /deployments`), and technical design system (Linear/Tenderly dark theme with animated technical grid) are fully implemented and verified.

## Pre-implementation verification findings (Stage 4)

1. Preflight test suites: Confirmed all 24 Foundry tests and 74 Stage 4 backend pytest tests passed prior to Stage 5 modifications.
2. Verified `GET /deployments` and `GET /verifications/{pid}` provide complete transparency so the frontend never needs to fake state or parse unindexed logs.
3. Automated scenario runner integrates directly with the existing `deploy_and_seed.py` workflow, supporting dynamic Anvil ports in automated test fixtures and standard port 8545 in local dev.

## Implemented files and functionality

- `frontend/src/styles/`:
  - `tokens.css`: Tokenized dark workbench palette (`#080A0D` app bg, `#11161D` surface, `#7CE0BE` mint accent, semantic status tokens, monospace stacks).
  - `background.css`: Animated SVG/CSS grid background with traveling lines and `prefers-reduced-motion` accessibility support.
  - `components.css`: Comprehensive styling for layout, navigation rails, cards, side-by-side comparison tables, simulation delta grids, rule inspectors, and modals.
- `frontend/src/api/`:
  - `types.ts`: Strictly typed TypeScript interfaces matching all backend schemas (Manifest, GroundedClaim, Conflict, VerificationReport, RuleResult, SimulationDelta, ScenarioRunResult).
  - `client.ts`: Typed API client covering all backend endpoints with automatic error formatting.
- `frontend/src/components/`:
  - `common/`: Icons (minimal SVG set), StatusBadge, CopyValue, AddressValue, HashValue, ConfirmModal, EmptyState, ErrorState.
  - `lifecycle/LifecycleStrip.tsx`: 8-stage interactive governance progression tracker.
  - `scenarios/ScenarioModal.tsx`: Step-by-step interactive scenario runner modal for Scenario A, Scenario B1, and Scenario C with real-time logs and receipt links.
  - `layout/`: Persistent `Sidebar.tsx`, `TopBar.tsx`, and `AppShell.tsx`.
- `frontend/src/pages/`:
  - `OverviewPage.tsx`: System overview, lifecycle strip, contract addresses, and scenario launchpad.
  - `ExecutionPage.tsx`: Centrepiece technical workbench. Approved manifest vs submitted calldata comparison, EVM simulation state deltas (ETH, USDC, allowance, implementation, ownership), R1–R9 checklist with collapsible debug inspector, EIP-712 attestation viewer, and guarded execution trigger with confirmation modal.
  - `ProposalsPage.tsx`: Dual-pane evidence document reader with quote highlights, grounded claims table with search and field filter, and cross-source conflict callout banner.
  - `ManifestPage.tsx`: Syntax-highlighted canonical JSON viewer, cryptographic hash commitment cards, and live tamper verification.
  - `AuditPage.tsx`: Searchable and filterable audit trail for analyses, manifest commitments, verifications, and execution receipts.
- `backend/app/scenarios/runner.py`:
  - Deterministic orchestration for Scenario A (valid payout executed), Scenario B1 (substituted calldata blocked on R2), and Scenario C (clean environment reset and seed).
- `backend/app/api/routes.py`:
  - Registered `POST /scenarios/{name}/run`, `GET /sources`, `GET /sources/{source_id}`, `GET /verifications/{pid}`, and `GET /deployments`.
- `backend/tests/test_scenarios_runner.py`:
  - 5 comprehensive integration tests verifying Scenario C reset, Scenario A execution, Scenario B1 blocking, invalid scenario rejection, and read endpoints.

## Executed commands and outcomes

| Command | Directory | Outcome | Details |
| --- | --- | --- | --- |
| `uv run pytest` | `backend/` | PASS | 84 tests passed in 21.19s across 17 test suites |
| `forge test -vv` | `contracts/` | PASS | 24 tests passed across 3 test suites |
| `npm run build` | `frontend/` | PASS | Vite production build succeeded in 80ms (0 errors) |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 warnings and 0 errors |

## Exit gate checklist

- [x] Technical workbench aesthetic implemented with cohesive dark palette, mint accent, and monospace data elements.
- [x] Animated background grid with traveling lines respects `prefers-reduced-motion`.
- [x] Persistent desktop application shell with live health and chain status indicators.
- [x] Five operational views implemented: Overview, Execution Workbench, Proposals & Evidence, Manifests & Versions, Audit Explorer.
- [x] Execution workbench shows side-by-side approved vs submitted comparison and truthful EVM simulation state deltas without fabricated fallbacks.
- [x] Evaluated rule checklist correctly maps the 8 rules (R1–R7, R9) defined in the authoritative specification; R8 status documented.
- [x] Environment guard strictly restricts destructive deployments and state resets to local development chains (31337, 1337).
- [x] Scenario runner protected with mutex locking against concurrent execution corruption.
- [x] Scenario B1 demonstrates two-layer defense (off-chain attestation withholding + on-chain GuardedExecutor revert) with verified token balance immutability.
- [x] EIP-712 attestation details (verdict, deadline, signature, verifier) clearly displayed.
- [x] Guarded execution triggered through interactive confirmation modal with live on-chain status update.
- [x] Proposals view provides evidence reader with quote highlighting, claims table, and conflict banner.
- [x] Manifest view shows canonical JSON, hash chain commitments, and interactive tamper test.
- [x] Audit explorer displays chronological filterable timeline of system actions.
- [x] Scenario runner service (`backend/app/scenarios/runner.py`) automates Scenarios A, B1, and C with postcondition validation.
- [x] All 84 backend tests pass, 24 Foundry tests pass, and frontend passes typecheck, build, and linting.

## Next steps (Stage 6: UUPS Proxy Upgrades & Bytecode Scanning)

1. Implement `BoxUUPS.sol`, `BoxV2.sol`, and `BoxEvil.sol` under `contracts/src/` to demonstrate storage layout and proxy upgrade safety.
2. Extend `decode.py` and `simulate.py` to support `upgradeToAndCall` verification and implementation slot diffing.
3. Implement bytecode analysis and storage layout collision checks (evaluating Rule R6 and upgrade attack vectors).
4. Expose proxy upgrade verification in the frontend execution workbench.

## Pre-implementation verification findings (Stage 3)

1. Preflight test suites: Confirmed all 24 Foundry tests and 48 Stage 3 backend pytest tests passed prior to Stage 4 modifications.
2. Anvil JSON-RPC snapshot compatibility: Verified that Anvil returns `{'result': '0x0'}` for `evm_snapshot` and requires the exact un-cast string passed to `evm_revert`, returning `{'result': True}`.
3. Impersonation & Gas: Verified that impersonating the contract executor on Anvil requires standard gas price matching `w3.eth.gas_price`; temporary artificial gas funding is excluded from diffs and wiped clean by `evm_revert`.

## Implemented files and functionality

- `backend/app/verification/decode.py`:
  - Enforces exactly 68 bytes for static ERC-20 calldata (`transfer` and `approve`). Rejects truncated calldata and trailing bytes.
  - Enforces canonical address encoding (upper 12 bytes of address parameter word must be 0x00). Non-zero padding is rejected.
  - Rejects invalid target addresses, non-hex strings, and negative ETH values.
  - Classifies supported selectors (`transfer`, `approve`) vs unsupported (`upgradeToAndCall`, unknown).
  - Computes exact `calldata_hash` and `actionHash`.
  - Generates field-by-field diff comparing `target`, `value`, `function`, `recipient`, `amountRaw`, and `actionHash` against the approved governance manifest.
- `backend/app/verification/simulate.py`:
  - Captures baseline state: executor nonce, block number, and fixed watchlist balances (ETH, tokens, allowances from Treasury, EIP-1967 implementation slot, contract owner).
  - Raw JSON-RPC `evm_snapshot` and `evm_revert` compatibility without arbitrary ID casting.
  - Impersonates deployed executor contract address via `anvil_impersonateAccount`.
  - Executes `treasury.exec(target, value, data)` through the authorized authorization path.
  - Captures emitted logs and applies bounded dynamic discovery (capped at 10 unique addresses).
  - In `finally`: stops impersonation, reverts snapshot via `evm_revert`, and verifies restoration of executor nonce, block number, watchlist state, and artificial funding. Fails closed with `SimulationError` if restoration fails.
- `backend/app/verification/verify.py`:
  - Implements deterministic rule engine evaluating in strict order:
    - **R1**: Approved version hash and evidence root match on-chain `GovernanceRegistry` record.
    - **R2**: Submitted `actionHash` and decoded transaction parameters match approved manifest action.
    - **R3**: Simulated token outflow is within envelope limit and recipient receives exact approved amount.
    - **R4**: Zero unexpected token balance increases observed across watched addresses.
    - **R5**: Treasury allowances remained unchanged when `allowApprovals` is false.
    - **R6**: EIP-1967 implementation storage slots remained unchanged when `allowImplChange` is false.
    - **R7**: Selector is within approved whitelist.
    - **R9**: Contract owner and access control roles remained unchanged when `allowRoleChanges` is false.
  - Strict verdict taxonomy: `VERIFIED`, `MISMATCH`, `UNSUPPORTED`, `UNCERTAIN`.
  - Attestation issuance strictly gated to `VERIFIED` verdicts; signs EIP-712 typed data with deadline derived from target chain's latest block timestamp (`latest_block["timestamp"] + ttl_seconds`).
  - Persists full audit trail in `verifications` table.
- `backend/app/db.py`:
  - Added `verifications` table to store verification attempts, rule outcomes, diffs, simulation results, attestation signatures, deadlines, and execution records.
- `backend/app/api/routes.py`:
  - `POST /verify` & `POST /verify/{pid}`: Runs full verification pipeline.
  - `POST /execute` & `POST /execute/{pid}`: Implements mandatory TOCTOU protection immediately before broadcasting:
    1. Re-reads live on-chain `GovernanceRegistry.approved(pid)` tuple.
    2. Re-checks `GuardedExecutor.executed(pid) == false`.
    3. Confirms submitted calldata matches approved `actionHash`.
    4. Re-checks deadline against live block timestamp.
    5. Recovers verifier signature and validates against executor contract's `verifier()`.
    6. Broadcasts transaction through `GuardedExecutor.execute(...)` (never direct to Treasury).
- `scripts/deploy_and_seed.py`:
  - Automates deployment of core contracts, wires executor to treasury, funds Treasury with 1,000,000 USDC, and seeds proposal `PROP-002` for acceptance scenarios.

## Executed commands and outcomes

| Command | Directory | Outcome | Details |
| --- | --- | --- | --- |
| `uv run pytest` | `backend/` | PASS | 74 tests passed in 14.92s across 16 test suites |
| `forge test -vv` | `contracts/` | PASS | 24 tests passed across 3 test suites |
| `npm run build` | `frontend/` | PASS | Vite production build succeeded in 66ms |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 errors and 0 warnings |

## Exit gate checklist

- [x] Supported calldata is decoded strictly and compared against the complete required manifest.
- [x] Simulation uses the actual Anvil EVM and deployed authorization path.
- [x] Snapshot creation and reversion work with pinned Anvil/Web3.py versions.
- [x] Snapshot restoration is verified after success and failure.
- [x] Executor nonce, block number, and relevant watched state are restored.
- [x] Fixed-watchlist checks are independent of bounded dynamic discovery.
- [x] Incomplete observations and simulator failures cannot produce `VERIFIED`.
- [x] Rule IDs, ordering, and verdict semantics match the build guide.
- [x] EIP-712 signatures use the exact contract domain and type.
- [x] Attestation deadlines derive from chain time (`w3.eth.get_block("latest")["timestamp"] + ttl`).
- [x] Only `VERIFIED` results can be attested.
- [x] Live governance approval and replay state are rechecked immediately before broadcasting.
- [x] Production execution goes through `GuardedExecutor`, never directly through `Treasury`.
- [x] Scenario A (valid payout execution) passes.
- [x] Scenario B1 (substituted payout blocked) passes.
- [x] Snapshot, deadline, adversarial, and TOCTOU tests pass.
- [x] All existing Foundry and backend tests pass.
- [x] Documentation and repository diff are reviewed.

## Next steps (Stage 5: Dashboard and Scenario Runner)

1. Implement scenario runner endpoint (`POST /scenarios/{name}/run`) executing A, B1, C deterministically.
2. Build frontend Execution view showing approved action beside submitted action, observed simulation effects, the failed rule (if any), verdict badge, and attestation status.
3. Build Proposal, Manifest, and Audit views integrating with backend endpoints.
