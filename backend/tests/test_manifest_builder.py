"""Tests for manifest drafting, confirmation, eligibility enforcement, and tampering detection."""

import json
from pathlib import Path
import pytest

from app.chain.client import PK_PROPOSER
from app.claims.schema import ClaimStatus
from app.db import get_db_connection, init_db
from app.ingestion.pdf import ingest_source
from app.manifest.builder import (
    EligibilityError,
    TamperError,
    build_manifest_draft,
    confirm_manifest_with_signature,
    verify_manifest_integrity,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
MOCK_TOKEN = "0x6b175474e89094c44da98b954eedeac495271d0f"
ADDR_RECIPIENT = "0x9965507d1a55bcc6475675304ca994970de97744"


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_manifest.db"
    db_path = str(db_file)
    init_db(db_path)
    return db_path


def seed_clean_proposal_v1(db_path: str, pid: str = "PROP-CLEAN") -> str:
    pdf_bytes = (FIXTURES_DIR / "clean_proposal_v1.pdf").read_bytes()
    source_meta = ingest_source(raw_bytes=pdf_bytes, filename="clean_proposal_v1.pdf", db_path=db_path)
    source_id = source_meta["id"]

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES (?, ?, 'amount', '1000000', '$1.0M', 'grant payout of $1.0M (1,000,000 USDC)', ?, 1, 0.95, ?, '{}', datetime('now'))
            """,
            (f"clm_{pid}_amount", pid, source_id, ClaimStatus.GROUNDED.value),
        )
        conn.execute(
            """
            INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES (?, ?, 'recipient', ?, ?, 'designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744', ?, 1, 0.95, ?, '{}', datetime('now'))
            """,
            (f"clm_{pid}_recipient", pid, ADDR_RECIPIENT, ADDR_RECIPIENT, source_id, ClaimStatus.GROUNDED.value),
        )
    return source_id


def test_clean_proposal_draft_and_confirm(temp_db: str):
    pid = "PROP-002"
    source_id = seed_clean_proposal_v1(temp_db, pid=pid)

    # 1. Draft manifest
    draft = build_manifest_draft(
        proposal_id=pid,
        token_address=MOCK_TOKEN,
        token_decimals=6,
        version=1,
        source_id=source_id,
        db_path=temp_db,
    )

    manifest = draft["manifest"]
    assert manifest["proposalId"] == pid
    assert manifest["version"] == 1
    assert manifest["action"]["kind"] == "erc20_payout"
    assert manifest["action"]["amountRaw"] == "1000000000000"  # 1M * 10^6
    assert manifest["action"]["recipient"] == ADDR_RECIPIENT
    assert manifest["action"]["token"] == MOCK_TOKEN.lower()

    # 2. Confirm and sign manifest
    confirmed = confirm_manifest_with_signature(
        proposal_id=pid,
        version=1,
        proposer_private_key=PK_PROPOSER,
        token_address=MOCK_TOKEN,
        token_decimals=6,
        source_id=source_id,
        db_path=temp_db,
    )

    assert confirmed["status"] == "CONFIRMED"
    assert confirmed["proposer_signature"].startswith("0x") or len(confirmed["proposer_signature"]) == 130 or len(confirmed["proposer_signature"]) == 132
    assert confirmed["version_hash"] == draft["version_hash"]


def test_version_chain_v1_and_v2(temp_db: str):
    pid = "PROP-002"
    src_v1 = seed_clean_proposal_v1(temp_db, pid=pid)

    # Confirm v1
    conf_v1 = confirm_manifest_with_signature(
        proposal_id=pid,
        version=1,
        proposer_private_key=PK_PROPOSER,
        token_address=MOCK_TOKEN,
        token_decimals=6,
        source_id=src_v1,
        db_path=temp_db,
    )

    # Ingest v2
    pdf_v2_bytes = (FIXTURES_DIR / "clean_proposal_v2.pdf").read_bytes()
    source_meta_v2 = ingest_source(raw_bytes=pdf_v2_bytes, filename="clean_proposal_v2.pdf", db_path=temp_db)
    src_v2 = source_meta_v2["id"]

    # Confirm v2 referencing v1
    conf_v2 = confirm_manifest_with_signature(
        proposal_id=pid,
        version=2,
        proposer_private_key=PK_PROPOSER,
        token_address=MOCK_TOKEN,
        token_decimals=6,
        source_id=src_v2,
        db_path=temp_db,
    )

    assert conf_v2["version"] == 2
    assert conf_v2["prev_version_hash"] == conf_v1["version_hash"], "Version 2 must point to Version 1 hash"
    assert conf_v2["version_hash"] != conf_v1["version_hash"], "Version 2 hash must differ from Version 1"
    # Action hashes are identical because the payout action did not change!
    assert conf_v2["action_hash"] == conf_v1["action_hash"]


def test_conflict_blocks_manifest_confirmation(temp_db: str):
    pid = "PROP-CONFLICTED"
    # Seed conflicting claims and unresolved conflict
    with get_db_connection(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO conflicts (id, proposal_id, field, value_a, display_value_a, source_id_a, quote_a, page_a, value_b, display_value_b, source_id_b, quote_b, page_b, status, created_at)
            VALUES ('cnf_1', ?, 'amount', '5000000', '$5.0M', 'src_1', 'quote 1', 1, '5800000', '$5.8M', 'src_2', 'quote 2', 1, 'UNRESOLVED', datetime('now'))
            """,
            (pid,),
        )
        conn.execute(
            """
            INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES ('clm_1', ?, 'amount', '5000000', '$5.0M', 'quote 1', 'src_1', 1, 0.95, 'UNCERTAIN', '{}', datetime('now'))
            """,
            (pid,),
        )
        conn.execute(
            """
            INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES ('clm_2', ?, 'recipient', ?, ?, 'quote 2', 'src_1', 1, 0.95, 'GROUNDED', '{}', datetime('now'))
            """,
            (pid, ADDR_RECIPIENT, ADDR_RECIPIENT),
        )

    # Attempting to draft or confirm manifest must be strictly rejected
    with pytest.raises(EligibilityError, match="has unresolved conflicts and cannot be confirmed"):
        build_manifest_draft(
            proposal_id=pid,
            token_address=MOCK_TOKEN,
            db_path=temp_db,
        )

    with pytest.raises(EligibilityError, match="has unresolved conflicts and cannot be confirmed"):
        confirm_manifest_with_signature(
            proposal_id=pid,
            version=1,
            proposer_private_key=PK_PROPOSER,
            token_address=MOCK_TOKEN,
            db_path=temp_db,
        )


