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
