# DAO Accountability Engine: Final Build Guide (CASCADE '26, Problem 4.1)

One document to follow from start to finish. Concepts (hashes, calldata, proxies, simulation) are explained in `dao-theory-guide.md`; read its sections 0, 3.2, 5.3, 6 and 8 first (about 30 minutes).

Items marked **[verify]** depend on tool versions or provider terms. Check them before relying on them.

---

## 1. What you are building

A system that proves that **what a DAO executes matches what voters were asked to approve**.

The real gap: an OpenZeppelin Governor's `proposalId` already hashes the exact calldata, so calldata cannot be swapped after the vote. What can mismatch is the **prose voters read** versus the **calldata that was proposed**, and the **behaviour of the code** it runs. Your product binds prose to a structured manifest, commits it on-chain, verifies the submitted execution against it, and refuses to execute on mismatch.

```
proposal text + evidence  --LLM (grounded)-->  claims  --human confirms-->  manifest (one action)
        |                                                                       |
        +---------------- hashes ---> versionHash ---> committed on-chain ---> approved by governance
                                                                                |
submitted tx (target,value,data) --decode + static scan + simulate--> observed effects
        |                                                                       |
        +--------------- compared with manifest envelope (deny by default) -----+
                                           |
                       verdict -> verifier signs attestation (only if VERIFIED)
                                           |
                  GuardedExecutor checks everything on-chain, then executes (or reverts)
```

### Problem requirements and where they are met

| Requirement | Component |
|---|---|
| Verifiable proposals | canonical manifest, version hash chain, evidence root, `GovernanceRegistry` |
| Decision intelligence | grounded LLM claims, cross-source conflict detection, uncertainty labels |
| Conflict-of-interest disclosures | declared wallets + wallet graph (optional tier) |
| Execution accountability | decode + simulate + envelope check + `GuardedExecutor` |
| Malicious upgrade scenario | UUPS upgrade scenario, blocked through the real executor |

### What the statement does and doesn't require
- Offline LLM/OCR: not required. Hosted LLM allowed.
- Privacy-first: not required for 4.1 (it appears in 4.2/4.3). Keep documents off-chain and put only hashes on-chain.
- Raster scans: not mentioned. Digital PDFs and web text are core; a scanned fixture is optional.
- Halt or flag: "autonomously halt or flag". You will do both: flag in the UI, halt through the executor.

Ask the event leads two questions before you commit hours: how it will be evaluated (live demo or scripted inputs) and whether a public testnet is expected. This guide assumes a local chain.

---

## 2. Scope and honesty rules

**Tiers**

| Tier | Scope | Budget |
|---|---|---|
| T0 (must) | ERC-20 payout enforced by the executor; grounded claims and conflict detection; manifest committed and approved; verification pipeline; effects-diff dashboard; deterministic scenario runner | about 12 h |
| T1 (thin, named in the problem text) | malicious UUPS upgrade scenario blocked through the real executor | about 2 h |
| T2 (only with leftover time, in this order) | hybrid/local LLM, seeded wallet graph, Docker packaging, scanned-PDF fixture, nested `multicall` decoding | rest |

**Fixed scope decisions**
1. Exactly **one executable action per proposal version**. The upgrade scenario is a separate proposal.
2. Supported action kinds: `erc20_payout` and `proxy_upgrade`. Anything else returns `UNSUPPORTED`.
3. Governance is **simulated** (one governance account, or a tiny voting contract if time allows). Say this in the UI and README. Full Governor + Timelock integration is future work.
4. The verifier is a **single trusted key**. Say this in the README. Mitigations to mention, not build: threshold verifiers, challenge window, reproducible open verification.
5. Verification covers **defined watched state** only. If a relevant effect cannot be observed or interpreted, the verdict is `UNSUPPORTED` or `UNCERTAIN`, never `VERIFIED`.
6. The LLM never decides a verdict. Hashes, decoding, simulation and rules do.

**Verdicts:** `1 VERIFIED`, `2 MISMATCH` (with rule IDs and diff), `3 UNSUPPORTED` (needs review), `4 UNCERTAIN` (evidence quality). Attestations are signed only for `VERIFIED`.

