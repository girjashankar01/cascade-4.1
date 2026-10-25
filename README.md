# DAO Accountability Engine — cascade-4.1

CASCADE ’26, Problem 4.1. Architectural source of truth:
[final build guide](docs/dao-build-guide-final.md). The older
[project handoff](docs/project%20handoff.md) is preserved as background.

Stage 1 core contracts, Python EIP-712 signing, and cross-language on-chain
verification are fully implemented and passing. Validation status is recorded in
[handoff.md](handoff.md) and technical decisions in [decisions.md](decisions.md).

## Stage 1 status and test results

- **Solidity contracts (`contracts/src/`):**
  - `MockToken.sol`: OpenZeppelin ERC-20 (6 decimals) for payout simulation.
  - `GovernanceRegistry.sol`: Sequential proposal version hash chain with ownership protection and governance-only approvals.
  - `Treasury.sol`: Holds ETH/tokens; execution restricted strictly to the configured executor.
  - `GuardedExecutor.sol`: EIP-712 attestation verification (`GuardedExecutor`, `v1`), `VERIFIED == 1` check, actionHash validation, and single-use execution via Treasury.
- **Python cryptography (`backend/app/chain/attest.py`):**
  - Exact `actionHash` computation: `keccak256(abi.encode(target, value, keccak256(calldata)))`.
  - Canonical EIP-712 structured data signing with `eth-account` (v0.14).
- **Test validation results:**
  - `forge test -vv`: 22 passed across 3 suites (19 unit/revert tests in `Stage1Core.t.sol`).
  - `uv run pytest`: 6 passed across 3 suites (`test_attest.py`, `test_health.py`, `test_interop.py`).
  - Cross-language interop test: Python computes action hash, signs EIP-712 attestation, and executes successfully on live Anvil chain.

## Planned architecture and limits

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
