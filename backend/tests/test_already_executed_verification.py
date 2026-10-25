"""Regression test: verification of already-executed proposals skips simulation and returns ALREADY_EXECUTED."""

import os
import socket
import subprocess
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.chain.client import (
    PK_DEPLOYER,
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_VERIFIER,
    deploy_system,
    get_web3,
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
    STATUS_ALREADY_EXECUTED,
    VERDICT_ALREADY_EXECUTED,
    verify_proposal_transaction,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
RECIPIENT_ADDR = "0x9965507D1a55BCC6475675304Ca994970De97744"
PAYOUT_AMOUNT = 1_000_000 * 10**6  # 1,000,000 USDC


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def anvil_env(tmp_path_factory):
    port = find_free_port()
    proc = subprocess.Popen(
        ["anvil", "--port", str(port), "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc_url = f"http://127.0.0.1:{port}"
    w3 = get_web3(rpc_url)

    # Wait for node to be responsive
    for _ in range(30):
        if w3.is_connected():
            break
        time.sleep(0.1)

    db_file = tmp_path_factory.mktemp("db") / "test_exec.db"
    db_path = str(db_file)
    init_db(db_path)

    # Deploy core contracts
    sys_contracts = deploy_system(w3)

    yield {
        "w3": w3,
        "rpc_url": rpc_url,
        "db_path": db_path,
        "token": sys_contracts["token"],
        "registry": sys_contracts["registry"],
        "treasury": sys_contracts["treasury"],
        "executor": sys_contracts["executor"],
        "client": TestClient(app),
    }

    proc.terminate()
    proc.wait()


def test_verify_on_already_executed_proposal_returns_explicit_result(anvil_env):
    """Proves that verifying an already-executed proposal returns ALREADY_EXECUTED with tx_hash and block_number."""
    w3 = anvil_env["w3"]
    token = anvil_env["token"]
    registry = anvil_env["registry"]
    treasury = anvil_env["treasury"]
    executor = anvil_env["executor"]
    db_path = anvil_env["db_path"]
    client = anvil_env["client"]

    pid = "PROP-002"
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

    # Commit and approve on-chain
    send_tx(w3, PK_PROPOSER, registry.functions.commitVersion(pid_b32, vhash_bytes, ahash_bytes, eroot_bytes))
    send_tx(w3, PK_GOVERNANCE, registry.functions.approve(pid_b32, vhash_bytes))

    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    # 1. First verification when unexecuted produces a clean VERIFIED report with attestation signature
    report1 = verify_proposal_transaction(
        proposal_id=pid,
        target=token.address,
        value=0,
        data=calldata,
        registry_address=registry.address,
        treasury_address=treasury.address,
        executor_address=executor.address,
        verifier_private_key=PK_VERIFIER,
        ttl_seconds=3600,
        rpc_url=anvil_env["rpc_url"],
        db_path=db_path,
    )
    assert report1.verdict == "VERIFIED"
    assert report1.executed is False
    assert report1.attestation_sig is not None

    # 2. Execute on-chain through GuardedExecutor
    sig_bytes = bytes.fromhex(report1.attestation_sig[2:])
    exec_receipt = send_tx(
        w3,
        PK_PROPOSER,
        executor.functions.execute(
            pid_b32,
            token.address,
            0,
            calldata,
            1,  # VERIFIED
            report1.deadline,
            sig_bytes,
        ),
    )
    assert exec_receipt.status == 1
    exec_tx_hash = exec_receipt.transactionHash.hex()
    exec_block_num = exec_receipt.blockNumber

    # Record execution in database (as done by execute endpoint)
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE verifications
            SET executed = 1, tx_hash = ?, block_number = ?
            WHERE proposal_id = ? AND verdict = 'VERIFIED'
            """,
            (exec_tx_hash, exec_block_num, pid),
        )

    # Confirm treasury is now completely drained of test funds
    assert token.functions.balanceOf(treasury.address).call() == 0
    # Confirm executor records executed state
    assert executor.functions.executed(pid_b32).call() is True

    # 3. Second verification: proposal is ALREADY EXECUTED
    # Must NOT fail rule R3 or simulate an empty treasury!
    report2 = verify_proposal_transaction(
        proposal_id=pid,
        target=token.address,
        value=0,
        data=calldata,
        registry_address=registry.address,
        treasury_address=treasury.address,
        executor_address=executor.address,
        verifier_private_key=PK_VERIFIER,
        ttl_seconds=3600,
        rpc_url=anvil_env["rpc_url"],
        db_path=db_path,
    )

    r2_dict = report2.to_dict()

    # Verify explicit already-executed response
    assert report2.executed is True
    assert r2_dict["executed"] is True
    assert report2.status == STATUS_ALREADY_EXECUTED
    assert r2_dict["status"] == STATUS_ALREADY_EXECUTED
    assert r2_dict["verdict"] == VERDICT_ALREADY_EXECUTED
    assert r2_dict["tx_hash"].lower() == ("0x" + exec_tx_hash.lower()).replace("0x0x", "0x")
    assert r2_dict["block_number"] == exec_block_num

    # Simulation was skipped, so rules list is empty (no false R3 outflow failure)
    assert len(report2.rules) == 0
    assert r2_dict["simulation"]["skipped"] is True