---

## 3. Architecture decisions (final)

| Area         | Choice                                                                            | Why / rejected alternatives                                                                                        |
| ------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Chain        | Foundry + Anvil, local                                                            | deterministic, offline; testnets add faucet/RPC/wifi risk; Python-simulated chain fails the "on-chain" requirement |
| Chain design | registry + token + treasury + guarded executor + UUPS proxy, simulated governance | full Governor/Timelock is a stretch; registry-only has no enforcement                                              |
| Enforcement  | on-chain action-hash match + EIP-712 attestation                                  | dashboard-only flags cannot halt; Safe guards are for multisigs, not Timelock-owned treasuries                     |
| Backend      | Python 3.11+, FastAPI, web3.py, pydantic, SQLite                                  | one process, libraries for everything                                                                              |
| Documents    | PyMuPDF native text first; RapidOCR (pip, ONNX) fallback for scans                | avoids system packages; Tesseract also works but needs an OS install                                               |
| LLM          | one hosted provider first behind an interface; Ollama later                       | fastest to useful structured extraction                                                                            |
| Retrieval    | none (chunk lookup + SQLite FTS if needed)                                        | a vector DB adds nothing at this scale                                                                             |
| Frontend     | Vite + React (or Next.js)                                                         | you know JS; Streamlit is weaker for diffs                                                                         |
| Graph (T2)   | NetworkX + Cytoscape.js or a plain edge table                                     |                                                                                                                    |
| Dev loop     | native (uv, Node, `anvil`, `forge`)                                               | Docker is packaging, added at the end                                                                              |

---

## 4. Setup (hour 0)

Prerequisites: Python 3.11+, Node 20+, Foundry, Git. Docker only needs to be installed and verified (`docker --version`, `docker compose version`); do not build Compose now.

```bash
curl -L https://foundry.paradigm.xyz | bash && foundryup        # [verify install command at getfoundry.sh]
forge --version && anvil --version && cast --version
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn web3 eth-account pydantic pymupdf rapidocr-onnxruntime httpx python-multipart pytest
```

Repo layout:

```
dao-integrity/
  contracts/   src/{MockToken,GovernanceRegistry,Treasury,GuardedExecutor,BoxUUPS,BoxV2,BoxEvil}.sol
               test/  script/Deploy.s.sol
  backend/app/
    ingestion/ pdf.py ocr.py
    llm/       base.py online.py local.py router.py cache.py
    claims/    schema.py ground.py conflicts.py
    chain/     client.py canon.py manifest.py simulate.py decode.py bytecode.py attest.py verify.py
    graph/     build.py queries.py            (T2)
    api/       routes.py   main.py   db.py
  frontend/
  fixtures/    proposal.pdf  forum_post.txt  expected_claims.json  (scanned.pdf optional)
  scripts/     deploy_and_seed.py  run_scenarios.py
  data/        (SQLite, uploads, LLM cache; gitignored)
  .env.example  .gitignore  .dockerignore  README.md
```

`.env.example`:
```
RPC_URL=http://127.0.0.1:8545
LLM_MODE=online            # online | local | hybrid
LLM_ONLINE_PROVIDER=       # choose after testing on fixtures
LLM_API_KEY=               # never committed, never in images
LLM_LOCAL_MODEL=
LLM_TIMEOUT_S=30
LLM_CACHE=on
```

Anvil dev accounts (public keys, dev only). Use separate accounts for the four roles:

| Account | Role |
|---|---|
| 0 | deployer |
| 1 | proposer |
| 2 | governance (simulated) |
| 3 | verifier |
| 4 | attacker |
| 5 | honest recipient |

Do the theory guide's terminal crash lab (about 60-90 minutes, can overlap with setup) before writing contracts.

---

## 5. Core design (final specifications)

### 5.1 Manifest
Canonical JSON signed by the proposer. One action.

