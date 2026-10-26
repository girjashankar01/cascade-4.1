"""End-to-end integration tests for Scenario A, Scenario B1, TOCTOU protection, and adversarial tests."""

from pathlib import Path
import socket
import subprocess
import time
from typing import Generator
import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from web3 import Web3

from app.chain.attest import VERIFIED, sign_attestation
from app.chain.client import (
    PK_ATTACKER,
    PK_DEPLOYER,
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_VERIFIER,
    deploy_contract,
    proposal_id_to_bytes32,
    send_tx,
)
from app.claims.schema import ClaimStatus
from app.db import get_db_connection, init_db
from app.ingestion.pdf import ingest_source
from app.main import app
from app.manifest.builder import confirm_manifest_with_signature
from app.manifest.hashes import encode_erc20_transfer_calldata
from app.verification.verify import (
    VERDICT_MISMATCH,
    VERDICT_VERIFIED,
    verify_proposal_transaction,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
RECIPIENT_ADDR = "0x9965507D1a55BCC6475675304Ca994970De97744"
ATTACKER_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
PAYOUT_AMOUNT = 1_000_000 * 10**6  # 1M USDC


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
def test_setup(anvil_node: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test_scenarios.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    db_path = str(db_file)
    init_db(db_path)

    import app.db as db_mod
    orig_db_path = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_file

    w3 = Web3(Web3.HTTPProvider(anvil_node))
    gov_addr = Account.from_key(PK_GOVERNANCE).address
    verifier_addr = Account.from_key(PK_VERIFIER).address

    token = deploy_contract(w3, PK_DEPLOYER, "MockToken", "USD Coin", "USDC", 10_000_000 * 10**6)
    registry = deploy_contract(w3, PK_DEPLOYER, "GovernanceRegistry", gov_addr)
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

    client = TestClient(app)

    yield {
        "w3": w3,
        "client": client,
        "token": token,
        "registry": registry,
        "treasury": treasury,
        "executor": executor,
        "db_path": db_path,
        "rpc_url": anvil_node,
    }

    db_mod.DEFAULT_DB_PATH = orig_db_path


def seed_and_approve_proposal(env: dict, pid: str = "PROP-002") -> dict:
    w3 = env["w3"]
    token = env["token"]
    registry = env["registry"]
    db_path = env["db_path"]

    pdf_bytes = (FIXTURES_DIR / "clean_proposal_v1.pdf").read_bytes()
    src_meta = ingest_source(raw_bytes=pdf_bytes, filename="clean_proposal_v1.pdf", db_path=db_path)
    src_id = src_meta["id"]

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES (?, ?, 'amount', '1000000', '$1.0M', 'grant payout of $1.0M (1,000,000 USDC)', ?, 1, 0.95, ?, '{}', datetime('now'))
            """,
            (f"clm_{pid}_amount", pid, src_id, ClaimStatus.GROUNDED.value),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES (?, ?, 'recipient', ?, ?, 'designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744', ?, 1, 0.95, ?, '{}', datetime('now'))
            """,
            (f"clm_{pid}_recipient", pid, RECIPIENT_ADDR.lower(), RECIPIENT_ADDR, src_id, ClaimStatus.GROUNDED.value),
        )

    confirmed = confirm_manifest_with_signature(
        proposal_id=pid,
        version=1,
        proposer_private_key=PK_PROPOSER,
        token_address=token.address,
        token_decimals=6,
        source_id=src_id,
        db_path=db_path,
    )

    pid_b32 = proposal_id_to_bytes32(pid)
    vhash_bytes = bytes.fromhex(confirmed["version_hash"][2:])
    ahash_bytes = bytes.fromhex(confirmed["action_hash"][2:])
    eroot_bytes = bytes.fromhex(confirmed["evidence_root"][2:])

    # Proposer commits on registry
    send_tx(w3, PK_PROPOSER, registry.functions.commitVersion(pid_b32, vhash_bytes, ahash_bytes, eroot_bytes))
    # Governance approves on registry
    send_tx(w3, PK_GOVERNANCE, registry.functions.approve(pid_b32, vhash_bytes))

    return confirmed


def test_scenario_a_valid_payout_execution(test_setup):
    """Scenario A: Valid approved payout -> VERIFIED -> attestation -> execute -> exact balance transfer."""
    env = test_setup
    w3 = env["w3"]
    token = env["token"]
    registry = env["registry"]
    treasury = env["treasury"]
    executor = env["executor"]
    client = env["client"]

    pid = "PROP-002"
    confirmed = seed_and_approve_proposal(env, pid=pid)

    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    # 1. Call POST /verify
    verify_resp = client.post(
        f"/verify/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "registry_address": registry.address,
            "treasury_address": treasury.address,
            "executor_address": executor.address,
            "verifier_private_key": PK_VERIFIER,
            "ttl_seconds": 3600,
            "rpc_url": env["rpc_url"],
        },
    )

    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["verdict"] == VERDICT_VERIFIED
    assert vdata["all_passed"] is True
    assert vdata["attestation_sig"] is not None
    assert vdata["deadline"] is not None

    recipient_bal_before = token.functions.balanceOf(RECIPIENT_ADDR).call()
    treasury_bal_before = token.functions.balanceOf(treasury.address).call()

    # 2. Call POST /execute
    exec_resp = client.post(
        f"/execute/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "executor_address": executor.address,
            "registry_address": registry.address,
            "caller_private_key": PK_PROPOSER,
            "rpc_url": env["rpc_url"],
        },
    )

    assert exec_resp.status_code == 200
    edata = exec_resp.json()
    assert edata["success"] is True
    assert edata["status"] == "EXECUTED"

    recipient_bal_after = token.functions.balanceOf(RECIPIENT_ADDR).call()
    treasury_bal_after = token.functions.balanceOf(treasury.address).call()

    # Recipient receives exact amount, treasury decreases by exact amount
    assert recipient_bal_after - recipient_bal_before == PAYOUT_AMOUNT
    assert treasury_bal_before - treasury_bal_after == PAYOUT_AMOUNT

    # GuardedExecutor records executed[pid] == true
    assert executor.functions.executed(proposal_id_to_bytes32(pid)).call() is True

    # 3. Replay attempt reverts
    replay_resp = client.post(
        f"/execute/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "executor_address": executor.address,
            "registry_address": registry.address,
            "rpc_url": env["rpc_url"],
        },
    )
    assert replay_resp.status_code == 400
    assert "replay blocked" in replay_resp.json()["detail"].lower()


