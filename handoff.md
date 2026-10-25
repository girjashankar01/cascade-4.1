# Stage 2 handoff

Updated 2026-10-25. **Stage 2 complete.** Evidence ingestion, canonical claim extraction, deterministic text grounding, numeric cross-checks, cross-source conflict detection, LLM routing with SQLite caching and audit trails, and all Stage 2 FastAPI endpoints are verified.

## Pre-implementation verification findings (Stage 1)

1. `Treasury.setExecutor`: Verified deployer-restricted (`msg.sender == deployer`) and single-use (`executor == address(0)`), permanently locked thereafter.
2. `GovernanceRegistry` version commits: Identified that `commitVersion` previously retained prior approvals across revisions. Fixed by invalidating `_approved[pid]` upon new version commits, fulfilling Section 9 testing criteria ("A text revision with an identical action invalidates the old approval"). Verified with regression test `test_TextRevision_InvalidatesPriorApproval`.
3. `MockToken.mint`: Added deployer-only access control (`require(msg.sender == deployer, "only deployer")`), verified with regression test `test_Revert_MockTokenMint_Unauthorized`.
4. Artifact loading: Verified `test_interop.py` compiles and loads live Foundry artifacts from `contracts/out/` directly, with zero hardcoded bytecode.
5. ActionHash: Independently verified Python and Solidity compute identical action hash `0x67ace4504a92394fd5e07872975fa56b94ce9583abb97c64adb24df2b4c36995` for test input.

## Implemented files and functionality

- `backend/app/db.py`: SQLite initialization with `sources`, `claims`, `conflicts`, `analyses`, and `llm_cache` tables; context manager with Row factory and PRAGMA foreign keys.
- `backend/app/ingestion/ocr.py`: RapidOCR fallback execution with pluggable mock handler `_OCR_MOCK_HANDLER` to avoid external ONNX model downloads during test runs.
- `backend/app/ingestion/pdf.py`: PyMuPDF native digital text extraction with 1-indexed pages; 50-character usable text threshold triggering OCR fallback; SHA-256 collision-safe storage under `data/sources/`; idempotent ingestion.
- `backend/app/claims/schema.py`: Pydantic models for canonical fields (`amount`, `token`, `recipient`, `purpose`, `assumptions`), strict validation on confidence (0.0–1.0) and page (>=1), statuses `GROUNDED`, `UNCERTAIN`, `REJECTED`, and `Conflict` model.
- `backend/app/claims/ground.py`: Normalization for whitespace, lowercase, and Unicode dash variants; exact substring check against source page; `Decimal`-based monetary normalization equating `$5.0M` and `5,000,000` as integer strings; quote numeric cross-checks.
- `backend/app/claims/conflicts.py`: Deterministic cross-source contradiction detection; surfaces `$5.0M` vs `$5.8M` discrepancy with both quotes and page references; marks affected claims `UNCERTAIN`.
- `backend/app/llm/base.py`: `LLMProvider` protocol and `LLMUnavailableError` (code `LLM_UNAVAILABLE`).
- `backend/app/llm/cache.py`: SQLite cache keyed by `SHA256(prompt_hash:input_hash:model)`.
- `backend/app/llm/online.py`: Hosted provider implementation with system prompt, markdown JSON block extraction, and timeout handling.
- `backend/app/llm/router.py`: Caching router with single retry on invalid JSON/schema, closed failure with `LLM_UNAVAILABLE`, and audit trail logging in `analyses` table.
- `backend/app/api/routes.py`:
  - `POST /sources`: accepts PDF upload or plain text with SHA-256 deduplication.
  - `POST /analyze/{pid}`: runs extraction, grounding, and conflict detection.
  - `GET /claims/{pid}`: returns persisted claims, validation details, and conflicts.
  - `GET /audit/{pid}`: returns audit trail.
- `backend/app/main.py`: lifespan database initialization and router registration.
- `fixtures/`: `proposal.pdf` ($5.0M, 5,000,000 USDC to 0x9965507D1a55BCC6475675304Ca994970De97744), `forum_post.txt` ($5.8M conflicting discussion), `expected_claims.json` (deterministic test oracle).

## Executed commands and outcomes

| Command | Directory | Outcome | Details |
| --- | --- | --- | --- |
| `uv run pytest` | `backend/` | PASS | 30 tests passed in 2.49s across 8 test suites |
| `forge test -vv` | `contracts/` | PASS | 24 tests passed across 3 test suites |
| `npm run build` | `frontend/` | PASS | Vite production build succeeded in 67ms |
| `npm run lint` | `frontend/` | PASS | Oxlint passed with 0 errors and 0 warnings |

## Exit gate checklist

- [x] Grounding rejects fabricated quotes without accepting paraphrases.
- [x] Numeric normalization equates `$5.0M` and `5,000,000` under same unit and rejects genuine mismatches.
- [x] Discrepancy between `$5.0M` and `$5.8M` surfaced with both quotes and source references.
- [x] Low-confidence claims (< 0.8), OCR-derived claims, and unresolved conflicts remain `UNCERTAIN`.
- [x] SQLite tables (`sources`, `claims`, `conflicts`, `analyses`, `llm_cache`) implemented.
- [x] All four Stage 2 routes registered, functional, and covered by end-to-end tests.
- [x] Stage 1 regression tests pass.
- [x] Documentation and handoff updated.

## Next steps (Stage 3: Manifest Construction, Commitment, and Approval)

1. Implement `canon.py` for deterministic JSON canonicalization (sorted keys, no spaces, UTF-8, integer strings).
2. Implement manifest builder drafting action envelope (`erc20_payout`) from confirmed claims.
3. Compute `proposalTextHash`, `evidenceRoot`, `versionHash`, and `actionHash`.
4. Implement `POST /manifest/{pid}` and `POST /manifest/{pid}/confirm`.
5. Implement on-chain commitment (`POST /commit/{pid}`) and governance approval (`POST /approve/{pid}`).
6. Add tamper tests (one-byte change to evidence or manifest invalidates versionHash).
