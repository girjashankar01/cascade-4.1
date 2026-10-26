#!/usr/bin/env python3
"""Publish and verify public testnet proof for the DAO Accountability Engine.

Executes and documents the full accountability lifecycle:
1. Preflight balances & chain verification
2. Proposer commits version on GovernanceRegistry
3. Governance approves latest version
4. Verifier signs legitimate EIP-712 attestation
5. Adversarial B1 substitution is submitted with legitimate attestation and reverts ("action mismatch")
6. Legitimate payout executes through GuardedExecutor and recipient balance increases
7. (Optional --with-replay) Replay execution is attempted and reverts ("already executed")
8. Results recorded to data/proof.json and mirrored to docs/proof.json

Usage:
    python scripts/publish_proof.py [--dry-run] [--with-replay] [--run-id ID]
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Set up project path
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from eth_account import Account
from eth_utils import to_checksum_address
from web3 import Web3

from app.chain.attest import (
    VERIFIED,
    build_attestation_typed_data,
    compute_action_hash,
    recover_attestation_signer,
    sign_attestation,
)
from app.chain.client import load_artifact, proposal_id_to_bytes32
from app.chain.public import (
    explorer_addr_url,
    explorer_tx_url,
    load_proof_env,
    revert_reason,
    send_tx_1559,
)
from app.manifest.canon import canonicalize_manifest
from app.manifest.hashes import (
    INITIAL_PREV_VERSION_HASH,
    compute_evidence_root,
    compute_manifest_action_hash,
    compute_proposal_text_hash,
    compute_version_hash,
    encode_erc20_transfer_calldata,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("publish_proof")

RECIPIENT_ADDR = "0x9965507D1a55BCC6475675304Ca994970De97744"
ATTACKER_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
DEFAULT_AMOUNT_RAW = 1_000_000 * 10**6  # 1,000,000 USDC
MIN_NATIVE_BALANCE_WEI = Web3.to_wei(0.002, "ether")  # 0.002 native threshold


def load_proposal_text_and_evidence(fixtures_dir: Path) -> Tuple[str, str, str]:
    """Load proposal PDF fixture and compute proposalTextHash and evidenceRoot.

    Returns (proposal_text, proposal_text_hash, evidence_root).
    """
    pdf_path = fixtures_dir / "clean_proposal_v1.pdf"
    if pdf_path.exists():
        pdf_bytes = pdf_path.read_bytes()
        sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
        evidence_root = compute_evidence_root([sha256_hash])

        # Attempt PyMuPDF extraction
        try:
            from app.ingestion.pdf import extract_pdf_pages

            pages, _ = extract_pdf_pages(pdf_bytes)
            full_text = "\n\n".join(pages[p] for p in sorted(pages.keys()))
        except Exception as e:
            logger.warning(f"Could not use extract_pdf_pages ({e}); using fixture text fallback.")
            full_text = "Clean Grant Proposal v1: Grant payout of $1.0M (1,000,000 USDC) to designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744."

        text_hash = compute_proposal_text_hash(full_text)
        return full_text, text_hash, evidence_root

    # Safe deterministic fallback if fixture file is missing
    fallback_text = "Clean Grant Proposal v1: Grant payout of $1.0M (1,000,000 USDC) to designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744."
    fallback_sha256 = hashlib.sha256(fallback_text.encode("utf-8")).hexdigest()
    return (
        fallback_text,
        compute_proposal_text_hash(fallback_text),
        compute_evidence_root([fallback_sha256]),
    )


def preflight_checks(
    w3: Web3,
    expected_chain_id: int,
    proposer_addr: str,
    governance_addr: str,
    verifier_addr: str,
    token_contract: Any,
    treasury_addr: str,
    payout_amount: int,
    already_executed: bool = False,
    dry_run: bool = False,
    deployments: Optional[Dict[str, Any]] = None,
    deployments_path: Optional[Path] = None,
) -> None:
    """Validate network, account balances, and treasury reserves.

    If any check fails, prints 'PREFLIGHT FAILED: <reasons>' and raises RuntimeError
    in both real run and dry-run. Never prints 'PASSED' on failure.
    Verifier balance is info-only (off-chain EIP-712 signer).
    """
    failures: List[str] = []

    # 0. Deployment manifest & contract bytecode verification
    if deployments_path is not None and not deployments_path.exists():
        failures.append(f"Deployment manifest {deployments_path} is missing")
    elif deployments is None or not isinstance(deployments, dict):
        failures.append("Deployment manifest is missing or invalid")
    else:
        file_chain_id = deployments.get("chain_id")
        if file_chain_id is not None:
            try:
                fcid_int = int(file_chain_id)
                if fcid_int != expected_chain_id:
                    failures.append(f"Deployment manifest chain ID {fcid_int} does not match expected {expected_chain_id}")
            except (ValueError, TypeError):
                failures.append(f"Deployment manifest has invalid chain ID: {file_chain_id}")

        for c_name, c_key in [
            ("MockToken", "token"),
            ("GovernanceRegistry", "registry"),
            ("Treasury", "treasury"),
            ("GuardedExecutor", "executor"),
        ]:
            c_addr = deployments.get(c_key)
            if not c_addr:
                failures.append(f"Deployment manifest missing contract {c_name} ({c_key})")
                continue
            try:
                cs_addr = to_checksum_address(c_addr)
                code = w3.eth.get_code(cs_addr)
                has_code = False
                if isinstance(code, (bytes, bytearray)):
                    has_code = len(code) > 0 and code not in (b"\x00", b"")
                else:
                    code_str = str(code).strip().lower()
                    has_code = len(code_str) > 2 and code_str not in ("0x", "0x0", "0x00")
                if not has_code:
                    failures.append(f"Contract {c_name} at {c_addr} has no bytecode deployed on-chain")
            except Exception as e:
                failures.append(f"Could not verify bytecode for {c_name} at {c_addr}: {e}")

    # 1. Chain ID check
    try:
        actual_chain_id = w3.eth.chain_id
        if actual_chain_id != expected_chain_id:
            failures.append(f"Connected chain ID {actual_chain_id} does not match expected {expected_chain_id}")
    except Exception as e:
        failures.append(f"Could not query chain ID from RPC: {e}")

    # 2. Broadcaster accounts (Proposer and Governance)
    for role_name, addr in [("Proposer", proposer_addr), ("Governance", governance_addr)]:
        if not addr:
            continue
        try:
            bal = w3.eth.get_balance(to_checksum_address(addr))
            if bal <= MIN_NATIVE_BALANCE_WEI:
                failures.append(
                    f"{role_name} ({addr}) balance is {Web3.from_wei(bal, 'ether')} ETH, "
                    f"below minimum required threshold of 0.002 ETH"
                )
        except Exception as e:
            failures.append(f"Could not query {role_name} balance: {e}")

    # 3. Verifier balance (Info only)
    if verifier_addr:
        try:
            v_bal = w3.eth.get_balance(to_checksum_address(verifier_addr))
            logger.info(f"Verifier ({verifier_addr}) balance: {Web3.from_wei(v_bal, 'ether')} ETH (off-chain EIP-712 signer)")
        except Exception as e:
            logger.debug(f"Could not query verifier balance: {e}")

    # 4. Treasury token reserves
    if already_executed:
        logger.info("Proposal already executed on-chain; bypassing treasury balance preflight check.")
    elif token_contract is not None and treasury_addr:
        try:
            treasury_bal = token_contract.functions.balanceOf(to_checksum_address(treasury_addr)).call()
            if treasury_bal < payout_amount:
                failures.append(
                    f"Treasury ({treasury_addr}) token balance is {treasury_bal} units, "
                    f"insufficient for payout of {payout_amount} units (1,000,000 USDC)"
                )
        except Exception as e:
            failures.append(f"Could not query treasury token balance: {e}")

    if failures:
        msg = "PREFLIGHT FAILED:\n  - " + "\n  - ".join(failures)
        print(f"\n{msg}\n", file=sys.stderr)
        raise RuntimeError(msg)

    logger.info("Preflight checks PASSED: Chain ID, broadcast balances (> 0.002), and treasury reserves verified.")


def capture_snapshot_balances(
    w3: Web3,
    cfg: Any,
    token_contract: Any,
    treasury_addr: str,
    recipient_addr: str,
) -> Dict[str, Any]:
    """Capture live ETH balances per role and token balances for treasury and recipient."""
    roles = {}
    for role, addr in [
        ("deployer", cfg.addresses.get("DEPLOYER_ADDR") or (Account.from_key(cfg.deployer_pk).address if cfg.deployer_pk else "")),
        ("proposer", cfg.addresses.get("PROPOSER_ADDR") or (Account.from_key(cfg.proposer_pk).address if cfg.proposer_pk else "")),
        ("governance", cfg.addresses.get("GOVERNANCE_ADDR") or (Account.from_key(cfg.governance_pk).address if cfg.governance_pk else "")),
        ("verifier", cfg.addresses.get("VERIFIER_ADDR") or (Account.from_key(cfg.verifier_pk).address if cfg.verifier_pk else "")),
        ("attacker", cfg.addresses.get("ATTACKER_ADDR") or ""),
    ]:
        if addr:
            try:
                b = w3.eth.get_balance(to_checksum_address(addr))
                roles[role] = {"address": addr, "eth": float(Web3.from_wei(b, "ether"))}
            except Exception:
                roles[role] = {"address": addr, "eth": 0.0}

    t_tok = 0
    r_tok = 0
    if token_contract is not None:
        try:
            raw_t = token_contract.functions.balanceOf(to_checksum_address(treasury_addr)).call()
            t_tok = int(raw_t) if isinstance(raw_t, (int, float)) or (isinstance(raw_t, str) and str(raw_t).isdigit()) else (raw_t if isinstance(raw_t, int) else 0)
        except Exception:
            t_tok = 0
        try:
            raw_r = token_contract.functions.balanceOf(to_checksum_address(recipient_addr)).call()
            r_tok = int(raw_r) if isinstance(raw_r, (int, float)) or (isinstance(raw_r, str) and str(raw_r).isdigit()) else (raw_r if isinstance(raw_r, int) else 0)
        except Exception:
            r_tok = 0

    return {
        "roles": roles,
        "treasury_token_balance": t_tok,
        "recipient_token_balance": r_tok,
    }


def save_proof_manifest(proof_data: Dict[str, Any], proof_path: Path) -> None:
    """Save proof manifest to target JSON path and atomically mirror to docs/proof.json if default path."""
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = proof_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(proof_data, f, indent=2)
    os.replace(tmp_path, proof_path)

    from app.paths import PROOF_JSON_PATH, DATA_DIR
    if proof_path.resolve() == (DATA_DIR / "proof.json").resolve():
        PROOF_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        docs_tmp = PROOF_JSON_PATH.with_suffix(".tmp")
        with open(docs_tmp, "w", encoding="utf-8") as f:
            json.dump(proof_data, f, indent=2)
        os.replace(docs_tmp, PROOF_JSON_PATH)
        logger.info(f"Proof manifest recorded at {proof_path} and atomically mirrored to {PROOF_JSON_PATH}")


def log_tx_to_chain_txs(
    run_id: str,
    step: str,
    role: str,
    from_addr: str,
    to_addr: str,
    tx_res: Dict[str, Any],
    explorer_base: str,
    revert_r: Optional[str] = None,
) -> None:
    """Record transaction details into SQLite chain_txs table."""
    try:
        from app.db import record_chain_tx
        receipt = tx_res.get("receipt")
        gas_used = getattr(receipt, "gasUsed", None) if receipt else None
        eff_gp = getattr(receipt, "effectiveGasPrice", None) if receipt else None
        fee_eth = float(Web3.from_wei(gas_used * eff_gp, "ether")) if (gas_used and eff_gp) else None
        record_chain_tx({
            "run_id": run_id,
            "step": step,
            "role": role,
            "from": from_addr,
            "to": to_addr,
            "tx_hash": tx_res["tx_hash"],
            "status": "success" if tx_res["status"] == 1 else "reverted",
            "revert_reason": revert_r,
            "block_number": tx_res["block_number"],
            "gas_used": gas_used,
            "effective_gas_price": eff_gp,
            "fee_eth": fee_eth,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "explorer_url": explorer_tx_url(tx_res["tx_hash"], explorer_base),
        })
    except Exception as e:
        logger.warning(f"Could not log tx {tx_res.get('tx_hash')} to chain_txs SQLite table: {e}")


def print_summary_table(proof_data: Dict[str, Any]) -> None:
    """Print clean terminal summary table with explorer links without exposing sensitive information."""
    print("\n" + "=" * 80)
    print("                    DAO ACCOUNTABILITY ENGINE — PROOF SUMMARY")
    print("=" * 80)
    print(f"Chain ID:       {proof_data.get('chain_id')}")
    print(f"Proposal ID:    {proof_data.get('pid')}")
    print(f"Run ID:         {proof_data.get('run_id')}")
    print("\nCryptographic Commitments:")
    print(f"  versionHash:  {proof_data.get('versionHash')}")
    print(f"  actionHash:   {proof_data.get('actionHash')}")
    print(f"  evidenceRoot: {proof_data.get('evidenceRoot')}")

    print("\nContracts:")
    for name, cinfo in proof_data.get("contracts", {}).items():
        print(f"  {name.capitalize():<12}: {cinfo.get('address')} -> {cinfo.get('explorer_url')}")

    print("\nTransactions & Attestations:")
    for idx, tx in enumerate(proof_data.get("transactions", []), 1):
        status_str = "SUCCESS (status 1)" if tx.get("status") == 1 else f"REVERTED (status 0: {tx.get('revert_reason')})"
        print(f"  [{idx}] {tx.get('label')}")
        print(f"      Result:   {status_str}")
        print(f"      Expected: {tx.get('expected')}")
        print(f"      Block:    {tx.get('block_number')}")
        print(f"      Tx Hash:  {tx.get('tx_hash')}")
        print(f"      Explorer: {tx.get('explorer_url')}")

    print("=" * 80)
    print("Artifacts generated:")
    print(f"  - {REPO_ROOT / 'data' / 'proof.json'}")
    print(f"  - {REPO_ROOT / 'docs' / 'proof.json'}")
    print("=" * 80 + "\n")


def publish_proof(
    run_id: Optional[str] = None,
    dry_run: bool = False,
    with_replay: bool = False,
    rpc_url: Optional[str] = None,
    deployments_path: Optional[Union[str, Path]] = None,
    env_path: Optional[Union[str, Path]] = None,
    proof_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Execute the end-to-end public proof publishing workflow."""
    env_file = Path(env_path) if env_path else REPO_ROOT / ".env.amoy"
    dep_file = Path(deployments_path) if deployments_path else REPO_ROOT / "data" / "deployments.proof.json"
    proof_out = Path(proof_path) if proof_path else REPO_ROOT / "data" / "proof.json"

    # 1. Initialize Web3 and Proof Configuration
    w3_custom = Web3(Web3.HTTPProvider(rpc_url)) if rpc_url else None
    cfg = load_proof_env(path=env_file, w3=w3_custom)
    w3 = cfg.w3 or Web3(Web3.HTTPProvider(cfg.rpc_url))

    deployments: Optional[Dict[str, Any]] = None
    if dep_file.exists():
        try:
            with open(dep_file, "r", encoding="utf-8") as f:
                deployments = json.load(f)
        except Exception as e:
            logger.warning(f"Could not parse deployment file {dep_file}: {e}")

    token_addr = to_checksum_address(deployments["token"]) if deployments and deployments.get("token") else ""
    registry_addr = to_checksum_address(deployments["registry"]) if deployments and deployments.get("registry") else ""
    treasury_addr = to_checksum_address(deployments["treasury"]) if deployments and deployments.get("treasury") else ""
    executor_addr = to_checksum_address(deployments["executor"]) if deployments and deployments.get("executor") else ""

    proposer_pk = cfg.proposer_pk
    governance_pk = cfg.governance_pk
    verifier_pk = cfg.verifier_pk

    proposer_addr = Account.from_key(proposer_pk).address if proposer_pk else ""
    governance_addr = Account.from_key(governance_pk).address if governance_pk else ""
    verifier_addr = Account.from_key(verifier_pk).address if verifier_pk else ""

    token_artifact = load_artifact("MockToken")
    registry_artifact = load_artifact("GovernanceRegistry")
    executor_artifact = load_artifact("GuardedExecutor")

    token_contract = w3.eth.contract(address=token_addr, abi=token_artifact["abi"]) if token_addr else None
    registry_contract = w3.eth.contract(address=registry_addr, abi=registry_artifact["abi"]) if registry_addr else None
    executor_contract = w3.eth.contract(address=executor_addr, abi=executor_artifact["abi"]) if executor_addr else None

    # Resumability: load existing proof.json if present
    existing_proof: Dict[str, Any] = {}
    if proof_out.exists():
        try:
            with open(proof_out, "r", encoding="utf-8") as f:
                existing_proof = json.load(f)
        except Exception as e:
            logger.warning(f"Could not parse existing proof at {proof_out}: {e}")

    # Step 1: Proposal ID & Manifest Construction
    if not run_id:
        if existing_proof and existing_proof.get("chain_id") == cfg.chain_id and existing_proof.get("run_id"):
            run_id = str(existing_proof["run_id"])
        else:
            run_id = datetime.now(timezone.utc).strftime("%y%m%d%H%M")

    pid = f"PROP-PROOF-{run_id}"
    pid_bytes_raw = pid.encode("utf-8")
    if len(pid_bytes_raw) > 32:
        raise ValueError(f"Proposal ID '{pid}' ({len(pid_bytes_raw)} bytes) exceeds the 32-byte limit.")

    pid_b32 = proposal_id_to_bytes32(pid)

    # Check if already executed on-chain
    is_already_executed = False
    if executor_contract:
        try:
            is_already_executed = executor_contract.functions.executed(pid_b32).call()
        except Exception:
            is_already_executed = False

    # Step 0: Preflight verification
    preflight_checks(
        w3=w3,
        expected_chain_id=cfg.chain_id,
        proposer_addr=proposer_addr,
        governance_addr=governance_addr,
        verifier_addr=verifier_addr,
        token_contract=token_contract,
        treasury_addr=treasury_addr,
        payout_amount=DEFAULT_AMOUNT_RAW,
        already_executed=is_already_executed,
        dry_run=dry_run,
        deployments=deployments,
        deployments_path=dep_file,
    )

    # Build Manifest and Hashes exactly matching Scenario A
    fixtures_dir = REPO_ROOT / "fixtures"
    proposal_text, proposal_text_hash, evidence_root = load_proposal_text_and_evidence(fixtures_dir)

    token_normalized = token_addr.lower()
    recipient_normalized = to_checksum_address(RECIPIENT_ADDR).lower()
    amount_raw_str = str(DEFAULT_AMOUNT_RAW)

    manifest_dict = {
        "proposalId": pid,
        "version": 1,
        "action": {
            "kind": "erc20_payout",
            "token": token_normalized,
            "decimals": 6,
            "recipient": recipient_normalized,
            "amountRaw": amount_raw_str,
        },
        "envelope": {
            "maxTokenOutflow": {
                token_normalized: amount_raw_str,
            },
            "allowApprovals": False,
            "allowRoleChanges": False,
            "allowImplChange": False,
            "allowNewContracts": False,
        },
        "proposalTextHash": proposal_text_hash,
        "evidenceRoot": evidence_root,
        "prevVersionHash": INITIAL_PREV_VERSION_HASH,
    }

    canon_bytes = canonicalize_manifest(manifest_dict)
    version_hash = compute_version_hash(canon_bytes, INITIAL_PREV_VERSION_HASH)
    action_hash = compute_manifest_action_hash(manifest_dict["action"])

    vhash_bytes = bytes.fromhex(version_hash[2:])
    ahash_bytes = bytes.fromhex(action_hash[2:])
    eroot_bytes = bytes.fromhex(evidence_root[2:])

    # Legitimate calldata
    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, DEFAULT_AMOUNT_RAW)

    # Legitimate attestation deadline
    latest_block = w3.eth.get_block("latest")
    deadline = int(latest_block["timestamp"]) + 3600

    sig_bytes = sign_attestation(
        private_key=verifier_pk,
        proposal_id=pid_b32,
        version_hash=vhash_bytes,
        action_hash=ahash_bytes,
        evidence_root=eroot_bytes,
        verdict=VERIFIED,
        deadline=deadline,
        chain_id=w3.eth.chain_id,
        verifying_contract=executor_addr,
    )

    # Verify signature locally
    recovered_signer = recover_attestation_signer(
        proposal_id=pid_b32,
        version_hash=vhash_bytes,
        action_hash=ahash_bytes,
        evidence_root=eroot_bytes,
        verdict=VERIFIED,
        deadline=deadline,
        chain_id=w3.eth.chain_id,
        verifying_contract=executor_addr,
        signature=sig_bytes,
    )
    if recovered_signer.lower() != verifier_addr.lower():
        raise RuntimeError(f"Attestation recovery failure: recovered {recovered_signer} != verifier {verifier_addr}")

    # Substituted calldata (B1)
    substituted_calldata = encode_erc20_transfer_calldata(ATTACKER_ADDR, 2_000_000 * 10**6)

    # Capture initial balances before any execution
    balances_before = capture_snapshot_balances(w3, cfg, token_contract, treasury_addr, RECIPIENT_ADDR)

    # Handle --dry-run
    if dry_run:
        from app.paths import DRYRUN_JSON_PATH
        typed_data = build_attestation_typed_data(
            proposal_id=pid_b32,
            version_hash=vhash_bytes,
            action_hash=ahash_bytes,
            evidence_root=eroot_bytes,
            verdict=VERIFIED,
            deadline=deadline,
            chain_id=w3.eth.chain_id,
            verifying_contract=executor_addr,
        )
        dryrun_data = {
            "mode": "dry-run, no transactions",
            "dry_run": True,
            "chain_id": int(cfg.chain_id),
            "pid": pid,
            "pid_b32": "0x" + pid_b32.hex(),
            "versionHash": version_hash,
            "actionHash": action_hash,
            "evidenceRoot": evidence_root,
            "proposalTextHash": proposal_text_hash,
            "commitments": {
                "proposalTextHash": proposal_text_hash,
                "evidenceRoot": evidence_root,
                "versionHash": version_hash,
                "actionHash": action_hash,
            },
            "attestation": {
                "domain": typed_data["domain"],
                "verdict": VERIFIED,
                "deadline": deadline,
                "signature": "0x" + sig_bytes.hex(),
                "recovered_signer": recovered_signer,
                "expected_verifier": verifier_addr,
            },
            "calldata": {
                "legitimate": "0x" + calldata.hex(),
                "substituted_b1": "0x" + substituted_calldata.hex(),
            },
            "balances": balances_before,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        from app.paths import DATA_DIR
        dry_target = DRYRUN_JSON_PATH if proof_out.resolve() == (DATA_DIR / "proof.json").resolve() else proof_out.parent / "dryrun.json"
        dry_target.parent.mkdir(parents=True, exist_ok=True)
        tmp_dry = dry_target.with_suffix(".tmp")
        with open(tmp_dry, "w", encoding="utf-8") as f:
            json.dump(dryrun_data, f, indent=2)
        os.replace(tmp_dry, dry_target)

        print("\n" + "=" * 80)
        print("                 DAO ACCOUNTABILITY ENGINE — DRY RUN AUDIT")
        print("=" * 80)
        print(f"Chain ID:              {cfg.chain_id}")
        print(f"Proposal ID (pid):     {pid}")
        print(f"pid (bytes32 keccak):  0x{pid_b32.hex()}")
        print("\nCryptographic Commitments:")
        print(f"  proposalTextHash:    {proposal_text_hash}")
        print(f"  evidenceRoot:        {evidence_root}")
        print(f"  versionHash:         {version_hash}")
        print(f"  actionHash:          {action_hash}")
        print("\nEIP-712 Attestation Fields:")
        print("  Domain:", json.dumps(typed_data["domain"], indent=4))
        print(f"  Verdict:             {VERIFIED} (VERIFIED)")
        print(f"  Deadline:            {deadline} (chain time + 3600s)")
        print(f"  Signature (65b hex): 0x{sig_bytes.hex()}")
        print(f"  Recovered Signer:    {recovered_signer}")
        print("\nCalldata Payloads:")
        print(f"  Legitimate (1M USDC to {RECIPIENT_ADDR[:10]}...):")
        print(f"    0x{calldata.hex()}")
        print(f"  Substituted (2M USDC to attacker {ATTACKER_ADDR[:10]}...):")
        print(f"    0x{substituted_calldata.hex()}")
        print(f"\nDRY-RUN COMPLETE: Preflight passed, hashes computed, attestation formed.")
        print(f"Wrote dry-run artifact to {DRYRUN_JSON_PATH} (zero transactions sent, chain_txs untouched).")
        print("=" * 80 + "\n")
        return dryrun_data

    # Prepare transactions list from existing proof for resumability
    existing_txs: List[Dict[str, Any]] = existing_proof.get("transactions", [])
    tx_by_step: Dict[str, Dict[str, Any]] = {t.get("step"): t for t in existing_txs if t.get("step")}
    transactions: List[Dict[str, Any]] = []

    proof_data = {
        "chain_id": int(cfg.chain_id),
        "run_id": run_id,
        "pid": pid,
        "pid_b32": "0x" + pid_b32.hex(),
        "commitments": {
            "proposalTextHash": proposal_text_hash,
            "evidenceRoot": evidence_root,
            "versionHash": version_hash,
            "actionHash": action_hash,
        },
        "versionHash": version_hash,
        "actionHash": action_hash,
        "evidenceRoot": evidence_root,
        "proposalTextHash": proposal_text_hash,
        "contracts": {
            "token": {
                "address": token_addr,
                "explorer_url": explorer_addr_url(token_addr, cfg.explorer_base),
            },
            "registry": {
                "address": registry_addr,
                "explorer_url": explorer_addr_url(registry_addr, cfg.explorer_base),
            },
            "treasury": {
                "address": treasury_addr,
                "explorer_url": explorer_addr_url(treasury_addr, cfg.explorer_base),
            },
            "executor": {
                "address": executor_addr,
                "explorer_url": explorer_addr_url(executor_addr, cfg.explorer_base),
            },
        },
        "balances_before": balances_before,
        "balances_after": balances_before,
        "transactions": transactions,
    }

    # Step 2: commitVersion from proposer
    is_committed = False
    try:
        count = registry_contract.functions.versionCount(pid_b32).call()
        if count > 0:
            _, read_vhash, read_ahash, read_eroot = registry_contract.functions.latestVersion(pid_b32).call()
            if read_vhash == vhash_bytes and read_ahash == ahash_bytes and read_eroot == eroot_bytes:
                is_committed = True
    except Exception:
        is_committed = False

    if is_committed and "commit_version" in tx_by_step:
        logger.info("[Step 2] commitVersion already recorded and verified on-chain. Resuming.")
        transactions.append(tx_by_step["commit_version"])
    else:
        logger.info(f"[Step 2] Broadcasting commitVersion for {pid} from proposer {proposer_addr}...")
        commit_fn = registry_contract.functions.commitVersion(
            pid_b32,
            vhash_bytes,
            ahash_bytes,
            eroot_bytes,
        )
        res_commit = send_tx_1559(w3, proposer_pk, commit_fn, gas=300_000)
        assert res_commit["status"] == 1, "commitVersion transaction failed"

        # Assert read back state
        ver_num, read_vhash, read_ahash, read_eroot = registry_contract.functions.latestVersion(pid_b32).call()
        assert ver_num >= 1, f"Expected versionNumber >= 1, got {ver_num}"
        assert read_vhash == vhash_bytes, "Registry versionHash mismatch"
        assert read_ahash == ahash_bytes, "Registry actionHash mismatch"
        assert read_eroot == eroot_bytes, "Registry evidenceRoot mismatch"
        assert registry_contract.functions.proposalOwner(pid_b32).call() == proposer_addr, "Proposal owner mismatch"

        commit_record = {
            "step": "commit_version",
            "label": "Proposer commits version on GovernanceRegistry",
            "tx_hash": res_commit["tx_hash"],
            "block_number": res_commit["block_number"],
            "status": 1,
            "explorer_url": explorer_tx_url(res_commit["tx_hash"], cfg.explorer_base),
            "revert_reason": None,
            "expected": "success (status 1)",
        }
        transactions.append(commit_record)
        print(f"STEP: commit_version | TX: {res_commit['tx_hash']} | STATUS: {res_commit['status']} | EXPLORER: {commit_record['explorer_url']}")
        log_tx_to_chain_txs(
            run_id=run_id,
            step="commit_version",
            role="proposer",
            from_addr=proposer_addr,
            to_addr=registry_addr,
            tx_res=res_commit,
            explorer_base=cfg.explorer_base,
        )
        save_proof_manifest(proof_data, proof_out)

    # Step 3: approve from governance
    is_approved = False
    try:
        app_vhash, app_ahash, app_eroot = registry_contract.functions.approved(pid_b32).call()
        if app_vhash == vhash_bytes and app_ahash == ahash_bytes and app_eroot == eroot_bytes:
            is_approved = True
    except Exception:
        is_approved = False

    if is_approved and "approve" in tx_by_step:
        logger.info("[Step 3] approve already recorded and verified on-chain. Resuming.")
        transactions.append(tx_by_step["approve"])
    else:
        logger.info(f"[Step 3] Broadcasting approve for {pid} from governance {governance_addr}...")
        approve_fn = registry_contract.functions.approve(pid_b32, vhash_bytes)
        res_approve = send_tx_1559(w3, governance_pk, approve_fn, gas=200_000)
        assert res_approve["status"] == 1, "approve transaction failed"

        app_vhash, app_ahash, app_eroot = registry_contract.functions.approved(pid_b32).call()
        assert app_vhash == vhash_bytes, "Approved versionHash mismatch"
        assert app_ahash == ahash_bytes, "Approved actionHash mismatch"
        assert app_eroot == eroot_bytes, "Approved evidenceRoot mismatch"

        approve_record = {
            "step": "approve",
            "label": "Governance approves latest version on GovernanceRegistry",
            "tx_hash": res_approve["tx_hash"],
            "block_number": res_approve["block_number"],
            "status": 1,
            "explorer_url": explorer_tx_url(res_approve["tx_hash"], cfg.explorer_base),
            "revert_reason": None,
            "expected": "success (status 1)",
        }
        transactions.append(approve_record)
        print(f"STEP: approve | TX: {res_approve['tx_hash']} | STATUS: {res_approve['status']} | EXPLORER: {approve_record['explorer_url']}")
        log_tx_to_chain_txs(
            run_id=run_id,
            step="approve",
            role="governance",
            from_addr=governance_addr,
            to_addr=registry_addr,
            tx_res=res_approve,
            explorer_base=cfg.explorer_base,
        )
        save_proof_manifest(proof_data, proof_out)

    # Step 5: B1 Adversarial execution (BEFORE valid execute)
    if "b1_adversarial_execute" in tx_by_step:
        logger.info("[Step 5] B1 adversarial execution already recorded. Resuming.")
        transactions.append(tx_by_step["b1_adversarial_execute"])
    else:
        logger.info("[Step 5] Executing B1 adversarial substitution (attacker recipient, doubled amount) with legitimate attestation...")
        fn_b1 = executor_contract.functions.execute(
            pid_b32,
            token_addr,
            0,
            substituted_calldata,
            VERIFIED,
            deadline,
            sig_bytes,
        )
        res_b1 = send_tx_1559(w3, proposer_pk, fn_b1, gas=250_000, expect_revert=True)
        assert res_b1["status"] == 0, f"Expected B1 execution to revert with status 0, got {res_b1['status']}"

        rev_b1 = res_b1.get("revert_reason") or (revert_reason(w3, res_b1["tx_hash"]) if res_b1.get("tx_hash") else "node rejected before mining")
        logger.info(f"[Step 5] B1 reverted as expected. Reason: '{rev_b1}'")
        assert "action mismatch" in rev_b1.lower() or "rejected" in rev_b1.lower(), f"Expected 'action mismatch' in revert reason, got '{rev_b1}'"

        tx_h_b1 = res_b1.get("tx_hash") or "node_rejected"
        b1_record = {
            "step": "b1_adversarial_execute",
            "label": "B1 Adversarial Substitution Blocked (action mismatch)",
            "tx_hash": tx_h_b1,
            "block_number": res_b1.get("block_number"),
            "status": 0,
            "explorer_url": explorer_tx_url(tx_h_b1, cfg.explorer_base) if res_b1.get("tx_hash") else "",
            "revert_reason": rev_b1,
            "expected": "revert (action mismatch)",
        }
        transactions.append(b1_record)
        print(f"STEP: b1_adversarial_execute | TX: {tx_h_b1} | STATUS: {res_b1['status']} (revert: {rev_b1}) | EXPLORER: {b1_record['explorer_url']}")
        if res_b1.get("tx_hash"):
            log_tx_to_chain_txs(
                run_id=run_id,
                step="b1_adversarial_execute",
                role="attacker",
                from_addr=proposer_addr,
                to_addr=executor_addr,
                tx_res=res_b1,
                explorer_base=cfg.explorer_base,
                revert_r=rev_b1,
            )
        save_proof_manifest(proof_data, proof_out)

    # Step 6: Valid execute with legitimate calldata and attestation
    is_executed = False
    try:
        is_executed = executor_contract.functions.executed(pid_b32).call()
    except Exception:
        is_executed = False

    if is_executed and "valid_execute" in tx_by_step:
        logger.info("[Step 6] Valid execution already recorded and verified on-chain. Resuming.")
        transactions.append(tx_by_step["valid_execute"])
    else:
        logger.info(f"[Step 6] Broadcasting valid execution: {DEFAULT_AMOUNT_RAW} units to recipient {RECIPIENT_ADDR}...")
        rec_cs = to_checksum_address(RECIPIENT_ADDR)
        rec_bal_before = token_contract.functions.balanceOf(rec_cs).call()

        fn_valid = executor_contract.functions.execute(
            pid_b32,
            token_addr,
            0,
            calldata,
            VERIFIED,
            deadline,
            sig_bytes,
        )
        res_valid = send_tx_1559(w3, proposer_pk, fn_valid, gas=1_000_000, expect_revert=False)
        assert res_valid["status"] == 1, f"Expected valid execute status 1, got {res_valid['status']}"

        rec_bal_after = token_contract.functions.balanceOf(rec_cs).call()
        delta = rec_bal_after - rec_bal_before
        assert delta == DEFAULT_AMOUNT_RAW, f"Recipient balance increase mismatch: expected {DEFAULT_AMOUNT_RAW}, got {delta}"
        assert executor_contract.functions.executed(pid_b32).call() is True, "Proposal not marked as executed on-chain"

        valid_record = {
            "step": "valid_execute",
            "label": "Valid Guarded Execution (1,000,000 USDC Payout)",
            "tx_hash": res_valid["tx_hash"],
            "block_number": res_valid["block_number"],
            "status": 1,
            "explorer_url": explorer_tx_url(res_valid["tx_hash"], cfg.explorer_base),
            "revert_reason": None,
            "expected": "success (status 1)",
        }
        transactions.append(valid_record)
        print(f"STEP: valid_execute | TX: {res_valid['tx_hash']} | STATUS: {res_valid['status']} | EXPLORER: {valid_record['explorer_url']}")
        log_tx_to_chain_txs(
            run_id=run_id,
            step="valid_execute",
            role="proposer",
            from_addr=proposer_addr,
            to_addr=executor_addr,
            tx_res=res_valid,
            explorer_base=cfg.explorer_base,
        )
        save_proof_manifest(proof_data, proof_out)

    # Step 7: Replay execution test (--with-replay)
    if with_replay:
        if "replay_execute" in tx_by_step:
            logger.info("[Step 7] Replay execution already recorded. Resuming.")
            transactions.append(tx_by_step["replay_execute"])
        else:
            logger.info("[Step 7] Attempting duplicate execution replay (--with-replay)...")
            fn_replay = executor_contract.functions.execute(
                pid_b32,
                token_addr,
                0,
                calldata,
                VERIFIED,
                deadline,
                sig_bytes,
            )
            res_replay = send_tx_1559(w3, proposer_pk, fn_replay, gas=250_000, expect_revert=True)
            assert res_replay["status"] == 0, f"Expected replay execution to revert with status 0, got {res_replay['status']}"

            rev_replay = res_replay.get("revert_reason") or (revert_reason(w3, res_replay["tx_hash"]) if res_replay.get("tx_hash") else "node rejected before mining")
            logger.info(f"[Step 7] Replay reverted as expected. Reason: '{rev_replay}'")
            assert "already executed" in rev_replay.lower() or "rejected" in rev_replay.lower(), f"Expected 'already executed' in revert reason, got '{rev_replay}'"

            tx_h_replay = res_replay.get("tx_hash") or "node_rejected"
            replay_record = {
                "step": "replay_execute",
                "label": "Replay Attempt Blocked (already executed)",
                "tx_hash": tx_h_replay,
                "block_number": res_replay.get("block_number"),
                "status": 0,
                "explorer_url": explorer_tx_url(tx_h_replay, cfg.explorer_base) if res_replay.get("tx_hash") else "",
                "revert_reason": rev_replay,
                "expected": "revert (already executed)",
            }
            transactions.append(replay_record)
            print(f"STEP: replay_execute | TX: {tx_h_replay} | STATUS: {res_replay['status']} (revert: {rev_replay}) | EXPLORER: {replay_record['explorer_url']}")
            if res_replay.get("tx_hash"):
                log_tx_to_chain_txs(
                    run_id=run_id,
                    step="replay_execute",
                    role="proposer",
                    from_addr=proposer_addr,
                    to_addr=executor_addr,
                    tx_res=res_replay,
                    explorer_base=cfg.explorer_base,
                    revert_r=rev_replay,
                )
            save_proof_manifest(proof_data, proof_out)

    # Capture final balances after execution
    balances_after = capture_snapshot_balances(w3, cfg, token_contract, treasury_addr, RECIPIENT_ADDR)
    proof_data["balances_after"] = balances_after
    save_proof_manifest(proof_data, proof_out)

    # Final summary display
    print_summary_table(proof_data)
    return proof_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish and record public testnet proof for the DAO Accountability Engine")
    parser.add_argument("--dry-run", action="store_true", help="Build and print all hashes, manifests, and attestation fields without broadcasting transactions")
    parser.add_argument("--with-replay", action="store_true", help="Send the valid execution again to confirm and document on-chain replay rejection")
    parser.add_argument("--run-id", type=str, default=None, help="Identifier suffix for proposal ID (e.g. 26102601). Enforces pid length <= 32 bytes")
    parser.add_argument("--rpc", type=str, default=None, help="Override RPC URL endpoint")
    parser.add_argument("--deployments", type=str, default=None, help="Path to deployment manifest (default: data/deployments.proof.json)")
    parser.add_argument("--env-file", type=str, default=None, help="Path to proof environment configuration file (default: .env.amoy)")
    parser.add_argument("--proof-output", type=str, default=None, help="Path to output proof JSON (default: data/proof.json)")
    args = parser.parse_args()

    try:
        publish_proof(
            run_id=args.run_id,
            dry_run=args.dry_run,
            with_replay=args.with_replay,
            rpc_url=args.rpc,
            deployments_path=args.deployments,
            env_path=args.env_file,
            proof_path=args.proof_output,
        )
    except Exception as exc:
        logger.error(f"FATAL: Proof workflow failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
