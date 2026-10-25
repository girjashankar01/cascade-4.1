"""Generate deterministic test fixtures for Stage 2."""

import json
from pathlib import Path
import pymupdf

fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
fixtures_dir.mkdir(parents=True, exist_ok=True)

# 1. proposal.pdf
pdf_path = fixtures_dir / "proposal.pdf"
doc = pymupdf.open()
page = doc.new_page()

proposal_text = """DAO Treasury Grant Proposal: PROP-001

1. Executive Summary
This proposal requests a payout of $5.0M (5,000,000 USDC) to the designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744.

2. Purpose
Funding infrastructure security audits and core protocol development for Q1.

3. Key Assumptions
Assumes milestone completion and quarterly reporting delivered to community governance. All transfers shall be executed via the GuardedExecutor contract.
"""

rect = pymupdf.Rect(50, 50, 550, 750)
page.insert_textbox(rect, proposal_text, fontsize=11)
doc.save(str(pdf_path))
doc.close()

# Verify PDF extraction
vdoc = pymupdf.open(str(pdf_path))
extracted = vdoc[0].get_text()
vdoc.close()
assert "$5.0M" in extracted
assert "5,000,000 USDC" in extracted
assert "0x9965507D1a55BCC6475675304Ca994970De97744" in extracted

# 2. forum_post.txt
forum_path = fixtures_dir / "forum_post.txt"
forum_text = """Community Discussion on Proposal PROP-001

Author: Governance Working Group
Date: October 2026

Regarding the grant proposal PROP-001 for recipient 0x9965507D1a55BCC6475675304Ca994970De97744, during the recent community budget review the revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC) to account for additional third-party audits and contingency costs.
"""
with open(forum_path, "w", encoding="utf-8") as f:
    f.write(forum_text)

# 3. expected_claims.json
oracle_data = {
    "proposal_id": "PROP-001",
    "sources": [
        {
            "filename": "proposal.pdf",
            "claims": [
                {
                    "field": "amount",
                    "value": "5000000",
                    "display_value": "$5.0M",
                    "quote": "This proposal requests a payout of $5.0M (5,000,000 USDC) to the designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744.",
                    "page": 1,
                    "confidence": 0.95,
                    "expected_status": "UNCERTAIN"  # Due to cross-source conflict with forum_post.txt
                },
                {
                    "field": "token",
                    "value": "USDC",
                    "display_value": "USDC",
                    "quote": "This proposal requests a payout of $5.0M (5,000,000 USDC) to the designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744.",
                    "page": 1,
                    "confidence": 0.95,
                    "expected_status": "GROUNDED"
                },
                {
                    "field": "recipient",
                    "value": "0x9965507D1a55BCC6475675304Ca994970De97744",
                    "display_value": "0x9965507D1a55BCC6475675304Ca994970De97744",
                    "quote": "This proposal requests a payout of $5.0M (5,000,000 USDC) to the designated recipient address 0x9965507D1a55BCC6475675304Ca994970De97744.",
                    "page": 1,
                    "confidence": 0.95,
                    "expected_status": "GROUNDED"
                },
                {
                    "field": "purpose",
                    "value": "Funding infrastructure security audits and core protocol development for Q1.",
                    "display_value": "Funding infrastructure security audits and core protocol development for Q1.",
                    "quote": "Funding infrastructure security audits and core protocol development for Q1.",
                    "page": 1,
                    "confidence": 0.90,
                    "expected_status": "GROUNDED"
                },
                {
                    "field": "assumptions",
                    "value": "Assumes milestone completion and quarterly reporting delivered to community governance.",
                    "display_value": "Assumes milestone completion and quarterly reporting delivered to community governance.",
                    "quote": "Assumes milestone completion and quarterly reporting delivered to community governance.",
                    "page": 1,
                    "confidence": 0.90,
                    "expected_status": "GROUNDED"
                }
            ]
        },
        {
            "filename": "forum_post.txt",
            "claims": [
                {
                    "field": "amount",
                    "value": "5800000",
                    "display_value": "$5.8M",
                    "quote": "revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC) to account for additional third-party audits and contingency costs.",
                    "page": 1,
                    "confidence": 0.95,
                    "expected_status": "UNCERTAIN"  # Due to cross-source conflict
                },
                {
                    "field": "token",
                    "value": "USDC",
                    "display_value": "USDC",
                    "quote": "revised allocation discussed in working group sessions is $5.8M (5,800,000 USDC)",
                    "page": 1,
                    "confidence": 0.95,
                    "expected_status": "GROUNDED"
                },
                {
                    "field": "recipient",
                    "value": "0x9965507D1a55BCC6475675304Ca994970De97744",
                    "display_value": "0x9965507D1a55BCC6475675304Ca994970De97744",
                    "quote": "Regarding the grant proposal PROP-001 for recipient 0x9965507D1a55BCC6475675304Ca994970De97744",
                    "page": 1,
                    "confidence": 0.95,
                    "expected_status": "GROUNDED"
                }
            ]
        }
    ],
    "expected_conflict": {
        "field": "amount",
        "value_a": "5000000",
        "value_b": "5800000",
        "status": "UNRESOLVED"
    }
}

expected_claims_path = fixtures_dir / "expected_claims.json"
with open(expected_claims_path, "w", encoding="utf-8") as f:
    json.dump(oracle_data, f, indent=2)

print("Generated fixtures successfully in:", fixtures_dir)