```json
{
  "proposalId": "PROP-001", "version": 2,
  "action": {
    "kind": "erc20_payout",
    "token": "0xToken", "decimals": 6,
    "recipient": "0xRecipient",
    "amountRaw": "5000000000000"
  },
  "envelope": {
    "maxTokenOutflow": {"0xToken": "5000000000000"},
    "allowApprovals": false, "allowRoleChanges": false,
    "allowImplChange": false, "allowNewContracts": false
  },
  "proposalTextHash": "0x...",     
  "evidenceRoot": "0x...",         
  "prevVersionHash": "0x..."
}
```

Upgrade variant:
```json
"action": {
  "kind": "proxy_upgrade", "proxy": "0xProxy", "newImpl": "0xImpl",
  "expectedImplCodeHash": "0x...",
  "declaredSelectors": ["0x...", "0x..."]       // functions the proposal text says the new version adds/changes
}, "envelope": { "allowImplChange": true, ... }
```

The LLM drafts the manifest from evidence; **a human confirms every field in the UI**; the proposer signs it. The LLM never silently decides what is approved.

### 5.2 Canonicalization (one function, used everywhere)
Sorted keys, no whitespace, UTF-8, all numbers as **integer strings**, lowercase addresses, no floats. Test with fixed vectors (key order, whitespace, unicode, large integers). Cross-check with a Solidity test where relevant.

### 5.3 Hashes and the approval chain
```
proposalTextHash = keccak(exact proposal text voters saw)
evidenceRoot     = keccak(sorted list of evidence file sha256 hashes)   [or a Merkle root]
versionHash      = keccak(canonical(manifest) || prevVersionHash)       // manifest includes proposalTextHash and evidenceRoot
actionHash       = keccak(abi.encode(target, value, keccak(calldata)))  // calldata derived deterministically from manifest.action
```
Chain of trust, each link one deterministic check:

```
governance approves versionHash
  -> registry.approved[pid] = (versionHash, actionHash, evidenceRoot)    // written only by the governance account
  -> verifier recomputes everything off-chain, signs attestation over
     (pid, versionHash, actionHash, evidenceRoot, verdict, deadline)
  -> GuardedExecutor re-checks on-chain, then executes via Treasury
```
A text revision with an identical action changes `versionHash`, so old approvals and attestations stop working. Honest wording: this proves which text version was committed and referenced by the vote, not that each voter read it.

### 5.4 Roles (four keys, four responsibilities)

| Role | Does | Must not be able to |
|---|---|---|
| Proposer | signs and commits manifest versions | approve versions |
| Governance (simulated) | `registry.approve(pid, versionHash)` | sign attestations |
| Verifier | signs EIP-712 attestations | approve versions |
| Executor (contract) | enforces, then calls Treasury | change approvals |

### 5.5 Contracts

- **MockToken**: OpenZeppelin ERC-20, 6 decimals, mint to deployer. Mimics USDC.
- **GovernanceRegistry**:
  - `commitVersion(pid, versionHash, actionHash, evidenceRoot)`: proposer only for that `pid` (first committer owns it); versions strictly sequential; stores the chain; emits an event.
  - `approve(pid, versionHash)`: only `governance`; version must be the latest committed; copies `(versionHash, actionHash, evidenceRoot)` into `approved[pid]`.
  - `approved(pid) returns (versionHash, actionHash, evidenceRoot)`.
- **Treasury**: holds funds (and owns the proxy in the upgrade scenario). `exec(target, value, data)` callable **only by the executor**.
- **GuardedExecutor**: OpenZeppelin `EIP712`, `ECDSA`. Immutable `registry`, `treasury`, `verifier`. One execution per `pid`.
- **BoxUUPS / BoxV2 / BoxEvil**: UUPS implementations; V2 is benign; Evil adds a hidden `sweep()` and extra `delegatecall`. Proxy = OpenZeppelin `ERC1967Proxy`, owner = Treasury, `_authorizeUpgrade` is `onlyOwner`.

