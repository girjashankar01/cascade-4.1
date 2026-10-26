"""Unit and integration tests for online chain endpoints:
- GET /chain/status
- GET /chain/balances
- GET /chain/txs
- GET /chain/tx/{hash}
- Proof-mode cheat-code-free simulation
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from web3 import Web3

from app.db import get_chain_tx, get_chain_txs, init_db, record_chain_tx
from app.main import app
from app.verification.simulate import simulate_execution


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    """Provide TestClient with isolated SQLite database and clean environment."""
    db_file = tmp_path / "test_chain.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    init_db(db_file)
    client = TestClient(app)
    return client, db_file


def test_chain_status_endpoint_local_and_proof_mode(test_client, monkeypatch):
    client, _ = test_client

    # Test local mode with mocked Web3
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 31337
    mock_w3.eth.block_number = 42

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        monkeypatch.setenv("CHAIN_MODE", "local")
        resp = client.get("/chain/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain_id"] == 31337
        assert data["latest_block"] == 42
        assert data["rpc_connected"] is True
        assert data["rpc_health"] == "healthy"
        assert data["chain_mode"] == "local"
        assert "contract_addresses" in data
        assert "explorer_base" in data

    # Test proof mode on Sepolia (11155111)
    mock_w3_sepolia = MagicMock()
    mock_w3_sepolia.is_connected.return_value = True
    mock_w3_sepolia.eth.chain_id = 11155111
    mock_w3_sepolia.eth.block_number = 11994850

    with patch("app.api.routes.get_web3", return_value=mock_w3_sepolia):
        monkeypatch.setenv("CHAIN_MODE", "proof")
        resp = client.get("/chain/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain_id"] == 11155111
        assert data["latest_block"] == 11994850
        assert data["chain_mode"] == "proof"
        assert data["explorer_base"] == "https://sepolia.etherscan.io"


def test_chain_status_disconnected_node(test_client):
    client, _ = test_client
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = False

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        resp = client.get("/chain/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rpc_connected"] is False
        assert data["rpc_health"] == "disconnected"


def test_chain_balances_endpoint(test_client, monkeypatch):
    client, _ = test_client
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 11155111
    # Mock balance responses: 0.05 ETH = 50000000000000000 wei
    mock_w3.eth.get_balance.return_value = 50_000_000_000_000_000

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        monkeypatch.setenv("CHAIN_MODE", "proof")
        resp = client.get("/chain/balances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chain_id"] == 11155111
        assert data["chain_mode"] == "proof"
        assert "roles" in data
        roles = data["roles"]
        assert "deployer" in roles
        assert "proposer" in roles
        assert "governance" in roles
        assert "verifier" in roles
        assert "attacker" in roles
        assert roles["proposer"]["balance_eth"] == 0.05
        assert roles["proposer"]["balance_wei"] == 50_000_000_000_000_000
        assert "treasury" in data
        assert "token_balance" in data["treasury"]


def test_chain_balances_disconnected_fails_with_503(test_client):
    client, _ = test_client
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = False

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        resp = client.get("/chain/balances")
        assert resp.status_code == 503
        assert "Cannot connect" in resp.json()["detail"]


def test_chain_txs_and_single_tx_endpoints(test_client):
    client, db_file = test_client

    # 1. Initially empty
    resp = client.get("/chain/txs")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Record transactions in chain_txs table
    tx1 = {
        "tx_hash": "0x1111111111111111111111111111111111111111111111111111111111111111",
        "run_id": "run-alpha",
        "step": "commit_version",
        "role": "proposer",
        "from": "0xbec46Ec04538B467EAc77019185992Bc0e828775",
        "to": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        "status": "success",
        "revert_reason": None,
        "block_number": 100,
        "gas_used": 150000,
        "effective_gas_price": 2000000000,
        "fee_eth": 0.0003,
        "timestamp": "2026-10-26T07:00:00Z",
        "explorer_url": "https://sepolia.etherscan.io/tx/0x1111",
    }
    tx2 = {
        "tx_hash": "0x2222222222222222222222222222222222222222222222222222222222222222",
        "run_id": "run-alpha",
        "step": "b1_adversarial_execute",
        "role": "attacker",
        "from": "0xbec46Ec04538B467EAc77019185992Bc0e828775",
        "to": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
        "status": "reverted",
        "revert_reason": "action mismatch",
        "block_number": 101,
        "gas_used": 120000,
        "effective_gas_price": 2500000000,
        "fee_eth": 0.0003,
        "timestamp": "2026-10-26T07:05:00Z",
        "explorer_url": "https://sepolia.etherscan.io/tx/0x2222",
    }
    tx3 = {
        "tx_hash": "0x3333333333333333333333333333333333333333333333333333333333333333",
        "run_id": "run-beta",
        "step": "valid_execute",
        "role": "proposer",
        "from": "0xbec46Ec04538B467EAc77019185992Bc0e828775",
        "to": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
        "status": "success",
        "revert_reason": None,
        "block_number": 102,
        "gas_used": 200000,
        "effective_gas_price": 2000000000,
        "fee_eth": 0.0004,
        "timestamp": "2026-10-26T07:10:00Z",
        "explorer_url": "https://sepolia.etherscan.io/tx/0x3333",
    }
    record_chain_tx(tx1, db_file)
    record_chain_tx(tx2, db_file)
    record_chain_tx(tx3, db_file)

    # 3. Query all transactions (ordered newest first: tx3, tx2, tx1)
    resp = client.get("/chain/txs")
    assert resp.status_code == 200
    txs = resp.json()
    assert len(txs) == 3
    assert txs[0]["tx_hash"] == tx3["tx_hash"]
    assert txs[1]["tx_hash"] == tx2["tx_hash"]
    assert txs[2]["tx_hash"] == tx1["tx_hash"]

    # 4. Filter by run_id
    resp_filtered = client.get("/chain/txs?run_id=run-alpha")
    assert resp_filtered.status_code == 200
    alpha_txs = resp_filtered.json()
    assert len(alpha_txs) == 2
    assert all(t["run_id"] == "run-alpha" for t in alpha_txs)

    # 5. Test limit
    resp_limit = client.get("/chain/txs?limit=1")
    assert resp_limit.status_code == 200
    assert len(resp_limit.json()) == 1

    # 6. Query single transaction by hash
    resp_single = client.get(f"/chain/tx/{tx2['tx_hash']}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["tx_hash"] == tx2["tx_hash"]
    assert single_data["status"] == "reverted"
    assert single_data["revert_reason"] == "action mismatch"
    assert single_data["role"] == "attacker"

    # 7. Query unknown transaction hash
    resp_404 = client.get("/chain/tx/0x9999999999999999999999999999999999999999999999999999999999999999")
    assert resp_404.status_code == 404


def test_simulation_in_proof_mode_cheat_code_free(monkeypatch):
    """Verify that in proof mode, simulate_execution uses on-chain eth_call and zero Anvil cheat codes."""
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_balance.return_value = 10**18
    mock_w3.eth.get_storage_at.return_value = b"\x00" * 32
    mock_w3.eth.call.return_value = b""

    # Track provider make_request calls to ensure zero cheat codes are called
    cheat_code_calls = []

    def mock_make_request(method, params):
        cheat_code_calls.append(method)
        return {"result": True}

    mock_w3.provider.make_request.side_effect = mock_make_request

    # Mock contract calls
    mock_treasury = MagicMock()
    mock_treasury.functions.exec.return_value.call.return_value = b""
    mock_token = MagicMock()
    mock_token.functions.balanceOf.return_value.call.return_value = 10_000_000 * 10**6
    mock_token.functions.allowance.return_value.call.return_value = 0

    def mock_contract(address, abi):
        for item in abi:
            if item.get("name") == "exec":
                return mock_treasury
        return mock_token

    mock_w3.eth.contract.side_effect = mock_contract

    monkeypatch.setenv("CHAIN_MODE", "proof")
    amount = 1_000_000 * 10**6
    manifest = {
        "action": {
            "type": "payout",
            "recipient": "0x9965507D1a55BCC6475675304Ca994970De97744",
            "amount": amount,
        }
    }
    # Calldata for ERC20 transfer(address,uint256)
    recip_clean = "9965507d1a55bcc6475675304ca994970de97744".rjust(64, "0")
    amount_clean = hex(amount)[2:].rjust(64, "0")
    calldata = f"0xa9059cbb{recip_clean}{amount_clean}"

    sim = simulate_execution(
        w3=mock_w3,
        treasury_address="0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
        executor_address="0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
        target="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        value=0,
        data=calldata,
        manifest=manifest,
    )

    # 1. Assert cheat code methods were NEVER called
    assert "evm_snapshot" not in cheat_code_calls
    assert "anvil_impersonateAccount" not in cheat_code_calls
    assert "anvil_setBalance" not in cheat_code_calls
    assert "evm_revert" not in cheat_code_calls

    # 2. Assert valid simulation result returned
    assert sim["success"] is True
    assert sim["tx_status"] == 1
    assert sim["restoration_verified"] is True
    assert sim["treasury_outflow"] == 1_000_000 * 10**6
    assert sim["recipient_inflow"] == 1_000_000 * 10**6
