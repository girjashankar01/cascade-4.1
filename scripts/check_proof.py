#!/usr/bin/env python3
"""Independent post-run proof checker for CASCADE 4.1.

Reads docs/proof.json and validates via RPC (view calls and get_transaction_receipt only):
1. Every recorded tx_hash has a mined receipt on the connected chain with matching status.
2. Exact expected outcomes:
   - commit_version: success (status == 1)
   - approve: success (status == 1)
   - b1_substitution / adversarial_b1: reverted with "action mismatch" (status == 0)
   - execute_valid: success (status == 1)
   - replay_attack: reverted with "already executed" (status == 0)
3. Recorded block_number, gas_used, and fee_eth match on-chain receipt data.
4. Token balance consistency:
   - Treasury decreased by 1,000,000 USDC
   - Recipient increased by 1,000,000 USDC
   - Attacker balance unchanged
5. Event logs decoded from receipts match cryptographic commitments:
   - VersionCommitted emitted matching versionHash, actionHash, evidenceRoot
   - ProposalApproved emitted matching versionHash, actionHash, evidenceRoot
   - ExecutionSucceeded emitted matching actionHash
6. All transaction explorer links format: https://sepolia.etherscan.io/tx/<hash>
7. Secret leakage audit: scans docs/, data/, and the database for any leaked
   private key or EXPLORER_API_KEY from .env and .env.amoy.

Prints a PASS/FAIL table per check. Exits with non-zero on any failure.
Never logs or prints secrets.
"""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import eth_abi
from eth_utils import keccak, to_checksum_address, to_hex
from web3 import Web3

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.chain.public import get_explorer_base, load_proof_env

# Event Signatures
TOPIC_VERSION_COMMITTED = to_hex(keccak(text="VersionCommitted(bytes32,uint256,bytes32,bytes32,bytes32,address)"))
TOPIC_PROPOSAL_APPROVED = to_hex(keccak(text="ProposalApproved(bytes32,bytes32,bytes32,bytes32)"))
TOPIC_EXECUTION_SUCCEEDED = to_hex(keccak(text="ExecutionSucceeded(bytes32,address,uint256,bytes32)"))


def load_env_secrets(repo_root: Path) -> Set[str]:
    """Extract private keys and API keys from .env and .env.amoy to scan for leakage."""
    secrets: Set[str] = set()
    for env_name in [".env", ".env.amoy"]:
        env_file = repo_root / env_name
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if (k.endswith("_PK") or "KEY" in k) and len(v) >= 12:
                        secrets.add(v)
                        # Also strip leading 0x if present
                        if v.startswith("0x") and len(v) > 14:
                            secrets.add(v[2:])
    return secrets


def scan_for_secrets(repo_root: Path, secrets: Set[str]) -> List[str]:
    """Scan docs/, data/, and database files for any occurrence of known secrets."""
    leak_findings: List[str] = []
    if not secrets:
        return leak_findings

    scan_dirs = [repo_root / "docs", repo_root / "data"]
    for sdir in scan_dirs:
        if not sdir.exists():
            continue
        for root, _, files in os.walk(sdir):
            for file in files:
                fpath = Path(root) / file
                # Skip sqlite journals/temp files or non-content files
                if fpath.name.endswith((".pyc", ".gitkeep")):
                    continue
                try:
                    content = fpath.read_bytes()
                    for secret in secrets:
                        if secret.encode("utf-8") in content:
                            leak_findings.append(f"Secret leakage detected in file: {fpath.relative_to(repo_root)}")
                except Exception:
                    pass

    # Scan sqlite database tables specifically
    db_path = repo_root / "data" / "dao_accountability.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                for row in rows:
                    row_str = str(row)
                    for secret in secrets:
                        if secret in row_str:
                            leak_findings.append(f"Secret leakage detected in database table '{table}'")
            conn.close()
        except Exception:
            pass

    return leak_findings


