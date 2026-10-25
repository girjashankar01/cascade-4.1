"""Deterministic cross-source conflict detection between grounded claims."""

import logging
from typing import List, Tuple

from app.claims.schema import Claim, ClaimStatus, Conflict

logger = logging.getLogger(__name__)


def values_conflict(field: str, val_a: str, val_b: str) -> bool:
    """Determine deterministically whether two values for the same field contradict each other."""
    if val_a == val_b:
        return False

    if field == "amount":
        # Amount values are normalized to integer strings (e.g. '5000000' vs '5800000')
        # If strings differ, they represent different monetary amounts
        return val_a != val_b

    if field == "recipient":
        # Check EVM address equality case-insensitively
        return val_a.lower() != val_b.lower()

    if field == "token":
        # Check token symbols case-insensitively
        return val_a.upper() != val_b.upper()

    # For text fields (purpose, assumptions), differing text is not necessarily a contradiction,
    # unless completely contradictory, but for core fields amount/recipient/token it is definitive.
    return False


def detect_conflicts(
    claims: List[Claim],
    proposal_id: str,
) -> Tuple[List[Conflict], List[Claim]]:
    """Detect cross-source contradictions among valid claims.

    Returns (conflicts_list, updated_claims_list with conflicting claims marked UNCERTAIN).
    """
    conflicts: List[Conflict] = []
    # Filter only claims that are not REJECTED
    valid_claims = [c for c in claims if c.status != ClaimStatus.REJECTED]
    conflicting_claim_ids = set()

    conflict_idx = 1
    # Compare each pair of claims from different sources on the same field
    for i in range(len(valid_claims)):
        for j in range(i + 1, len(valid_claims)):
            claim_a = valid_claims[i]
            claim_b = valid_claims[j]

            # Only compare claims from different sources for the same canonical field
            if claim_a.field == claim_b.field and claim_a.source_id != claim_b.source_id:
                if values_conflict(claim_a.field, claim_a.value, claim_b.value):
                    conflict_id = f"conf_{proposal_id}_{conflict_idx}"
                    conflict_idx += 1

                    conflicts.append(
                        Conflict(
                            id=conflict_id,
                            proposal_id=proposal_id,
                            field=claim_a.field,
                            value_a=claim_a.value,
                            display_value_a=claim_a.display_value,
                            source_id_a=claim_a.source_id,
                            quote_a=claim_a.quote,
                            page_a=claim_a.page,
                            value_b=claim_b.value,
                            display_value_b=claim_b.display_value,
                            source_id_b=claim_b.source_id,
                            quote_b=claim_b.quote,
                            page_b=claim_b.page,
                            status="UNRESOLVED",
                        )
                    )
                    conflicting_claim_ids.add(claim_a.id)
                    conflicting_claim_ids.add(claim_b.id)

    # Update claims status: any claim involved in a conflict becomes UNCERTAIN
    updated_claims: List[Claim] = []
    for c in claims:
        if c.id in conflicting_claim_ids:
            updated_details = list(c.validation_details)
            updated_details.append("Conflicting evidence detected across sources (marked UNCERTAIN)")
            updated_claim = c.model_copy(
                update={
                    "status": ClaimStatus.UNCERTAIN,
                    "validation_details": updated_details,
                }
            )
            updated_claims.append(updated_claim)
        else:
            updated_claims.append(c)

    return conflicts, updated_claims
