# Stage 3 handoff

Updated 2026-10-25. **Stage 3 complete.** Canonical manifest serialization (`canon.py`), version hash chaining & evidence root commitments (`hashes.py`), manifest builder with eligibility/conflict gates (`builder.py`), on-chain GovernanceRegistry version commit & approval (`client.py`), tampering detection, clean v1/v2 fixtures, and Stage 3 FastAPI endpoints are fully implemented and verified.

## Pre-implementation verification findings (Stage 2)

1. Preflight test suites: Confirmed all 24 Foundry tests and 30 backend pytest tests passed prior to Stage 3 modifications.
2. Conflict safety: Confirmed that the unresolved `$5.0M` vs `$5.8M` contradiction in `PROP-001` strictly prevents automated or manual manifest confirmation, raising `EligibilityError` and returning HTTP 422.
3. Sub-millisecond audit collision: Identified and fixed sub-millisecond audit ID collision in `LLMRouter.analyze_sources` by incorporating nanosecond timestamps and uuid entropy.

## Implemented files and functionality

- `backend/app/manifest/canon.py`: Deterministic JSON serialization:
  - Lexicographical object key sorting.
  - Complete elimination of insignificant whitespace.
  - Strict float rejection (`ValueError` on any `float` input).
  - Ethereum address lowercasing (`0x...` 40-hex normalization).
  - Integer-string normalization for token amounts and monetary quantities.
  - Raw UTF-8 byte encoding (`ensure_ascii=False`).
- `backend/app/manifest/hashes.py`: Deterministic cryptographic commitments:
  - `proposalTextHash = keccak256(UTF-8 bytes of proposal text)`.
  - `evidenceRoot = keccak256(concatenated sorted 32-byte binary SHA-256 digests)`.
  - `versionHash = keccak256(canonical_manifest_bytes + 32-byte binary prevVersionHash)`.
  - `actionHash = keccak256(abi.encode(target, value, keccak256(calldata)))` with ABI-encoded `transfer(address,uint256)` calldata.
- `backend/app/manifest/builder.py`:
  - `check_claims_eligibility`: Enforces that proposals have zero unresolved conflicts, mandatory claims (`amount`, `recipient`) are `GROUNDED`, and sources are proposal-scoped.
  - `build_manifest_draft`: Assembles single-action manifest matching Section 5.1 (`erc20_payout`, outflow envelope, text hash, evidence root, prev version hash).
  - `confirm_manifest_with_signature`: Records human confirmation, signs `versionHash` with proposer private key, and stores in SQLite `manifests` table with status `CONFIRMED`.
  - `verify_manifest_integrity`: Recomputes all commitments, checks against stored manifest, and verifies against on-chain `GovernanceRegistry`. Detects tampering and raises `TamperError` naming the exact mismatched hash.
- `backend/app/chain/client.py`:
  - `deploy_system`: Deploys `MockToken`, `GovernanceRegistry`, `Treasury`, and `GuardedExecutor` on local Anvil nodes.
  - `commit_version_onchain`: Submits `commitVersion(pid, versionHash, actionHash, evidenceRoot)` by proposer.
  - `approve_version_onchain`: Submits `approve(pid, versionHash)` by simulated governance account.
  - `get_onchain_version` & `get_onchain_approved`: Queries on-chain version chain and approved records.
- `backend/app/db.py`:
  - Extended SQLite schema with `manifests` and `versions` tables.
- `backend/app/api/routes.py`:
  - `POST /manifest/{pid}`: Drafts manifest from grounded claims; returns 422 if conflicted/ineligible.
  - `POST /manifest/{pid}/confirm`: Confirms and signs manifest with proposer key.
  - `GET /manifest/{pid}`: Retrieves confirmed manifest and canonical JSON.
  - `POST /commit/{pid}`: Commits version to GovernanceRegistry on-chain and records in database.
  - `POST /approve/{pid}`: Governance approves latest committed version on-chain.
  - `GET /versions/{pid}`: Retrieves complete version chain history and approval records.
  - `POST /verify-version/{pid}`: Verifies manifest integrity against tampering.
- `fixtures/`:
  - `clean_proposal_v1.pdf`: Clean proposal for $1.0M payout to `0x9965507D1a55BCC6475675304Ca994970De97744`.
  - `clean_proposal_v2.pdf`: Text revision of proposal for identical payout action, enabling version chaining tests.

## Executed commands and outcomes

| Command | Directory | Outcome | Details |
| --- | --- | --- | --- |
| `uv run pytest` | `backend/` | PASS | 48 tests passed in 3.61s across 13 test suites |
| `forge test -vv` | `contracts/` | PASS | 24 tests passed across 3 test suites |
| `npm run build` | `frontend/` | PASS | Vite production build succeeded in 67ms |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 errors and 0 warnings |

## Exit gate checklist

- [x] `canon.py` verified with fixed test vectors (key order, whitespace, unicode, integer strings, float rejection).
- [x] Manifest builder drafts valid single-action manifest from confirmed claims.
- [x] Proposer signs version hash with development key (`confirm_manifest_with_signature`).
- [x] Cryptographic commitments calculated: `proposalTextHash`, `evidenceRoot`, `versionHash`, and `actionHash`.
- [x] Versions 1 and 2 committed on-chain with visible hash chain (`test_onchain_governance.py`).
- [x] Version 2 approved by governance account on-chain.
- [x] Committing Version 3 automatically invalidates prior approval on `GovernanceRegistry`.
- [x] Disputed proposal ($5.0M vs $5.8M) strictly blocks manifest confirmation.
- [x] Tampering detection verified: 1-byte change to manifest, evidence, or text fails verification and identifies the mismatched commitment.
- [x] All Stage 3 API routes implemented, registered, and verified with integration tests.
- [x] Documentation, README, decisions, and handoff updated.

## Next steps (Stage 4: Verification Pipeline, Transaction Simulation, and Guarded Execution)

1. Implement transaction simulation (`simulate.py`) using local Anvil fork/node and `eth_call` state overrides.
2. Implement 7 deterministic verification rules (`verify.py`):
   - Rule 1: Approved on-chain version match.
   - Rule 2: Evidence root match.
   - Rule 3: Single executable action match.
   - Rule 4: Action hash equality (`keccak256(abi.encode(target, value, keccak256(calldata)))`).
   - Rule 5: Calldata decoding and parameter cross-check against manifest action.
   - Rule 6: Watched-state simulation scope and token outflow limit enforcement.
   - Rule 7: Zero unobservable/unsupported state changes.
3. Generate EIP-712 attestation with verdict `VERIFIED = 1` and deadline when all rules pass.
4. Execute verified transaction on-chain via `GuardedExecutor.execute(...)` and verify Treasury token transfer.
5. Implement `POST /verify` and `POST /execute` API endpoints.
