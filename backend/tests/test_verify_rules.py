"""Unit tests for deterministic verification rules R1, R2, R3, R4, R5, R6, R7, R9 (verify.py)."""

import pytest

from app.verification.decode import DecodedTransaction
from app.verification.verify import (
    VERDICT_MISMATCH,
    VERDICT_UNCERTAIN,
    VERDICT_UNSUPPORTED,
    VERDICT_VERIFIED,
    evaluate_rules,
)

TOKEN_ADDR = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
RECIPIENT_ADDR = "0x9965507d1a55bcc6475675304ca994970de97744"
ATTACKER_ADDR = "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65"
AMOUNT_RAW = "1000000000000"
V_HASH = "0x" + "11" * 32
A_HASH = "0x" + "22" * 32
E_ROOT = "0x" + "33" * 32


@pytest.fixture
def base_manifest():
    return {
        "proposalId": "PROP-002",
        "version": 1,
        "version_hash": V_HASH,
        "evidence_root": E_ROOT,
        "action": {
            "kind": "erc20_payout",
            "token": TOKEN_ADDR,
            "decimals": 6,
            "recipient": RECIPIENT_ADDR,
            "amountRaw": AMOUNT_RAW,
        },
        "envelope": {
            "maxTokenOutflow": {TOKEN_ADDR: AMOUNT_RAW},
            "allowApprovals": False,
            "allowRoleChanges": False,
            "allowImplChange": False,
            "allowNewContracts": False,
        },
    }


@pytest.fixture
def perfect_decoded():
    return DecodedTransaction(
        target=TOKEN_ADDR,
        value=0,
        raw_data=b"\x00" * 68,
        selector="0xa9059cbb",
        method_name="transfer(address,uint256)",
        is_supported=True,
        token=TOKEN_ADDR,
        recipient=RECIPIENT_ADDR,
        amount_raw=AMOUNT_RAW,
        calldata_hash="0x" + "aa" * 32,
        action_hash=A_HASH,
        decoding_error=None,
        diff={},
        matches_manifest=True,
    )


@pytest.fixture
def perfect_sim_result():
    return {
        "success": True,
        "restoration_verified": True,
        "treasury_outflow": int(AMOUNT_RAW),
        "recipient_inflow": int(AMOUNT_RAW),
        "unexpected_gains": {},
        "allowance_changes": {},
        "slot_changes": {},
        "owner_changes": {},
        "dynamic_addresses": [],
        "discovery_cap_reached": False,
    }


def test_rule_evaluation_all_pass_gives_verified(base_manifest, perfect_decoded, perfect_sim_result):
    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=perfect_sim_result,
    )
    assert verdict == VERDICT_VERIFIED
    assert all(r.status == "PASS" for r in rules)


def test_rule_r1_failure_on_version_mismatch(base_manifest, perfect_decoded, perfect_sim_result):
    # On-chain approved version hash differs from manifest
    tampered_tuple = ("0x" + "99" * 32, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=tampered_tuple,
        decoded_tx=perfect_decoded,
        sim_result=perfect_sim_result,
    )
    assert verdict == VERDICT_MISMATCH
    r1 = next(r for r in rules if r.rule_id == "R1")
    assert r1.status == "FAIL"


def test_rule_r2_failure_on_action_mismatch(base_manifest, perfect_decoded, perfect_sim_result):
    # Action hash does not match
    bad_decoded = DecodedTransaction(
        target=TOKEN_ADDR,
        value=0,
        raw_data=b"\x00" * 68,
        selector="0xa9059cbb",
        method_name="transfer(address,uint256)",
        is_supported=True,
        token=TOKEN_ADDR,
        recipient=ATTACKER_ADDR,
        amount_raw=AMOUNT_RAW,
        action_hash="0x" + "ff" * 32,  # wrong action hash!
        matches_manifest=False,
    )
    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=bad_decoded,
        sim_result=perfect_sim_result,
    )
    assert verdict == VERDICT_MISMATCH
    r2 = next(r for r in rules if r.rule_id == "R2")
    assert r2.status == "FAIL"


def test_rule_r3_failure_on_outflow_exceeded(base_manifest, perfect_decoded, perfect_sim_result):
    # Simulated treasury outflow exceeds allowed envelope
    sim_excessive = dict(perfect_sim_result)
    sim_excessive["treasury_outflow"] = int(AMOUNT_RAW) * 2

    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=sim_excessive,
    )
    assert verdict == VERDICT_MISMATCH
    r3 = next(r for r in rules if r.rule_id == "R3")
    assert r3.status == "FAIL"


def test_rule_r4_failure_on_unexpected_gains(base_manifest, perfect_decoded, perfect_sim_result):
    # An unexpected address receives tokens during simulation
    sim_gains = dict(perfect_sim_result)
    sim_gains["unexpected_gains"] = {ATTACKER_ADDR: 500}

    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=sim_gains,
    )
    assert verdict == VERDICT_MISMATCH
    r4 = next(r for r in rules if r.rule_id == "R4")
    assert r4.status == "FAIL"


def test_rule_r5_failure_on_allowance_change(base_manifest, perfect_decoded, perfect_sim_result):
    # Envelope says allowApprovals = False, but simulation produced an allowance delta
    sim_allowance = dict(perfect_sim_result)
    sim_allowance["allowance_changes"] = {ATTACKER_ADDR: 1_000_000}

    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=sim_allowance,
    )
    assert verdict == VERDICT_MISMATCH
    r5 = next(r for r in rules if r.rule_id == "R5")
    assert r5.status == "FAIL"


def test_rule_r6_failure_on_impl_slot_change(base_manifest, perfect_decoded, perfect_sim_result):
    # Envelope says allowImplChange = False, but simulation changed EIP-1967 slot
    sim_slot = dict(perfect_sim_result)
    sim_slot["slot_changes"] = {TOKEN_ADDR: {"before": "0x00", "after": "0x11"}}

    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=sim_slot,
    )
    assert verdict == VERDICT_MISMATCH
    r6 = next(r for r in rules if r.rule_id == "R6")
    assert r6.status == "FAIL"


def test_rule_r9_failure_on_owner_change(base_manifest, perfect_decoded, perfect_sim_result):
    # Envelope says allowRoleChanges = False, but contract owner changed
    sim_owner = dict(perfect_sim_result)
    sim_owner["owner_changes"] = {TOKEN_ADDR: {"before": "0x00", "after": "0x11"}}

    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=sim_owner,
    )
    assert verdict == VERDICT_MISMATCH
    r9 = next(r for r in rules if r.rule_id == "R9")
    assert r9.status == "FAIL"


def test_verdict_unsupported_when_selector_not_supported(base_manifest, perfect_decoded, perfect_sim_result):
    unsupported_tx = DecodedTransaction(
        target=TOKEN_ADDR,
        value=0,
        raw_data=b"\x12\x34\x56\x78",
        selector="0x12345678",
        method_name="unknown",
        is_supported=False,
    )
    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=unsupported_tx,
        sim_result=perfect_sim_result,
    )
    assert verdict == VERDICT_UNSUPPORTED


def test_verdict_uncertain_when_restoration_fails(base_manifest, perfect_decoded, perfect_sim_result):
    unrestored_sim = dict(perfect_sim_result)
    unrestored_sim["restoration_verified"] = False

    approved_tuple = (V_HASH, A_HASH, E_ROOT)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=base_manifest,
        onchain_approved_tuple=approved_tuple,
        decoded_tx=perfect_decoded,
        sim_result=unrestored_sim,
    )
    assert verdict == VERDICT_UNCERTAIN
