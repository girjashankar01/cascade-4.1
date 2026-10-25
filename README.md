# DAO Accountability Engine — cascade-4.1

CASCADE ’26, Problem 4.1. Architectural source of truth:
[final build guide](docs/dao-build-guide-final.md). The older
[project handoff](docs/project%20handoff.md) is preserved as background.

Stages 0, 1, 2, and 3 are fully implemented and verified:
- **Stage 0:** Environment scaffolding, Python 3.11 via `uv`, Foundry 1.8.6, React/Vite frontend.
- **Stage 1:** Core contracts (`MockToken`, `GovernanceRegistry`, `Treasury`, `GuardedExecutor`), Python EIP-712 signing, and on-chain verification.
- **Stage 2:** Evidence ingestion (PDF/plain-text with PyMuPDF & RapidOCR fallback), Pydantic claim schema, deterministic text grounding, numeric cross-checks, cross-source conflict detection, SQLite-backed LLM caching/audit trail, and Stage 2 FastAPI endpoints.
- **Stage 3:** Canonical manifest serialization (`canon.py`), version hash chaining & evidence root commitments (`hashes.py`), manifest builder with eligibility/conflict gates (`builder.py`), on-chain GovernanceRegistry version commit & approval (`client.py`), tampering detection, clean v1/v2 fixtures, and Stage 3 FastAPI endpoints.

Validation status is recorded in [handoff.md](handoff.md) and technical decisions in [decisions.md](decisions.md).

## Stage 1, 2 & 3 status and test results

- **Smart contracts (`contracts/src/`):**
  - `MockToken.sol`: OpenZeppelin ERC-20 (6 decimals) with deployer-restricted minting.
  - `GovernanceRegistry.sol`: Sequential 1-indexed proposal hash chain; committing new versions invalidates previous approvals.
  - `Treasury.sol`: Holds funds; calls restricted strictly to the configured executor.
  - `GuardedExecutor.sol`: EIP-712 attestation verification (`GuardedExecutor`, `v1`), `VERIFIED == 1` enforcement, actionHash validation, single-use proposal execution.
- **Backend ingestion & claims (`backend/app/`):**
  - `ingestion/`: PyMuPDF native extraction (1-indexed pages), 50-character OCR fallback threshold, SHA-256 collision-safe storage, idempotent re-uploads.
  - `claims/`: Canonical schema (`amount`, `token`, `recipient`, `purpose`, `assumptions`), deterministic text grounding against extracted pages, Decimal-based monetary normalization, cross-source conflict detection.
  - `llm/`: Protocol-based provider interface, SQLite cache keyed by `SHA256(prompt:input:model)`, single retry on invalid output, closed failure with `LLM_UNAVAILABLE`, and audit logging.
- **Manifest, hash chaining & governance (`backend/app/manifest/`, `backend/app/chain/`):**
  - `manifest/canon.py`: Deterministic canonical serialization (sorted keys, no whitespace, UTF-8, integer strings, lowercased Ethereum addresses, strict float rejection).
  - `manifest/hashes.py`: Cryptographic hash formulas (`proposalTextHash`, `evidenceRoot` over sorted 32-byte sha256 digests, `versionHash = keccak256(canon_bytes || prevVersionHash)`, `actionHash = keccak256(abi.encode(target, value, keccak256(calldata)))`).
  - `manifest/builder.py`: Manifest drafting from grounded claims; strict eligibility blocking on unresolved conflicts ($5.0M vs $5.8M) or missing mandatory claims; proposer signing; deterministic tamper detection identifying exact mismatched commitments.
  - `chain/client.py`: Web3 client for deploying and interacting with `GovernanceRegistry`, committing versions, and executing simulated governance approvals.
  - `api/routes.py`:
    - `POST /sources`: Ingests PDF or text sources.
    - `POST /analyze/{pid}`: Runs extraction, grounding, and conflict detection.
    - `GET /claims/{pid}`: Fetches claims and unresolved conflicts.
    - `GET /audit/{pid}`: Fetches immutable audit trail.
    - `POST /manifest/{pid}`: Drafts canonical manifest from grounded claims.
    - `POST /manifest/{pid}/confirm`: Confirms manifest and signs versionHash with proposer key.
    - `GET /manifest/{pid}`: Fetches confirmed manifest.
    - `POST /commit/{pid}`: Commits manifest version to GovernanceRegistry on-chain.
    - `POST /approve/{pid}`: Governance approves committed version on-chain.
    - `GET /versions/{pid}`: Fetches complete version chain and approval records.
    - `POST /verify-version/{pid}`: Verifies manifest integrity against tampering.
- **Test validation results:**
  - `cd contracts && forge test -vv`: 24 passed across 3 suites.
  - `cd backend && uv run pytest`: 48 passed across 13 test suites.
  - `cd frontend && npm run build && npm run lint`: 0 warnings, 0 errors.

## Environment variables

Configured in root `.env` (template in `.env.example`):

```text
RPC_URL=http://127.0.0.1:8545
DATABASE_PATH=data/dao_accountability.db
LLM_MODE=online
LLM_ONLINE_PROVIDER=gemini
LLM_API_KEY=
LLM_TIMEOUT_S=30
LLM_CACHE=on
```

React UI → FastAPI/Python → SQLite and a local EVM chain (Foundry/Anvil).
Later stages will bind proposal text/evidence to one-action manifests, a registry,
treasury and guarded executor with EIP-712 attestations. Governance is planned to be
simulated, with one trusted verifier key and verification of defined watched state
only. LLMs assist extraction; deterministic rules decide verdicts. Full
Governor/Timelock, threshold verification, ingestion, dashboards, wallets, payout
logic, upgrades, database schema, OCR execution and Docker packaging are future work.

