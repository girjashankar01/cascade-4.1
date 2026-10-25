# Stage 1 handoff

Updated 2026-10-25. **Stage 1 complete.** Core smart contracts, Python EIP-712 attestation signing, and end-to-end Python-to-Solidity interoperability are verified.

## Implemented files and functionality

- `contracts/src/MockToken.sol`: OpenZeppelin ERC-20 with 6 decimals mimicking USDC with initial minting to deployer.
- `contracts/src/GovernanceRegistry.sol`: Sequential 1-indexed proposal version commitments, proposer ownership, zero/duplicate hash rejection, and governance-only approval of latest versions.
- `contracts/src/Treasury.sol`: Holds ETH and ERC-20 tokens; `exec` is callable strictly by the authorized executor; one-time atomic executor configuration by deployer.
- `contracts/src/GuardedExecutor.sol`: EIP-712 typed data verification (`GuardedExecutor`, `v1`), `VERIFIED = 1` enforcement, single-use proposal execution (`executed[pid]`), actionHash validation, verifier signature recovery, and CEI execution via Treasury.
- `contracts/test/Stage1Core.t.sol`: 19 comprehensive Foundry unit and revert tests covering valid payouts, action mismatches, expired deadlines, invalid signatures, non-VERIFIED verdicts, replay protection, access controls, zero hashes, and downstream revert rollbacks.
- `backend/app/chain/__init__.py`, `attest.py`: Core action-hash computation (`keccak256(abi.encode(target, value, keccak256(calldata)))`) and EIP-712 typed data signing using `eth-account` and `web3.py`.
- `backend/tests/test_attest.py`: Unit tests for action hash computation, typed data construction, and signature recovery.
- `backend/tests/test_interop.py`: End-to-end automated integration test deploying contracts to an ephemeral Anvil node, computing hashes and signing attestations in Python, and executing successfully through `GuardedExecutor` on-chain.

## Executed commands and outcomes

| Command | Working Directory | Outcome | Details |
| --- | --- | --- | --- |
| `forge build` | `contracts/` | PASS | 44 files compiled with Solc 0.8.30 |
| `forge test -vv` | `contracts/` | PASS | 22 passed across 3 suites (19 in `Stage1Core.t.sol`, 2 in `Counter.t.sol`, 1 in `Dependency.t.sol`) |
| `uv run pytest` | `backend/` | PASS | 6 passed (4 in `test_attest.py`, 1 in `test_health.py`, 1 in `test_interop.py`) |
| `npm run build` | `frontend/` | PASS | Production bundle generated with zero errors |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 errors and 0 warnings |

## Cross-language interoperability outcome

1. **ActionHash Equality:**
   - Vector: `target = 0x1111111111111111111111111111111111111111`, `value = 100`, `data = "hello world"`.
   - Result: Python and Solidity independently compute `0x67ace4504a92394fd5e07872975fa56b94ce9583abb97c64adb24df2b4c36995` (exact match).
2. **On-Chain EIP-712 Execution:**
   - In `test_interop.py`, contracts are deployed to Anvil.
   - Payout of 50,000 USDC is prepared.
   - Python signs EIP-712 attestation with Anvil Account 3 verifier key.
   - `GuardedExecutor.execute` is called with Python signature and calldata.
   - On-chain transaction succeeds (`receipt.status == 1`); recipient balance increases by 50,000 USDC.
   - Replay execution reverts on-chain with `"already executed"`.
   - Substituted attacker recipient reverts on-chain with `"action mismatch"`.
   - Signature from non-verifier key reverts on-chain with `"bad attestation"`.

## Acceptance gate checklist

- [x] Four contracts implemented according to specifications in `contracts/src/`.
- [x] All 22 Foundry unit and revert tests pass.
- [x] Python and Solidity compute identical action hashes.
- [x] Python-signed EIP-712 attestation verifies and executes on-chain via Solidity `GuardedExecutor`.
- [x] Technical decisions recorded in `decisions.md`.
- [x] Workspace and handoff status updated.

## Next steps (Stage 2: Evidence and Claims)

1. Implement document ingestion in `backend/app/ingestion/` (PyMuPDF for text extraction with page numbers, RapidOCR fallback).
2. Define Pydantic claims schema in `backend/app/claims/schema.py` (`field`, `value`, `quote`, `source_id`, `page`, `confidence`).
3. Implement text grounding validation and numeric cross-checks.
4. Implement deterministic cross-source conflict detection.
5. Create test fixtures (`proposal.pdf`, `forum_post.txt`).
