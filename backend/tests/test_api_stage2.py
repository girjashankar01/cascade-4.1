"""End-to-end integration tests for Stage 2 FastAPI endpoints."""

import io
from pathlib import Path
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from app.api.routes import set_llm_router
from app.db import init_db
from app.llm.base import LLMProvider
from app.llm.router import LLMRouter
from app.main import app


class MockStage2Provider(LLMProvider):
    """Deterministic mock provider returning expected claims from both fixtures."""

    def __init__(self):
        self.name = "mock-stage2"
        self.model = "mock-v1"

    def extract_claims(self, prompt: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        claims = []
        for src in sources:
            fname = src.get("filename", "")
            src_id = src.get("id", "")
            if "proposal" in fname.lower():
                claims.extend(
                    [
                        {
                            "field": "amount",
                            "value": "$5.0M",
                            "quote": "This proposal requests a payout of $5.0M (5,000,000 USDC) to the designated recipient address",
                            "source_id": src_id,
                            "page": 1,
                            "confidence": 0.95,
                        },
                        {
                            "field": "recipient",
                            "value": "0x9965507D1a55BCC6475675304Ca994970De97744",
                            "quote": "0x9965507D1a55BCC6475675304Ca994970De97744.",
                            "source_id": src_id,
                            "page": 1,
                            "confidence": 0.95,
                        },
                        {
                            "field": "purpose",
                            "value": "Funding infrastructure security audits and core protocol development for Q1.",
                            "quote": "Funding infrastructure security audits and core protocol development for Q1.",
                            "source_id": src_id,
                            "page": 1,
                            "confidence": 0.90,
                        },
                    ]
                )
            elif "forum" in fname.lower():
                claims.extend(
                    [
                        {
                            "field": "amount",
                            "value": "$5.8M",
                            "quote": "revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC)",
                            "source_id": src_id,
                            "page": 1,
                            "confidence": 0.95,
                        },
                        {
                            "field": "recipient",
                            "value": "0x9965507D1a55BCC6475675304Ca994970De97744",
                            "quote": "recipient 0x9965507D1a55BCC6475675304Ca994970De97744",
                            "source_id": src_id,
                            "page": 1,
                            "confidence": 0.95,
                        },
                    ]
                )
        return claims

    def summarize(self, claims: List[Dict[str, Any]]) -> str:
        return "Extraction complete."


@pytest.fixture(autouse=True)
def setup_test_api(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "test_api.db"
    init_db(db_file)
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    storage_dir = tmp_path / "sources"
    monkeypatch.setattr("app.ingestion.pdf.DEFAULT_STORAGE_DIR", storage_dir)

    provider = MockStage2Provider()
    router = LLMRouter(provider=provider, db_path=db_file)
    set_llm_router(router)

    yield

    set_llm_router(None)


def test_sources_and_analysis_e2e_flow():
    client = TestClient(app)

    # 1. Ingest proposal.pdf
    fixtures_dir = Path(__file__).resolve().parents[2] / "fixtures"
    pdf_bytes = (fixtures_dir / "proposal.pdf").read_bytes()

    res_pdf = client.post(
        "/sources",
        files={"file": ("proposal.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_pdf.status_code == 201
    pdf_data = res_pdf.json()
    assert "source_id" in pdf_data
    assert pdf_data["filename"] == "proposal.pdf"
    assert pdf_data["page_count"] == 1

    # 2. Ingest forum_post.txt
    forum_text = (fixtures_dir / "forum_post.txt").read_text(encoding="utf-8")
    res_forum = client.post(
        "/sources",
        data={"content": forum_text, "filename": "forum_post.txt"},
    )
    assert res_forum.status_code == 201
    forum_data = res_forum.json()
    assert "source_id" in forum_data

    # 3. Analyze proposal PROP-001
    res_anl = client.post("/analyze/PROP-001")
    assert res_anl.status_code == 200
    anl_data = res_anl.json()

    assert anl_data["proposal_id"] == "PROP-001"
    # Material conflict between $5.0M and $5.8M exists, so status must be UNCERTAIN
    assert anl_data["status"] == "UNCERTAIN"
    assert len(anl_data["claims"]) > 0
    assert len(anl_data["conflicts"]) == 1

    conflict = anl_data["conflicts"][0]
    assert conflict["field"] == "amount"
    assert conflict["value_a"] == "5000000"
    assert conflict["value_b"] == "5800000"
    assert conflict["display_value_a"] == "$5.0M"
    assert conflict["display_value_b"] == "$5.8M"

    # 4. GET /claims/PROP-001
    res_claims = client.get("/claims/PROP-001")
    assert res_claims.status_code == 200
    claims_data = res_claims.json()
    assert claims_data["proposal_id"] == "PROP-001"
    assert len(claims_data["claims"]) == len(anl_data["claims"])
    assert len(claims_data["conflicts"]) == 1

    # 5. GET /audit/PROP-001
    res_audit = client.get("/audit/PROP-001")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert len(audit_data) >= 1
    assert audit_data[0]["proposal_id"] == "PROP-001"
    assert audit_data[0]["cache_status"] == "generated_now"
    assert audit_data[0]["status"] == "SUCCESS"


def test_sources_empty_file_rejected():
    client = TestClient(app)
    res = client.post("/sources", files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")})
    assert res.status_code == 400
