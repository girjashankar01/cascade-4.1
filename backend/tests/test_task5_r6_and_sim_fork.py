"""Tests for Task 5: R6 Honesty, Selector Inspection, and SIM_FORK_URL isolation."""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest
from web3 import Web3

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for p in (SCRIPTS_DIR, BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.verification.decode import DecodedTransaction
from app.verification.simulate import simulate_execution
from app.verification.verify import evaluate_rules


def test_r6_reduced_in_proof_mode_annotation():
    """Rule R6 must annotate [REDUCED IN PROOF MODE] in name and explanation when proof_mode is True."""
    manifest = {
        "proposalId": "PROP-1",
        "version": 1,
        "action": {"kind": "erc20_payout", "recipient": "0x1111111111111111111111111111111111111111", "amountRaw": "1000", "token": "0x2222222222222222222222222222222222222222"},
        "envelope": {"allowImplChange": False, "maxTokenOutflow": {"0x2222222222222222222222222222222222222222": "1000"}},
        "proposalTextHash": "0x" + "aa" * 32,
        "evidenceRoot": "0x" + "bb" * 32,
    }
    from app.manifest.canon import canonicalize_manifest
    from app.manifest.hashes import INITIAL_PREV_VERSION_HASH, compute_manifest_action_hash, compute_version_hash

    canon_bytes = canonicalize_manifest(manifest)
    vhash = compute_version_hash(canon_bytes, INITIAL_PREV_VERSION_HASH)
    ahash = compute_manifest_action_hash(manifest["action"])
    eroot = manifest["evidenceRoot"]

    decoded_tx = DecodedTransaction(
        target="0x2222222222222222222222222222222222222222",
        value=0,
        raw_data=bytes.fromhex("a9059cbb" + "00"*12 + "11"*20 + "00"*31 + "01"),
        selector="0xa9059cbb",
        method_name="transfer(address,uint256)",
        is_supported=True,
        action_hash=ahash,
        matches_manifest=True,
    )

    sim_result = {
        "success": True,
        "proof_mode": True,
        "slot_changes": {},
        "treasury_outflow": 1,
        "recipient_inflow": 1,
        "unexpected_gains": {},
        "allowance_changes": {},
    }

    verdict, outcomes = evaluate_rules(
        proposal_id="PROP-1",
        manifest=manifest,
        onchain_approved_tuple=(vhash, ahash, eroot),
        decoded_tx=decoded_tx,
        sim_result=sim_result,
        w3=None,
    )

    r6 = next(r for r in outcomes if r.rule_id == "R6")
    assert "[REDUCED IN PROOF MODE]" in r6.name
    assert "[REDUCED IN PROOF MODE]" in r6.explanation
    assert r6.status == "PASS"


def test_r6_flags_upgrade_selector_when_impl_change_disallowed():
    """Rule R6 must FAIL if calldata contains an upgrade selector when allowImplChange is False."""
    manifest = {
        "proposalId": "PROP-1",
        "version": 1,
        "action": {"kind": "erc20_payout", "recipient": "0x1111111111111111111111111111111111111111", "amountRaw": "1000", "token": "0x2222222222222222222222222222222222222222"},
        "envelope": {"allowImplChange": False, "maxTokenOutflow": {"0x2222222222222222222222222222222222222222": "1000"}},
        "proposalTextHash": "0x" + "aa" * 32,
        "evidenceRoot": "0x" + "bb" * 32,
    }
    from app.manifest.canon import canonicalize_manifest
    from app.manifest.hashes import INITIAL_PREV_VERSION_HASH, compute_manifest_action_hash, compute_version_hash

    canon_bytes = canonicalize_manifest(manifest)
    vhash = compute_version_hash(canon_bytes, INITIAL_PREV_VERSION_HASH)
    ahash = compute_manifest_action_hash(manifest["action"])
    eroot = manifest["evidenceRoot"]

    # Target selector is upgradeToAndCall (0x4f1ef286)
    decoded_tx = DecodedTransaction(
        target="0x2222222222222222222222222222222222222222",
        value=0,
        raw_data=bytes.fromhex("4f1ef286" + "00"*32),
        selector="0x4f1ef286",
        method_name="upgradeToAndCall(address,bytes)",
        is_supported=True,
        action_hash=ahash,
        matches_manifest=True,
    )

    sim_result = {
        "success": True,
        "proof_mode": True,
        "slot_changes": {},
        "treasury_outflow": 0,
        "recipient_inflow": 0,
        "unexpected_gains": {},
        "allowance_changes": {},
    }

    verdict, outcomes = evaluate_rules(
        proposal_id="PROP-1",
        manifest=manifest,
        onchain_approved_tuple=(vhash, ahash, eroot),
        decoded_tx=decoded_tx,
        sim_result=sim_result,
        w3=None,
    )

    r6 = next(r for r in outcomes if r.rule_id == "R6")
    assert r6.status == "FAIL"
    assert "Unauthorized upgrade selector 0x4f1ef286 detected" in r6.explanation


def test_sim_fork_url_not_used_when_unset(monkeypatch):
    """simulate_execution must stay in proof_onchain mode when SIM_FORK_URL is unset."""
    monkeypatch.delenv("SIM_FORK_URL", raising=False)
    monkeypatch.setenv("CHAIN_MODE", "proof")

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_balance.return_value = 10**18
    mock_w3.eth.call.return_value = b""

    manifest = {
        "action": {"kind": "erc20_payout", "recipient": "0x1111111111111111111111111111111111111111", "amountRaw": "1000"},
    }

    with patch("app.verification.simulate.read_account_state") as mock_read:
        mock_read.return_value = {"token_balance": 1000, "allowance_from_treasury": 0, "impl_slot": "", "owner": ""}
        res = simulate_execution(
            w3=mock_w3,
            treasury_address="0x3333333333333333333333333333333333333333",
            executor_address="0x4444444444444444444444444444444444444444",
            target="0x2222222222222222222222222222222222222222",
            value=0,
            data="0xa9059cbb",
            manifest=manifest,
        )

    assert res["proof_mode"] is True
    assert res["simulation_mode"] == "proof_onchain"
