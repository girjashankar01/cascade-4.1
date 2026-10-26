"""Web3 client for deploying and interacting with DAO Governance contracts."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from eth_account import Account
from web3 import Web3

from app.chain.attest import to_bytes32

logger = logging.getLogger(__name__)

# Standard Anvil test private keys
PK_DEPLOYER = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
PK_PROPOSER = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
PK_GOVERNANCE = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
PK_VERIFIER = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
PK_ATTACKER = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"

DEFAULT_RPC_URL = os.environ.get("RPC_URL", "http://127.0.0.1:8545")


def get_web3(rpc_url: Optional[str] = None) -> Web3:
    url = rpc_url or DEFAULT_RPC_URL
    return Web3(Web3.HTTPProvider(url))


def load_artifact(contract_name: str) -> Dict[str, Any]:
    contracts_dir = Path(__file__).resolve().parents[3] / "contracts" / "out"
    artifact_path = contracts_dir / f"{contract_name}.sol" / f"{contract_name}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found at {artifact_path}. Run 'forge build' first.")
    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)


def proposal_id_to_bytes32(pid: Union[str, bytes]) -> bytes:
    """Normalize proposalId to 32 bytes.

    If 66-char hex string (0x...), converts hex to 32 bytes.
    Otherwise hashes with Keccak-256 (e.g. Web3.keccak(text=pid)).
    """
    if isinstance(pid, bytes):
        if len(pid) == 32:
            return pid
        return pid.rjust(32, b"\x00")
    s = pid.strip()
    if (s.startswith("0x") or s.startswith("0X")) and len(s) == 66:
        return bytes.fromhex(s[2:])
    return Web3.keccak(text=s)


def send_tx(w3: Web3, from_key: str, fn_call: Any, gas: int = 2_000_000) -> Any:
    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    is_local_chain = True
    try:
        is_local_chain = w3.eth.chain_id in {31337, 1337}
    except Exception:
        is_local_chain = True

    if chain_mode == "proof" or not is_local_chain:
        from app.chain.public import send_tx_1559
        res = send_tx_1559(w3, from_key, fn_call, gas=gas, wait_timeout=120)
        return res["receipt"]

    account = Account.from_key(from_key)
    tx = fn_call.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": gas,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, from_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction failed with status 0: {tx_hash.hex()}")
    return receipt


def deploy_contract(w3: Web3, from_key: str, artifact_name: str, *args: Any) -> Any:
    artifact = load_artifact(artifact_name)
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]["object"]
    factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    account = Account.from_key(from_key)

    tx = factory.constructor(*args).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 4_000_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, from_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
    if receipt.status != 1:
        raise RuntimeError(f"Deployment of {artifact_name} failed: {tx_hash.hex()}")
    return w3.eth.contract(address=receipt.contractAddress, abi=abi)


def deploy_system(
    w3: Web3,
    deployer_key: str = PK_DEPLOYER,
    governance_key: str = PK_GOVERNANCE,
    verifier_key: str = PK_VERIFIER,
) -> Dict[str, Any]:
    """Deploy MockToken, GovernanceRegistry, Treasury, GuardedExecutor, and wire them up."""
    governance_addr = Account.from_key(governance_key).address
    verifier_addr = Account.from_key(verifier_key).address

    token = deploy_contract(w3, deployer_key, "MockToken", "USD Coin", "USDC", 10_000_000 * 10**6)
    registry = deploy_contract(w3, deployer_key, "GovernanceRegistry", governance_addr)
    treasury = deploy_contract(w3, deployer_key, "Treasury")
    executor = deploy_contract(
        w3,
        deployer_key,
        "GuardedExecutor",
        registry.address,
        treasury.address,
        verifier_addr,
    )

    send_tx(w3, deployer_key, treasury.functions.setExecutor(executor.address))
    send_tx(w3, deployer_key, token.functions.transfer(treasury.address, 1_000_000 * 10**6))

    return {
        "token": token,
        "registry": registry,
        "treasury": treasury,
        "executor": executor,
        "governance_address": governance_addr,
        "verifier_address": verifier_addr,
    }


def commit_version_onchain(
    registry_address: str,
    proposal_id: Union[str, bytes],
    version_hash: Union[str, bytes],
    action_hash: Union[str, bytes],
    evidence_root: Union[str, bytes],
    proposer_key: str = PK_PROPOSER,
    rpc_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Call commitVersion on GovernanceRegistry contract."""
    w3 = get_web3(rpc_url)
    artifact = load_artifact("GovernanceRegistry")
    registry = w3.eth.contract(address=Web3.to_checksum_address(registry_address), abi=artifact["abi"])

    pid_b32 = proposal_id_to_bytes32(proposal_id)
    vhash_b32 = to_bytes32(version_hash)
    ahash_b32 = to_bytes32(action_hash)
    eroot_b32 = to_bytes32(evidence_root)

    receipt = send_tx(
        w3,
        proposer_key,
        registry.functions.commitVersion(pid_b32, vhash_b32, ahash_b32, eroot_b32),
    )

    # Read back latest version from chain to confirm
    latest_ver_num, stored_vhash, stored_ahash, stored_eroot = registry.functions.latestVersion(pid_b32).call()

    return {
        "tx_hash": f"0x{receipt.transactionHash.hex().removeprefix('0x')}",
        "block_number": receipt.blockNumber,
        "version_number": latest_ver_num,
        "stored_version_hash": "0x" + stored_vhash.hex().lower(),
        "stored_action_hash": "0x" + stored_ahash.hex().lower(),
        "stored_evidence_root": "0x" + stored_eroot.hex().lower(),
    }


