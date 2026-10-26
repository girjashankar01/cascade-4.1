# Technical decisions

## 2026-10-25 — Stage 0 scope and source of truth

Follow `docs/dao-build-guide-final.md` over the older project handoff. Implement only
environment scaffolding and validation; production contracts, ingestion, LLMs,
wallets, database schema and verification workflows remain future work.

## 2026-10-25 — uv manages all Python operations

The explicit task override supersedes the guide's venv and pip instructions.
Use a backend uv project, Python 3.11 pin, uv lockfile and an optional `ocr` extra.
SQLite uses the standard library; OCR must not be required for startup.

## 2026-10-25 — Preserve enclosing repository and isolate tool installs

Git inspection resolves to `C:/Users/abhig`, an existing enclosing repository.
Do not initialize another repository or change the enclosing repository's settings.
Scope Git checks to this workspace. Install missing tools under ignored `.tools/`
where practical, avoiding global installation and privileges.

## 2026-10-25 — Retain the guide's future architecture

Local Anvil, React/TypeScript/Vite, FastAPI/web3.py/pydantic/SQLite, hosted LLM first,
one action per proposal, simulated governance, one trusted verifier and watched-state
verification are guide-established choices, not implemented capabilities.
Full Governor/Timelock, vector databases, Docker packaging and local inference are deferred.

## 2026-10-25 — Foundry on Windows and reproducible dependency imports

The official Foundry npm wrapper 1.7.1 failed because its postinstall uses Unix
environment assignment syntax under cmd.exe. Install its official Windows x64
binary packages with scripts disabled instead; `scripts/install-foundry.ps1`
reproduces this. Dot-source `scripts/dev-tools.ps1` for session-only PATH/cache setup.
Foundry init/install use `--no-git`; dependency installation uses an absolute root
because `--root .` failed with a path-prefix error. Pin OpenZeppelin v5.4.0
and solc 0.8.30, and compile an import smoke test without production logic.

## 2026-10-25 — Validation completed and remaining limits

Locked uv sync and the backend health test passed on Python 3.11.17. The live
health endpoint, frontend and Anvil worked together, and the Python script read
block 0. Three Foundry tests and the frontend build/lint passed. No Stage 1 work
was added. Optional RapidOCR is declared/resolved but its inference path is untested.
The installed Starlette warns about the httpx-based TestClient; the current health
test passes, so keep this visible as a dependency maintenance item rather than
expanding Stage 0. Slow downloads were resolved through cached retries with a longer
uv HTTP timeout. No system-level install, public deployment or keys were needed.

## 2026-10-25 — Publish the scaffold without changing the enclosing repository

The user requested publication to `girjashankar01/cascade-4.1`. Clone that target
into a separate temporary checkout and preserve its existing main-branch history.
Do not redirect the home repository's remote or initialize a repository inside
this workspace. Include project source, documentation and lockfiles; exclude local
tools, caches, environments and builds. Publish only the vendored Solidity source,
licenses and package metadata, omitting upstream tests that contain deterministic
private-key fixtures. Verify the trimmed contract dependencies before pushing.

## 2026-10-25 — Stage 1 contracts architecture and EIP-712 domain

Implemented the four Stage 1 core contracts in `contracts/src/`:
1. `MockToken.sol`: OpenZeppelin ERC-20 with 6 decimals mimicking USDC with initial minting.
2. `GovernanceRegistry.sol`: Enforces proposal ownership by first committer, sequential 1-indexed versions, rejection of zero and duplicate version hashes, and governance-only approval of latest committed versions.
3. `Treasury.sol`: Holds ETH and ERC-20 tokens. Call routing is restricted exclusively to `executor`. Wiring resolves the mutual dependency with `GuardedExecutor` via a deployer-only `setExecutor` call that is permanently locked after single execution.
4. `GuardedExecutor.sol`: Inherits OpenZeppelin `EIP712` and uses `ECDSA`. Enforces single-use execution per proposal ID, valid deadline, `VERIFIED == 1` verdict, approved version match, `actionHash` match, and verifier signature recovery over the EIP-712 typed digest. Emits events and records `executed[pid] = true` before calling `treasury.exec(...)` (Checks-Effects-Interactions pattern).

The EIP-712 domain is standardized across Solidity and Python:
- Domain: `name = "GuardedExecutor"`, `version = "1"`, dynamic `chainId`, and `verifyingContract`.
- Type string: `Attestation(bytes32 proposalId,bytes32 versionHash,bytes32 actionHash,bytes32 evidenceRoot,uint8 verdict,uint256 deadline)`.
- `actionHash`: Deterministically calculated as `keccak256(abi.encode(target, value, keccak256(calldata)))`.

