"""Tests for cryptographic hash formulas and sensitivity (hashes.py)."""

import hashlib
import pytest
from eth_utils import keccak

from app.manifest.canon import canonicalize_manifest
from app.manifest.hashes import (
    INITIAL_PREV_VERSION_HASH,
    compute_evidence_root,
    compute_manifest_action_hash,
    compute_proposal_text_hash,
    compute_version_hash,
    encode_erc20_transfer_calldata,
    normalize_hex_32,
)


def test_proposal_text_hash_determinism_and_sensitivity():
    text_v1 = "Proposal PROP-001: Payout 50,000 USDC to recipient."
    text_v1_modified = "Proposal PROP-001: Payout 50,001 USDC to recipient."

    hash_v1 = compute_proposal_text_hash(text_v1)
    hash_v1_again = compute_proposal_text_hash(text_v1.encode("utf-8"))
    assert hash_v1 == hash_v1_again
    assert hash_v1.startswith("0x") and len(hash_v1) == 66

    hash_modified = compute_proposal_text_hash(text_v1_modified)
    assert hash_v1 != hash_modified, "1-character change must alter proposalTextHash"


def test_evidence_root_sorting_and_sensitivity():
    doc1 = b"Evidence Document 1: Invoice for protocol audit"
    doc2 = b"Evidence Document 2: Milestone completion report"

    h1 = hashlib.sha256(doc1).hexdigest()
    h2 = hashlib.sha256(doc2).hexdigest()

    # Order invariance: list order does not affect root because evidenceRoot sorts hashes
    root_12 = compute_evidence_root([h1, h2])
    root_21 = compute_evidence_root([h2, h1])
    assert root_12 == root_21, "evidenceRoot must be permutation-invariant"

    # Sensitivity: change 1 byte of doc1 -> SHA-256 changes -> evidenceRoot changes
    doc1_tampered = b"Evidence Document 1: Invoice for protocol audit!"
    h1_tampered = hashlib.sha256(doc1_tampered).hexdigest()
    root_tampered = compute_evidence_root([h1_tampered, h2])
    assert root_12 != root_tampered, "1-byte change to evidence must alter evidenceRoot"

    # Empty list
    root_empty = compute_evidence_root([])
    assert root_empty == "0x" + keccak(b"").hex().lower()


def test_version_hash_chaining_and_sensitivity():
    manifest_v1 = {
        "proposalId": "PROP-001",
        "version": 1,
        "action": {
            "kind": "erc20_payout",
            "token": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "decimals": 6,
            "recipient": "0x9965507d1a55bcc6475675304ca994970de97744",
            "amountRaw": "1000000000000",
        },
        "envelope": {
            "maxTokenOutflow": {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "1000000000000"},
            "allowApprovals": False,
            "allowRoleChanges": False,
            "allowImplChange": False,
            "allowNewContracts": False,
        },
        "proposalTextHash": "0x" + "aa" * 32,
        "evidenceRoot": "0x" + "bb" * 32,
        "prevVersionHash": INITIAL_PREV_VERSION_HASH,
    }

    canon_bytes_v1 = canonicalize_manifest(manifest_v1)
    vhash_v1 = compute_version_hash(canon_bytes_v1, INITIAL_PREV_VERSION_HASH)
    assert vhash_v1.startswith("0x") and len(vhash_v1) == 66

    # 1-byte change to manifest changes versionHash
    manifest_tampered = dict(manifest_v1)
    manifest_tampered["proposalId"] = "PROP-002"
    canon_bytes_tampered = canonicalize_manifest(manifest_tampered)
    vhash_tampered = compute_version_hash(canon_bytes_tampered, INITIAL_PREV_VERSION_HASH)
    assert vhash_v1 != vhash_tampered

    # Version 2 with identical action but updated text hash and pointing to vhash_v1
    manifest_v2 = dict(manifest_v1)
    manifest_v2["version"] = 2
    manifest_v2["proposalTextHash"] = "0x" + "cc" * 32
    manifest_v2["prevVersionHash"] = vhash_v1

    canon_bytes_v2 = canonicalize_manifest(manifest_v2)
    vhash_v2 = compute_version_hash(canon_bytes_v2, vhash_v1)

    assert vhash_v2 != vhash_v1, "Version 2 must have a distinct versionHash from Version 1"


def test_action_hash_erc20_payout():
    action = {
        "kind": "erc20_payout",
        "token": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "decimals": 6,
        "recipient": "0x9965507d1a55bcc6475675304ca994970de97744",
        "amountRaw": "50000000000",
    }
    ahash = compute_manifest_action_hash(action)
    assert ahash.startswith("0x") and len(ahash) == 66

    # Changing amount changes actionHash
    action_diff_amount = dict(action)
    action_diff_amount["amountRaw"] = "50000000001"
    assert ahash != compute_manifest_action_hash(action_diff_amount)

    # Changing recipient changes actionHash
    action_diff_recipient = dict(action)
    action_diff_recipient["recipient"] = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8"
    assert ahash != compute_manifest_action_hash(action_diff_recipient)
