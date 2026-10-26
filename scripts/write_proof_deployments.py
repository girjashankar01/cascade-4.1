#!/usr/bin/env python3
"""Parse Foundry broadcast artifacts and output data/deployments.proof.json."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_env_defaults(repo_root: Path) -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    env_file = repo_root / ".env.amoy"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


def parse_broadcast_manifest(broadcast_path: Path, chain_id: Optional[str] = None, env_defaults: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Parse Foundry broadcast run-latest.json into deployments.proof.json schema."""
    with open(broadcast_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    defaults = env_defaults or {}
    txs: List[Dict[str, Any]] = data.get("transactions", [])

    token_addr: Optional[str] = None
    registry_addr: Optional[str] = None
    treasury_addr: Optional[str] = None
    executor_addr: Optional[str] = None
    deployer_addr: Optional[str] = None
    governance_arg: Optional[str] = None
    verifier_arg: Optional[str] = None
    deploy_tx_hashes: List[str] = []
    deploy_block_numbers: List[int] = []

    for item in txs:
        tx_hash = item.get("hash")
        if tx_hash:
            deploy_tx_hashes.append(tx_hash)

        block_num = item.get("blockNumber") or (item.get("receipt") or {}).get("blockNumber")
        if block_num is not None:
            try:
                bn = int(block_num, 16) if isinstance(block_num, str) and block_num.startswith("0x") else int(block_num)
                deploy_block_numbers.append(bn)
            except Exception:
                pass

        tx_detail = item.get("transaction", {})
        from_addr = item.get("from") or tx_detail.get("from")
        if from_addr and not deployer_addr:
            deployer_addr = from_addr

        contract_name = item.get("contractName")
        contract_addr = item.get("contractAddress")
        args = item.get("arguments", [])

        if contract_name == "MockToken" and contract_addr:
            token_addr = contract_addr
        elif contract_name == "GovernanceRegistry" and contract_addr:
            registry_addr = contract_addr
            if args:
                governance_arg = args[0]
        elif contract_name == "Treasury" and contract_addr:
            treasury_addr = contract_addr
        elif contract_name == "GuardedExecutor" and contract_addr:
            executor_addr = contract_addr
            if len(args) >= 3:
                verifier_arg = args[2]

    # Resolve participants with fallback to env/.env.amoy
    governance_addr = (
        os.environ.get("GOVERNANCE_ADDR")
        or defaults.get("GOVERNANCE_ADDR")
        or governance_arg
        or ""
    )
    verifier_addr = (
        os.environ.get("VERIFIER_ADDR")
        or defaults.get("VERIFIER_ADDR")
        or verifier_arg
        or ""
    )
    proposer_addr = (
        os.environ.get("PROPOSER_ADDR")
        or defaults.get("PROPOSER_ADDR")
        or ""
    )
    deployer_addr = (
        deployer_addr
        or os.environ.get("DEPLOYER_ADDR")
        or defaults.get("DEPLOYER_ADDR")
        or ""
    )

    resolved_cid = chain_id or defaults.get("CHAIN_ID") or "11155111"

    return {
        "token": token_addr,
        "registry": registry_addr,
        "treasury": treasury_addr,
        "executor": executor_addr,
        "deployer": deployer_addr,
        "governance": governance_addr,
        "verifier": verifier_addr,
        "proposer": proposer_addr,
        "chain_id": int(resolved_cid) if str(resolved_cid).isdigit() else resolved_cid,
        "deploy_tx_hashes": deploy_tx_hashes,
        "deploy_block_numbers": deploy_block_numbers,
    }


def main() -> None:
    repo_root = find_repo_root()
    env_defaults = load_env_defaults(repo_root)

    # Resolve chain ID from CLI or env (default to 11155111 for proof mode)
    chain_id_str = os.environ.get("CHAIN_ID") or env_defaults.get("CHAIN_ID") or "11155111"

    broadcast_base = repo_root / "contracts" / "broadcast" / "DeployProof.s.sol"
    target_dir = broadcast_base / chain_id_str
    run_latest_path = target_dir / "run-latest.json"

    if not run_latest_path.exists():
        print(f"Error: Broadcast file not found at {run_latest_path}", file=sys.stderr)
        print(f"Please broadcast the deployment first using:", file=sys.stderr)
        print(f"  cd contracts && forge script script/DeployProof.s.sol --rpc-url \"$AMOY_RPC\" --account \"$DEPLOYER_ACCOUNT\" --broadcast", file=sys.stderr)
        sys.exit(1)

    print(f"Loading broadcast log: {run_latest_path} (Chain ID: {chain_id_str})")

    proof_deployments = parse_broadcast_manifest(run_latest_path, chain_id_str, env_defaults)

    out_dir = repo_root / "data"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "deployments.proof.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(proof_deployments, f, indent=2)

    print(f"SUCCESS: Wrote proof deployments to {out_file}")
    print(json.dumps(proof_deployments, indent=2))


if __name__ == "__main__":
    main()
