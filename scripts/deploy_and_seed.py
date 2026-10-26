"""Deploy core DAO contracts to Anvil, fund treasury, and seed clean proposal state."""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Auto-bootstrap into backend virtualenv if invoked with system python
backend_dir = Path(__file__).resolve().parents[1] / "backend"
venv_python = backend_dir / ".venv" / "bin" / "python"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)

from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

from eth_account import Account
from web3 import Web3

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.chain.client import (
    DEFAULT_RPC_URL,
    PK_DEPLOYER,
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_VERIFIER,
    approve_version_onchain,
    commit_version_onchain,
    deploy_contract,
    get_web3,
    send_tx,
)
from app.claims.schema import ClaimStatus
from app.db import get_db_connection, init_db
from app.ingestion.pdf import ingest_source
from app.manifest.builder import confirm_manifest_with_signature

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy_and_seed")

RECIPIENT_ADDRESS = "0x9965507D1a55BCC6475675304Ca994970De97744"
LOCAL_CHAIN_IDS = {31337, 1337}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}
DEMO_PROPOSAL_IDS = ("PROP-001", "PROP-002", "PROP-B1", "PROP-B2", "PROP-B3")


def verify_local_chain(w3: Web3) -> None:
    """Verify that the connected chain is a permitted local development chain."""
    verify_local_environment(w3)


def verify_local_environment(w3: Web3, rpc_url: Optional[str] = None) -> None:
    """Verify that both the RPC endpoint and chain ID strictly belong to a local development node."""
    target_url = rpc_url or DEFAULT_RPC_URL
    parsed = urlparse(target_url)
    hostname = (parsed.hostname or "").lower()

    if hostname and hostname not in LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to execute deployment on non-local RPC host '{hostname}' ({target_url}). "
            f"Only local loopback hosts ({LOCAL_HOSTS}) are permitted."
        )

    if not w3.is_connected():
        raise RuntimeError(
            f"Cannot connect to local Anvil node at {target_url}. "
            f"Please ensure Anvil is running locally ('anvil') before deploying and seeding."
        )

    try:
        chain_id = w3.eth.chain_id
    except Exception as e:
        raise RuntimeError(f"Unable to query chain ID from Web3 provider at {target_url}: {e}") from e

    if chain_id not in LOCAL_CHAIN_IDS:
        raise RuntimeError(
            f"Refusing to execute deployment or state reset on non-local chain ID {chain_id}. "
            f"Only local development chains ({LOCAL_CHAIN_IDS}) are permitted."
        )


