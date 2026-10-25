"""Tests for LLM router, retry policy, caching, and audit trail."""

from pathlib import Path
from typing import Any, Dict, List
import pytest

from app.db import get_db_connection, init_db
from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.router import LLMRouter


class MockSuccessProvider(LLMProvider):
    def __init__(self, name: str = "mock-success"):
        self.name = name
        self.model = "mock-model-v1"
        self.call_count = 0

    def extract_claims(self, prompt: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.call_count += 1
        return [
            {
                "field": "amount",
                "value": "$5.0M",
                "quote": "requests a payout of $5.0M",
                "source_id": sources[0]["id"],
                "page": 1,
                "confidence": 0.95,
            }
        ]

    def summarize(self, claims: List[Dict[str, Any]]) -> str:
        return f"Extracted {len(claims)} claims."


class MockFailingProvider(LLMProvider):
    def __init__(self, fail_times: int = 1):
        self.name = "mock-failing"
        self.model = "mock-model-fail"
        self.call_count = 0
        self.fail_times = fail_times

    def extract_claims(self, prompt: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise ValueError("Invalid schema returned by mock LLM")
        return [
            {
                "field": "amount",
                "value": "$5.0M",
                "quote": "requests a payout of $5.0M",
                "source_id": sources[0]["id"],
                "page": 1,
                "confidence": 0.95,
            }
        ]

    def summarize(self, claims: List[Dict[str, Any]]) -> str:
        return "summary"


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_llm.db"
    init_db(db_file)
    return db_file


def test_cache_miss_then_cache_hit(temp_db):
    provider = MockSuccessProvider()
    router = LLMRouter(provider=provider, db_path=temp_db)
    sources = [{"id": "src_1", "sha256": "h1", "extracted_pages": {1: "page text"}}]

    # First call: cache miss
    claims, status1 = router.analyze_sources("PROP-001", sources)
    assert status1 == "generated_now"
    assert provider.call_count == 1
    assert len(claims) == 1

    # Second call with identical input: cache hit
    claims2, status2 = router.analyze_sources("PROP-001", sources)
    assert status2 == "cached"
    assert provider.call_count == 1  # Provider was NOT called again
    assert len(claims2) == 1

    # Check audit record persisted
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analyses WHERE proposal_id = 'PROP-001' ORDER BY created_at ASC")
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0]["cache_status"] == "generated_now"
        assert rows[1]["cache_status"] == "cached"


def test_single_retry_on_invalid_output(temp_db):
    # Fails once with invalid schema, succeeds on attempt 2
    provider = MockFailingProvider(fail_times=1)
    router = LLMRouter(provider=provider, db_path=temp_db)
    sources = [{"id": "src_1", "sha256": "h1", "extracted_pages": {1: "page text"}}]

    claims, status = router.analyze_sources("PROP-002", sources)
    assert status == "generated_now"
    assert provider.call_count == 2  # Retried exactly once
    assert len(claims) == 1


def test_double_failure_raises_llm_unavailable(temp_db):
    # Fails twice: should exhaust retry and raise LLMUnavailableError
    provider = MockFailingProvider(fail_times=2)
    router = LLMRouter(provider=provider, db_path=temp_db)
    sources = [{"id": "src_1", "sha256": "h1", "extracted_pages": {1: "page text"}}]

    with pytest.raises(LLMUnavailableError):
        router.analyze_sources("PROP-003", sources)

    assert provider.call_count == 2

    # Verify failed audit record written
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analyses WHERE proposal_id = 'PROP-003'")
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "FAILED"
        assert row["error_code"] == "LLM_UNAVAILABLE"