## 2026-10-25 — Python/Solidity cross-language interoperability gate

Implemented `backend/app/chain/attest.py` using `eth-account` (v0.14) and `web3.py`.
- `compute_action_hash` matches Solidity's ABI encoding and Keccak hashing exactly.
- `sign_attestation` and `get_signable_attestation` construct the exact EIP-712 domain and message dictionary.
- Cross-language integration tests in `contracts/test/Stage1Core.t.sol` (21 test cases) and `backend/tests/test_interop.py` verify that Python-computed action hashes and Python-generated signatures are verified and executed by the Solidity `GuardedExecutor` contract on a live Anvil instance.

## 2026-10-25 — Stage 1 contract refinements (prior approval invalidation and mint restriction)

1. `GovernanceRegistry.sol`: When `commitVersion` is called on a proposal that has a prior active approval, `_approved[pid]` is cleared (`delete _approved[pid]`). This strictly implements the build guide requirement: "A text revision with an identical action changes versionHash, so old approvals and attestations stop working." Regression test `test_TextRevision_InvalidatesPriorApproval` added.
2. `MockToken.sol`: Restricted `mint` function to `deployer` only (`require(msg.sender == deployer, "only deployer")`), preventing unauthorized minting during simulation and test runs. Regression test `test_Revert_MockTokenMint_Unauthorized` added.

## 2026-10-25 — Stage 2 evidence ingestion, schema, and SQLite architecture

1. Ingestion:
   - PyMuPDF (`pymupdf`) performs native digital text extraction with 1-indexed page numbers.
   - Usable text threshold is defined at 50 characters per page (`MIN_USABLE_TEXT_LENGTH = 50`); pages below threshold trigger OCR fallback.
   - OCR fallback uses `ocr_page_bytes` with pluggable mock handler (`_OCR_MOCK_HANDLER`) so tests never download ONNX models.
   - Files are stored under `data/sources/<sha256>_<filename>` and indexed by content hash for idempotent re-ingestion.
2. Canonical schema:
   - Canonical fields are restricted to `amount`, `token`, `recipient`, `purpose`, and `assumptions`. Aliases (`payout_amount`, `budget`, `beneficiary`) are mapped deterministically.
   - Monetary values normalize to integer strings (`$5.0M` -> `5000000`, `5,000,000` -> `5000000`) using `Decimal`, avoiding floating-point equality errors while preserving original `display_value` and `quote`.
3. Deterministic text grounding:
   - Normalization normalizes whitespace, lowercase, quotes, and Unicode dashes (`–`, `—`, `−` -> `-`).
   - Strict substring inclusion is required; paraphrased or fabricated quotes are marked `REJECTED`.
   - Numeric values in quotes are cross-checked; mismatch causes `REJECTED`.
4. Deterministic conflict detection:
   - Compares grounded claims across differing sources for the same canonical field.
   - Discrepancies (e.g. `$5.0M` in proposal PDF vs `$5.8M` in forum text) produce a structured `Conflict` object with both quotes and page references, marking affected claims `UNCERTAIN`.
5. LLM Router, Cache & Audit:
   - Cache key is `SHA256(prompt_hash:input_hash:model)` persisted in `llm_cache`.
   - Single retry on schema or JSON failure, then fails closed with `LLM_UNAVAILABLE`.
   - All attempts log an immutable audit record in `analyses` table without secrets.

## 2026-10-25 — Stage 3 canonicalization, hash chaining, and on-chain governance architecture

1. Canonical manifest serialization (`canon.py`):
   - One shared canonicalization engine is used across Python manifest building, signature signing/verification, and tamper detection.
   - Implemented lexicographical sorting of dictionary keys, removal of all insignificant whitespace (`separators=(',', ':')`), and UTF-8 byte serialization (`ensure_ascii=False`).
   - Strictly forbids floating-point values in manifest objects (`ValueError`), ensuring all numerical values (token amounts, decimals, versions) are encoded as integer strings or integers.
   - Normalized all 40-hex Ethereum addresses (`0x...`) to lowercase in manifest actions and envelopes.
