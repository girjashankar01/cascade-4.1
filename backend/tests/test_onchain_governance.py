"""On-chain GovernanceRegistry version chaining, approval, and tamper verification test against Anvil."""

import socket
import subprocess
import time
from typing import Generator
import pytest
from eth_account import Account
from web3 import Web3

from app.chain.client import (
    PK_DEPLOYER,
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_ATTACKER,
    approve_version_onchain,
    commit_version_onchain,
    deploy_contract,
    get_onchain_approved,
    get_onchain_version,
    proposal_id_to_bytes32,
)
from app.manifest.builder import TamperError, verify_manifest_integrity
from app.manifest.canon import canonicalize_manifest
from app.manifest.hashes import (
    INITIAL_PREV_VERSION_HASH,
    compute_manifest_action_hash,
    compute_version_hash,
)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def anvil_node() -> Generator[str, None, None]:
    port = find_free_port()
    proc = subprocess.Popen(
        ["anvil", "--host", "127.0.0.1", "--port", str(port), "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    w3 = Web3(Web3.HTTPProvider(url))
    for _ in range(50):
        if w3.is_connected():
            break
        time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("Failed to connect to local Anvil instance")

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_onchain_version_chain_and_governance_approval(anvil_node: str):
    w3 = Web3(Web3.HTTPProvider(anvil_node))
    governance_addr = Account.from_key(PK_GOVERNANCE).address

    # 1. Deploy GovernanceRegistry
    registry = deploy_contract(w3, PK_DEPLOYER, "GovernanceRegistry", governance_addr)
    registry_address = registry.address

    pid = "PROP-002"
    pid_b32 = proposal_id_to_bytes32(pid)

    # 2. Version 1 manifest & commitments
    manifest_v1 = {
        "proposalId": pid,
        "version": 1,
        "action": {
            "kind": "erc20_payout",
            "token": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "decimals": 6,
            "recipient": "0x9965507d1a55bcc6475675304ca994970de97744",
            "amountRaw": "1000000000000",
        },
        "envelope": {
            "maxTokenOutflow": {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "1000000000000"},
            "allowApprovals": False,
            "allowRoleChanges": False,
            "allowImplChange": False,
            "allowNewContracts": False,
        },
        "proposalTextHash": "0x" + "11" * 32,
        "evidenceRoot": "0x" + "22" * 32,
        "prevVersionHash": INITIAL_PREV_VERSION_HASH,
    }

    canon_bytes_v1 = canonicalize_manifest(manifest_v1)
    vhash_v1 = compute_version_hash(canon_bytes_v1, INITIAL_PREV_VERSION_HASH)
    ahash_v1 = compute_manifest_action_hash(manifest_v1["action"])
    eroot_v1 = manifest_v1["evidenceRoot"]

    # 3. Proposer commits Version 1
    res_v1 = commit_version_onchain(
        registry_address=registry_address,
        proposal_id=pid,
        version_hash=vhash_v1,
        action_hash=ahash_v1,
        evidence_root=eroot_v1,
        proposer_key=PK_PROPOSER,
        rpc_url=anvil_node,
    )
    assert res_v1["version_number"] == 1
    assert res_v1["stored_version_hash"] == vhash_v1
    assert res_v1["stored_action_hash"] == ahash_v1

    # 4. Non-proposer cannot commit a new version for the same proposal
    with pytest.raises(Exception):
        commit_version_onchain(
            registry_address=registry_address,
            proposal_id=pid,
            version_hash="0x" + "99" * 32,
            action_hash=ahash_v1,
            evidence_root=eroot_v1,
            proposer_key=PK_ATTACKER,
            rpc_url=anvil_node,
        )

    # 5. Version 2 (text revision with identical action)
    manifest_v2 = dict(manifest_v1)
    manifest_v2["version"] = 2
    manifest_v2["proposalTextHash"] = "0x" + "33" * 32  # revised text
    manifest_v2["prevVersionHash"] = vhash_v1

    canon_bytes_v2 = canonicalize_manifest(manifest_v2)
    vhash_v2 = compute_version_hash(canon_bytes_v2, vhash_v1)
    ahash_v2 = compute_manifest_action_hash(manifest_v2["action"])
    eroot_v2 = manifest_v2["evidenceRoot"]

    res_v2 = commit_version_onchain(
        registry_address=registry_address,
        proposal_id=pid,
        version_hash=vhash_v2,
        action_hash=ahash_v2,
        evidence_root=eroot_v2,
        proposer_key=PK_PROPOSER,
        rpc_url=anvil_node,
    )
    assert res_v2["version_number"] == 2
    assert res_v2["stored_version_hash"] == vhash_v2

    # Verify version count on registry
    assert registry.functions.versionCount(pid_b32).call() == 2

    # 6. Non-governance account cannot approve
    with pytest.raises(Exception):
        approve_version_onchain(
            registry_address=registry_address,
            proposal_id=pid,
            version_hash=vhash_v2,
            governance_key=PK_ATTACKER,
            rpc_url=anvil_node,
        )

    # 7. Approving an older non-latest version reverts
    with pytest.raises(Exception):
        approve_version_onchain(
            registry_address=registry_address,
            proposal_id=pid,
            version_hash=vhash_v1,  # v1 is not latest!
            governance_key=PK_GOVERNANCE,
            rpc_url=anvil_node,
        )

    # 8. Governance approves latest committed version (Version 2)
    app_res = approve_version_onchain(
        registry_address=registry_address,
        proposal_id=pid,
        version_hash=vhash_v2,
        governance_key=PK_GOVERNANCE,
        rpc_url=anvil_node,
    )
    assert app_res["approved_version_hash"] == vhash_v2
    assert app_res["approved_action_hash"] == ahash_v2

    # Verify on-chain approved record matches Version 2 tuple
    on_vhash, on_ahash, on_eroot = get_onchain_approved(registry_address, pid, rpc_url=anvil_node)
    assert on_vhash == vhash_v2
    assert on_ahash == ahash_v2
    assert on_eroot == eroot_v2

    # 9. Verify integrity against on-chain registry passes
    v2_report = verify_manifest_integrity(
        proposal_id=pid,
        version=2,
        manifest_dict=manifest_v2,
        registry_address=registry_address,
        rpc_url=anvil_node,
    )
    assert v2_report["verified"] is True
    assert v2_report["onchain_verified"] is True

    # 10. Tamper test against on-chain registry: modifying manifest fails on-chain check
    tampered_v2 = dict(manifest_v2)
    tampered_v2["action"] = dict(manifest_v2["action"])
    tampered_v2["action"]["amountRaw"] = "2000000000000"  # tampered amount

    with pytest.raises(TamperError, match="Tamper detected on-chain"):
        verify_manifest_integrity(
            proposal_id=pid,
            version=2,
            manifest_dict=tampered_v2,
            registry_address=registry_address,
            rpc_url=anvil_node,
        )

    # 11. Invalidation test: committing Version 3 clears prior approval!
    manifest_v3 = dict(manifest_v2)
    manifest_v3["version"] = 3
    manifest_v3["prevVersionHash"] = vhash_v2
    canon_bytes_v3 = canonicalize_manifest(manifest_v3)
    vhash_v3 = compute_version_hash(canon_bytes_v3, vhash_v2)

    commit_version_onchain(
        registry_address=registry_address,
        proposal_id=pid,
        version_hash=vhash_v3,
        action_hash=ahash_v2,
        evidence_root=eroot_v2,
        proposer_key=PK_PROPOSER,
        rpc_url=anvil_node,
    )

    # Check approved state on-chain: must now be zeroed out
    app_v3_vhash, _, _ = get_onchain_approved(registry_address, pid, rpc_url=anvil_node)
    assert app_v3_vhash == "0x" + "00" * 32, "Prior approval must be invalidated upon committing new version"
