"""Tests for Stage 5 scenario runner endpoint and auxiliary read endpoints."""

from pathlib import Path
import socket
import subprocess
import time
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from web3 import Web3

from app.db import get_db_connection, init_db
from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


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


@pytest.fixture
def client_env(anvil_node: str, tmp_path: Path):
    db_file = tmp_path / "test_stage5.db"
    db_path = str(db_file)
    init_db(db_path)

    import app.db as db_mod
    orig_db_path = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_file

    client = TestClient(app)

    yield {
        "client": client,
        "rpc_url": anvil_node,
        "db_path": db_path,
    }

    db_mod.DEFAULT_DB_PATH = orig_db_path


def test_scenario_c_reset_and_seed(client_env):
    """Test POST /scenarios/C/run cleans state and seeds PROP-002."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    resp = client.post("/scenarios/C/run", json={"rpc_url": rpc_url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "C"
    assert data["success"] is True
    assert "deployments" in data
    assert data["deployments"]["seeded_proposal_id"] == "PROP-002"
    assert len(data["steps"]) >= 3


def test_scenario_a_valid_payout_run(client_env):
    """Test POST /scenarios/A/run performs full verification, attestation, and on-chain execution."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    # First reset & seed
    reset_resp = client.post("/scenarios/C/run", json={"rpc_url": rpc_url})
    assert reset_resp.status_code == 200

    resp = client.post("/scenarios/A/run", json={"rpc_url": rpc_url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "A"
    assert data["success"] is True
    assert data["verdict"] == "VERIFIED"
    assert data["execution_result"] is not None
    assert data["execution_result"]["status"] == 1
    assert data["state_deltas"] is not None
    assert data["state_deltas"]["amount_raw"] == "1000000000000"


def test_scenario_b1_substituted_payout_run(client_env):
    """Test POST /scenarios/B1/run detects action mismatch and blocks execution."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    resp = client.post("/scenarios/B1/run", json={"rpc_url": rpc_url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "B1"
    assert data["success"] is True
    assert data["blocked_as_expected"] is True
    assert data["verdict"] == "MISMATCH"
    assert data["verification_report"]["attestation_sig"] is None
    assert data["execution_result"] is None


def test_scenario_invalid_name(client_env):
    """Test POST /scenarios/invalid/run returns HTTP 400."""
    client = client_env["client"]
    resp = client.post("/scenarios/invalid/run", json={})
    assert resp.status_code == 400
    assert "unknown scenario" in resp.json()["detail"].lower()


def test_sources_and_verifications_read_endpoints(client_env):
    """Test GET /sources, GET /sources/{id}, and GET /verifications/{pid}."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    # Run Scenario C to have seeded data
    client.post("/scenarios/C/run", json={"rpc_url": rpc_url})

    # Test GET /sources
    src_resp = client.get("/sources")
    assert src_resp.status_code == 200
    sources = src_resp.json()
    assert len(sources) >= 1
    src_id = sources[0]["id"]

    # Test GET /sources/{id}
    detail_resp = client.get(f"/sources/{src_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == src_id
    assert "extracted_pages" in detail
    assert "1" in detail["extracted_pages"]

    # Run Scenario A so we have a verification
    client.post("/scenarios/A/run", json={"rpc_url": rpc_url})

    # Test GET /verifications/PROP-002
    v_resp = client.get("/verifications/PROP-002")
    assert v_resp.status_code == 200
    v_list = v_resp.json()
    assert len(v_list) >= 1
    latest_v = v_list[0]
    assert latest_v["verdict"] == "VERIFIED"
    assert latest_v["executed"] is True
    assert "rules" in latest_v
    assert "diff" in latest_v
    assert "simulation" in latest_v

    # Test GET /deployments
    dep_resp = client.get("/deployments")
    assert dep_resp.status_code == 200
    dep = dep_resp.json()
    assert "token" in dep
    assert "registry" in dep
    assert "treasury" in dep
    assert "executor" in dep


def test_rule_registry_specification_consistency(client_env):
    """Test that evaluated rules match the authoritative CASCADE specification (R1-R7, R9; no R8)."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    # Reset & seed then verify
    client.post("/scenarios/C/run", json={"rpc_url": rpc_url})
    v_resp = client.post("/scenarios/A/run", json={"rpc_url": rpc_url})
    assert v_resp.status_code == 200
    data = v_resp.json()

    rules = data["verification_report"]["rules"]
    rule_ids = [r["rule_id"] for r in rules]
    # The specification in docs/dao-build-guide-final.md Section 5.6 defines:
    # R1 (version), R2 (action), R3 (token outflow), R4 (unexpected balance increase),
    # R5 (allowance change), R6 (implementation slot), R7 (selector whitelist), R9 (owner/role change).
    # Rule R8 was never defined in the specification.
    assert rule_ids == ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R9"]

    for r in rules:
        assert r["status"] in ("PASS", "FAIL", "UNCERTAIN", "NOT_APPLICABLE", "NOT_RUN")
        assert len(r["explanation"]) > 0
        assert isinstance(r["evidence"], dict)


def test_scenario_b1_cannot_bypass_execution_endpoint(client_env):
    """Test that Scenario B1's substituted calldata cannot be executed through the /execute API."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    # Run Scenario B1
    b1_resp = client.post("/scenarios/B1/run", json={"rpc_url": rpc_url})
    assert b1_resp.status_code == 200
    b1_data = b1_resp.json()
    assert b1_data["verdict"] == "MISMATCH"
    assert b1_data["blocked_as_expected"] is True
    assert b1_data["outcome_classification"] == "Rejected before submission & on-chain transaction reverted"
    assert b1_data["balances_verified"]["treasury_protected"] is True
    assert b1_data["balances_verified"]["attacker_zero_gain"] is True

    # Attempt to bypass verifier by calling POST /execute directly
    from app.manifest.hashes import encode_erc20_transfer_calldata
    attacker_calldata = "0x" + encode_erc20_transfer_calldata(
        "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", 2_000_000 * 10**6
    ).hex()

    dep = client.get("/deployments").json()
    exec_resp = client.post(
        "/execute/PROP-B1",
        json={
            "proposal_id": "PROP-B1",
            "target": dep["token"],
            "value": 0,
            "data": attacker_calldata,
            "executor_address": dep["executor"],
            "registry_address": dep["registry"],
            "rpc_url": rpc_url,
        },
    )
    # Must fail with HTTP 400 because actionHash mismatches and no VERIFIED attestation exists
    assert exec_resp.status_code == 400
    detail = exec_resp.json()["detail"].lower()
    assert "actionhash" in detail or "no verified attestation" in detail


def test_unsafe_chain_id_rejected():
    """Test that non-local chain IDs are strictly rejected to prevent accidental production execution."""
    from unittest.mock import MagicMock
    from app.scenarios.runner import verify_local_chain

    mock_w3 = MagicMock()
    # Mainnet chain ID is 1
    mock_w3.eth.chain_id = 1
    with pytest.raises(ValueError, match="Refusing to execute scenario against non-local chain ID 1"):
        verify_local_chain(mock_w3)

    # Sepolia chain ID is 11155111
    mock_w3.eth.chain_id = 11155111
    with pytest.raises(ValueError, match="Refusing to execute scenario against non-local chain ID 11155111"):
        verify_local_chain(mock_w3)

    # Local Anvil (31337) and Hardhat (1337) must pass
    mock_w3.eth.chain_id = 31337
    verify_local_chain(mock_w3)  # No exception
    mock_w3.eth.chain_id = 1337
    verify_local_chain(mock_w3)  # No exception


def test_concurrent_scenario_runs_locked(client_env):
    """Test that concurrent scenario execution is safely locked."""
    from app.scenarios.runner import _SCENARIO_LOCK, execute_scenario

    # Artificially acquire the scenario lock
    acquired = _SCENARIO_LOCK.acquire(blocking=False)
    assert acquired is True
    try:
        # Second call must raise ValueError due to lock contention
        with pytest.raises(ValueError, match="Another scenario run is currently in progress"):
            execute_scenario(name="A")
    finally:
        _SCENARIO_LOCK.release()


def test_health_endpoint_live_chain_status(client_env):
    """Test that GET /health inspects Web3 connectivity and returns live chain information."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "rpc_connected" in data
    assert "chain_id" in data
    assert "block_number" in data


def test_scenario_b3_evil_upgrade_blocked(client_env):
    """Test POST /scenarios/B3/run detects undeclared sweep() selector and blocks UUPS upgrade."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    client.post("/scenarios/C/run", json={"rpc_url": rpc_url})

    resp = client.post("/scenarios/B3/run", json={"rpc_url": rpc_url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "B3"
    assert data["success"] is True
    assert data["blocked_as_expected"] is True
    assert data["verdict"] == "MISMATCH"
    assert data["verification_report"]["attestation_sig"] is None
    assert data["slot_verified"]["slot_protected"] is True

    # Rule R7 must be the failing rule
    rules = data["verification_report"]["rules"]
    r7 = next(r for r in rules if r["rule_id"] == "R7")
    assert r7["status"] == "FAIL"
    assert "0x35faa416" in r7["evidence"]["undeclared_selectors"]


def test_scenario_b2_benign_upgrade_executed(client_env):
    """Test POST /scenarios/B2/run verifies and executes benign V2 UUPS upgrade."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    client.post("/scenarios/C/run", json={"rpc_url": rpc_url})

    resp = client.post("/scenarios/B2/run", json={"rpc_url": rpc_url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "B2"
    assert data["success"] is True
    assert data["verdict"] == "VERIFIED"
    assert data["verification_report"]["attestation_sig"] is not None
    assert data["slot_verified"]["version"] == "2.0.0"


def test_coi_endpoint(client_env):
    """Test GET /proposals/{pid}/coi returns wallet provenance and conflict-of-interest analysis."""
    client = client_env["client"]
    resp = client.get("/proposals/PROP-002/coi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["proposal_id"] == "PROP-002"
    assert data["has_linkage"] is True
    assert len(data["shortest_path"]) >= 2
    assert len(data["nodes"]) >= 3
    assert len(data["edges"]) >= 2
    assert len(data["undisclosed_connections"]) >= 1


def test_prop001_conflict_detection(client_env):
    """Test that Scenario C seeds PROP-001 with genuine conflicting sources ($5.0M vs $5.8M)."""
    client = client_env["client"]
    rpc_url = client_env["rpc_url"]

    client.post("/scenarios/C/run", json={"rpc_url": rpc_url})

    resp = client.get("/claims/PROP-001")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["conflicts"]) >= 1
    cnf = data["conflicts"][0]
    assert cnf["field"] == "amount"
    assert cnf["display_value_a"] == "$5.0M"
    assert cnf["display_value_b"] == "$5.8M"
    assert cnf["status"] == "CONFLICT"