Executor core (this is the project's trust anchor):

```solidity
bytes32 constant ATTEST_TYPEHASH = keccak256(
  "Attestation(bytes32 proposalId,bytes32 versionHash,bytes32 actionHash,bytes32 evidenceRoot,uint8 verdict,uint256 deadline)");
uint8 constant VERIFIED = 1;
mapping(bytes32 => bool) public executed;

function execute(bytes32 pid, address target, uint256 value, bytes calldata data,
                 uint8 verdict, uint256 deadline, bytes calldata sig) external {
    require(!executed[pid], "already executed");
    require(block.timestamp <= deadline, "attestation expired");
    require(verdict == VERIFIED, "not verified");
    (bytes32 versionHash, bytes32 approvedAction, bytes32 evidenceRoot) = registry.approved(pid);
    require(versionHash != bytes32(0), "no approved version");
    bytes32 ah = keccak256(abi.encode(target, value, keccak256(data)));
    require(ah == approvedAction, "action mismatch");
    bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(
        ATTEST_TYPEHASH, pid, versionHash, ah, evidenceRoot, verdict, deadline)));
    require(ECDSA.recover(digest, sig) == verifier, "bad attestation");
    executed[pid] = true;                              // effects before the external call
    treasury.exec(target, value, data);
}
```
The EIP-712 domain supplies `chainId` and `verifyingContract`, preventing cross-chain and cross-contract replay. Python signs the same structure with `eth_account` typed-data signing **[verify current function name, e.g. `encode_typed_data`]**.

### 5.6 Verification pipeline (backend `verify.py`)
Input: `proposalId` and a submitted `(target, value, data)`. Steps in order; the first failing rule sets the verdict and is shown in the UI:

1. **R1 version**: rebuild manifest, recompute `versionHash`; must equal `registry.approved(pid).versionHash`; manifest signature valid.
2. **R2 action**: recompute `actionHash` from `manifest.action`; must equal the registry's. Compute the submitted tx's hash; if different -> `MISMATCH` with a **field-level decoded diff** (recipient, amount, token, selector, value).
3. **Decode**: supported selectors only: `transfer(0xa9059cbb)`, `approve(0x095ea7b3)`, `upgradeToAndCall(0x4f1ef286)`. Unknown top-level selector -> `UNSUPPORTED`.
4. **Simulate** (5.7) and collect watched effects.
5. **Envelope check**: any watched effect outside the envelope -> `MISMATCH` (rules R3 token outflow, R4 unexpected balance increase, R5 allowance change, R6 implementation slot change, R9 owner/role change). Unobservable effect -> `UNSUPPORTED`/`UNCERTAIN`.
6. **Upgrade checks** (5.8) when `kind == proxy_upgrade`.
7. **Attest** only if everything passes (`VERIFIED`); sign the typed message with the verifier key.
8. Persist the full audit record (5.9).

### 5.7 Simulation: snapshot, impersonate, diff, revert
A snapshot does **not** list every changed slot. You diff **watched state** only:

- ETH and token balances of: treasury, declared recipient, every address appearing in decoded calldata, disclosed/seeded watchlist addresses, and addresses that appear in `Transfer` logs (logs only **expand** the watch list; they are never proof).
- Token `allowance(treasury, *)` for the watch list.
- EIP-1967 implementation slot of watched proxies.
- Explicitly supported `owner()` / role state.

```
id = evm_snapshot
anvil_impersonateAccount(executor)           # acts as the contract address; [verify on your Anvil version]
before = read watched state
send treasury.exec(target, value, data) from executor
after  = read watched state; collect receipt + logs
evm_revert(id)                               # world restored; verify with a re-read
effects = after - before
```
Optional: call-tree via `debug_traceCall`/`cast run` **[verify support on your Anvil version; never depend on it]**.

### 5.8 Upgrade scenario (T1)
The story: the proposal text describes a benign V2 in technical jargon; voters approve; the submitted implementation deviates. The hash of the declared `newImpl` matches (voters were fooled), so the check must look at **what the code is**:

- Read the EIP-1967 slot before/after in simulation: the change must be to `manifest.action.newImpl` and nothing else (`allowImplChange` only for that address).
- Fetch runtime code of `newImpl` and compute its hash; if `expectedImplCodeHash` is given it must match.
- Static scan (below): selectors in the new code must be within `baselineSelectors ∪ declaredSelectors`. **Undeclared selector -> `MISMATCH` (rule R7)**.
- Opcode findings are **relative to the previous implementation** (UUPS implementations legitimately contain `DELEGATECALL`): new `DELEGATECALL`, `CALLCODE`, `SELFDESTRUCT`, `CREATE/CREATE2` are reported as supporting evidence with a confidence label. The scan alone never blocks; the slot/policy/selector rules do.

```python
def scan(code: bytes):
    i, ops, sels = 0, set(), set()
    while i < len(code):
        op = code[i]
        if 0x60 <= op <= 0x7f:                         # PUSHn
            n = op - 0x5f
            if n == 4: sels.add(code[i+1:i+5].hex())   # PUSH4 operand = selector candidate (heuristic)
            i += 1 + n
        else:
            ops.add(op); i += 1
    names = {"DELEGATECALL":0xf4,"CALLCODE":0xf2,"SELFDESTRUCT":0xff,"CREATE":0xf0,"CREATE2":0xf5}
    return {n for n,o in names.items() if o in ops}, sels
```
Limits to state in the UI: `PUSH4` operands are not always selectors; dispatch can be computed; a dangerous function may be unreachable. This is heuristic evidence.

Proof of enforcement: B3 gets no attestation; `execute` reverts; show the implementation slot unchanged afterwards. If this cannot be completed reliably, present it as a **separate analysis scenario** and say so.

### 5.9 Evidence, LLM and grounding
- **Schema** (pydantic): claims `{field, value, quote, source_id, page, confidence}`.
- **Grounding**: normalize whitespace, case and dash variants; the `quote` must be a substring of that source's extracted text, else the claim is dropped and logged.
- **Number cross-check**: the number parsed from the quote must equal the claimed `value`.
- **Conflict detector** (deterministic): same field with different values across sources -> `CONFLICT` item showing both quotes (for example $5M in the post vs $5.8M in the PDF).
- **Uncertainty**: low OCR confidence on money fields, missing fields and unresolved conflicts are labelled `UNCERTAIN` and never used silently.
- The LLM may summarize and explain; it never produces a verdict.
- **Display rules**: show raw amount, human token amount (raw / 10^decimals) and USD **separately**; show USD only with a stated valuation source and timestamp. Label every LLM result **cached** or **generated now**.
- **Audit record per analysis**: input hashes, extraction output, provider/model/version, prompt hash, rule-set version, simulation results.

### 5.10 LLM modes (online first, hybrid later)
Interface:
```python
class LLMProvider(Protocol):
    name: str
    def extract_claims(self, sources: list[Source]) -> ClaimSet: ...
    def summarize(self, claims: ClaimSet) -> Summary: ...
```
Router policy:
1. Cache hit on `(prompt_hash, input_hash, model)` -> cached result (labelled).
2. `online`: call provider; on timeout/429/5xx/invalid JSON twice -> fall back to local if configured, else `LLM_UNAVAILABLE` (never fake output).
3. `local`: Ollama only.
4. `hybrid`: a source marked **confidential** goes to local only and **fails closed** (`LLM_UNAVAILABLE` if local is down; never falls through to online). Otherwise online, falling back to local on failure.
5. Record `provider`, `model`, `latency`, `fallback_used` in the audit record.

Free hosted tiers may use inputs for training and rate-limit mid-demo **[verify current terms for your provider]**: use only public fixtures online and replay from cache during the demo, but test the real inference path at least once.

### 5.11 Wallet graph (T2)
- Signed disclosure: proposer lists wallets they control; each wallet signs a message including `proposalId` (proof of control).
- Seeded history: `deploy_and_seed.py` creates funding transfers proposer -> shell -> recipient.
- Edges: `declared` (signed), `observed` (direct transfer), `shared_funder`, `common_contract`, labelled by evidence strength.
- Queries: path proposer wallets -> recipient within k hops; connected-but-undisclosed wallets.
- Wording: "linkage evidence", never "same person".

---

## 6. Build stages (follow in order)

Times are targets. Every stage ends with an **exit test**; do not move on because the code merely compiles.

### Stage 0 (hour 0-1): Environment
Do section 4. Create the FastAPI health route, a frontend shell, and a script that prints `block_number` from Anvil.
**Exit:** three processes (anvil, backend, frontend) run; backend reads the chain; `forge test` runs.

### Stage 1 (hours 1-3): Contracts and the signing test
1. `MockToken`, `GovernanceRegistry`, `Treasury`, `GuardedExecutor` (section 5.5).
2. **First cross-language test**: Python signs the EIP-712 attestation, a Foundry test (or on-chain call in a script) verifies it with identical domain and types. Also test `actionHash` equality between Python and Solidity.
3. Forge tests: valid payout passes; wrong recipient, wrong amount, wrong `versionHash`, invalid signature, expired deadline, non-VERIFIED verdict, replay (second `execute`) and unapproved proposal each revert; non-governance `approve` reverts; non-proposer `commitVersion` reverts.
**Exit:** all contract tests green, and Python-signed attestations verify on-chain.
**Gate:** if this is not working by hour 3, cut the upgrade scenario and graph first. **Never simplify the attestation.**

### Stage 2 (hours 3-5): Evidence and claims
1. Upload route: store files by sha256, metadata row. PyMuPDF text with page numbers; OCR fallback only when a page has almost no text.
2. LLM provider (online) with schema validation and one retry on invalid JSON; cache layer.
3. Grounding, number cross-check, conflict detector (5.9).
4. Fixtures: a digital proposal PDF ($5M, recipient, assumptions) and a forum post that conflicts (for example $5.8M).
**Exit:** fabricated quote is rejected; the $5M vs $5.8M conflict appears with both quotes; low-confidence items show `UNCERTAIN`.

### Stage 3 (hours 5-7): Manifest, commitment, approval
1. `canon.py` with test vectors; manifest builder from confirmed claims; UI confirmation step; proposer signs.
2. Compute `proposalTextHash`, `evidenceRoot`, `versionHash`, `actionHash`; call `commitVersion`; verify the round trip from chain.
3. Governance step: `approve(pid, versionHash)` from the governance account via a UI button/script.
4. Tamper tests: change one byte of evidence or manifest -> verification fails and names which hash.
**Exit:** versions 1 and 2 are committed (hash chain visible); version 2 is approved; tampering is detected.

### Stage 4 (hours 7-10): Verification pipeline and enforcement
1. `decode.py`, `simulate.py`, `verify.py` (5.6, 5.7), `attest.py`.
2. Scenario A: valid payout -> `VERIFIED` -> attestation -> `execute` succeeds -> recipient balance increases by the exact amount.
3. Scenario B1: submit a substituted payout (attacker recipient and/or larger amount) -> R2 `MISMATCH` with decoded diff -> no attestation -> `execute` reverts on-chain.
4. Negative tests where the correct answer is `MISMATCH` or `UNSUPPORTED` (a simulation bug that yields a false `VERIFIED` is the worst failure).
**Exit:** A executes; B1 is blocked on-chain; both are repeatable from a clean `deploy_and_seed.py`.

### Stage 5 (hours 10-12): Dashboard and scenario runner
Pages:
1. **Proposal**: sources, claims with quote popups and page numbers, conflicts, uncertainty, cached/generated labels.
2. **Manifest and versions**: manifest, hash chain, chain-verified badge, approval status.
3. **Execution**: approved action beside the submitted action, observed effects, the **failed rule**, verdict, attestation, transaction result. This page is the centrepiece.
4. **Audit**: input hashes, model, rule-set version.
Scenario runner (`POST /scenarios/{name}/run`) executes A, B1, C (and B3 when built) deterministically.
**Exit:** the whole flow works through the runner without reading source code.

### Stage 6 (hours 12-14): Upgrade scenario (T1)
1. Deploy UUPS `BoxUUPS` proxy (owner = Treasury), `BoxV2`, `BoxEvil` in `deploy_and_seed.py`.
2. Proposal text describes V2 in jargon; manifest declares `newImpl = BoxEvil` with `declaredSelectors` matching the prose (the community was misled); governance approves.
3. Implement slot diff, code-hash check, baseline-relative scan (5.8).
4. Scenario B3: verifier finds the undeclared `sweep()` selector -> R7 `MISMATCH`, no attestation, `execute` reverts, implementation slot unchanged.
5. Control case: benign V2 upgrade is `VERIFIED` and executes.
**Exit:** B3 blocked through the real executor; the benign upgrade passes.

### Stage 7 (hours 14-15): Hardening and rehearsal
- Failure paths: LLM down, OCR empty, Anvil restarted (re-run `deploy_and_seed.py`), stale DB rows.
- One real (non-cached) LLM run.
- Full rehearsal from a clean start with no manual DB or contract repair.
- README: setup, architecture, supported scope, limitations (single verifier, simulated governance, heuristic scan, watched-state only).
**Exit:** reproducible demo.

### Stage 8 (T2, in priority order, only if the core is stable)
1. **Hybrid/local LLM** (5.10): add Ollama provider through the same interface; pick a 7-8B instruct model that produces valid JSON on your fixtures (roughly 5-8 GB free RAM for a 4-bit model **[verify for your model]**); implement the router and fail-closed rule; run the parity test (online vs local on all fixtures: claims found, grounding pass rate, conflicts detected) and put the table in the README.
2. **Wallet graph** (5.11).
3. **Docker packaging** (section 8).
4. Scanned-PDF fixture; nested `multicall` decoding.

### Cut order if late
Graph polish -> graph -> scanned PDF -> nested multicall -> local LLM tuning -> Docker. Then the upgrade scenario. **Never cut:** Stage 1 tests, Stage 4 scenarios, grounding check, uncertainty labels, full attestation.

---

## 7. Demo script (5 minutes)

1. **Problem (30 s):** voters approve text; the chain executes bytes.
2. **Evidence (90 s):** upload the digital PDF and the conflicting forum post. Show claims with quotes, the $5M vs $5.8M conflict, uncertainty labels, cached vs generated. Optional extras only if built: scanned attachment, wallet graph.
3. **Commit and approve (30 s):** confirm the manifest, sign, commit version 2, approve; show the hash chain; tamper one byte and show the failure.
4. **Scenario A (45 s):** valid payout is simulated, attested and executed.
5. **Scenario B1 (60 s):** substituted recipient/amount: show approved vs submitted side by side, the failed rule, no attestation, on-chain revert.
6. **Scenario B3 (60 s):** obfuscated upgrade: hash matches, but the code exposes an undeclared function; verdict `MISMATCH`; executor reverts; slot unchanged.
7. **Honest limits (15 s):** one executable action per proposal, single verifier, simulated governance, heuristic scan, watched state only.

Make the failed transaction the centrepiece. Judges should see the expected recipient beside the substituted one, the exact rule, and proof that the executor refused.

---

## 8. Docker (packaging, added after the native slice works)

Policy: the inner dev loop stays native. Docker provides reproducibility and delivery, not security or correctness.

**Before coding (done):** Docker installed and verified; `.dockerignore`, `.gitignore`, `.env.example` exist; keys never in Git or images.

**After Stage 5 or 6 (about 30-45 minutes):**
1. Backend Dockerfile (slim Python image, install requirements, no model weights, no secrets). Run it alone against host Anvil and pass the scenarios.
2. Add `anvil` and `frontend` services to `docker-compose.yml` (frontend can stay on the host dev server if short on time). Mount `data/` as a volume for SQLite, uploads and the LLM cache.
3. `RPC_URL`: `http://anvil:8545` inside Compose, `http://127.0.0.1:8545` natively.
4. Ollama stays on the host; the container reaches it via `host.docker.internal` **[verify on your Docker version]**.

**Return-to-Docker checkpoints**

| Trigger | Action |
|---|---|
| Native slice works end to end | create Dockerfile and compose, first smoke test |
| Added a Python dependency | add to requirements; rebuild at the next checkpoint, not every edit |
| Added a system package | rebuild immediately and rerun the affected test |
| Final rehearsal | `docker compose down -v && docker compose up --build`, then run all scenarios |
| After the final build | freeze dependencies |

**Gotchas:** Anvil state is in memory; after a restart re-run `deploy_and_seed.py` and reset DB rows that reference addresses. A container is not automatically offline-capable: weights, packages, assets and API calls all matter. If time is short, ship native run instructions plus a Compose file that passes one smoke test; that beats a half-working container demo.

---

## 9. Testing checklist (definition of done)

Contracts
- [ ] Valid payout passes; wrong recipient, amount, version, signature, deadline, verdict, replay and unapproved proposal all revert.
- [ ] Only governance can approve; only the proposer can commit.
- [ ] Python-signed attestation verifies on-chain; `actionHash` equal in Python and Solidity.

Evidence and manifest
- [ ] Canonicalization vectors pass.
- [ ] Fabricated quote rejected; number cross-check works; conflict detected.
- [ ] One-byte tamper of evidence or manifest is detected and located.
- [ ] A text revision with an identical action invalidates the old approval.

Verification
- [ ] A: `VERIFIED`, executes, exact balance change.
- [ ] B1: `MISMATCH` with decoded diff, no attestation, on-chain revert.
- [ ] Unknown selector -> `UNSUPPORTED`; unobservable effect -> not `VERIFIED`.
- [ ] B3: undeclared selector -> `MISMATCH`, revert, slot unchanged; benign V2 passes.
- [ ] Snapshot revert verified by re-reading state.

Operations
- [ ] LLM down: router falls back or returns `LLM_UNAVAILABLE`; confidential input never reaches online.
- [ ] Anvil restart: `deploy_and_seed.py` restores a working demo.
- [ ] Fresh clone works from README; with the network off, cached scenarios and the chain still run.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| New to Solidity/Foundry/EVM | OpenZeppelin components, minimal custom code, crash lab first, hour-3 gate |
| EIP-712 or canonicalization mismatch blocks everything | cross-language test in Stage 1, before building on top |
| Simulation bug gives a false `VERIFIED` | negative tests; watched-state scope; unobservable -> not `VERIFIED` |
| LLM flakiness or rate limits | schema validation, grounding, cache, explicit `LLM_UNAVAILABLE` |
| Overclaiming security | verdict taxonomy, limits slide, README |
| Venue wifi | local chain, cache, offline run-through |
| Team coordination | freeze the manifest JSON and REST routes after Stage 3 so UI work can proceed in parallel |

---

## 11. API routes and data (reference)

Routes:
```
POST /sources                   upload file or pasted text
POST /analyze/{pid}             run LLM extraction + grounding + conflicts
GET  /claims/{pid}
POST /manifest/{pid}            draft from claims
POST /manifest/{pid}/confirm    human confirm + proposer signature
POST /commit/{pid}              commitVersion on-chain
POST /approve/{pid}             simulated governance approval
POST /verify                    {pid, target, value, data} -> verdict, rules, diff, attestation
POST /execute                   call GuardedExecutor
GET  /audit/{pid}
POST /scenarios/{name}/run      A | B1 | B3 | C
GET  /health
```
SQLite tables: `sources`, `claims`, `conflicts`, `manifests`, `versions`, `verifications`, `analyses` (audit), `llm_cache`.

---

## 12. Command cheat sheet

```bash
anvil                                                       # local chain
forge build && forge test -vv                               # contracts
forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast --private-key $PK0   # [verify flags]
python scripts/deploy_and_seed.py && python scripts/run_scenarios.py
uvicorn app.main:app --reload                               # backend
npm run dev                                                 # frontend
cast sig "approve(address,uint256)"                         # selector
cast storage <proxy> 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc   # EIP-1967 impl slot
docker compose up --build                                   # packaging check
```

Selectors used: `transfer 0xa9059cbb`, `approve 0x095ea7b3`, `upgradeToAndCall 0x4f1ef286`.