def test_scenario_b1_substituted_payout_blocked(test_setup):
    """Scenario B1: Substituted payout (attacker recipient and inflated amount) -> MISMATCH -> no attestation -> execute refused."""
    env = test_setup
    token = env["token"]
    registry = env["registry"]
    treasury = env["treasury"]
    executor = env["executor"]
    client = env["client"]

    pid = "PROP-B1"
    confirmed = seed_and_approve_proposal(env, pid=pid)

    # Substituted calldata: attacker address and 2,000,000 USDC
    inflated_amount = 2_000_000 * 10**6
    substituted_calldata = encode_erc20_transfer_calldata(ATTACKER_ADDR, inflated_amount)

    recipient_bal_before = token.functions.balanceOf(RECIPIENT_ADDR).call()
    attacker_bal_before = token.functions.balanceOf(ATTACKER_ADDR).call()
    treasury_bal_before = token.functions.balanceOf(treasury.address).call()

    # 1. Call POST /verify
    verify_resp = client.post(
        f"/verify/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + substituted_calldata.hex(),
            "registry_address": registry.address,
            "treasury_address": treasury.address,
            "executor_address": executor.address,
            "rpc_url": env["rpc_url"],
        },
    )

    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["verdict"] == VERDICT_MISMATCH
    assert vdata["all_passed"] is False
    assert vdata["attestation_sig"] is None  # NEVER issue attestation for MISMATCH!

    # Check field diff
    diff = vdata["diff"]
    assert diff["recipient"]["match"] is False
    assert diff["amountRaw"]["match"] is False

    # 2. Call POST /execute -> must refuse transaction
    exec_resp = client.post(
        f"/execute/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + substituted_calldata.hex(),
            "executor_address": executor.address,
            "registry_address": registry.address,
            "rpc_url": env["rpc_url"],
        },
    )

    assert exec_resp.status_code == 400
    detail = exec_resp.json()["detail"].lower()
    assert "actionhash" in detail or "attestation" in detail

    # Verify balances completely unchanged
    assert token.functions.balanceOf(RECIPIENT_ADDR).call() == recipient_bal_before
    assert token.functions.balanceOf(ATTACKER_ADDR).call() == attacker_bal_before
    assert token.functions.balanceOf(treasury.address).call() == treasury_bal_before


