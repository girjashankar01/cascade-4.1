"""Tests for deterministic conflict detection and uncertainty marking."""

import pytest
from app.claims.conflicts import detect_conflicts
from app.claims.schema import Claim, ClaimStatus


def test_equivalent_monetary_representations_no_conflict():
    claim_a = Claim(
        id="c1",
        proposal_id="PROP-001",
        field="amount",
        value="5000000",
        display_value="$5.0M",
        quote="requests a payout of $5.0M",
        source_id="src_pdf",
        page=1,
        confidence=0.95,
        status=ClaimStatus.GROUNDED,
    )
    claim_b = Claim(
        id="c2",
        proposal_id="PROP-001",
        field="amount",
        value="5000000",
        display_value="5,000,000 USDC",
        quote="allocation of 5,000,000 USDC",
        source_id="src_forum",
        page=1,
        confidence=0.95,
        status=ClaimStatus.GROUNDED,
    )

    conflicts, updated_claims = detect_conflicts([claim_a, claim_b], "PROP-001")
    assert len(conflicts) == 0
    assert all(c.status == ClaimStatus.GROUNDED for c in updated_claims)


def test_conflicting_amounts_detected():
    claim_a = Claim(
        id="c1",
        proposal_id="PROP-001",
        field="amount",
        value="5000000",
        display_value="$5.0M",
        quote="requests a payout of $5.0M (5,000,000 USDC)",
        source_id="src_pdf",
        page=1,
        confidence=0.95,
        status=ClaimStatus.GROUNDED,
    )
    claim_b = Claim(
        id="c2",
        proposal_id="PROP-001",
        field="amount",
        value="5800000",
        display_value="$5.8M",
        quote="revised allocation discussed is $5.8M (5,800,000 USDC)",
        source_id="src_forum",
        page=1,
        confidence=0.95,
        status=ClaimStatus.GROUNDED,
    )

    conflicts, updated_claims = detect_conflicts([claim_a, claim_b], "PROP-001")
    assert len(conflicts) == 1
    conf = conflicts[0]
    assert conf.field == "amount"
    assert conf.value_a == "5000000"
    assert conf.display_value_a == "$5.0M"
    assert conf.value_b == "5800000"
    assert conf.display_value_b == "$5.8M"
    assert conf.source_id_a == "src_pdf"
    assert conf.source_id_b == "src_forum"
    assert conf.status == "UNRESOLVED"

    # Both claims must now be marked UNCERTAIN
    assert all(c.status == ClaimStatus.UNCERTAIN for c in updated_claims)
    assert any("Conflicting evidence detected" in d for d in updated_claims[0].validation_details)


def test_rejected_claim_does_not_conflict_with_grounded():
    claim_grounded = Claim(
        id="c1",
        proposal_id="PROP-001",
        field="amount",
        value="5000000",
        display_value="$5.0M",
        quote="payout of $5.0M",
        source_id="src_pdf",
        page=1,
        confidence=0.95,
        status=ClaimStatus.GROUNDED,
    )
    claim_rejected = Claim(
        id="c2",
        proposal_id="PROP-001",
        field="amount",
        value="9999999",
        display_value="$10M",
        quote="fake hallucinated quote",
        source_id="src_forum",
        page=1,
        confidence=0.95,
        status=ClaimStatus.REJECTED,
    )

    conflicts, updated_claims = detect_conflicts([claim_grounded, claim_rejected], "PROP-001")
    assert len(conflicts) == 0
    grounded_res = next(c for c in updated_claims if c.id == "c1")
    assert grounded_res.status == ClaimStatus.GROUNDED
