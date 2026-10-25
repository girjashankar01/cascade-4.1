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