def test_adversarial_expired_deadline_reverts_execution(test_setup):
    """Adversarial: Deadline derived from chain time expires when chain time is advanced; execute reverts."""
    env = test_setup
    w3 = env["w3"]
    token = env["token"]
    registry = env["registry"]
    treasury = env["treasury"]
    executor = env["executor"]
    client = env["client"]

    pid = "PROP-EXPIRED"
    confirmed = seed_and_approve_proposal(env, pid=pid)
    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    # Verify with short TTL (10 seconds)
    verify_resp = client.post(
        f"/verify/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "registry_address": registry.address,
            "treasury_address": treasury.address,
            "executor_address": executor.address,
            "ttl_seconds": 10,
            "rpc_url": env["rpc_url"],
        },
    )
    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["verdict"] == VERDICT_VERIFIED

    # Advance Anvil chain time past deadline (30 seconds) and mine block
    w3.provider.make_request("anvil_increaseTime", [30])
    w3.provider.make_request("anvil_mine", [1])

    # Attempt to execute: must fail due to expired deadline
    exec_resp = client.post(
        f"/execute/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "executor_address": executor.address,
            "registry_address": registry.address,
            "rpc_url": env["rpc_url"],
        },
    )
    assert exec_resp.status_code == 400
    assert "expired" in exec_resp.json()["detail"].lower()


def test_adversarial_toctou_approval_invalidation_blocks_execution(test_setup):
    """Adversarial TOCTOU: Proposal approved and verified, but new version committed before execute -> execute refused."""
    env = test_setup
    w3 = env["w3"]
    token = env["token"]
    registry = env["registry"]
    treasury = env["treasury"]
    executor = env["executor"]
    client = env["client"]

    pid = "PROP-TOCTOU"
    confirmed = seed_and_approve_proposal(env, pid=pid)
    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    # 1. Verify succeeds
    verify_resp = client.post(
        f"/verify/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "registry_address": registry.address,
            "treasury_address": treasury.address,
            "executor_address": executor.address,
            "rpc_url": env["rpc_url"],
        },
    )
    assert verify_resp.status_code == 200

    # 2. Proposer commits version 2 before execute is called (invalidating prior approval!)
    pid_b32 = proposal_id_to_bytes32(pid)
    send_tx(
        w3,
        PK_PROPOSER,
        registry.functions.commitVersion(
            pid_b32,
            bytes.fromhex("aa" * 32),
            bytes.fromhex("bb" * 32),
            bytes.fromhex("cc" * 32),
        ),
    )

    # Check on registry: approved record is now cleared (0, 0, 0)
    app_vhash, _, _ = registry.functions.approved(pid_b32).call()
    assert app_vhash == b"\x00" * 32

    # 3. Attempting to execute must be caught by live TOCTOU check and rejected
    exec_resp = client.post(
        f"/execute/{pid}",
        json={
            "target": token.address,
            "value": 0,
            "data": "0x" + calldata.hex(),
            "executor_address": executor.address,
            "registry_address": registry.address,
            "rpc_url": env["rpc_url"],
        },
    )
    assert exec_resp.status_code == 400
    assert "no live active approval" in exec_resp.json()["detail"].lower()


def test_adversarial_direct_treasury_call_reverts(test_setup):
    """Adversarial: Direct call to Treasury.exec from non-executor reverts."""
    env = test_setup
    w3 = env["w3"]
    token = env["token"]
    treasury = env["treasury"]

    calldata = encode_erc20_transfer_calldata(ATTACKER_ADDR, 100_000 * 10**6)

    # Attacker calls treasury.exec directly
    with pytest.raises(Exception):
        send_tx(
            w3,
            PK_ATTACKER,
            treasury.functions.exec(token.address, 0, calldata),
        )
