"""Tests for public proof publishing and execution workflow (scripts/publish_proof.py).

Verifies the complete proof workflow against an isolated, ephemeral local Anvil instance:
- Preflight balance and chain verification
- Proposer commits version
- Governance approves latest version
- Verifier signs EIP-712 attestation
- B1 adversarial substitution reverts with "action mismatch"
- Legitimate execution succeeds and recipient balance increases
- Replay execution reverts with "already executed"
- Proof manifest is persisted and resumable
"""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from unittest.mock import patch

from eth_account import Account
from eth_utils import to_checksum_address
import pytest
from web3 import Web3

# Ensure scripts and backend modules are importable
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for path in (SCRIPTS_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.chain.client import (
    PK_DEPLOYER,
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_VERIFIER,
    deploy_contract,
    get_web3,
    send_tx,
)
from publish_proof import DEFAULT_AMOUNT_RAW, RECIPIENT_ADDR, publish_proof


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def proof_test_env(tmp_path_factory):
    """Launch an isolated, ephemeral Anvil node and deploy core contracts."""
    port = find_free_port()
    proc = subprocess.Popen(
        ["anvil", "--port", str(port), "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc_url = f"http://127.0.0.1:{port}"
    w3 = get_web3(rpc_url)

    # Wait for node to be responsive
    for _ in range(40):
        if w3.is_connected():
            break
        time.sleep(0.1)

    deployer_addr = Account.from_key(PK_DEPLOYER).address
    governance_addr = Account.from_key(PK_GOVERNANCE).address
    verifier_addr = Account.from_key(PK_VERIFIER).address
    proposer_addr = Account.from_key(PK_PROPOSER).address

    # Deploy core architecture matching DeployProof.s.sol
    token = deploy_contract(w3, PK_DEPLOYER, "MockToken", "USD Coin", "USDC", 10_000_000 * 10**6)
    registry = deploy_contract(w3, PK_DEPLOYER, "GovernanceRegistry", governance_addr)
    treasury = deploy_contract(w3, PK_DEPLOYER, "Treasury")
    executor = deploy_contract(
        w3,
        PK_DEPLOYER,
        "GuardedExecutor",
        registry.address,
        treasury.address,
        verifier_addr,
    )

    send_tx(w3, PK_DEPLOYER, treasury.functions.setExecutor(executor.address))
    send_tx(w3, PK_DEPLOYER, token.functions.transfer(treasury.address, 1_000_000 * 10**6))

    tmp_dir = tmp_path_factory.mktemp("proof_test")
    dep_path = tmp_dir / "deployments.proof.test.json"
    env_path = tmp_dir / ".env.test"
    proof_path = tmp_dir / "proof.test.json"

    # Write deployment manifest
    deployments = {
        "token": token.address,
        "registry": registry.address,
        "treasury": treasury.address,
        "executor": executor.address,
        "deployer": deployer_addr,
        "governance": governance_addr,
        "verifier": verifier_addr,
        "proposer": proposer_addr,
        "chain_id": w3.eth.chain_id,
        "deploy_tx_hashes": [],
    }
    with open(dep_path, "w", encoding="utf-8") as f:
        json.dump(deployments, f, indent=2)

    # Write test environment file
    env_lines = [
        f"CHAIN_ID={w3.eth.chain_id}",
        f"AMOY_RPC={rpc_url}",
        "EXPLORER_BASE=https://etherscan.io",
        f"DEPLOYER_PK={PK_DEPLOYER}",
        f"PROPOSER_PK={PK_PROPOSER}",
        f"GOVERNANCE_PK={PK_GOVERNANCE}",
        f"VERIFIER_PK={PK_VERIFIER}",
        f"DEPLOYER_ADDR={deployer_addr}",
        f"PROPOSER_ADDR={proposer_addr}",
        f"GOVERNANCE_ADDR={governance_addr}",
        f"VERIFIER_ADDR={verifier_addr}",
    ]
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")

    yield {
        "w3": w3,
        "rpc_url": rpc_url,
        "chain_id": w3.eth.chain_id,
        "token": token,
        "registry": registry,
        "treasury": treasury,
        "executor": executor,
        "dep_path": dep_path,
        "env_path": env_path,
        "proof_path": proof_path,
        "tmp_dir": tmp_dir,
    }

    proc.terminate()
    proc.wait()


def test_publish_proof_dry_run(proof_test_env):
    """Test publish_proof --dry-run prints hashes, creates no transactions, and does not alter chain state."""
    res = publish_proof(
        run_id="dryrun01",
        dry_run=True,
        rpc_url=proof_test_env["rpc_url"],
        deployments_path=proof_test_env["dep_path"],
        env_path=proof_test_env["env_path"],
        proof_path=proof_test_env["proof_path"],
    )
    assert res.get("dry_run") is True
    assert res.get("pid") == "PROP-PROOF-dryrun01"
    assert res.get("versionHash", "").startswith("0x")
    assert res.get("actionHash", "").startswith("0x")

    # Confirm proof.json was not created during dry run
    assert not proof_test_env["proof_path"].exists()


def test_publish_proof_full_flow_with_replay(proof_test_env):
    """Test full publish_proof execution: commitVersion, approve, B1 revert, valid execute, replay revert."""
    token = proof_test_env["token"]
    executor = proof_test_env["executor"]
    rec_addr = to_checksum_address(RECIPIENT_ADDR)

    bal_before = token.functions.balanceOf(rec_addr).call()

    result = publish_proof(
        run_id="e2e01",
        dry_run=False,
        with_replay=True,
        rpc_url=proof_test_env["rpc_url"],
        deployments_path=proof_test_env["dep_path"],
        env_path=proof_test_env["env_path"],
        proof_path=proof_test_env["proof_path"],
    )

    # 1. Validate result structure
    assert result["chain_id"] == proof_test_env["chain_id"]
    assert result["pid"] == "PROP-PROOF-e2e01"
    assert result["run_id"] == "e2e01"

    txs = result["transactions"]
    assert len(txs) == 5, f"Expected 5 transactions recorded, got {len(txs)}"

    # Check commitVersion
    commit_tx = txs[0]
    assert commit_tx["step"] == "commit_version"
    assert commit_tx["status"] == 1
    assert commit_tx["tx_hash"].startswith("0x")

    # Check approve
    approve_tx = txs[1]
    assert approve_tx["step"] == "approve"
    assert approve_tx["status"] == 1

    # Check B1 adversarial execute blocked
    b1_tx = txs[2]
    assert b1_tx["step"] == "b1_adversarial_execute"
    assert b1_tx["status"] == 0
    assert "action mismatch" in b1_tx["revert_reason"].lower()

    # Check valid execute
    valid_tx = txs[3]
    assert valid_tx["step"] == "valid_execute"
    assert valid_tx["status"] == 1

    # Check replay execute blocked
    replay_tx = txs[4]
    assert replay_tx["step"] == "replay_execute"
    assert replay_tx["status"] == 0
    assert "already executed" in replay_tx["revert_reason"].lower()

    # 2. Check on-chain balance deltas
    bal_after = token.functions.balanceOf(rec_addr).call()
    assert bal_after - bal_before == DEFAULT_AMOUNT_RAW, f"Recipient balance did not increase by 1M USDC: {bal_after - bal_before}"

    # 3. Check executor on-chain state
    pid_b32 = bytes.fromhex(result["pid_b32"][2:])
    assert executor.functions.executed(pid_b32).call() is True

    # 4. Check disk persistence
    assert proof_test_env["proof_path"].exists()
    with open(proof_test_env["proof_path"], "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["pid"] == "PROP-PROOF-e2e01"
    assert len(saved_data["transactions"]) == 5


def test_publish_proof_resumability(proof_test_env):
    """Test that publish_proof safely resumes an already completed run without re-submitting."""
    w3 = proof_test_env["w3"]
    block_before = w3.eth.block_number

    # Call publish_proof again with the same run_id and proof_path
    resumed = publish_proof(
        run_id="e2e01",
        dry_run=False,
        with_replay=True,
        rpc_url=proof_test_env["rpc_url"],
        deployments_path=proof_test_env["dep_path"],
        env_path=proof_test_env["env_path"],
        proof_path=proof_test_env["proof_path"],
    )

    block_after = w3.eth.block_number
    # No new blocks mined because all transactions were recognized as completed
    assert block_after == block_before
    assert len(resumed["transactions"]) == 5


def test_publish_proof_resumability_after_commit_crash(proof_test_env):
    """Simulate a crash after the commit tx is mined, then rerun; assert commit is not resent."""
    crash_proof_path = proof_test_env["tmp_dir"] / "proof.crash.json"

    # Ensure treasury has sufficient tokens
    token = proof_test_env["token"]
    treasury = proof_test_env["treasury"]
    w3 = proof_test_env["w3"]
    send_tx(w3, PK_DEPLOYER, token.functions.transfer(treasury.address, 1_000_000 * 10**6))

    # Run with a monkeypatched failure right after commit step
    real_send_tx = __import__("publish_proof").send_tx_1559
    call_count = 0

    def mock_send_tx(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call is commit_version: execute normally
            return real_send_tx(*args, **kwargs)
        # Second call is approve: simulate crash!
        raise KeyboardInterrupt("Simulated crash right after commit_version")

    with patch("publish_proof.send_tx_1559", side_effect=mock_send_tx):
        try:
            publish_proof(
                run_id="crash01",
                dry_run=False,
                with_replay=False,
                rpc_url=proof_test_env["rpc_url"],
                deployments_path=proof_test_env["dep_path"],
                env_path=proof_test_env["env_path"],
                proof_path=crash_proof_path,
            )
        except KeyboardInterrupt:
            pass

    # Verify that commit tx was recorded in proof JSON before crash
    assert crash_proof_path.exists()
    with open(crash_proof_path, "r", encoding="utf-8") as f:
        partial_data = json.load(f)
    assert len(partial_data["transactions"]) == 1
    commit_tx_hash = partial_data["transactions"][0]["tx_hash"]
    assert commit_tx_hash.startswith("0x")

    # Now rerun publish_proof normally to resume
    resumed = publish_proof(
        run_id="crash01",
        dry_run=False,
        with_replay=True,
        rpc_url=proof_test_env["rpc_url"],
        deployments_path=proof_test_env["dep_path"],
        env_path=proof_test_env["env_path"],
        proof_path=crash_proof_path,
    )

    # Commit tx must not have been resent; its recorded hash is preserved
    assert resumed["transactions"][0]["tx_hash"] == commit_tx_hash
    # All 5 transactions are now completed
    assert len(resumed["transactions"]) == 5


def test_get_proof_endpoint_published_and_missing(monkeypatch, tmp_path):
    """Test GET /proof endpoint behavior when proof.json exists and when missing/empty."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. When docs/proof.json exists with valid data
    res = client.get("/proof")
    assert res.status_code == 200
    data = res.json()
    assert "published" in data
    assert "message" in data

    # 2. When docs/proof.json is missing or mocked absent
    orig_exists = Path.exists
    def mock_exists(self):
        if "proof.json" in str(self):
            return False
        return orig_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists)

    res_missing = client.get("/proof")
    assert res_missing.status_code == 200
    data_missing = res_missing.json()
    assert data_missing["published"] is False
    assert "No proof published yet" in data_missing["message"]

