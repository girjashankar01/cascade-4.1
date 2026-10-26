"""Regression test for version history persistence and query (Issue 3).

Verifies that GET /versions/{pid} returns accurate on-chain version records and approval status.
"""

from fastapi.testclient import TestClient
from app.main import app


def test_versions_endpoint_returns_confirmed_version_history():
    """GET /versions/PROP-002 must return verified version record with matching hashes."""
    client = TestClient(app)
    resp = client.get("/versions/PROP-002")
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) >= 1, "Must contain at least 1 version record for PROP-002"
    v1 = versions[0]
    assert v1["version"] == 1
    assert v1["proposal_id"] == "PROP-002"
    assert v1["is_approved"] is True
    assert v1["onchain_verified"] is True
    assert v1["version_hash"].startswith("0x")
    assert v1["action_hash"].startswith("0x")
    assert v1["commit_tx_hash"].startswith("0x")
    assert v1["approve_tx_hash"].startswith("0x")