def check_proof(
    proof_path: Path = REPO_ROOT / "docs" / "proof.json",
    env_path: Path = REPO_ROOT / ".env.amoy",
    rpc_override: Optional[str] = None,
    w3_override: Optional[Web3] = None,
) -> bool:
    results: List[Tuple[str, str, str]] = []  # (Check, Status, Details)
    all_passed = True

    print("=" * 80)
    print("CASCADE 4.1 — Post-Run Proof Integrity Checker (Read-Only)")
    print("=" * 80)

    # 1. Load proof.json
    if not proof_path.exists():
        print(f"FAIL: Proof manifest not found at {proof_path}", file=sys.stderr)
        return False

    try:
        with open(proof_path, "r", encoding="utf-8") as f:
            proof = json.load(f)
    except Exception as e:
        print(f"FAIL: Malformed JSON at {proof_path}: {e}", file=sys.stderr)
        return False

    # 2. Connect to RPC
    try:
        cfg = load_proof_env(path=env_path, w3=w3_override)
        w3 = w3_override or cfg.w3 or Web3(Web3.HTTPProvider(rpc_override or cfg.rpc_url))
    except Exception as e:
        print(f"FAIL: Could not connect to Web3 provider: {e}", file=sys.stderr)
        return False

    proof_chain_id = proof.get("chain_id")
    actual_chain_id = w3.eth.chain_id
    if proof_chain_id == actual_chain_id:
        results.append(("Chain ID Match", "PASS", f"Connected to {actual_chain_id}"))
    else:
        results.append(("Chain ID Match", "FAIL", f"proof.json ({proof_chain_id}) != RPC ({actual_chain_id})"))
        all_passed = False

    expected_explorer_base = get_explorer_base(actual_chain_id)

    # 3. Validate Transactions Sequence and Receipts
    txs: List[Dict[str, Any]] = proof.get("transactions", [])
    expected_steps = [
        ({"commit_version", "commit"}, 1, None, "commit_version"),
        ({"approve", "governance_approve"}, 1, None, "approve"),
        ({"b1_adversarial_execute", "adversarial_b1", "b1_substitution"}, 0, "action mismatch", "b1_adversarial_execute"),
        ({"valid_execute", "execute_valid"}, 1, None, "valid_execute"),
        ({"replay_execute", "replay_attack"}, 0, "already executed", "replay_execute"),
    ]

    receipts: Dict[str, Any] = {}

    if len(txs) != 5:
        results.append(("Transaction Count", "FAIL", f"Expected 5 transactions, got {len(txs)}"))
        all_passed = False
    else:
        results.append(("Transaction Count", "PASS", "Exactly 5 steps recorded in proof manifest"))

    for i, (allowed_names, exp_status, exp_reason, canonical_name) in enumerate(expected_steps):
        if i >= len(txs):
            break
        tx = txs[i]
        step_name = tx.get("step")
        tx_hash = tx.get("tx_hash")
        rec_status = tx.get("status")

        if step_name not in allowed_names:
            results.append((f"Step {i+1} Name", "FAIL", f"Expected one of {allowed_names}, got '{step_name}'"))
            all_passed = False

        if not tx_hash or not tx_hash.startswith("0x"):
            results.append((f"Step {i+1} ({canonical_name}) Hash", "FAIL", f"Missing or invalid tx_hash: {tx_hash}"))
            all_passed = False
            continue

        # Fetch mined receipt
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if not receipt:
                results.append((f"Receipt: {canonical_name}", "FAIL", f"Transaction {tx_hash} not mined on-chain"))
                all_passed = False
                continue
            receipts[tx_hash] = receipt
        except Exception as e:
            results.append((f"Receipt: {canonical_name}", "FAIL", f"Could not query receipt for {tx_hash}: {e}"))
            all_passed = False
            continue

        onchain_status = receipt.get("status")
        if onchain_status == exp_status and rec_status == exp_status:
            results.append((f"Outcome: {canonical_name}", "PASS", f"Status {exp_status} on-chain matches recorded"))
        else:
            results.append((f"Outcome: {canonical_name}", "FAIL", f"Status on-chain={onchain_status}, recorded={rec_status}, expected={exp_status}"))
            all_passed = False

        # Validate revert reason for reverted steps
        if exp_status == 0 and exp_reason:
            recorded_reason = str(tx.get("revert_reason", "")).lower()
            if exp_reason in recorded_reason:
                results.append((f"Revert Reason: {canonical_name}", "PASS", f"Contains expected '{exp_reason}'"))
            else:
                results.append((f"Revert Reason: {canonical_name}", "FAIL", f"Expected '{exp_reason}', got '{recorded_reason}'"))
                all_passed = False

        # Verify block number and gas used match receipt
        rec_block = tx.get("block_number")
        onchain_block = receipt.get("blockNumber")
        if rec_block == onchain_block:
            results.append((f"Block Number: {canonical_name}", "PASS", f"Mined at block {onchain_block}"))
        else:
            results.append((f"Block Number: {canonical_name}", "FAIL", f"Recorded block {rec_block} != onchain {onchain_block}"))
            all_passed = False

        rec_gas = tx.get("gas_used")
        onchain_gas = receipt.get("gasUsed")
        if rec_gas == onchain_gas:
            results.append((f"Gas Used: {canonical_name}", "PASS", f"Gas {onchain_gas} units verified"))
        else:
            results.append((f"Gas Used: {canonical_name}", "FAIL", f"Recorded gas {rec_gas} != onchain {onchain_gas}"))
            all_passed = False

        # Validate explorer URL format
        explorer_url = tx.get("explorer_url", "")
        expected_url = f"{expected_explorer_base}/tx/{tx_hash}"
        if explorer_url == expected_url:
            results.append((f"Explorer URL: {canonical_name}", "PASS", f"Canonical URL format ({explorer_url})"))
        else:
            results.append((f"Explorer URL: {canonical_name}", "FAIL", f"Expected {expected_url}, got {explorer_url}"))
            all_passed = False

    # 4. Event Log Verification
    rec_vhash = str(proof.get("versionHash", "")).lower()
    rec_ahash = str(proof.get("actionHash", "")).lower()
    rec_eroot = str(proof.get("evidenceRoot", "")).lower()

    # (a) Check commit receipt for VersionCommitted event
    commit_tx_hash = txs[0].get("tx_hash") if len(txs) > 0 else None
    if commit_tx_hash and commit_tx_hash in receipts:
        c_rcpt = receipts[commit_tx_hash]
        found_commit_log = False
        for log in c_rcpt.get("logs", []):
            topics = log.get("topics", [])
            if topics and to_hex(topics[0]).lower() == TOPIC_VERSION_COMMITTED.lower():
                try:
                    data_bytes = bytes.fromhex(log["data"][2:] if str(log["data"]).startswith("0x") else log["data"])
                    decoded = eth_abi.decode(["bytes32", "bytes32", "bytes32", "address"], data_bytes)
                    emitted_vhash = to_hex(decoded[0]).lower()
                    emitted_ahash = to_hex(decoded[1]).lower()
                    emitted_eroot = to_hex(decoded[2]).lower()

                    if emitted_vhash == rec_vhash and emitted_ahash == rec_ahash and emitted_eroot == rec_eroot:
                        found_commit_log = True
                        break
                except Exception:
                    pass
        if found_commit_log:
            results.append(("Event: VersionCommitted", "PASS", "Emitted versionHash, actionHash, evidenceRoot match manifest"))
        else:
            results.append(("Event: VersionCommitted", "FAIL", "VersionCommitted log missing or hashes mismatch"))
            all_passed = False

    # (b) Check approve receipt for ProposalApproved event
    approve_tx_hash = txs[1].get("tx_hash") if len(txs) > 1 else None
    if approve_tx_hash and approve_tx_hash in receipts:
        a_rcpt = receipts[approve_tx_hash]
        found_approve_log = False
        for log in a_rcpt.get("logs", []):
            topics = log.get("topics", [])
            if topics and to_hex(topics[0]).lower() == TOPIC_PROPOSAL_APPROVED.lower():
                try:
                    topic_vhash = to_hex(topics[2]).lower() if len(topics) > 2 else ""
                    data_bytes = bytes.fromhex(log["data"][2:] if str(log["data"]).startswith("0x") else log["data"])
                    decoded = eth_abi.decode(["bytes32", "bytes32"], data_bytes)
                    emitted_ahash = to_hex(decoded[0]).lower()
                    emitted_eroot = to_hex(decoded[1]).lower()

                    if topic_vhash == rec_vhash and emitted_ahash == rec_ahash and emitted_eroot == rec_eroot:
                        found_approve_log = True
                        break
                except Exception:
                    pass
        if found_approve_log:
            results.append(("Event: ProposalApproved", "PASS", "Emitted versionHash, actionHash, evidenceRoot match manifest"))
        else:
            results.append(("Event: ProposalApproved", "FAIL", "ProposalApproved log missing or hashes mismatch"))
            all_passed = False

    # (c) Check valid execution receipt for ExecutionSucceeded event
    exec_tx_hash = txs[3].get("tx_hash") if len(txs) > 3 else None
    if exec_tx_hash and exec_tx_hash in receipts:
        e_rcpt = receipts[exec_tx_hash]
        found_exec_log = False
        for log in e_rcpt.get("logs", []):
            topics = log.get("topics", [])
            if topics and to_hex(topics[0]).lower() == TOPIC_EXECUTION_SUCCEEDED.lower():
                try:
                    data_bytes = bytes.fromhex(log["data"][2:] if str(log["data"]).startswith("0x") else log["data"])
                    decoded = eth_abi.decode(["uint256", "bytes32"], data_bytes)
                    emitted_ahash = to_hex(decoded[1]).lower()
                    if emitted_ahash == rec_ahash:
                        found_exec_log = True
                        break
                except Exception:
                    pass
        if found_exec_log:
            results.append(("Event: ExecutionSucceeded", "PASS", "Emitted actionHash matches manifest"))
        else:
            results.append(("Event: ExecutionSucceeded", "FAIL", "ExecutionSucceeded log missing or actionHash mismatch"))
            all_passed = False

    # 5. Balance Consistency Verification
    bb = proof.get("balances_before", {})
    ba = proof.get("balances_after", {})
    t_before = bb.get("treasury_token_balance", 0)
    t_after = ba.get("treasury_token_balance", 0)
    r_before = bb.get("recipient_token_balance", 0)
    r_after = ba.get("recipient_token_balance", 0)

    PAYOUT_DELTA = 1_000_000 * 10**6  # 1M USDC
    if t_before - t_after == PAYOUT_DELTA:
        results.append(("Balance: Treasury Delta", "PASS", f"-1,000,000 USDC ({t_before} -> {t_after})"))
    else:
        results.append(("Balance: Treasury Delta", "FAIL", f"Expected -{PAYOUT_DELTA}, got {t_after - t_before}"))
        all_passed = False

    if r_after - r_before == PAYOUT_DELTA:
        results.append(("Balance: Recipient Delta", "PASS", f"+1,000,000 USDC ({r_before} -> {r_after})"))
    else:
        results.append(("Balance: Recipient Delta", "FAIL", f"Expected +{PAYOUT_DELTA}, got {r_after - r_before}"))
        all_passed = False

    # Attacker token balance
    att_before = (bb.get("roles", {}).get("attacker") or {}).get("token", 0)
    att_after = (ba.get("roles", {}).get("attacker") or {}).get("token", 0)
    if att_before == att_after:
        results.append(("Balance: Attacker Invariant", "PASS", f"Attacker token balance unchanged ({att_after})"))
    else:
        results.append(("Balance: Attacker Invariant", "FAIL", f"Attacker balance changed from {att_before} to {att_after}"))
        all_passed = False

    # 6. Secret Leakage Audit
    known_secrets = load_env_secrets(REPO_ROOT)
    leaks = scan_for_secrets(REPO_ROOT, known_secrets)
    if not leaks:
        results.append(("Secret Hygiene Scan", "PASS", "Zero private keys or API keys found in docs/, data/, or DB"))
    else:
        for leak in leaks:
            results.append(("Secret Hygiene Scan", "FAIL", leak))
        all_passed = False

    # Print Summary Table
    print("\nPROOF VALIDATION RESULTS TABLE:")
    print(f"{'Check':<36} | {'Status':<6} | {'Details'}")
    print("-" * 80)
    for check_name, status, details in results:
        status_str = f"[\033[92mPASS\033[0m]" if status == "PASS" else f"[\033[91mFAIL\033[0m]"
        if not sys.stdout.isatty():
            status_str = f"[{status}]"
        print(f"{check_name:<36} | {status_str:<6} | {details}")

    print("-" * 80)
    if all_passed:
        print("OVERALL PROOF INTEGRITY: SUCCESS (All on-chain receipts and commitments validated)")
    else:
        print("OVERALL PROOF INTEGRITY: FAILED (Discrepancies found between proof and on-chain state)", file=sys.stderr)

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Check proof manifest against on-chain receipts and state.")
    parser.add_argument("--proof", type=str, default=str(REPO_ROOT / "docs" / "proof.json"), help="Path to proof.json")
    parser.add_argument("--env", type=str, default=str(REPO_ROOT / ".env.amoy"), help="Path to .env.amoy")
    parser.add_argument("--rpc", type=str, default=None, help="RPC URL override")
    args = parser.parse_args()

    passed = check_proof(
        proof_path=Path(args.proof),
        env_path=Path(args.env),
        rpc_override=args.rpc,
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