2. Cryptographic hash commitments (`hashes.py`):
   - `proposalTextHash`: Computed as `keccak256` over the UTF-8 bytes of the exact proposal text seen by voters.
   - `evidenceRoot`: Computed as `keccak256` over the binary concatenation of sorted 32-byte SHA-256 digests of relevant evidence documents.
   - `versionHash`: Computed as `keccak256(canonical_manifest_utf8_bytes + 32-byte binary prevVersionHash)`. Version 1 links to `INITIAL_PREV_VERSION_HASH = "0x" + "00"*32`.
   - `actionHash`: Computed as `keccak256(abi.encode(target, value, keccak256(calldata)))`, matching Solidity GuardedExecutor exactly.
3. Eligibility gates and human confirmation (`builder.py`):
   - `check_claims_eligibility` strictly enforces that proposals with unresolved conflicts (e.g. `$5.0M` vs `$5.8M`) or `UNCERTAIN`/`REJECTED` mandatory claims (`amount`, `recipient`) cannot be drafted or confirmed, raising `EligibilityError` and returning HTTP 422.
   - Human confirmation requires proposer key signature over `versionHash`, persisted in SQLite `manifests` table.
4. On-chain version chain & approval invalidation:
   - `commit_version_onchain` submits `commitVersion` from the designated proposer account to `GovernanceRegistry`.
   - `approve_version_onchain` submits `approve` from the simulated governance account.
   - Committing any subsequent version clears `_approved[pid]` on `GovernanceRegistry`, ensuring text revisions with identical actions cannot reuse previous approvals.
5. Tampering verification:
   - `verify_manifest_integrity` independently recomputes all four commitments (`proposalTextHash`, `evidenceRoot`, `versionHash`, `actionHash`) and verifies them against stored records and the on-chain registry.
   - Tampering with any byte of the manifest, evidence files, or proposal text raises `TamperError`, specifically identifying which commitment mismatched.

## 2026-10-25 — Stage 4 verification pipeline, EVM simulation, and guarded execution

1. Strict calldata decoding (`decode.py`):
   - Static ERC-20 calls (`transfer`, `approve`) require exactly 68 bytes (4-byte selector + 2 * 32-byte arguments).
   - Canonical address encoding enforces that the upper 12 bytes of the address word must be zero (`0x00`). Calldata with non-zero padding is strictly rejected.
   - ETH values must be non-negative integers; negative values are rejected.
   - Generates a field-level diff comparing target, value, selector, recipient, amountRaw, and actionHash against the approved governance manifest.
2. Anvil EVM simulation and snapshot restoration (`simulate.py`):
   - Operates through the actual authorization path by impersonating the deployed `GuardedExecutor` contract on Anvil (`anvil_impersonateAccount`) and calling `Treasury.exec(target, value, data)`.
   - Captures raw JSON-RPC response from `evm_snapshot` without arbitrary integer/hex casting, and passes the exact raw identifier to `evm_revert`.
   - Verifies restoration in `finally`: checks that executor nonce, block number, fixed watchlist state, and artificial gas funding are completely restored to baseline. If restoration fails or cannot be demonstrated, fails closed with `SimulationError`.
   - Bounded dynamic discovery inspects `Transfer` logs to discover up to 10 unique addresses for additional balance reads, without weakening the authoritative fixed watchlist.
3. Deterministic verification rule engine (`verify.py`):
   - Rules R1, R2, R3, R4, R5, R6, R7, R9 are evaluated in strict order.
   - Verdict taxonomy adheres strictly to `VERIFIED`, `MISMATCH`, `UNSUPPORTED`, `UNCERTAIN`.
   - The LLM is never invoked to resolve verdicts or evaluate rules.
4. Attestation and deadline semantics (`attest.py`):
   - EIP-712 attestations are generated ONLY when the verdict is `VERIFIED`. Never issued for `MISMATCH`, `UNSUPPORTED`, or `UNCERTAIN`.
   - Deadlines are derived strictly from the target chain's latest block timestamp (`w3.eth.get_block("latest")["timestamp"] + ttl_seconds`), never from the host system clock.
5. Mandatory TOCTOU protection before broadcast (`routes.py`):
   - Immediately before broadcasting execution on `/execute`, re-reads `GovernanceRegistry.approved(pid)`, confirms the full returned tuple matches the verified record, verifies `GuardedExecutor.executed(pid) == false`, checks current block timestamp against deadline, and validates verifier signature recovery before calling `GuardedExecutor.execute(...)`.

## 2026-10-25 — Stage 5 frontend architecture, design system, and scenario runner