def approve_version_onchain(
    registry_address: str,
    proposal_id: Union[str, bytes],
    version_hash: Union[str, bytes],
    governance_key: str = PK_GOVERNANCE,
    rpc_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Call approve on GovernanceRegistry contract from the governance account."""
    w3 = get_web3(rpc_url)
    artifact = load_artifact("GovernanceRegistry")
    registry = w3.eth.contract(address=Web3.to_checksum_address(registry_address), abi=artifact["abi"])

    pid_b32 = proposal_id_to_bytes32(proposal_id)
    vhash_b32 = to_bytes32(version_hash)

    receipt = send_tx(
        w3,
        governance_key,
        registry.functions.approve(pid_b32, vhash_b32),
    )

    # Read back approved state to confirm
    app_vhash, app_ahash, app_eroot = registry.functions.approved(pid_b32).call()

    return {
        "tx_hash": f"0x{receipt.transactionHash.hex().removeprefix('0x')}",
        "block_number": receipt.blockNumber,
        "approved_version_hash": "0x" + app_vhash.hex().lower(),
        "approved_action_hash": "0x" + app_ahash.hex().lower(),
        "approved_evidence_root": "0x" + app_eroot.hex().lower(),
    }


def get_onchain_version(
    registry_address: str,
    proposal_id: Union[str, bytes],
    version_number: int,
    rpc_url: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Read specific version data from GovernanceRegistry."""
    w3 = get_web3(rpc_url)
    artifact = load_artifact("GovernanceRegistry")
    registry = w3.eth.contract(address=Web3.to_checksum_address(registry_address), abi=artifact["abi"])

    pid_b32 = proposal_id_to_bytes32(proposal_id)
    vhash, ahash, eroot = registry.functions.getVersion(pid_b32, version_number).call()
    return (
        "0x" + vhash.hex().lower(),
        "0x" + ahash.hex().lower(),
        "0x" + eroot.hex().lower(),
    )


def get_onchain_approved(
    registry_address: str,
    proposal_id: Union[str, bytes],
    rpc_url: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Read currently approved record from GovernanceRegistry."""
    w3 = get_web3(rpc_url)
    artifact = load_artifact("GovernanceRegistry")
    registry = w3.eth.contract(address=Web3.to_checksum_address(registry_address), abi=artifact["abi"])

    pid_b32 = proposal_id_to_bytes32(proposal_id)
    vhash, ahash, eroot = registry.functions.approved(pid_b32).call()
    return (
        "0x" + vhash.hex().lower(),
        "0x" + ahash.hex().lower(),
        "0x" + eroot.hex().lower(),
    )
