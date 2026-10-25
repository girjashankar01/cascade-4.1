"""Tests for deterministic quote grounding and numeric cross-checks."""

import pytest
from app.claims.ground import normalize_monetary_value, normalize_text, validate_and_ground_claim
from app.claims.schema import ClaimStatus, RawExtractedClaim


@pytest.fixture
def mock_sources():
    return {
        "src_001": {
            "id": "src_001",
            "sha256": "hash001",
            "ocr_used": False,
            "extracted_pages": {
                1: "Proposal requests a payout of $5.0M (5,000,000 USDC) to 0x9965507D1a55BCC6475675304Ca994970De97744 for Q1 security audits – with milestone reporting.",
                2: "Second page details on project scope and milestones.",
            },
        },
        "src_ocr": {
            "id": "src_ocr",
            "sha256": "hashocr",
            "ocr_used": True,
            "extracted_pages": {
                1: "Scanned memo stating grant amount of $100,000 USDC.",
            },
        },
    }


def test_grounding_normalization():
    # Test dashes, quotes, whitespace, and case
    raw = "Security  Audits — ‘Q1’   – “Milestones”"
    norm = normalize_text(raw)
    assert norm == 'security audits - \'q1\' - "milestones"'


def test_monetary_normalization():
    assert normalize_monetary_value("$5.0M") == "5000000"
    assert normalize_monetary_value("$5M") == "5000000"
    assert normalize_monetary_value("5,000,000 USDC") == "5000000"
    assert normalize_monetary_value("5000000") == "5000000"
    assert normalize_monetary_value("$5.8M") == "5800000"
    assert normalize_monetary_value("5,800,000") == "5800000"
    assert normalize_monetary_value("$500k") == "500000"


def test_valid_grounded_claim(mock_sources):
    raw = RawExtractedClaim(
        field="amount",
        value="$5.0M",
        quote="requests a payout of $5.0M (5,000,000 USDC)",
        source_id="src_001",
        page=1,
        confidence=0.95,
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.GROUNDED
    assert claim.value == "5000000"
    assert claim.display_value == "$5.0M"


def test_fabricated_quote_rejected(mock_sources):
    raw = RawExtractedClaim(
        field="amount",
        value="$5.0M",
        quote="this exact quote was completely fabricated by the model",
        source_id="src_001",
        page=1,
        confidence=0.95,
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.REJECTED
    assert any("not a substring" in d for d in claim.validation_details)


def test_numeric_mismatch_rejected(mock_sources):
    # Model claims $5.8M, but quote states $5.0M
    raw = RawExtractedClaim(
        field="amount",
        value="$5.8M",
        quote="requests a payout of $5.0M (5,000,000 USDC)",
        source_id="src_001",
        page=1,
        confidence=0.95,
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.REJECTED
    assert any("not supported by numbers in quote" in d for d in claim.validation_details)


def test_missing_source_rejected(mock_sources):
    raw = RawExtractedClaim(
        field="amount",
        value="$5.0M",
        quote="payout of $5.0M",
        source_id="src_nonexistent",
        page=1,
        confidence=0.95,
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.REJECTED
    assert any("does not exist" in d for d in claim.validation_details)


def test_nonexistent_page_rejected(mock_sources):
    raw = RawExtractedClaim(
        field="amount",
        value="$5.0M",
        quote="payout of $5.0M",
        source_id="src_001",
        page=99,
        confidence=0.95,
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.REJECTED
    assert any("Page 99 does not exist" in d for d in claim.validation_details)


def test_low_confidence_uncertain(mock_sources):
    raw = RawExtractedClaim(
        field="purpose",
        value="security audits",
        quote="security audits",
        source_id="src_001",
        page=1,
        confidence=0.65,  # Below 0.8
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.UNCERTAIN
    assert any("Low confidence" in d for d in claim.validation_details)


def test_ocr_source_uncertain(mock_sources):
    raw = RawExtractedClaim(
        field="amount",
        value="$100,000",
        quote="grant amount of $100,000 USDC",
        source_id="src_ocr",
        page=1,
        confidence=0.95,
    )
    claim = validate_and_ground_claim(raw, "PROP-001", mock_sources)
    assert claim.status == ClaimStatus.UNCERTAIN
    assert any("OCR fallback" in d for d in claim.validation_details)