1. Technical workbench visual identity:
   - Built a high-density, low-latency technical workbench design system inspired by Linear, Tenderly, and modern developer tooling.
   - Tokenized dark palette in `frontend/src/styles/tokens.css`: `#080A0D` app background, `#11161D` elevated surface, `#171E27` border/hover states, with `#7CE0BE` mint accent.
   - Established semantic status indicators: green/mint (`VERIFIED`, `PASSED`, `EXECUTED`), red/coral (`MISMATCH`, `FAILED`, `BLOCKED`), amber (`UNCERTAIN`, `CONFLICT`), and slate (`UNSUPPORTED`, `PENDING`).
   - Typography uses clean system geometric sans (`Inter`, system-ui) paired with JetBrains Mono / SF Mono for addresses, hashes, and hexadecimal calldata.

2. Animated technical background motif (`frontend/src/styles/background.css`):
   - Implemented a 40px square grid background with radial vignette fading to darker edges.
   - Horizontal and vertical traveling beam animations travel strictly along the grid lines with staggered delays and subtle glow.
   - Includes standard CSS `@media (prefers-reduced-motion: reduce)` override to freeze traveling animations while maintaining subtle grid structure.

3. Complete operational workbench views (`frontend/src/pages/`):
   - `OverviewPage.tsx`: Interactive 8-stage governance progression strip (Evidence Ingestion → Grounded Claims → Canonical Manifest → On-Chain Approval → EVM Simulation → Deterministic Verification → EIP-712 Attestation → Guarded Execution), system deployment status, and 1-click scenario triggers.
   - `ExecutionPage.tsx`: The primary demonstration view. Displays approved manifest parameters side-by-side with submitted calldata diffs, EVM simulation balance deltas (ETH, USDC, allowance, implementation, ownership), deterministic rule checklist R1–R9 with collapsible debug inspector, EIP-712 attestation inspector, and guarded execution action with confirmation modal.
   - `ProposalsPage.tsx`: Evidence document browser with extracted pages viewer and quote highlight matching, grounded claims table with search and field filtering, and cross-source conflict callout banner with citation links.
   - `ManifestPage.tsx`: Syntax-highlighted canonical JSON viewer, cryptographic hash commitment cards (`proposalTextHash`, `evidenceRoot`, `versionHash`, `actionHash`), mathematical formulas, and live interactive tamper detection.
   - `AuditPage.tsx`: Chronological searchable audit explorer tracking all historical analysis, manifest creations, verification evaluations, and on-chain execution receipts.

4. Scenario runner service & backend endpoints:
   - Implemented `backend/app/scenarios/runner.py` exposing `POST /scenarios/{name}/run` with payloads supporting `rpc_url` and `reset_first`.
   - **Scenario A (Valid Payout)**: Deploys clean contracts, funds Treasury with 1,000,000 USDC, seeds approved proposal `PROP-002` (50,000 USDC to Team Alice), decodes submitted calldata, simulates EVM execution, passes R1–R9, issues EIP-712 attestation, executes on-chain via `GuardedExecutor`, and records transaction hash.
   - **Scenario B1 (Substituted Payout Blocked)**: Re-runs verification with substituted attacker calldata (recipient replaced with Mallory or inflated amount). Simulates execution, evaluates rules, fails on R2 (`MISMATCH`), issues zero attestation, and verifies that on-chain execution is strictly blocked.
   - **Scenario C (Environment Reset & Seed)**: Cleans and redeploys the environment to a pristine initial state with proposal `PROP-002` approved and ready for verification.
   - Added auxiliary read endpoints in `backend/app/api/routes.py`:
     - `GET /sources`: Lists stored evidence documents.
     - `GET /sources/{source_id}`: Retrieves single source with extracted page text and metadata.
     - `GET /verifications/{pid}`: Retrieves verification attempts, diffs, simulation deltas, and execution receipts for a proposal.
     - `GET /deployments`: Exposes active contract addresses (`mock_token`, `governance_registry`, `treasury`, `guarded_executor`).

## 2026-10-25 — Stage 5 independent audit, security hardening, and specification reconciliation

1. Rule R8 specification reconciliation:
   - Audit revealed that `docs/dao-build-guide-final.md` Section 5.6 defines 8 rules: R1 (version), R2 (action), R3 (token outflow), R4 (unexpected balance increase), R5 (allowance change), R6 (implementation slot), R7 (selector whitelist / static scan), and R9 (owner/role change).
   - Rule R8 is unassigned in the authoritative specification. Reconciled documentation and frontend headers to eliminate confusion, confirming that the 8 evaluated rules strictly correspond to the build guide's rule set.

