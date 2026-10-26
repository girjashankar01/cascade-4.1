"""Unit tests for Task 1: On-chain code verification, chain_id matching, and deployment manifest validation.

Tests use mocked RPC responses to verify:
1. GET /chain/status contracts_deployed logic (eth_getCode on all 4 contracts, chain_id matching)
2. scripts/write_proof_deployments.py refusal on missing broadcast, failed receipts, or missing code
3. scripts/publish_proof.py preflight checks refusal on missing file, wrong chain_id, or missing bytecode
"""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for p in (SCRIPTS_DIR, BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.api.routes import reset_chain_cache
from app.main import app
from publish_proof import preflight_checks
from write_proof_deployments import parse_broadcast_manifest


# --- GET /chain/status Tests ---

def test_chain_status_contracts_deployed_false_when_code_missing(tmp_path, monkeypatch):
    """GET /chain/status must return contracts_deployed=false when any contract has no on-chain code."""
    reset_chain_cache()
    dep_file = tmp_path / "deployments.proof.json"
    dep_data = {
        "token": "0x1111111111111111111111111111111111111111",
        "registry": "0x2222222222222222222222222222222222222222",
        "treasury": "0x3333333333333333333333333333333333333333",
        "executor": "0x4444444444444444444444444444444444444444",
        "chain_id": 11155111,
    }
    with open(dep_file, "w", encoding="utf-8") as f:
        json.dump(dep_data, f)

    monkeypatch.setattr("app.api.routes.DEPLOYMENTS_PROOF_PATH", dep_file)

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.block_number = 5000000

    def mock_get_code(addr):
        # Executor has no code
        if "44444444" in str(addr):
            return b""
        return b"\x60\x80\x60\x40"

    mock_w3.eth.get_code.side_effect = mock_get_code

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        client = TestClient(app)
        res = client.get("/chain/status")
        assert res.status_code == 200
        data = res.json()
        assert data["chain_id"] == 11155111
        assert data["contracts_deployed"] is False
        assert data["contracts"]["token"]["has_code"] is True
        assert data["contracts"]["executor"]["has_code"] is False


def test_chain_status_contracts_deployed_false_when_chain_id_mismatch(tmp_path, monkeypatch):
    """GET /chain/status must return contracts_deployed=false when deployments chain_id != connected chain_id."""
    reset_chain_cache()
    dep_file = tmp_path / "deployments.proof.json"
    dep_data = {
        "token": "0x1111111111111111111111111111111111111111",
        "registry": "0x2222222222222222222222222222222222222222",
        "treasury": "0x3333333333333333333333333333333333333333",
        "executor": "0x4444444444444444444444444444444444444444",
        "chain_id": 11155111,
    }
    with open(dep_file, "w", encoding="utf-8") as f:
        json.dump(dep_data, f)

    monkeypatch.setattr("app.api.routes.DEPLOYMENTS_PROOF_PATH", dep_file)

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 31337  # Mismatched connected chain
    mock_w3.eth.block_number = 100
    mock_w3.eth.get_code.return_value = b"\x60\x80\x60\x40"

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        client = TestClient(app)
        res = client.get("/chain/status")
        assert res.status_code == 200
        data = res.json()
        assert data["chain_id"] == 31337
        assert data["contracts_deployed"] is False


def test_chain_status_contracts_deployed_true_when_valid(tmp_path, monkeypatch):
    """GET /chain/status returns contracts_deployed=true when all contracts have code and chain_id matches."""
    reset_chain_cache()
    dep_file = tmp_path / "deployments.proof.json"
    dep_data = {
        "token": "0x1111111111111111111111111111111111111111",
        "registry": "0x2222222222222222222222222222222222222222",
        "treasury": "0x3333333333333333333333333333333333333333",
        "executor": "0x4444444444444444444444444444444444444444",
        "chain_id": 11155111,
    }
    with open(dep_file, "w", encoding="utf-8") as f:
        json.dump(dep_data, f)

    monkeypatch.setattr("app.api.routes.DEPLOYMENTS_PROOF_PATH", dep_file)

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.block_number = 5000000
    mock_w3.eth.get_code.return_value = b"\x60\x80\x60\x40"

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        client = TestClient(app)
        res = client.get("/chain/status")
        assert res.status_code == 200
        data = res.json()
        assert data["contracts_deployed"] is True
        for k in ["token", "registry", "treasury", "executor"]:
            assert data["contracts"][k]["has_code"] is True


# --- write_proof_deployments Tests ---

def test_parse_broadcast_manifest_refuses_failed_receipt(tmp_path):
    """parse_broadcast_manifest must raise ValueError if any deploy receipt has status != 1."""
    run_latest = tmp_path / "run-latest.json"
    data = {
        "transactions": [
            {
                "hash": "0xaaa",
                "contractName": "MockToken",
                "contractAddress": "0x1111111111111111111111111111111111111111",
                "receipt": {"status": "0x0"},
            }
        ]
    }
    with open(run_latest, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError) as exc:
        parse_broadcast_manifest(run_latest, chain_id="11155111")
    assert "failed with status 0x0" in str(exc.value)


def test_parse_broadcast_manifest_refuses_when_contract_missing(tmp_path):
    """parse_broadcast_manifest must raise ValueError if any of the 4 contracts is missing."""
    run_latest = tmp_path / "run-latest.json"
    data = {
        "transactions": [
            {
                "hash": "0xaaa",
                "contractName": "MockToken",
                "contractAddress": "0x1111111111111111111111111111111111111111",
                "receipt": {"status": "0x1"},
            }
        ]
    }
    with open(run_latest, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError) as exc:
        parse_broadcast_manifest(run_latest, chain_id="11155111")
    assert "missing required deployments" in str(exc.value)


def test_parse_broadcast_manifest_refuses_empty_code_on_chain(tmp_path):
    """parse_broadcast_manifest must raise ValueError if any contract has no on-chain bytecode."""
    run_latest = tmp_path / "run-latest.json"
    data = {
        "transactions": [
            {"hash": "0x1", "contractName": "MockToken", "contractAddress": "0x1111111111111111111111111111111111111111", "receipt": {"status": "0x1"}},
            {"hash": "0x2", "contractName": "GovernanceRegistry", "contractAddress": "0x2222222222222222222222222222222222222222", "receipt": {"status": "0x1"}},
            {"hash": "0x3", "contractName": "Treasury", "contractAddress": "0x3333333333333333333333333333333333333333", "receipt": {"status": "0x1"}},
            {"hash": "0x4", "contractName": "GuardedExecutor", "contractAddress": "0x4444444444444444444444444444444444444444", "receipt": {"status": "0x1"}},
        ]
    }
    with open(run_latest, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111

    def mock_get_code(addr):
        if "33333333" in str(addr):
            return b""  # Treasury has no bytecode
        return b"\x60\x80"

    mock_w3.eth.get_code.side_effect = mock_get_code

    with pytest.raises(ValueError) as exc:
        parse_broadcast_manifest(run_latest, chain_id="11155111", w3=mock_w3)
    assert "Contract Treasury at 0x3333333333333333333333333333333333333333 has no bytecode" in str(exc.value)


# --- publish_proof preflight Tests ---

def test_publish_proof_preflight_fails_missing_deployments_file(tmp_path):
    """publish_proof preflight_checks must fail if deployments.proof.json does not exist."""
    missing_path = tmp_path / "does_not_exist.json"
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111

    with pytest.raises(RuntimeError) as exc:
        preflight_checks(
            w3=mock_w3,
            expected_chain_id=11155111,
            proposer_addr="0x1111111111111111111111111111111111111111",
            governance_addr="0x2222222222222222222222222222222222222222",
            verifier_addr="0x3333333333333333333333333333333333333333",
            token_contract=None,
            treasury_addr="0x4444444444444444444444444444444444444444",
            payout_amount=1_000_000 * 10**6,
            deployments=None,
            deployments_path=missing_path,
        )
    assert "PREFLIGHT FAILED" in str(exc.value)
    assert "is missing" in str(exc.value)


def test_publish_proof_preflight_fails_chain_id_mismatch(tmp_path):
    """publish_proof preflight_checks must fail if deployments.proof.json chain_id does not match."""
    dep_path = tmp_path / "deployments.proof.json"
    dep_path.write_text("{}")
    deployments = {
        "chain_id": 84532,
        "token": "0x1111111111111111111111111111111111111111",
        "registry": "0x2222222222222222222222222222222222222222",
        "treasury": "0x3333333333333333333333333333333333333333",
        "executor": "0x4444444444444444444444444444444444444444",
    }
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_code.return_value = b"\x60\x80"
    mock_w3.eth.get_balance.return_value = 10**18

    with pytest.raises(RuntimeError) as exc:
        preflight_checks(
            w3=mock_w3,
            expected_chain_id=11155111,
            proposer_addr="0x1111111111111111111111111111111111111111",
            governance_addr="0x2222222222222222222222222222222222222222",
            verifier_addr="0x3333333333333333333333333333333333333333",
            token_contract=None,
            treasury_addr="0x4444444444444444444444444444444444444444",
            payout_amount=1_000_000 * 10**6,
            deployments=deployments,
            deployments_path=dep_path,
        )
    assert "PREFLIGHT FAILED" in str(exc.value)
    assert "chain ID 84532 does not match expected 11155111" in str(exc.value)


def test_publish_proof_preflight_fails_empty_contract_code(tmp_path):
    """publish_proof preflight_checks must fail if any contract address has no on-chain bytecode."""
    dep_path = tmp_path / "deployments.proof.json"
    dep_path.write_text("{}")
    deployments = {
        "chain_id": 11155111,
        "token": "0x1111111111111111111111111111111111111111",
        "registry": "0x2222222222222222222222222222222222222222",
        "treasury": "0x3333333333333333333333333333333333333333",
        "executor": "0x4444444444444444444444444444444444444444",
    }
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_balance.return_value = 10**18

    def mock_get_code(addr):
        if "44444444" in str(addr):
            return b""  # Executor has no bytecode
        return b"\x60\x80"

    mock_w3.eth.get_code.side_effect = mock_get_code

    with pytest.raises(RuntimeError) as exc:
        preflight_checks(
            w3=mock_w3,
            expected_chain_id=11155111,
            proposer_addr="0x1111111111111111111111111111111111111111",
            governance_addr="0x2222222222222222222222222222222222222222",
            verifier_addr="0x3333333333333333333333333333333333333333",
            token_contract=None,
            treasury_addr="0x4444444444444444444444444444444444444444",
            payout_amount=1_000_000 * 10**6,
            deployments=deployments,
            deployments_path=dep_path,
        )
    assert "PREFLIGHT FAILED" in str(exc.value)
    assert "Contract GuardedExecutor at 0x4444444444444444444444444444444444444444 has no bytecode" in str(exc.value)
