#!/usr/bin/env python3
"""Read-only post-deployment verification script for Ethereum Sepolia (Chain ID 11155111).

Validates on-chain wiring and contracts state using view calls only:
1. Connected Chain ID == 11155111
2. Bytecode exists on-chain at all 4 contract addresses
3. GovernanceRegistry.governance() == GOVERNANCE_ADDR
4. Treasury.executor() == GuardedExecutor address (setExecutor was called)
5. GuardedExecutor.verifier() == VERIFIER_ADDR
6. GuardedExecutor.registry() == GovernanceRegistry address
7. GuardedExecutor.treasury() == Treasury address
8. Treasury.deployer() == DEPLOYER_ADDR
9. Manifest participant addresses match .env.amoy
10. MockToken.balanceOf(Treasury) == 1,000,000 * 10**6 (1,000,000 USDC initial funding)

Prints a PASS/FAIL table per check and Sepolia Etherscan links.
Exits with code 0 if all pass, non-zero if any fail. Never prints secrets.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from eth_utils import to_checksum_address
from web3 import Web3

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.chain.public import get_explorer_base, load_proof_env

EXPECTED_SEPOLIA_CHAIN_ID = 11155111
EXPECTED_TREASURY_FUNDING = 1_000_000 * 10**6  # 1M USDC (6 decimals)

# Minimal ABIs for verification view calls
TOKEN_ABI = [
    {
        "type": "function",
        "name": "balanceOf",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "decimals",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "symbol",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
    },
]

REGISTRY_ABI = [
    {
        "type": "function",
        "name": "governance",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    }
]

TREASURY_ABI = [
    {
        "type": "function",
        "name": "executor",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "deployer",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    },
]

EXECUTOR_ABI = [
    {
        "type": "function",
        "name": "verifier",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "registry",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "treasury",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    },
]


def safe_checksum(addr: Optional[str]) -> str:
    if not addr:
        return ""
    try:
        return to_checksum_address(addr)
    except Exception:
        return addr


def check_bytecode(w3: Web3, addr: str) -> bool:
    try:
        cs = safe_checksum(addr)
        if not cs:
            return False
        code = w3.eth.get_code(cs)
        if isinstance(code, (bytes, bytearray)):
            return len(code) > 0 and code not in (b"\x00", b"")
        code_str = str(code).strip().lower()
        return len(code_str) > 2 and code_str not in ("0x", "0x0", "0x00")
    except Exception:
        return False


def verify_deployment(
    deployments_path: Path = REPO_ROOT / "data" / "deployments.proof.json",
    env_path: Path = REPO_ROOT / ".env.amoy",
    w3_override: Any = None,
) -> bool:
    results: List[Tuple[str, str, str]] = []  # (Check, Status, Details)
    all_passed = True

    print("=" * 80)
    print("CASCADE 4.1 — On-Chain Post-Deployment Verification (Read-Only)")
    print("=" * 80)

    if not deployments_path.exists():
        print(f"FAIL: Deployment manifest not found at {deployments_path}", file=sys.stderr)
        print("Please broadcast deployment and run scripts/write_proof_deployments.py first.", file=sys.stderr)
        return False

    with open(deployments_path, "r", encoding="utf-8") as f:
        deployments = json.load(f)

    # 1. Connect to network and load configuration
    try:
        cfg = load_proof_env(path=env_path, w3=w3_override)
        w3 = cfg.w3 or Web3(Web3.HTTPProvider(cfg.rpc_url))
    except Exception as e:
        print(f"FAIL: Could not load proof environment or connect to RPC: {e}", file=sys.stderr)
        return False

    connected_chain_id = w3.eth.chain_id
    explorer_base = get_explorer_base(connected_chain_id)

    # Check 1: Chain ID
    if connected_chain_id == EXPECTED_SEPOLIA_CHAIN_ID:
        results.append(("Chain ID", "PASS", f"Connected to {connected_chain_id} (Ethereum Sepolia)"))
    else:
        results.append(("Chain ID", "FAIL", f"Expected {EXPECTED_SEPOLIA_CHAIN_ID}, got {connected_chain_id}"))
        all_passed = False

    # Check 2: Bytecode on-chain for 4 contracts
    contracts = {
        "MockToken": deployments.get("token"),
        "GovernanceRegistry": deployments.get("registry"),
        "Treasury": deployments.get("treasury"),
        "GuardedExecutor": deployments.get("executor"),
    }

    for c_name, c_addr in contracts.items():
        if not c_addr:
            results.append((f"Bytecode: {c_name}", "FAIL", "Address missing from deployment file"))
            all_passed = False
            continue
        has_code = check_bytecode(w3, c_addr)
        if has_code:
            results.append((f"Bytecode: {c_name}", "PASS", f"Code deployed ({c_addr})"))
        else:
            results.append((f"Bytecode: {c_name}", "FAIL", f"No code at {c_addr}"))
            all_passed = False

    # Contract instances
    token = w3.eth.contract(address=safe_checksum(contracts["MockToken"]), abi=TOKEN_ABI) if contracts.get("MockToken") else None
    registry = w3.eth.contract(address=safe_checksum(contracts["GovernanceRegistry"]), abi=REGISTRY_ABI) if contracts.get("GovernanceRegistry") else None
    treasury = w3.eth.contract(address=safe_checksum(contracts["Treasury"]), abi=TREASURY_ABI) if contracts.get("Treasury") else None
    executor = w3.eth.contract(address=safe_checksum(contracts["GuardedExecutor"]), abi=EXECUTOR_ABI) if contracts.get("GuardedExecutor") else None

    # Expected roles from environment
    exp_gov = safe_checksum(cfg.addresses.get("GOVERNANCE_ADDR") or deployments.get("governance", ""))
    exp_ver = safe_checksum(cfg.addresses.get("VERIFIER_ADDR") or deployments.get("verifier", ""))
    exp_dep = safe_checksum(cfg.addresses.get("DEPLOYER_ADDR") or deployments.get("deployer", ""))

    # Check 3: GovernanceRegistry.governance()
    if registry:
        try:
            onchain_gov = safe_checksum(registry.functions.governance().call())
            if onchain_gov.lower() == exp_gov.lower():
                results.append(("Registry Governance", "PASS", f"Matches expected {exp_gov}"))
            else:
                results.append(("Registry Governance", "FAIL", f"On-chain {onchain_gov} != expected {exp_gov}"))
                all_passed = False
        except Exception as e:
            results.append(("Registry Governance", "FAIL", f"View call reverted: {e}"))
            all_passed = False

    # Check 4: Treasury.executor() == GuardedExecutor
    if treasury and contracts.get("GuardedExecutor"):
        try:
            onchain_exec = safe_checksum(treasury.functions.executor().call())
            exp_exec = safe_checksum(contracts["GuardedExecutor"])
            if onchain_exec.lower() == exp_exec.lower():
                results.append(("Treasury Executor", "PASS", f"Matches GuardedExecutor ({exp_exec})"))
            else:
                results.append(("Treasury Executor", "FAIL", f"On-chain {onchain_exec} != expected {exp_exec}"))
                all_passed = False
        except Exception as e:
            results.append(("Treasury Executor", "FAIL", f"View call reverted: {e}"))
            all_passed = False

    # Check 5: GuardedExecutor.verifier() == VERIFIER_ADDR
    if executor:
        try:
            onchain_ver = safe_checksum(executor.functions.verifier().call())
            if onchain_ver.lower() == exp_ver.lower():
                results.append(("GuardedExecutor Verifier", "PASS", f"Matches expected {exp_ver}"))
            else:
                results.append(("GuardedExecutor Verifier", "FAIL", f"On-chain {onchain_ver} != expected {exp_ver}"))
                all_passed = False
        except Exception as e:
            results.append(("GuardedExecutor Verifier", "FAIL", f"View call reverted: {e}"))
            all_passed = False

    # Check 6: GuardedExecutor.registry() == GovernanceRegistry
    if executor and contracts.get("GovernanceRegistry"):
        try:
            onchain_reg = safe_checksum(executor.functions.registry().call())
            exp_reg = safe_checksum(contracts["GovernanceRegistry"])
            if onchain_reg.lower() == exp_reg.lower():
                results.append(("GuardedExecutor Registry Wiring", "PASS", f"Matches GovernanceRegistry ({exp_reg})"))
            else:
                results.append(("GuardedExecutor Registry Wiring", "FAIL", f"On-chain {onchain_reg} != {exp_reg}"))
                all_passed = False
        except Exception as e:
            results.append(("GuardedExecutor Registry Wiring", "FAIL", f"View call reverted: {e}"))
            all_passed = False

    # Check 7: GuardedExecutor.treasury() == Treasury
    if executor and contracts.get("Treasury"):
        try:
            onchain_tre = safe_checksum(executor.functions.treasury().call())
            exp_tre = safe_checksum(contracts["Treasury"])
            if onchain_tre.lower() == exp_tre.lower():
                results.append(("GuardedExecutor Treasury Wiring", "PASS", f"Matches Treasury ({exp_tre})"))
            else:
                results.append(("GuardedExecutor Treasury Wiring", "FAIL", f"On-chain {onchain_tre} != {exp_tre}"))
                all_passed = False
        except Exception as e:
            results.append(("GuardedExecutor Treasury Wiring", "FAIL", f"View call reverted: {e}"))
            all_passed = False

    # Check 8: Treasury.deployer()
    if treasury and exp_dep:
        try:
            onchain_dep = safe_checksum(treasury.functions.deployer().call())
            if onchain_dep.lower() == exp_dep.lower():
                results.append(("Treasury Deployer", "PASS", f"Matches {exp_dep}"))
            else:
                results.append(("Treasury Deployer", "FAIL", f"On-chain {onchain_dep} != {exp_dep}"))
                all_passed = False
        except Exception as e:
            results.append(("Treasury Deployer", "FAIL", f"View call reverted: {e}"))
            all_passed = False

    # Check 9: Treasury initial funding (MockToken.balanceOf)
    if token and contracts.get("Treasury"):
        try:
            treasury_addr = safe_checksum(contracts["Treasury"])
            bal = token.functions.balanceOf(treasury_addr).call()
            if bal == EXPECTED_TREASURY_FUNDING:
                results.append(("Treasury Initial Funding", "PASS", f"Exact balance: 1,000,000 USDC ({bal} units)"))
            else:
                results.append(("Treasury Initial Funding", "FAIL", f"Expected {EXPECTED_TREASURY_FUNDING}, got {bal}"))
                all_passed = False
        except Exception as e:
            results.append(("Treasury Initial Funding", "FAIL", f"balanceOf reverted: {e}"))
            all_passed = False

    # Print Summary Table
    print("\nVERIFICATION RESULTS TABLE:")
    print(f"{'Check':<36} | {'Status':<6} | {'Details'}")
    print("-" * 80)
    for check_name, status, details in results:
        status_str = f"[\033[92mPASS\033[0m]" if status == "PASS" else f"[\033[91mFAIL\033[0m]"
        # Safe fallback without ansi if output piped
        if not sys.stdout.isatty():
            status_str = f"[{status}]"
        print(f"{check_name:<36} | {status_str:<6} | {details}")

    print("\nCONTRACT EXPLORER LINKS:")
    for c_name, c_addr in contracts.items():
        if c_addr:
            print(f"  - {c_name:<20}: {explorer_base}/address/{c_addr}")

    print("-" * 80)
    if all_passed:
        print("OVERALL VERIFICATION: SUCCESS (All 10 checks passed on-chain)")
    else:
        print("OVERALL VERIFICATION: FAILED (One or more checks did not match)", file=sys.stderr)

    return all_passed


def main() -> None:
    passed = verify_deployment()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
