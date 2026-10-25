"""Integration tests for Stage 3 manifest, commitment, approval, and tamper API routes."""

import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.chain.client import PK_PROPOSER
from app.claims.schema import ClaimStatus
from app.db import get_db_connection, init_db
from app.llm.base import LLMProvider
from app.llm.router import LLMRouter
from app.main import app
from app.api.routes import set_llm_router

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
MOCK_TOKEN = "0x6b175474e89094c44da98b954eedeac495271d0f"
ADDR_RECIPIENT = "0x9965507D1a55BCC6475675304Ca994970De97744"


class MockCleanLLMProvider(LLMProvider):
    def __init__(self):
        self.name = "mock_clean_llm"
        self.model = "mock-v1"

    def extract_claims(self, prompt: str, sources: list[dict]) -> list[dict]:
        claims = []
        for src in sources:
            src_id = src.get("id", "src_1")
            claims.extend(
                [
                    {
                        "field": "amount",
                        "value": "$1.0M",
                        "quote": "This proposal requests a payout of $1.0M (1,000,000 USDC)",
                        "source_id": src_id,
                        "page": 1,
                        "confidence": 0.95,
                    },
                    {
                        "field": "recipient",
                        "value": ADDR_RECIPIENT,
                        "quote": "0x9965507D1a55BCC6475675304Ca994970De97744.",
                        "source_id": src_id,
                        "page": 1,
                        "confidence": 0.95,
                    },
                ]
            )
        return claims

    def summarize(self, claims: list[dict]) -> str:
        return "Clean extraction summary."


@pytest.fixture
def client(tmp_path: Path):
    db_file = tmp_path / "test_api_stage3.db"
    db_path = str(db_file)
    init_db(db_path)

    # Monkeypatch db_path in get_db_connection default
    import app.db as db_mod
    orig_db_path = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_file

    with TestClient(app) as test_client:
        yield test_client

    db_mod.DEFAULT_DB_PATH = orig_db_path
    set_llm_router(None)


def test_conflict_strictly_blocks_manifest_routes(client: TestClient):
    pid = "PROP-001"
    # Seed conflicting claims and unresolved conflict in DB
    with get_db_connection() as conn:
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
            (pid, ADDR_RECIPIENT.lower(), ADDR_RECIPIENT),
        )

    # 1. Draft manifest should fail with 422 Unprocessable Entity
    draft_res = client.post(
        f"/manifest/{pid}",
        json={"token_address": MOCK_TOKEN, "token_decimals": 6, "version": 1},
    )
    assert draft_res.status_code == 422
    assert "ELIGIBILITY_ERROR" in draft_res.json()["detail"]["error"]
    assert "unresolved conflicts" in draft_res.json()["detail"]["message"]

    # 2. Confirm manifest should also fail with 422
    conf_res = client.post(
        f"/manifest/{pid}/confirm",
        json={"token_address": MOCK_TOKEN, "token_decimals": 6, "version": 1},
    )
    assert conf_res.status_code == 422
    assert "ELIGIBILITY_ERROR" in conf_res.json()["detail"]["error"]


def test_clean_proposal_manifest_commit_approve_verify_flow(client: TestClient):
    pid = "PROP-002"

    # 1. Ingest clean proposal PDF
    pdf_bytes = (FIXTURES_DIR / "clean_proposal_v1.pdf").read_bytes()
    upload_res = client.post(
        "/sources",
        files={"file": ("clean_proposal_v1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["source_id"]

    # 2. Run analysis with mock clean provider
    clean_router = LLMRouter(provider=MockCleanLLMProvider())
    set_llm_router(clean_router)

    analyze_res = client.post(f"/analyze/{pid}")
    assert analyze_res.status_code == 200
    assert analyze_res.json()["status"] == "SUCCESS"
    assert len(analyze_res.json()["conflicts"]) == 0

    # 3. POST /manifest/{pid} -> Draft manifest
    draft_res = client.post(
        f"/manifest/{pid}",
        json={"token_address": MOCK_TOKEN, "token_decimals": 6, "version": 1},
    )
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert draft_data["manifest"]["proposalId"] == pid
    assert draft_data["manifest"]["version"] == 1
    assert draft_data["version_hash"].startswith("0x")

    # 4. POST /manifest/{pid}/confirm -> Human confirmation + Proposer signature
    confirm_res = client.post(
        f"/manifest/{pid}/confirm",
        json={
            "token_address": MOCK_TOKEN,
            "token_decimals": 6,
            "version": 1,
            "proposer_private_key": PK_PROPOSER,
        },
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "CONFIRMED"
    assert confirm_data["proposer_signature"] is not None

    # 5. GET /manifest/{pid} -> Read back confirmed manifest
    get_man_res = client.get(f"/manifest/{pid}")
    assert get_man_res.status_code == 200
    assert get_man_res.json()["version"] == 1
    assert get_man_res.json()["version_hash"] == confirm_data["version_hash"]

    # 6. POST /commit/{pid} -> Commit to database
    commit_res = client.post(f"/commit/{pid}", json={"version": 1})
    assert commit_res.status_code == 200
    assert commit_res.json()["status"] == "COMMITTED"
    assert commit_res.json()["version"] == 1

    # 7. POST /approve/{pid} -> Governance approve
    approve_res = client.post(f"/approve/{pid}", json={"version": 1})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # 8. GET /versions/{pid} -> Check version chain
    chain_res = client.get(f"/versions/{pid}")
    assert chain_res.status_code == 200
    chain_list = chain_res.json()
    assert len(chain_list) == 1
    assert chain_list[0]["version"] == 1
    assert chain_list[0]["is_approved"] is True

    # 9. POST /verify-version/{pid} -> Untampered verification succeeds
    verify_res = client.post(f"/verify-version/{pid}", json={"version": 1})
    assert verify_res.status_code == 200
    assert verify_res.json()["verified"] is True

    # 10. POST /verify-version/{pid} -> Tampering detection
    tampered_manifest = dict(draft_data["manifest"])
    tampered_manifest["action"]["amountRaw"] = "999999999999"  # altered amount

    tamper_res = client.post(
        f"/verify-version/{pid}",
        json={"version": 1, "manifest_dict": tampered_manifest},
    )
    assert tamper_res.status_code == 200
    assert tamper_res.json()["verified"] is False
    assert tamper_res.json()["tamper_detected"] is True
    assert "Tamper detected" in tamper_res.json()["error"]