def test_missing_mandatory_claim_blocks_confirmation(temp_db: str):
    pid = "PROP-MISSING"
    # Seed with only amount, missing recipient
    with get_db_connection(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
            VALUES ('clm_1', ?, 'amount', '1000000', '$1.0M', 'quote', 'src_1', 1, 0.95, 'GROUNDED', '{}', datetime('now'))
            """,
            (pid,),
        )

    with pytest.raises(EligibilityError, match="Missing mandatory claims for manifest"):
        build_manifest_draft(
            proposal_id=pid,
            token_address=MOCK_TOKEN,
            db_path=temp_db,
        )


def test_tamper_detection(temp_db: str):
    pid = "PROP-TAMPER"
    source_id = seed_clean_proposal_v1(temp_db, pid=pid)

    confirmed = confirm_manifest_with_signature(
        proposal_id=pid,
        version=1,
        proposer_private_key=PK_PROPOSER,
        token_address=MOCK_TOKEN,
        token_decimals=6,
        source_id=source_id,
        db_path=temp_db,
    )

    manifest_dict = confirmed["manifest"]

    # 1. Verification of untampered manifest succeeds
    report = verify_manifest_integrity(
        proposal_id=pid,
        version=1,
        manifest_dict=manifest_dict,
        db_path=temp_db,
    )
    assert report["verified"] is True

    # 2. Tamper with manifest action: change recipient
    tampered_manifest = json.loads(json.dumps(manifest_dict))
    tampered_manifest["action"]["recipient"] = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8"

    with pytest.raises(TamperError, match="Tamper detected in (versionHash|actionHash)"):
        verify_manifest_integrity(
            proposal_id=pid,
            version=1,
            manifest_dict=tampered_manifest,
            db_path=temp_db,
        )

    # 3. Tamper with proposal text
    with pytest.raises(TamperError, match="Tamper detected in proposalTextHash"):
        verify_manifest_integrity(
            proposal_id=pid,
            version=1,
            manifest_dict=manifest_dict,
            proposal_text="Tampered proposal text that was not voted on!",
            db_path=temp_db,
        )

    # 4. Tamper with evidence hashes
    with pytest.raises(TamperError, match="Tamper detected in evidenceRoot"):
        verify_manifest_integrity(
            proposal_id=pid,
            version=1,
            manifest_dict=manifest_dict,
            evidence_hashes=["0x" + "ff" * 32],
            db_path=temp_db,
        )
