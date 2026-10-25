"""Deterministic text grounding, numeric cross-checks, and claim validation."""

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.claims.schema import Claim, ClaimStatus, RawExtractedClaim, normalize_field_name

logger = logging.getLogger(__name__)

# Unicode dash characters to ASCII hyphen
DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")
# Curly quotes to ASCII quotes
QUOTE_RE = re.compile(r"[\u201c\u201d\u201e\u201f]")
APOS_RE = re.compile(r"[\u2018\u2019\u201a\u201b]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize whitespace, case, dashes, and quotes for deterministic substring grounding."""
    if not text:
        return ""
    t = DASH_RE.sub("-", text)
    t = QUOTE_RE.sub('"', t)
    t = APOS_RE.sub("'", t)
    t = WHITESPACE_RE.sub(" ", t).strip()
    return t.lower()


def normalize_monetary_value(raw: str) -> Optional[str]:
    """Parse monetary expressions ($5M, $5.0M, $5.8M, 5,000,000, 5000000, etc.) into an exact integer string."""
    if not raw:
        return None

    cleaned = raw.strip().replace(",", "")
    cleaned = re.sub(r"^\$", "", cleaned).strip()
    cleaned = re.sub(r"(?i)\b(usdc|usd)\b", "", cleaned).strip()
    cleaned = re.sub(r"\$", "", cleaned).strip()

    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([kmbKMB])?$", cleaned)
    if not match:
        return None

    num_str, multiplier = match.groups()
    try:
        val = Decimal(num_str)
    except InvalidOperation:
        return None

    if multiplier:
        mult_map = {
            "k": Decimal("1000"),
            "m": Decimal("1000000"),
            "b": Decimal("1000000000"),
        }
        val = val * mult_map[multiplier.lower()]

    # Return integer string if exact integer
    if val == val.to_integral():
        return str(int(val))
    return str(val)


def extract_numbers_from_quote(quote: str) -> List[str]:
    """Extract normalized monetary and numeric values present within a quote string."""
    candidates: List[str] = []
    # Pattern to match monetary strings like $5.0M, $5.8M, 5,000,000, 5,800,000, 5000000
    pattern = re.compile(r"\$?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:[kmbKMB]\b|usdc\b|usd\b)?", re.IGNORECASE)
    for match in pattern.finditer(quote):
        matched_str = match.group().strip()
        parsed = normalize_monetary_value(matched_str)
        if parsed is not None:
            candidates.append(parsed)

    # Also match plain numeric strings
    plain_num_pattern = re.compile(r"\b\d+(?:\.\d+)?\s*[kmbKMB]?\b")
    for match in plain_num_pattern.finditer(quote):
        parsed = normalize_monetary_value(match.group().strip())
        if parsed is not None and parsed not in candidates:
            candidates.append(parsed)

    return candidates


def validate_and_ground_claim(
    raw: RawExtractedClaim,
    proposal_id: str,
    sources_map: Dict[str, Dict[str, Any]],
    claim_index: int = 1,
) -> Claim:
    """Validate a raw claim against source text, verifying grounding, numeric accuracy, and uncertainty."""
    claim_id = f"clm_{proposal_id}_{claim_index}"
    details: List[str] = []
    status = ClaimStatus.GROUNDED

    # 1. Validate source existence
    source_meta = sources_map.get(raw.source_id)
    if not source_meta:
        status = ClaimStatus.REJECTED
        details.append(f"Source ID '{raw.source_id}' does not exist")
        return Claim(
            id=claim_id,
            proposal_id=proposal_id,
            field=raw.field,
            value=raw.value,
            display_value=raw.value,
            quote=raw.quote,
            source_id=raw.source_id,
            page=raw.page,
            confidence=raw.confidence,
            status=status,
            validation_details=details,
        )

    # 2. Validate page existence
    extracted_pages: Dict[int, str] = source_meta.get("extracted_pages", {})
    # Note: extracted_pages keys might be int or str in serialization
    page_text = extracted_pages.get(raw.page) or extracted_pages.get(str(raw.page))
    if page_text is None:
        status = ClaimStatus.REJECTED
        details.append(f"Page {raw.page} does not exist in source '{raw.source_id}'")
        return Claim(
            id=claim_id,
            proposal_id=proposal_id,
            field=raw.field,
            value=raw.value,
            display_value=raw.value,
            quote=raw.quote,
            source_id=raw.source_id,
            page=raw.page,
            confidence=raw.confidence,
            status=status,
            validation_details=details,
        )

    # 3. Grounding substring check
    norm_quote = normalize_text(raw.quote)
    norm_page = normalize_text(page_text)

    if not norm_quote or norm_quote not in norm_page:
        status = ClaimStatus.REJECTED
        details.append("Quote is not a substring of extracted page text (exact grounding required)")
        return Claim(
            id=claim_id,
            proposal_id=proposal_id,
            field=raw.field,
            value=raw.value,
            display_value=raw.value,
            quote=raw.quote,
            source_id=raw.source_id,
            page=raw.page,
            confidence=raw.confidence,
            status=status,
            validation_details=details,
        )

    # 4. Canonical field normalization and numeric cross-checks
    canonical_field = normalize_field_name(raw.field)
    display_value = raw.value.strip()
    normalized_value = display_value

    if canonical_field == "amount":
        parsed_claim_amount = normalize_monetary_value(display_value)
        if parsed_claim_amount is None:
            status = ClaimStatus.REJECTED
            details.append(f"Cannot parse monetary claim value '{display_value}'")
        else:
            normalized_value = parsed_claim_amount
            # Cross-check quote for evidence of this exact amount
            quote_amounts = extract_numbers_from_quote(raw.quote)
            if normalized_value not in quote_amounts:
                status = ClaimStatus.REJECTED
                details.append(
                    f"Claimed amount {normalized_value} not supported by numbers in quote: {quote_amounts}"
                )
            else:
                details.append(f"Numeric evidence verified: {normalized_value}")

    elif canonical_field == "recipient":
        # Check for Ethereum address format (0x + 40 hex chars)
        match = re.search(r"0x[a-fA-F0-9]{40}", display_value)
        if match:
            normalized_value = match.group()
            # Verify address is present in quote
            if normalized_value.lower() not in raw.quote.lower():
                status = ClaimStatus.REJECTED
                details.append(f"Recipient address {normalized_value} not found in quote")
            else:
                details.append(f"Recipient address verified: {normalized_value}")
        else:
            status = ClaimStatus.UNCERTAIN
            details.append(f"Recipient is not a valid 40-character hex EVM address: '{display_value}'")

    elif canonical_field == "token":
        normalized_value = display_value.upper()
        if normalized_value not in raw.quote.upper():
            status = ClaimStatus.REJECTED
            details.append(f"Token symbol {normalized_value} not mentioned in quote")

    # 5. Confidence and uncertainty labeling
    if status == ClaimStatus.GROUNDED:
        if raw.confidence < 0.8:
            status = ClaimStatus.UNCERTAIN
            details.append(f"Low confidence ({raw.confidence:.2f} < 0.8)")

        if source_meta.get("ocr_used", False):
            status = ClaimStatus.UNCERTAIN
            details.append("Source relied on OCR fallback")

    return Claim(
        id=claim_id,
        proposal_id=proposal_id,
        field=canonical_field,
        value=normalized_value,
        display_value=display_value,
        quote=raw.quote,
        source_id=raw.source_id,
        page=raw.page,
        confidence=raw.confidence,
        status=status,
        validation_details=details,
    )