2. Strict local environment guard:
   - Added `verify_local_chain(w3)` in `scripts/deploy_and_seed.py` and `backend/app/scenarios/runner.py`.
   - Restricts destructive reset, deployments, and automated testing to permitted local development chains (`chain_id in {31337, 1337}`). Rejects public testnets and mainnet with `ValueError`/`RuntimeError`, preventing accidental state mutation.

3. Scenario concurrency locking:
   - Implemented `_SCENARIO_LOCK = threading.Lock()` in `runner.py` with non-blocking acquisition. Rejects concurrent scenario runs with HTTP 400, preventing race conditions during Anvil deployments and database resets.

4. Scenario B1 two-layer defense and balance immutability:
   - Documented the dual defense boundaries:
     - Off-chain verifier: detects R2 `MISMATCH` and withholds EIP-712 attestation signature (`attestation_sig is None`).
     - On-chain contract: `GuardedExecutor` checks `ah == approvedAction` and recovers verifier signature, reverting any direct attack attempt.
   - Enhanced `run_scenario_b1` to query and assert on-chain token balances of Treasury, Recipient, and Attacker before and after execution, returning cryptographic proof that no funds were transferred.

5. Simulation deltas vs real execution truthfulness:
   - Eliminated hardcoded fallback values (`|| 1_000_000` / `|| 0`) in `ExecutionPage.tsx`. Lookups from `sim.baseline_state` now faithfully render observed balances or `'—'`, with clear labeling distinguishing simulated sandbox predictions from confirmed on-chain receipts.

6. Live chain health probing:
   - Enhanced `/health` endpoint to query Web3 connectivity and return live `rpc_connected`, `chain_id`, and `block_number`.
   - Frontend `Sidebar.tsx` and `OverviewPage.tsx` now dynamically reflect real Anvil status, showing red disconnected badges when the local node is down rather than static placeholders.

## 2026-10-25 — Stage 6: UUPS proxy upgrades, bytecode static analysis, and COI provenance

1. **UUPS Proxy Architecture**: Implemented `BoxUUPS.sol`, `BoxV2.sol`, and `BoxEvil.sol` behind OpenZeppelin `ERC1967Proxy`. Ownership is granted strictly to `Treasury`, ensuring that only proposals verified through `GuardedExecutor` and executed via `Treasury.exec` can perform upgrades through `upgradeToAndCall(address,bytes)` (`0x4f1ef286`).
2. **Bytecode Scanner & Rule R7**: Evaluates candidate function selectors via PUSH4 opcode scanning on the new implementation runtime code. Selectors must reside within `baselineSelectors ∪ declaredSelectors`. When `BoxEvil` exposes an undeclared backdoor `sweep()` (`0x35faa416`), Rule R7 strictly fails with `MISMATCH`, withholds the EIP-712 attestation, and execution is refused by `GuardedExecutor`.
3. **Rule R6 Implementation Slot Tracking**: During Anvil EVM simulation, changes to the EIP-1967 implementation slot (`0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`) are verified against `manifest.envelope.allowImplChange`. Payout proposals enforce strict slot immutability; proxy upgrades require exact match with `manifest.action.newImpl`.
4. **Conflict-of-Interest (COI) Provenance**: Implemented NetworkX provenance graph under `app.claims.coi` with endpoint `GET /proposals/{pid}/coi`. Tracks signed wallet disclosures, observed on-chain transfers (proposer -> intermediary -> beneficiary), and flags undisclosed counterparties without inferring subjective intent ("linkage evidence", never "same person").
5. **Scenario B3 & B2 Determinism**: Automated Scenario B3 demonstrates malicious upgrade blocking with proof of unchanged implementation slot on-chain; Scenario B2 demonstrates benign V2 upgrade with verified on-chain version advancement to "2.0.0".
6. **Frontend Transparency**: Added COI Disclosure Card, Adversarial Simulation Workbench for arbitrary calldata payloads, cached vs generated extraction badges, and documented the simulated governance approval key model.

## 2026-10-25 — Final Phase 6 Remediation, Verification & Phase 7 Readiness