def deploy_and_seed(
    w3: Optional[Web3] = None,
    rpc_url: Optional[str] = None,
    db_path: Optional[str] = None,
    save_deployments: bool = False,
    output_manifest_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """Deploy MockToken, GovernanceRegistry, Treasury, GuardedExecutor, and seed demo proposals.

    Idempotent: Safe to execute repeatedly without accumulating duplicate records or orphaned state.
    """
    start_time = time.perf_counter()
    url = rpc_url or DEFAULT_RPC_URL
    if w3 is None:
        w3 = get_web3(url)

    logger.info("[1/6] Validating local development environment & Anvil connectivity...")
    verify_local_environment(w3, rpc_url=url)

    deployer_addr = Account.from_key(PK_DEPLOYER).address
    governance_addr = Account.from_key(PK_GOVERNANCE).address
    verifier_addr = Account.from_key(PK_VERIFIER).address
    proposer_addr = Account.from_key(PK_PROPOSER).address

    logger.info("[2/6] Initializing database & purging stale demo proposal records...")
    init_db(db_path)

    # Clean previous records for all demo proposals to ensure total idempotency
    with get_db_connection(db_path) as conn:
        placeholders = ",".join(["?"] * len(DEMO_PROPOSAL_IDS))
        conn.execute(f"DELETE FROM claims WHERE proposal_id IN ({placeholders})", DEMO_PROPOSAL_IDS)
        conn.execute(f"DELETE FROM conflicts WHERE proposal_id IN ({placeholders})", DEMO_PROPOSAL_IDS)
        conn.execute(f"DELETE FROM manifests WHERE proposal_id IN ({placeholders})", DEMO_PROPOSAL_IDS)
        conn.execute(f"DELETE FROM versions WHERE proposal_id IN ({placeholders})", DEMO_PROPOSAL_IDS)
        conn.execute(f"DELETE FROM verifications WHERE proposal_id IN ({placeholders})", DEMO_PROPOSAL_IDS)
        conn.execute(f"DELETE FROM analyses WHERE proposal_id IN ({placeholders})", DEMO_PROPOSAL_IDS)

    logger.info("[3/6] Deploying core DAO contracts (Token, Registry, Treasury, GuardedExecutor)...")
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

    logger.info("[4/6] Deploying UUPS upgrade contracts & ERC1967 proxy...")
    box_impl = deploy_contract(w3, PK_DEPLOYER, "BoxUUPS")
    box_v2 = deploy_contract(w3, PK_DEPLOYER, "BoxV2")
    box_evil = deploy_contract(w3, PK_DEPLOYER, "BoxEvil")

    treasury_clean = treasury.address.lower().replace("0x", "")
    init_data = bytes.fromhex("c4d66de8") + (b"\x00" * 12) + bytes.fromhex(treasury_clean)
    box_proxy = deploy_contract(
        w3,
        PK_DEPLOYER,
        "ERC1967Proxy",
        box_impl.address,
        init_data,
    )

    logger.info("[5/6] Seeding proposals (PROP-002 clean payout, PROP-001 genuine conflict)...")
    # Seed clean proposal PROP-002
    pid = "PROP-002"
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
    pdf_v1_path = fixtures_dir / "clean_proposal_v1.pdf"

    if pdf_v1_path.exists():
        pdf_bytes = pdf_v1_path.read_bytes()
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
                (f"clm_{pid}_recipient", pid, RECIPIENT_ADDRESS.lower(), RECIPIENT_ADDRESS, src_id, ClaimStatus.GROUNDED.value),
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

        commit_res = commit_version_onchain(
            registry_address=registry.address,
            proposal_id=pid,
            version_hash=confirmed["version_hash"],
            action_hash=confirmed["action_hash"],
            evidence_root=confirmed["evidence_root"],
            proposer_key=PK_PROPOSER,
            rpc_url=url,
        )

        approve_res = approve_version_onchain(
            registry_address=registry.address,
            proposal_id=pid,
            version_hash=confirmed["version_hash"],
            governance_key=PK_GOVERNANCE,
            rpc_url=url,
        )

        # Record in versions table so GET /versions/{pid} returns accurate history
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO versions (
                    id, proposal_id, version, version_hash, action_hash, evidence_root,
                    prev_version_hash, commit_tx_hash, commit_block_number, committed_at,
                    approve_tx_hash, approve_block_number, approved_at,
                    onchain_verified, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, datetime('now'), 1, datetime('now'))
                """,
                (
                    f"ver_{pid}_1",
                    pid,
                    1,
                    confirmed["version_hash"],
                    confirmed["action_hash"],
                    confirmed["evidence_root"],
                    confirmed.get("prev_version_hash") or "0x" + "00" * 32,
                    commit_res.get("tx_hash"),
                    commit_res.get("block_number"),
                    approve_res.get("tx_hash"),
                    approve_res.get("block_number"),
                ),
            )

    # Seed conflicting proposal PROP-001 ($5.0M in PDF vs $5.8M in forum post)
    pid_conflict = "PROP-001"
    forum_path = fixtures_dir / "forum_post.txt"
    if pdf_v1_path.exists() and forum_path.exists():
        src_pdf = ingest_source(raw_bytes=pdf_v1_path.read_bytes(), filename="clean_proposal_v1.pdf", db_path=db_path)
        src_forum = ingest_source(raw_bytes=forum_path.read_bytes(), filename="forum_post.txt", db_path=db_path)

        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
                VALUES (?, ?, 'amount', '5000000', '$5.0M', 'grant payout of $5.0M (5,000,000 USDC)', ?, 1, 0.95, ?, '{}', datetime('now'))
                """,
                (f"clm_{pid_conflict}_amt_pdf", pid_conflict, src_pdf["id"], ClaimStatus.UNCERTAIN.value),
            )
            conn.execute(
                """
                INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
                VALUES (?, ?, 'amount', '5800000', '$5.8M', 'revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC)', ?, 1, 0.90, ?, '{}', datetime('now'))
                """,
                (f"clm_{pid_conflict}_amt_forum", pid_conflict, src_forum["id"], ClaimStatus.UNCERTAIN.value),
            )
            conn.execute(
                """
                INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
                VALUES (?, ?, 'recipient', ?, ?, 'designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744', ?, 1, 0.95, ?, '{}', datetime('now'))
                """,
                (f"clm_{pid_conflict}_recipient", pid_conflict, RECIPIENT_ADDRESS.lower(), RECIPIENT_ADDRESS, src_pdf["id"], ClaimStatus.GROUNDED.value),
            )
            conn.execute(
                """
                INSERT INTO conflicts (
                    id, proposal_id, field,
                    value_a, display_value_a, source_id_a, quote_a, page_a,
                    value_b, display_value_b, source_id_b, quote_b, page_b,
                    status, created_at
                ) VALUES (?, ?, 'amount', '5000000', '$5.0M', ?, 'grant payout of $5.0M (5,000,000 USDC)', 1, '5800000', '$5.8M', ?, 'revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC)', 1, 'CONFLICT', datetime('now'))
                """,
                (f"cnf_{pid_conflict}_amount", pid_conflict, src_pdf["id"], src_forum["id"]),
            )

    logger.info("[6/6] Verifying state invariants & persisting deployments.json...")
    # Verify contract deployments
    for name, contract_addr in [
        ("Token", token.address),
        ("Registry", registry.address),
        ("Treasury", treasury.address),
        ("Executor", executor.address),
        ("BoxUUPS", box_impl.address),
        ("BoxV2", box_v2.address),
        ("BoxEvil", box_evil.address),
        ("ERC1967Proxy", box_proxy.address),
    ]:
        code = w3.eth.get_code(Web3.to_checksum_address(contract_addr))
        if not code or len(code) <= 2:
            raise RuntimeError(f"Contract {name} at {contract_addr} has no runtime bytecode on-chain")

    # Verify treasury state
    treasury_bal = token.functions.balanceOf(treasury.address).call()
    if treasury_bal < 1_000_000 * 10**6:
        raise RuntimeError(f"Treasury funding postcondition failed: balance {treasury_bal} < 1,000,000 USDC")

    configured_executor = treasury.functions.executor().call()
    if configured_executor.lower() != executor.address.lower():
        raise RuntimeError(f"Treasury executor mismatch: expected {executor.address}, got {configured_executor}")

    # Verify proxy implementation slot
    from app.verification.simulate import EIP1967_IMPL_SLOT
    slot_data = w3.eth.get_storage_at(box_proxy.address, EIP1967_IMPL_SLOT)
    impl_in_slot = "0x" + slot_data[-20:].hex().lower()
    if impl_in_slot != box_impl.address.lower():
        raise RuntimeError(f"Box proxy implementation slot mismatch: expected {box_impl.address}, got {impl_in_slot}")

    # Verify proposal approval on-chain
    from app.chain.client import proposal_id_to_bytes32
    app_tuple = registry.functions.approved(proposal_id_to_bytes32(pid)).call()
    if app_tuple[0] == b"\x00" * 32:
        raise RuntimeError(f"Proposal {pid} approval postcondition failed: on-chain approved versionHash is zero")

    # Verify conflict in DB
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conflicts WHERE proposal_id = 'PROP-001' AND status = 'CONFLICT'")
        conflict_count = cursor.fetchone()[0]
        if conflict_count == 0:
            raise RuntimeError("Proposal PROP-001 conflict postcondition failed: conflict record missing from SQLite")

    deployments = {
        "rpc_url": url,
        "token": token.address,
        "registry": registry.address,
        "treasury": treasury.address,
        "executor": executor.address,
        "box_impl": box_impl.address,
        "box_proxy": box_proxy.address,
        "box_v2": box_v2.address,
        "box_evil": box_evil.address,
        "deployer": deployer_addr,
        "governance": governance_addr,
        "verifier": verifier_addr,
        "proposer": proposer_addr,
        "seeded_proposal_id": pid,
    }

    # Save to deployments manifest only if explicitly requested
    if output_manifest_path is not None:
        out_path = Path(output_manifest_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(deployments, f, indent=2)
        logger.info(f"Active deployments written to custom path: {out_path}")
    elif save_deployments:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        data_dir.mkdir(exist_ok=True)
        with open(data_dir / "deployments.json", "w", encoding="utf-8") as f:
            json.dump(deployments, f, indent=2)

        backend_data_dir = Path(__file__).resolve().parents[1] / "backend" / "data"
        if backend_data_dir.exists():
            with open(backend_data_dir / "deployments.json", "w", encoding="utf-8") as f:
                json.dump(deployments, f, indent=2)
        logger.info(f"Active deployments written to {data_dir / 'deployments.json'}")
    else:
        logger.info("Skipping manifest disk persistence (save_deployments=False)")

    duration = time.perf_counter() - start_time
    logger.info(f"SUCCESS: Deployed and seeded CASCADE 4.1 in {duration:.2f}s")
    return deployments


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deploy contracts and seed proposals for CASCADE 4.1")
    parser.add_argument("--save", action="store_true", default=True, help="Persist deployments to deployments.json (default: True)")
    parser.add_argument("--no-save", dest="save", action="store_false", help="Do not persist deployments to disk")
    parser.add_argument("--output", type=str, default=None, help="Custom output path for deployments.json")
    parser.add_argument("--rpc-url", type=str, default=None, help="RPC URL to deploy to")
    parser.add_argument("--db-path", type=str, default=None, help="SQLite database path")
    args = parser.parse_args()

    try:
        deploy_and_seed(
            rpc_url=args.rpc_url,
            db_path=args.db_path,
            save_deployments=args.save,
            output_manifest_path=args.output,
        )
        sys.exit(0)
    except Exception as exc:
        logger.error(f"FATAL: Deployment and seeding failed: {exc}")
        sys.exit(1)
