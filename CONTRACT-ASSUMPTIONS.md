# Frontend integration contracts

Updated 2026-10-26, Stage 2. Backend code is read-only. These are observed interfaces and conservative frontend assumptions, not claims of successful live scenario execution.

## Boundary and configuration

Only frontend/src/data/client.ts issues network requests. api.ts owns endpoint paths and operation coordination; adapters.ts maps unknown JSON into safe view models. Components receive Scenario, ActionSummary, Connection, Balances and RunResult objects, never raw backend records. Technical evidence is retrieved separately by run ID for the future closed technical drawer; no current screen renders it.

VITE_API_BASE_URL defaults to http://127.0.0.1:8000. It is public configuration and must not contain credentials, query strings or fragments. HTTP(S) only. Invalid live configuration never blocks demo mode. No wallets, signing keys, provider secrets or private-key forms are included.

## Implemented reads

| Endpoint | Required fields / handling |
|---|---|
| GET /health | status=ok, rpc_connected boolean; connected local chains require chain_id 31337 or 1337. Service and chain availability are separate. Missing/unsupported chain never means ready. Raw ID, URL and block number stay out of view models |
| GET /balances | connected=true, nonzero token address, treasury/recipient/attacker objects with nonzero addresses and nonnegative integer-string token_balance_raw. Ignore floating token_balance. Missing contracts, invalid strings and ambiguous all-zero fallback return unavailable, not invented zeros |
| GET /manifest/{proposal_id} | Enrichment after a successful live run. manifest.action.kind; payout requires amountRaw integer string, recipient address, decimals=6; upgrade requires newImpl address. Unknown shape remains unavailable. No fixture action is substituted into a live result |

The backend catches balance-read errors and can return partial/default values without an error flag. The frontend cannot establish full read correctness from this response. Live balances are labelled reported, not verified. Six-decimal test-token units match the repository's MockToken; unsupported precision yields an unavailable action rather than a guessed value. A stronger backend balance-read status would improve future live guarantees.

## Scenario runner

POST /scenarios/{name}/run accepts A, B1, C or B3. Body is {} (backend RPC defaults). reset_first is declared but ignored in backend routes, so the frontend never relies on it. No automatic POST retry.

- Common: scenario must equal the requested ID; success must be true. Runner success means completion, not permission to send money.
- A: verdict=VERIFIED; verification_report.verdict agrees; all_passed=true; execution_result.status=1; tx_hash has 32-byte hex form. Only then is the view outcome Allowed. This is a report from the trusted local service, not independent browser cryptographic verification.
- B1: verdict=MISMATCH, agreeing report, blocked_as_expected=true, execution_result=null. Stopped before money moved is Yes only if treasury_protected, attacker_zero_gain and recipient_unaffected are all true. Otherwise protection is unknown, even though the verifier rejected the action.
- B3: matching MISMATCH report and blocked_as_expected; no execution result. Slot protection must be explicitly true before asserting the protected change was stopped. Upgrade semantics are separate from payout fields.
- C: reset, not a payment. Nonempty completed steps, valid token/registry/treasury/executor deployment addresses, and seeded_proposal_id are required. Result is Reset; money-stopped is Not applicable. Deployment addresses never enter default copy.
- UNSUPPORTED / UNCERTAIN: Needs review, never Allowed. Unknown verdicts, contradictory reports, mismatched scenario IDs, missing evidence of successful execution and malformed payloads fail closed with a plain error.

Live enrichment fetches the approved plan and balances after the response. Failed optional reads remain unavailable and do not turn a confirmed completed operation into a second submission. Actual submitted payout fields that are absent/insufficient are explicitly unavailable; they are not copied from fixtures. Stage 3 can enrich field comparisons from documented report fields without weakening these gates.

## Concurrency, timeout and reset

Read timeout is 10 seconds; POST timeout 60 seconds. All workspaces share one live-operation coordinator. An uncertain submitted operation blocks further live submissions across tabs, including reset. A sessionStorage marker preserves this uncertainty on reload for the same API address; where storage is blocked, the in-memory lock still applies during the app session. Reads, demo sessions and mode switching remain available. There is no automatic unlock, automatic retry or fabricated live reset.

There is no dedicated /reset endpoint. Explicit live reset uses scenario C when available; demo reset only changes its local fixture session. The API never silently replaces a failed live reset with demo completion. A UI fallback must visibly switch to Demo data and explain which data was reset. The backend exposes no job-status/reconciliation endpoint; safely resolving an uncertain live run requires inspecting its actual record/backend state before a later session. This limitation is not bypassed with a generic retry button.

Backend deploy_and_seed.py and upgrade source/artifact dependencies are missing in this checkout, so live A re-seeding, C and B3 execution remain unverified external dependencies. Stage 2 browser checks issue health/balance reads only; no live scenario or reset was run.

## Fixture service and workspace state

Every workspace owns an independent fixture service. Initial balances are 1,000,000 test USDC in the fund and zero in recipient/bad actor; raw amounts use six decimals and BigInt formatting. A transfers exactly the fund amount. B1 and B3 move nothing. C records the current fixture balances before restoring the starting state. Fixture replay of a payment/upgrade starts from the documented initial snapshot and returns startedFromCleanState so Stage 3 can explain the restart rather than disguise continuity. Results are deep copied; one tab cannot alter another's record.

?mode=demo or ?mode=live selects the initial workspace source; the current workspace source is reflected back into the URL. New workspaces start with demo data. URL mode changes do not rewind workspace history. Session tabs are intentionally in memory; theme and reduced-motion preference persist separately. In-progress workspaces cannot close, change source, reset or reselect a scenario. Closing the final idle workspace creates a new empty demo workspace.

Stage 3 exposes the run/reset lifecycle. A provider holds running operations across routes and tabs, prevents duplicate submissions synchronously, and stores completion on the original workspace. Demo steps illustrate the fixture; live progress is indeterminate. Later live completions mark other live records historical. Technical evidence is rendered through a strict allowlist of validated hashes/addresses and known scalar values, never arbitrary nested response text. Remaining pages are Stage 4.