## Prerequisites

- Git; [installation](https://git-scm.com/downloads).
- uv; [installation](https://docs.astral.sh/uv/getting-started/installation/).
- Python 3.11+, selected/installed through uv. This backend pins 3.11.
- Node.js 20.19+ or 22.12+ (Node 24 works), npm; [downloads](https://nodejs.org/en/download).
- Foundry; [official installation](https://getfoundry.sh/getting-started/installation).
- Docker is optional; no container or Compose runtime is required for Stage 0.

Windows uv installation, if absent:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

On this machine uv exists at `$env:USERPROFILE/.local/bin/uv.exe` but that directory
was absent from PATH. From this project folder, prepare each PowerShell terminal:

```powershell
. ./scripts/dev-tools.ps1
```

This sets session-only PATH and local cache/interpreter/compiler locations.
It does not activate a manually managed Python environment. On other operating
systems, install uv/Foundry normally and omit the Windows helper.

Install project-local Foundry 1.7.1 on Windows x64:

```powershell
./scripts/install-foundry.ps1
. ./scripts/dev-tools.ps1
forge --version
anvil --version
cast --version
```

The helper installs official platform binary npm packages with scripts disabled.
The wrapper packages' Unix-style postinstall failed under Windows cmd.exe.
No global installation is needed. `.tools/` and `.cache/` are ignored.

## Structure

```text
contracts/          Foundry sample, test/, script/, vendored lib/, foundry.toml
backend/            pyproject.toml, uv.lock, .python-version, app/, tests/
frontend/           React/TypeScript/Vite app and npm lockfile
fixtures/           placeholder only; no proposal fixtures yet
scripts/            check_chain.py and Windows tooling helpers
data/               ignored runtime data; .gitkeep is tracked
.env.example        configuration template without credentials
README.md           setup and current capabilities
decisions.md        chronological technical decisions
handoff.md          actual implementation/validation state and next steps
docs/               preserved source documents
```

## Python setup and validation (uv only)

From the project folder, load the Windows helper if needed, then:

```powershell
cd backend
uv python install 3.11
uv python pin 3.11
uv sync --locked
uv run python --version
uv run pytest
```

uv manages `backend/.venv`; no manual activation is required. Runtime dependencies
are declared in `pyproject.toml`. pytest is a development dependency. SQLite uses
Python's standard-library `sqlite3`; no separate SQLite package is needed.
RapidOCR is optional: `uv sync --locked --extra ocr`. It is not imported at startup;
OCR inference is outside Stage 0 and is not validated by the health test.

## Environment

From the project folder, copy only if `.env` does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Keep actual configuration in the root `.env`. The chain-check script explicitly
loads that location; the health endpoint needs no configuration. Future backend
settings should resolve the same root file. Leave provider/key/model fields empty
until a later stage. Never place secrets in frontend variables or tracked files.
`RPC_URL` defaults to `http://127.0.0.1:8545`; the Stage 0 script accepts loopback
hosts only. No API credentials or wallet keys are needed for this scaffold.

## Run in separate terminals

Each terminal starts in the project folder. On Windows first run
`. ./scripts/dev-tools.ps1`.

Terminal 1 — local chain (silent mode avoids printing deterministic private keys):

```powershell
anvil --host 127.0.0.1 --silent
```

Terminal 2 — backend:

```powershell
cd backend
uv run uvicorn app.main:app --reload
```

Terminal 3 — frontend:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. From another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
cd backend
uv run python ../scripts/check_chain.py
```

Expected responses are `status: ok` and `block_number=<integer>` while Anvil runs.
Use Ctrl+C in each server terminal to stop it. No persistent services are installed.
Anvil state is ephemeral. Its deterministic accounts are local development only:
0 deployer, 1 proposer, 2 simulated governance, 3 verifier, 4 attacker, 5 recipient.
Never commit their private keys or reuse them on public networks.

## Contract and frontend checks

Dependencies are vendored under `contracts/lib/` without submodules. To reproduce
an installation only when the relevant dependency directory is absent:

```powershell
cd contracts
forge install foundry-rs/forge-std --no-git --shallow --root (Get-Location).Path
forge install OpenZeppelin/openzeppelin-contracts@v5.4.0 --no-git --shallow --root (Get-Location).Path
forge build
forge test
```

Use an absolute root: this Foundry version failed with `--root .` on this workspace.
Do not run `forge init` again over the existing scaffold. Solidity is pinned to
0.8.30; the OpenZeppelin remapping is
`@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/`.
The dependency test imports OpenZeppelin Math; it does not implement business logic.
The vendored forge-std init snapshot reports 1.17.0 without an explicit Git ref;
preserve it for the tested snapshot, since reinstalling its default branch can change it.

```powershell
cd frontend
npm ci
npm run build
npm run lint
```

## Workspace constraints and continuity

This folder is inside an existing repository rooted at `C:/Users/abhig`.
No nested repository was initialized and no commits were made in that enclosing repository. Scope Git commands
to this folder (for example `git status --short -- .`); do not stage the home directory.
The referenced `docs/dao-theory-guide.md` is missing; obtain it and complete the
guide's theory/crash lab before production contract work. Event evaluation format
and any testnet requirement remain unconfirmed. Do not deploy publicly in Stage 0.

Update README, decisions and handoff after each meaningful task. Follow the final
build guide in stage order; the explicit uv requirement overrides its older Python
commands. Any unresolved setup failure is a blocker, never a passed check.

The publication target is `https://github.com/girjashankar01/cascade-4.1`.
Publishing uses an isolated checkout of that repository, preserving its history.
Vendored Solidity dependencies include source, licensing and package metadata;
upstream test suites and development tooling are excluded from the publication.
