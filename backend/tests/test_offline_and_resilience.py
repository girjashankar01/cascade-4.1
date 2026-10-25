"""Phase 7 resilience, LLM timeout/429 handling, offline cache validation, and fast-reset tests."""

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.db import get_db_connection, init_db
from app.llm.base import LLMUnavailableError
from app.llm.cache import set_cached_response
from app.llm.online import OnlineLLMProvider
from app.llm.router import LLMRouter, compute_hash, compute_input_hash


@pytest.fixture
def temp_db(tmp_path):
    """Create an isolated temporary SQLite database for resilience tests."""
    db_file = tmp_path / "resilience_test.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def sample_sources() -> List[Dict[str, Any]]:
    return [
        {
            "id": "src_test_001",
            "sha256": "0x" + "aa" * 32,
            "filename": "proposal_v1.pdf",
            "extracted_pages": {1: "Team Alice requests grant of $1.0M (1,000,000 USDC) to 0x9965507D1a55BCC6475675304Ca994970De97744."},
        }
    ]


# -----------------------------------------------------------------------------
# Phase 7B: LLM Resilience, Timeouts, Rate Limits, and Credential Safety
# -----------------------------------------------------------------------------


def test_llm_missing_credentials_fails_closed(sample_sources):
    """Test that missing LLM_API_KEY raises LLMUnavailableError without attempting network calls."""
    provider = OnlineLLMProvider(api_key="")
    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.extract_claims("Extract claims", sample_sources)
    assert "LLM_API_KEY is not configured" in str(exc_info.value)
    assert exc_info.value.code == "LLM_UNAVAILABLE"


def test_llm_timeout_handling(monkeypatch, sample_sources):
    """Test that network timeout raises LLMUnavailableError with sanitized timeout duration."""
    provider = OnlineLLMProvider(api_key="test-key-12345", timeout_s=5.0)

    def mock_post(*args, **kwargs):
        raise httpx.TimeoutException("Connection timed out")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.extract_claims("Extract claims", sample_sources)
    assert "timed out after 5.0s" in str(exc_info.value)
    assert "test-key" not in str(exc_info.value)


def test_llm_rate_limit_429_with_retry_after(monkeypatch, sample_sources):
    """Test that HTTP 429 returns structured error with Retry-After information."""
    provider = OnlineLLMProvider(api_key="test-key-12345")

    mock_resp = httpx.Response(
        status_code=429,
        headers={"Retry-After": "60"},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: mock_resp)

    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.extract_claims("Extract claims", sample_sources)
    assert "429" in str(exc_info.value)
    assert "retry after 60s" in str(exc_info.value)


def test_llm_server_error_503_does_not_leak_raw_payload(monkeypatch, sample_sources):
    """Test that HTTP 503 raises LLMUnavailableError without leaking raw provider internals."""
    provider = OnlineLLMProvider(api_key="secret-bearer-key-xyz")

    mock_resp = httpx.Response(
        status_code=503,
        text='{"error": "Internal server overload at worker 42", "auth_echo": "secret-bearer-key-xyz"}',
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: mock_resp)

    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.extract_claims("Extract claims", sample_sources)
    assert "service error (HTTP 503)" in str(exc_info.value)
    assert "secret-bearer-key-xyz" not in str(exc_info.value)


def test_llm_connection_dns_failure(monkeypatch, sample_sources):
    """Test network connection and DNS errors are cleanly caught."""
    provider = OnlineLLMProvider(api_key="test-key")

    def mock_post(*args, **kwargs):
        raise httpx.ConnectError("DNS lookup failed for api.openai.com")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.extract_claims("Extract claims", sample_sources)
    assert "network/DNS error" in str(exc_info.value)


def test_llm_router_retry_exhaustion_and_audit_failure(temp_db, sample_sources):
    """Test that router retries invalid JSON once, then fails closed and records audit trail."""
    mock_provider = MagicMock()
    mock_provider.name = "mock-online"
    mock_provider.model = "test-model"
    # Returns malformed output on all attempts
    mock_provider.extract_claims.side_effect = ValueError("Unparseable output from model")

    router = LLMRouter(provider=mock_provider, db_path=temp_db)

    with pytest.raises(LLMUnavailableError):
        router.analyze_sources("PROP-TEST-RETRY", sample_sources)

    # Provider must have been called twice (1 initial + 1 retry)
    assert mock_provider.extract_claims.call_count == 2

    # Audit table must have recorded FAILED record with LLM_UNAVAILABLE
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, error_code FROM analyses WHERE proposal_id = 'PROP-TEST-RETRY'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "FAILED"
        assert row[1] == "LLM_UNAVAILABLE"


# -----------------------------------------------------------------------------
# Phase 7C: Offline Mode, Cache Invalidation, and Fail-Closed Verification
# -----------------------------------------------------------------------------


