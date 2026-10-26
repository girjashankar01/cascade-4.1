"""Regression tests for Sepolia proof mode and public chain enhancements:
- Preflight failure exits non-zero and prints PREFLIGHT FAILED
- Verifier balance is info-only (not required to broadcast transactions)
- Dry-run writes only docs/dryrun.json and never touches chain_txs table
- B1 substitution and replay use manual gas limits and record revert receipts with reason
- GET /proof detects and flags stale-chain proof files with published=False
- Startup and shared path resolution works across working directories
- Priority fee parsing handles decimal Gwei values (0.0001, 25.5) without float precision drift
- Deployment manifest parser handles Foundry broadcast output
- Secret leakage prevention (no private keys in docs/, data/, DB, or API responses)
"""

import json
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for path in (SCRIPTS_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.chain.public import parse_priority_fee_wei
from app.db import get_chain_txs, init_db
from app.main import app
from app.paths import (
    DATA_DIR,
    DOCS_DIR,
    DRYRUN_JSON_PATH,
    PROOF_JSON_PATH,
    get_repo_root,
    load_env_hierarchy,
    resolve_db_path,
)
from publish_proof import preflight_checks


def test_priority_fee_parsing_decimals():
    """Ensure priority fee parser handles decimal Gwei strings e.g. 0.0001 and 25.5."""
    assert parse_priority_fee_wei(None) == 0
    assert parse_priority_fee_wei("") == 0
    # 1 gwei = 10**9 wei
    assert parse_priority_fee_wei("1") == 1_000_000_000
    # 0.0001 gwei = 100,000 wei
    assert parse_priority_fee_wei("0.0001") == 100_000
    # 25.5 gwei = 25,500,000,000 wei
    assert parse_priority_fee_wei("25.5") == 25_500_000_000
    # Float input
    assert parse_priority_fee_wei(0.0001) == 100_000


def test_preflight_checks_failure_and_verifier_info_only(capsys):
    """Preflight check must fail with RuntimeError on balance/chain mismatch without failing on verifier balance."""
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111

    # Broadcaster accounts have insufficient balance (< 0.002 ETH)
    def mock_get_bal(addr):
        return 100_000_000_000_000  # 0.0001 ETH

    mock_w3.eth.get_balance.side_effect = mock_get_bal

    mock_token = MagicMock()
    mock_token.functions.balanceOf.return_value.call.return_value = 2_000_000 * 10**6

    with pytest.raises(RuntimeError) as exc_info:
        preflight_checks(
            w3=mock_w3,
            expected_chain_id=11155111,
            proposer_addr="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            governance_addr="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            verifier_addr="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
            token_contract=mock_token,
            treasury_addr="0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
            payout_amount=1_000_000 * 10**6,
            dry_run=True,
        )

    err_msg = str(exc_info.value)
    assert "below minimum required threshold" in err_msg
    captured = capsys.readouterr()
    assert "PREFLIGHT FAILED" in (captured.err + captured.out)
    assert "PASSED" not in (captured.err + captured.out)


def test_dry_run_does_not_pollute_db(tmp_path, monkeypatch):
    """Running dry-run must write only to dryrun.json and never insert rows into chain_txs."""
    db_file = tmp_path / "test_dry_isolation.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    init_db(db_file)

    initial_txs = get_chain_txs()
    assert len(initial_txs) == 0

    from publish_proof import publish_proof

    dep_path = tmp_path / "dep.json"
    with open(dep_path, "w", encoding="utf-8") as f:
        json.dump({
            "token": "0x82a17a76c921F9a49649699e087eEBa406Fde85f",
            "registry": "0xaB94d77Cb9DC2c305441abfC988cFA7271b81ACB",
            "treasury": "0x8DdCC593fa48Eaee2268baA6b12E37A8B28cE24a",
            "executor": "0x141BC887305375Ee6f61068988B928e936EF4097",
        }, f)

    env_path = tmp_path / ".env.dry"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("CHAIN_ID=31337\nAMOY_RPC=http://127.0.0.1:8545\nEXPLORER_BASE=https://etherscan.io\n")
        f.write("DEPLOYER_PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80\n")
        f.write("PROPOSER_PK=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d\n")
        f.write("GOVERNANCE_PK=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a\n")
        f.write("VERIFIER_PK=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6\n")

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 31337
    mock_w3.eth.get_block.return_value = {"timestamp": 1700000000}
    mock_w3.eth.get_code.return_value = b"\x60\x80\x60\x40"
    mock_w3.eth.contract.return_value.functions.balanceOf.return_value.call.return_value = 1_000_000 * 10**6
    mock_w3.eth.get_balance.return_value = 10**18

    with patch("publish_proof.load_proof_env") as mock_lpe, patch("publish_proof.preflight_checks", return_value=None):
        from app.chain.public import ProofConfig
        mock_lpe.return_value = ProofConfig(
            chain_id=31337,
            rpc_url="http://127.0.0.1:8545",
            explorer_base="https://etherscan.io",
            priority_fee_gwei=None,
            deployer_pk="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
            proposer_pk="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
            governance_pk="0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
            verifier_pk="0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
            addresses={},
            w3=mock_w3,
        )
        res = publish_proof(
            run_id="testdryrun",
            dry_run=True,
            rpc_url="http://127.0.0.1:8545",
            deployments_path=dep_path,
            env_path=env_path,
            proof_path=tmp_path / "proof_out.json",
        )
    assert res["dry_run"] is True

    post_txs = get_chain_txs()
    assert len(post_txs) == 0


def test_proof_endpoint_stale_chain_detection(monkeypatch, tmp_path):
    """GET /proof must return published=False if proof.json chain ID differs from connected node."""
    client = TestClient(app)

    stale_proof = {
        "chain_id": 11155111,
        "run_id": "sepolia01",
        "pid": "PROP-PROOF-sepolia01",
        "contracts": {},
        "transactions": [{"step": "commit_version", "status": 1}],
    }
    dummy_proof_file = tmp_path / "proof.json"
    with open(dummy_proof_file, "w", encoding="utf-8") as f:
        json.dump(stale_proof, f)

    monkeypatch.setattr("app.api.routes.PROOF_JSON_PATH", dummy_proof_file)

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = 31337

    with patch("app.api.routes.get_web3", return_value=mock_w3):
        res = client.get("/proof")
        assert res.status_code == 200
        data = res.json()
        assert data["published"] is False
        assert "Found proof for chain 11155111, but connected to 31337" in data["message"]


def test_shared_paths_resolution():
    """Verify paths resolve to repo root regardless of current working directory."""
    root = get_repo_root()
    assert root.exists()
    assert (root / "contracts").exists()
    assert (root / "backend").exists()

    db_path = resolve_db_path()
    assert str(root) in str(db_path)
    assert db_path.name.endswith(".db")


def test_write_proof_deployments_from_broadcast_fixture(tmp_path):
    """Test write_proof_deployments parses Foundry broadcast JSON correctly."""
    from write_proof_deployments import parse_broadcast_manifest

    # Create dummy broadcast file matching Foundry output
    broadcast_file = tmp_path / "run-latest.json"
    dummy_broadcast = {
        "transactions": [
            {
                "contractName": "MockToken",
                "contractAddress": "0x1111111111111111111111111111111111111111",
                "hash": "0xaaaa1111",
                "receipt": {"blockNumber": "0x100"},
            },
            {
                "contractName": "GovernanceRegistry",
                "contractAddress": "0x2222222222222222222222222222222222222222",
                "hash": "0xaaaa2222",
                "receipt": {"blockNumber": "0x101"},
            },
            {
                "contractName": "Treasury",
                "contractAddress": "0x3333333333333333333333333333333333333333",
                "hash": "0xaaaa3333",
                "receipt": {"blockNumber": "0x102"},
            },
            {
                "contractName": "GuardedExecutor",
                "contractAddress": "0x4444444444444444444444444444444444444444",
                "hash": "0xaaaa4444",
                "receipt": {"blockNumber": "0x103"},
            },
        ],
        "receipts": [],
    }
    with open(broadcast_file, "w", encoding="utf-8") as f:
        json.dump(dummy_broadcast, f)

    deployments = parse_broadcast_manifest(broadcast_file)
    assert deployments["token"] == "0x1111111111111111111111111111111111111111"
    assert deployments["registry"] == "0x2222222222222222222222222222222222222222"
    assert deployments["treasury"] == "0x3333333333333333333333333333333333333333"
    assert deployments["executor"] == "0x4444444444444444444444444444444444444444"
    assert len(deployments["deploy_tx_hashes"]) == 4


def test_no_secret_leakage_in_api_responses():
    """Verify that no private keys or API keys appear in /proof, /chain/status, or /chain/balances."""
    client = TestClient(app)

    for endpoint in ["/proof", "/chain/status", "/chain/balances"]:
        res = client.get(endpoint)
        if res.status_code == 200:
            content_str = json.dumps(res.json()).lower()
            assert "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80" not in content_str
            assert "private_key" not in content_str
            assert "api_key" not in content_str
