"""Conflict-of-Interest (COI) wallet provenance and linkage analysis module."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import networkx as nx

from app.chain.client import PK_PROPOSER
from eth_account import Account

DEFAULT_PROPOSER_ADDR = Account.from_key(PK_PROPOSER).address.lower()
DEFAULT_RECIPIENT_ADDR = "0x9965507d1a55bcc6475675304ca994970de97744"
SHELL_INTERMEDIARY_ADDR = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8"


@dataclass
class WalletNode:
    address: str
    label: str
    category: str  # "proposer", "recipient", "intermediary", "funder"
    is_declared: bool


@dataclass
class LinkEdge:
    source: str
    target: str
    edge_type: str  # "declared", "observed_transfer", "shared_funder", "common_contract"
    evidence_strength: str  # "high", "medium", "inferred"
    details: str
    amount_usd: Optional[float] = None
    tx_hash: Optional[str] = None


@dataclass
class COIReport:
    proposal_id: str
    proposer_address: str
    recipient_address: str
    has_linkage: bool
    shortest_path: List[str]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    undisclosed_connections: List[Dict[str, Any]]
    summary: str
    is_demo_data: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_proposal_coi_analysis(
    proposal_id: str,
    proposer: Optional[str] = None,
    recipient: Optional[str] = None,
) -> COIReport:
    """Perform provenance and conflict-of-interest linkage analysis for a proposal.

    Tracks:
    - Signed proposer wallet disclosures (proof of control).
    - Seeded and observed on-chain funding relationships.
    - Graph pathfinding between proposer and recipient.
    - Undisclosed intermediary connections.

    Note on Interpretation:
    - Provenance results reflect observed graph linkage and financial proximity.
    - They must not be interpreted as definitive proof of wrongdoing or subjective intent.
    - Demonstrates graph analysis over seeded/disclosed data, not live blockchain indexing.
    """
    if not proposal_id or not proposal_id.strip():
        raise ValueError("Invalid proposal ID")

    pid_clean = proposal_id.strip().upper()

    # If proposal is a protocol upgrade (PROP-B2, PROP-B3), no grant recipient exists
    if pid_clean.startswith("PROP-B2") or pid_clean.startswith("PROP-B3") or pid_clean.startswith("PROP-UPGRADE"):
        prop_addr = (proposer or DEFAULT_PROPOSER_ADDR).lower()
        return COIReport(
            proposal_id=proposal_id,
            proposer_address=prop_addr,
            recipient_address="",
            has_linkage=False,
            shortest_path=[],
            nodes=[
                asdict(WalletNode(
                    address=prop_addr,
                    label="Proposer Main Wallet",
                    category="proposer",
                    is_declared=True,
                ))
            ],
            edges=[],
            undisclosed_connections=[],
            summary="Protocol contract upgrade proposal: No grant recipient or funding intermediary linkage evaluated.",
            is_demo_data=True,
        )

    prop_addr = (proposer or DEFAULT_PROPOSER_ADDR).lower()
    rec_addr = (recipient or DEFAULT_RECIPIENT_ADDR).lower()
    shell_addr = SHELL_INTERMEDIARY_ADDR.lower()

    # Build directed provenance graph
    G = nx.DiGraph()

    nodes: List[WalletNode] = [
        WalletNode(
            address=prop_addr,
            label="Proposer Main Wallet",
            category="proposer",
            is_declared=True,
        ),
        WalletNode(
            address=shell_addr,
            label="Intermediary Entity (Horizon Labs)",
            category="intermediary",
            is_declared=False,
        ),
        WalletNode(
            address=rec_addr,
            label="Grant Beneficiary",
            category="recipient",
            is_declared=False,
        ),
    ]

    edges: List[LinkEdge] = [
        LinkEdge(
            source=prop_addr,
            target=shell_addr,
            edge_type="observed_transfer",
            evidence_strength="high",
            details="Observed seed funding transfer (150,000 USDC) 14 days prior to submission",
            amount_usd=150000.0,
            tx_hash="0x3a1f4b82c9e7104b2a8d6f0c4e2b8a7d1e9f0c2b4a6d8e0f2b4a6d8e0f2b4a6d",
        ),
        LinkEdge(
            source=shell_addr,
            target=rec_addr,
            edge_type="observed_transfer",
            evidence_strength="high",
            details="Direct operational transfer (50,000 USDC) & shared deployment signatory",
            amount_usd=50000.0,
            tx_hash="0x5b2c8e1f0a3d4e6f8a2b0c4d6e8f0a2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f",
        ),
        LinkEdge(
            source=prop_addr,
            target=rec_addr,
            edge_type="shared_funder",
            evidence_strength="inferred",
            details="Common initial gas funding from exchange hot wallet 0x28C6...34",
            amount_usd=None,
        ),
    ]

    for n in nodes:
        G.add_node(n.address, label=n.label, category=n.category, is_declared=n.is_declared)

    for e in edges:
        G.add_edge(
            e.source,
            e.target,
            edge_type=e.edge_type,
            evidence_strength=e.evidence_strength,
            details=e.details,
            amount_usd=e.amount_usd,
        )

    # Pathfinding
    has_linkage = False
    shortest_path: List[str] = []
    try:
        path = nx.shortest_path(G, source=prop_addr, target=rec_addr)
        shortest_path = path
        has_linkage = len(path) > 1
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        has_linkage = False
        shortest_path = []

    undisclosed = [
        {
            "address": shell_addr,
            "label": "Intermediary Entity (Horizon Labs)",
            "linkage_type": "undisclosed_funding_bridge",
            "evidence": "Received 150,000 USDC from proposer, routed 50,000 USDC to recipient",
            "risk_score": "MEDIUM",
        }
    ]

    summary = (
        f"Linkage evidence detected: Proposer ({prop_addr[:8]}...) is connected to Beneficiary "
        f"({rec_addr[:8]}...) via a 2-hop funding path through intermediary {shell_addr[:8]}... "
        f"(Horizon Labs). Note: This reflects on-chain transfer linkage and financial proximity, "
        f"not proof of subjective intent or wrongdoing."
    )

    return COIReport(
        proposal_id=proposal_id,
        proposer_address=prop_addr,
        recipient_address=rec_addr,
        has_linkage=has_linkage,
        shortest_path=shortest_path,
        nodes=[asdict(n) for n in nodes],
        edges=[asdict(e) for e in edges],
        undisclosed_connections=undisclosed,
        summary=summary,
        is_demo_data=True,
    )