def test_offline_cached_extraction_succeeds_without_network(temp_db, sample_sources):
    """Test that with external network/provider offline, valid cache returns claims without network call."""
    from app.llm.online import DEFAULT_SYSTEM_PROMPT

    mock_failing_provider = MagicMock()
    mock_failing_provider.name = "mock-failing"
    mock_failing_provider.model = "test-model"
    mock_failing_provider.extract_claims.side_effect = LLMUnavailableError("External network completely disabled")

    router = LLMRouter(provider=mock_failing_provider, db_path=temp_db)

    # Seed valid cache entry matching exact prompt and input hash
    prompt = "Extract factual payout claims with verbatim quotes."
    effective_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n{prompt}"
    prompt_h = compute_hash(effective_prompt)
    input_h = compute_input_hash(sample_sources)

    valid_claim_data = [
        {
            "field": "amount",
            "value": "1000000",
            "quote": "requests grant of $1.0M (1,000,000 USDC)",
            "source_id": "src_test_001",
            "page": 1,
            "confidence": 0.95,
        }
    ]
    set_cached_response(
        prompt_hash=prompt_h,
        input_hash=input_h,
        model="test-model",
        response_data=valid_claim_data,
        db_path=temp_db,
    )

    # Call analyze_sources: must succeed via cache without calling provider
    claims, cache_status = router.analyze_sources("PROP-TEST-OFFLINE", sample_sources, prompt=prompt)
    assert cache_status == "cached"
    assert len(claims) == 1
    assert claims[0].field == "amount"
    assert claims[0].value == "1000000"
    mock_failing_provider.extract_claims.assert_not_called()


def test_cache_invalidation_on_modified_evidence(temp_db, sample_sources):
    """Test that modifying source evidence changes input_hash and causes cache miss (prevents stale reuse)."""
    from app.llm.online import DEFAULT_SYSTEM_PROMPT

    mock_provider = MagicMock()
    mock_provider.name = "mock-online"
    mock_provider.model = "test-model"
    mock_provider.extract_claims.side_effect = LLMUnavailableError("No network")

    router = LLMRouter(provider=mock_provider, db_path=temp_db)

    prompt = "Extract factual payout claims with verbatim quotes."
    effective_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n{prompt}"
    prompt_h = compute_hash(effective_prompt)
    input_h_original = compute_input_hash(sample_sources)

    set_cached_response(
        prompt_hash=prompt_h,
        input_hash=input_h_original,
        model="test-model",
        response_data=[{"field": "amount", "value": "1000000", "quote": "q", "source_id": "s", "page": 1, "confidence": 0.9}],
        db_path=temp_db,
    )

    # Modify evidence (add conflicting text or second source)
    modified_sources = [
        {
            "id": "src_test_001",
            "sha256": "0x" + "bb" * 32,  # Modified hash!
            "filename": "proposal_v2.pdf",
            "extracted_pages": {1: "Team Alice requests grant of $5.8M."},
        }
    ]
    input_h_modified = compute_input_hash(modified_sources)
    assert input_h_original != input_h_modified

    # Router must NOT reuse old cache; provider is called and raises LLMUnavailableError
    with pytest.raises(LLMUnavailableError):
        router.analyze_sources("PROP-TEST-INVALIDATION", modified_sources, prompt=prompt)


def test_llm_failure_does_not_satisfy_mandatory_claims(temp_db):
    """Verify that an LLM failure cannot fabricate claims or satisfy mandatory verification rules."""
    from app.manifest.builder import EligibilityError, check_claims_eligibility

    # No claims exist because LLM extraction failed
    with pytest.raises(EligibilityError) as exc_info:
        check_claims_eligibility("PROP-NO-CLAIMS", db_path=temp_db)
    assert "No claims found for proposal 'PROP-NO-CLAIMS'" in str(exc_info.value)


# -----------------------------------------------------------------------------
# Phase 7A: Fast-Reset, Local Host Enforcement, and Idempotency Tests
# -----------------------------------------------------------------------------


def test_deploy_and_seed_rejects_non_local_rpc_host(temp_db):
    """Verify that deploy_and_seed strictly rejects non-local hostnames."""
    import sys
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from deploy_and_seed import deploy_and_seed

    mock_w3 = MagicMock()
    with pytest.raises(RuntimeError) as exc_info:
        deploy_and_seed(w3=mock_w3, rpc_url="https://mainnet.infura.io/v3/my-secret-key", db_path=temp_db)
    assert "Refusing to execute deployment on non-local RPC host" in str(exc_info.value)


def test_deploy_and_seed_rejects_disconnected_node(temp_db):
    """Verify that deploy_and_seed provides a clear actionable diagnostic when Anvil is down."""
    import sys
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from deploy_and_seed import deploy_and_seed

    with pytest.raises(RuntimeError) as exc_info:
        # Connecting to a dead port
        deploy_and_seed(rpc_url="http://127.0.0.1:59999", db_path=temp_db)
    assert "Cannot connect to local Anvil node" in str(exc_info.value)