1. **EVM Opcode Scanner Boundaries & Guarantees**:
   - Refined `scan_bytecode` in `backend/app/verification/verify.py` to document opcode scanning boundaries and defensive limitations.
   - Added targeted unit tests in `test_upgrade_verification.py` verifying that immediate data bytes inside `PUSH1`..`PUSH32` are never parsed as opcodes (e.g. `0x63` or `0xF4` inside 32-byte hash payloads).
   - Validated scanner behavior against real compiled Solidity 0.8.30 artifacts: confirmed `BoxEvil` exposes `0x35faa416` (`sweep()`), while `BoxV2` exposes strictly `0xd09de08a` (`increment()`), producing zero false positives when declared.

2. **COI Domain Adaptability & Neutral Phrasing**:
   - Extended `get_proposal_coi_analysis` in `app.claims.coi` to distinguish grant payout proposals from protocol upgrades (`PROP-B2`, `PROP-B3`). Upgrades correctly yield `has_linkage = False` with zero undisclosed connections.
   - Added `is_demo_data: bool = True` across backend schemas and frontend types, explicitly communicating that provenance analysis operates over seeded demonstration data rather than a live blockchain indexer.
   - Maintained neutral linkage language without attributing subjective intent or legal wrongdoing.

3. **UI Edge Case Remediation**:
   - Fixed `set-state-in-effect` oxlint warning in `ProposalsPage.tsx` by moving state clearing inside the asynchronous fetch sequence.
   - Made scenario runner output card dynamically render formatted `state_deltas` and `slot_verified` details instead of hardcoded values.
   - Made EVM simulation implementation slot indicator dynamic in `ExecutionPage.tsx` based on `sim.slot_changes`.

4. **Ready for Phase 7**:
   - All 28 Foundry tests pass.
   - All 97 backend pytest tests pass (including 14 scenario integration tests and 9 upgrade verification tests).
   - Frontend builds in 77ms and passes Oxlint with 0 errors and 0 warnings.

## 2026-10-25 — Phase 7: System Hardening, Reproducibility & Demo Rehearsal

1. **Virtualenv Auto-Bootstrapping in `scripts/deploy_and_seed.py`**:
   - To eliminate developer friction across differing shell contexts where `backend/.venv` may not be in `$PATH`, `scripts/deploy_and_seed.py` checks for `eth_account` and `web3`. If missing, it locates `backend/.venv/bin/python` and automatically re-executes itself via `os.execv`.
   - Also documented the canonical uv runner command: `uv run --project backend python scripts/deploy_and_seed.py`.

2. **Conflict Query Alignment in `manifest/builder.py`**:
   - `check_claims_eligibility` previously filtered `conflicts WHERE status = 'UNRESOLVED'`. The conflict detection engine inserts detected conflicts with `status = 'CONFLICT'`.
   - Updated the query to `status IN ('UNRESOLVED', 'CONFLICT')` and marked conflicting claims as `ClaimStatus.UNCERTAIN`. This guarantees that seeded conflicts (e.g. `PROP-001` with $5.0M PDF vs $5.8M forum post) strictly and deterministically block both `POST /manifest/{pid}` and `POST /manifest/{pid}/confirm` with HTTP 422 `ELIGIBILITY_ERROR`.

3. **LLM Error Shielding, Credential Protection & Fail-Closed Security**:
   - Enhanced `OnlineLLMProvider.extract_claims` with structured error handling:
     - Detects HTTP 429 and parses `Retry-After` header for rate-limit management.
     - Intercepts HTTP 5xx responses and logs generic error summaries without leaking backend stack traces or internal server state.
     - Catches `httpx.TimeoutException` and `httpx.ConnectError` cleanly.
     - Actively redacts `self.api_key` from all error messages.
     - Strictly enforces the fail-closed security invariant: LLM unavailability raises safe `RuntimeError("LLM_UNAVAILABLE")` or returns empty claims, which prevents manifest drafting and blocks downstream EIP-712 execution attestation.

4. **Offline Caching Model & Tamper Invalidation**:
   - SQLite cache keys entries using `SHA256(f"{system_prompt}\n{user_prompt}")`.
   - Validated that offline extraction works seamlessly without internet connectivity when pre-cached.
   - Verified that any alteration to the underlying evidence text changes the input content and prompt hash, resulting in a cache miss that safely fails closed rather than returning stale claims.

5. **Demo Reproducibility Under Five Minutes**:
   - The complete demonstration workflow (seed, Scenario C reset, Scenario A payout, Scenario B1 calldata defense, Scenario B2 upgrade, Scenario B3 malicious backdoor defense, and PROP-001 conflict block) executes in ~6.30 seconds.
   - The entire system can be reset, redeployed, and demonstrated live from a clean slate in under five minutes with zero manual database intervention.


