"""Strict Pydantic schemas for extracted claims, canonical fields, and conflicts."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ClaimStatus(str, Enum):
    GROUNDED = "GROUNDED"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"


CANONICAL_FIELDS = {"amount", "token", "recipient", "purpose", "assumptions"}

FIELD_ALIASES: Dict[str, str] = {
    "payout_amount": "amount",
    "payout": "amount",
    "budget": "amount",
    "grant_amount": "amount",
    "beneficiary": "recipient",
    "target": "recipient",
    "receiver": "recipient",
    "destination": "recipient",
    "currency": "token",
    "token_symbol": "token",
}


def normalize_field_name(raw_field: str) -> str:
    """Normalize a raw field name to its canonical identifier or reject unsupported fields."""
    cleaned = raw_field.strip().lower().replace(" ", "_")
    canonical = FIELD_ALIASES.get(cleaned, cleaned)
    if canonical not in CANONICAL_FIELDS:
        raise ValueError(
            f"Unsupported field '{raw_field}'. Supported canonical fields: {sorted(CANONICAL_FIELDS)}"
        )
    return canonical


class RawExtractedClaim(BaseModel):
    """Raw claim returned by an LLM before deterministic grounding and validation."""

    field: str
    value: str
    quote: str
    source_id: str
    page: int = 1
    confidence: float = 1.0

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        return normalize_field_name(v)

    @field_validator("page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"Page must be >= 1, got {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return float(v)


class Claim(BaseModel):
    """Validated claim with explicit status, original display value, and audit details."""

    id: str
    proposal_id: str
    field: str
    value: str  # Normalized value (e.g. integer string '5000000' or checksum address)
    display_value: str  # Original human/display string from evidence (e.g. '$5.0M')
    quote: str
    source_id: str
    page: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    status: ClaimStatus
    validation_details: List[str] = Field(default_factory=list)

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        return normalize_field_name(v)


class Conflict(BaseModel):
    """Contradiction detected across different sources for the same canonical field."""

    id: str
    proposal_id: str
    field: str
    value_a: str
    display_value_a: str
    source_id_a: str
    quote_a: str
    page_a: int
    value_b: str
    display_value_b: str
    source_id_b: str
    quote_b: str
    page_b: int
    status: str = "UNRESOLVED"


class AnalysisResponse(BaseModel):
    """API response model for POST /analyze/{pid} and GET /claims/{pid}."""

    proposal_id: str
    status: str
    claims: List[Claim]
    conflicts: List[Conflict]
    provider: str
    model: str
    cache_status: str  # 'cached' or 'generated_now'
    summary: Optional[str] = None
