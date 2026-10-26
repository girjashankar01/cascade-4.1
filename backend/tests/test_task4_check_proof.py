"""Tests for scripts/check_proof.py post-run proof checker."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for p in (SCRIPTS_DIR, BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from check_proof import (
    TOPIC_EXECUTION_SUCCEEDED,
    TOPIC_PROPOSAL_APPROVED,
    TOPIC_VERSION_COMMITTED,
    check_proof,
)


def test_check_proof_valid_flow(tmp_path):
    proof_file = tmp_path / "proof.json"
    env_file = tmp_path / ".env.test"

    vhash = "0x1111111111111111111111111111111111111111111111111111111111111111"
    ahash = "0x2222222222222222222222222222222222222222222222222222222222222222"
    eroot = "0x3333333333333333333333333333333333333333333333333333333333333333"

    tx1 = "0xaaaa111111111111111111111111111111111111111111111111111111111111"
    tx2 = "0xaaaa222222222222222222222222222222222222222222222222222222222222"
    tx3 = "0xaaaa333333333333333333333333333333333333333333333333333333333333"
    tx4 = "0xaaaa444444444444444444444444444444444444444444444444444444444444"
    tx5 = "0xaaaa555555555555555555555555555555555555555555555555555555555555"

    proof_data = {
        "chain_id": 11155111,
        "pid": "PROP-PROOF-test01",
        "versionHash": vhash,
        "actionHash": ahash,
        "evidenceRoot": eroot,
        "transactions": [
            {"step": "commit_version", "status": 1, "tx_hash": tx1, "block_number": 100, "gas_used": 150000, "explorer_url": f"https://sepolia.etherscan.io/tx/{tx1}"},
            {"step": "approve", "status": 1, "tx_hash": tx2, "block_number": 101, "gas_used": 120000, "explorer_url": f"https://sepolia.etherscan.io/tx/{tx2}"},
            {"step": "adversarial_b1", "status": 0, "tx_hash": tx3, "block_number": 102, "gas_used": 80000, "revert_reason": "Execution reverted: action mismatch", "explorer_url": f"https://sepolia.etherscan.io/tx/{tx3}"},
            {"step": "execute_valid", "status": 1, "tx_hash": tx4, "block_number": 103, "gas_used": 200000, "explorer_url": f"https://sepolia.etherscan.io/tx/{tx4}"},
            {"step": "replay_attack", "status": 0, "tx_hash": tx5, "block_number": 104, "gas_used": 60000, "revert_reason": "Execution reverted: already executed", "explorer_url": f"https://sepolia.etherscan.io/tx/{tx5}"},
        ],
        "balances_before": {
            "treasury_token_balance": 1_000_000 * 10**6,
            "recipient_token_balance": 0,
            "roles": {"attacker": {"token": 0}},
        },
        "balances_after": {
            "treasury_token_balance": 0,
            "recipient_token_balance": 1_000_000 * 10**6,
            "roles": {"attacker": {"token": 0}},
        },
    }
    proof_file.write_text(json.dumps(proof_data, indent=2))

    env_file.write_text(
        "CHAIN_ID=11155111\n"
        "AMOY_RPC=https://rpc.sepolia.org\n"
        "EXPLORER_BASE=https://sepolia.etherscan.io\n"
    )

    # Encode event log data
    import eth_abi
    commit_data = "0x" + eth_abi.encode(["bytes32", "bytes32", "bytes32", "address"], [bytes.fromhex(vhash[2:]), bytes.fromhex(ahash[2:]), bytes.fromhex(eroot[2:]), "0x90F79bf6EB2c4f870365E785982E1f101E93b906"]).hex()
    approve_data = "0x" + eth_abi.encode(["bytes32", "bytes32"], [bytes.fromhex(ahash[2:]), bytes.fromhex(eroot[2:])]).hex()
    exec_data = "0x" + eth_abi.encode(["uint256", "bytes32"], [0, bytes.fromhex(ahash[2:])]).hex()

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111

    receipts = {
        tx1: {"status": 1, "blockNumber": 100, "gasUsed": 150000, "logs": [{"topics": [bytes.fromhex(TOPIC_VERSION_COMMITTED[2:]), b"\x00"*32, b"\x00"*32], "data": commit_data}]},
        tx2: {"status": 1, "blockNumber": 101, "gasUsed": 120000, "logs": [{"topics": [bytes.fromhex(TOPIC_PROPOSAL_APPROVED[2:]), b"\x00"*32, bytes.fromhex(vhash[2:])], "data": approve_data}]},
        tx3: {"status": 0, "blockNumber": 102, "gasUsed": 80000, "logs": []},
        tx4: {"status": 1, "blockNumber": 103, "gasUsed": 200000, "logs": [{"topics": [bytes.fromhex(TOPIC_EXECUTION_SUCCEEDED[2:]), b"\x00"*32, b"\x00"*32], "data": exec_data}]},
        tx5: {"status": 0, "blockNumber": 104, "gasUsed": 60000, "logs": []},
    }

    def mock_get_receipt(h):
        return receipts.get(h)

    mock_w3.eth.get_transaction_receipt.side_effect = mock_get_receipt

    with patch("check_proof.scan_for_secrets", return_value=[]):
        passed = check_proof(proof_path=proof_file, env_path=env_file, w3_override=mock_w3)
        assert passed is True


def test_check_proof_fails_on_status_discrepancy(tmp_path):
    proof_file = tmp_path / "proof.json"
    env_file = tmp_path / ".env.test"

    tx1 = "0xaaaa111111111111111111111111111111111111111111111111111111111111"
    proof_data = {
        "chain_id": 11155111,
        "pid": "PROP-PROOF-test02",
        "transactions": [
            {"step": "commit_version", "status": 1, "tx_hash": tx1, "block_number": 100, "gas_used": 150000, "explorer_url": f"https://sepolia.etherscan.io/tx/{tx1}"},
        ],
    }
    proof_file.write_text(json.dumps(proof_data))
    env_file.write_text("CHAIN_ID=11155111\nAMOY_RPC=https://rpc.sepolia.org\n")

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    # Receipt shows revert (0) instead of recorded 1!
    mock_w3.eth.get_transaction_receipt.return_value = {"status": 0, "blockNumber": 100, "gasUsed": 150000, "logs": []}

    with patch("check_proof.scan_for_secrets", return_value=[]):
        passed = check_proof(proof_path=proof_file, env_path=env_file, w3_override=mock_w3)
        assert passed is False
