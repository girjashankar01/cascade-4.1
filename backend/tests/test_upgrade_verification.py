"""Unit and integration tests for Stage 6 proxy upgrades, Rule R6, and Rule R7 bytecode scanning."""

import pytest
from eth_utils import keccak

from app.manifest.hashes import (
    compute_manifest_action_hash,
    encode_upgrade_to_and_call_calldata,
)
from app.verification.decode import (
    SELECTOR_UPGRADE_TO_AND_CALL,
    decode_transaction,
)
from app.verification.verify import (
    VERDICT_MISMATCH,
    VERDICT_VERIFIED,
    evaluate_rules,
    scan_bytecode,
)

PROXY_ADDR = "0x1111111111111111111111111111111111111111"
BASE_IMPL = "0x2222222222222222222222222222222222222222"
V2_IMPL = "0x3333333333333333333333333333333333333333"
EVIL_IMPL = "0x4444444444444444444444444444444444444444"

# Selector constants
SEL_VERSION = "0x54fd4d50"
SEL_INCREMENT = "0xd09de08a"
SEL_SWEEP = "0x35faa416"  # keccak256("sweep()")[:4]


def test_scan_bytecode_finds_push4_and_opcodes():
    # Construct synthetic bytecode:
    # PUSH4 0x54fd4d50 (version)
    # DELEGATECALL (0xF4)
    # PUSH4 0x35faa416 (sweep)
    # SELFDESTRUCT (0xFF)
    code = (
        bytes.fromhex("6354fd4d50")  # PUSH4 54fd4d50
        + bytes.fromhex("f4")          # DELEGATECALL
        + bytes.fromhex("6335faa416")  # PUSH4 35faa416
        + bytes.fromhex("ff")          # SELFDESTRUCT
    )

    ops, sels = scan_bytecode(code)
    assert "DELEGATECALL" in ops
    assert "SELFDESTRUCT" in ops
    assert "0x54fd4d50" in sels
    assert "0x35faa416" in sels


def test_decode_upgrade_to_and_call_calldata():
    calldata = encode_upgrade_to_and_call_calldata(V2_IMPL, b"")
    assert len(calldata) == 100
    assert calldata.hex().startswith("4f1ef286")

    manifest = {
        "proposalId": "PROP-UPGRADE-V2",
        "action": {
            "kind": "proxy_upgrade",
            "proxy": PROXY_ADDR,
            "newImpl": V2_IMPL,
            "declaredSelectors": [SEL_VERSION, SEL_INCREMENT],
        },
        "envelope": {
            "allowImplChange": True,
            "allowApprovals": False,
            "allowRoleChanges": False,
        },
    }

    decoded = decode_transaction(
        target=PROXY_ADDR,
        value=0,
        data=calldata,
        manifest=manifest,
    )

    assert decoded.is_supported is True
    assert decoded.selector == SELECTOR_UPGRADE_TO_AND_CALL
    assert decoded.recipient == V2_IMPL.lower()
    assert decoded.matches_manifest is True
    assert decoded.diff["target"]["match"] is True
    assert decoded.diff["recipient"]["match"] is True


def test_decode_upgrade_calldata_mismatch_detection():
    # Calldata points to EVIL_IMPL, but manifest approved V2_IMPL
    calldata = encode_upgrade_to_and_call_calldata(EVIL_IMPL, b"")

    manifest = {
        "proposalId": "PROP-UPGRADE-V2",
        "action": {
            "kind": "proxy_upgrade",
            "proxy": PROXY_ADDR,
            "newImpl": V2_IMPL,
            "declaredSelectors": [SEL_VERSION, SEL_INCREMENT],
        },
        "envelope": {"allowImplChange": True},
    }

    decoded = decode_transaction(
        target=PROXY_ADDR,
        value=0,
        data=calldata,
        manifest=manifest,
    )

    assert decoded.is_supported is True
    assert decoded.matches_manifest is False
    assert decoded.diff["recipient"]["match"] is False
    assert decoded.diff["recipient"]["approved"] == V2_IMPL.lower()
    assert decoded.diff["recipient"]["submitted"] == EVIL_IMPL.lower()


def test_compute_manifest_action_hash_for_proxy_upgrade():
    action = {
        "kind": "proxy_upgrade",
        "proxy": PROXY_ADDR,
        "newImpl": V2_IMPL,
    }
    ah = compute_manifest_action_hash(action)
    assert ah.startswith("0x")
    assert len(ah) == 66


def test_rule_r6_detects_unauthorized_slot_change():
    valid_token = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    valid_recip = "0x9965507d1a55bcc6475675304ca994970de97744"
    manifest = {
        "proposalId": "PROP-002",
        "action": {
            "kind": "erc20_payout",
            "token": valid_token,
            "recipient": valid_recip,
            "amountRaw": "1000",
        },
        "envelope": {"allowImplChange": False},
        "version_hash": "0x" + "11" * 32,
    }

    # Simulation observed an unexpected implementation slot change
    sim_result = {
        "success": True,
        "tx_status": 1,
        "restoration_verified": True,
        "slot_changes": {
            PROXY_ADDR.lower(): {"before": "0x" + "00" * 32, "after": "0x" + "22" * 32}
        },
    }

    calldata = bytes.fromhex("a9059cbb") + b"\x00" * 12 + bytes.fromhex(valid_recip[2:]) + (1000).to_bytes(32, "big")
    decoded = decode_transaction(target=valid_token, value=0, data=calldata, manifest=manifest)
    assert decoded.is_supported is True

    # In onchain approval tuple, assume matching versionHash and actionHash
    onchain = ("0x" + "11" * 32, decoded.action_hash, "0x" + "33" * 32)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-002",
        manifest=manifest,
        onchain_approved_tuple=onchain,
        decoded_tx=decoded,
        sim_result=sim_result,
    )

    assert verdict == VERDICT_MISMATCH
    r6 = next(r for r in rules if r.rule_id == "R6")
    assert r6.status == "FAIL"
    assert "Unauthorized implementation slot changes" in r6.explanation


def test_rule_r7_detects_undeclared_selector(monkeypatch):
    # Manifest declares version and increment, but NOT sweep
    manifest = {
        "proposalId": "PROP-UPGRADE-EVIL",
        "action": {
            "kind": "proxy_upgrade",
            "proxy": PROXY_ADDR,
            "newImpl": EVIL_IMPL,
            "declaredSelectors": [SEL_VERSION, SEL_INCREMENT],
        },
        "envelope": {"allowImplChange": True},
        "version_hash": "0x" + "11" * 32,
    }

    calldata = encode_upgrade_to_and_call_calldata(EVIL_IMPL, b"")
    decoded = decode_transaction(target=PROXY_ADDR, value=0, data=calldata, manifest=manifest)
    assert decoded.is_supported is True

    # Mock web3 get_code to return synthetic bytecode containing SEL_SWEEP
    evil_code = (
        bytes.fromhex("6354fd4d50")  # PUSH4 54fd4d50 (version)
        + bytes.fromhex("6335faa416")  # PUSH4 35faa416 (sweep - undeclared!)
    )

    class MockEth:
        def get_code(self, addr):
            return evil_code

        def get_storage_at(self, addr, slot):
            return b"\x00" * 32

    class MockWeb3:
        eth = MockEth()

    monkeypatch.setattr("app.verification.verify.get_web3", lambda *args, **kwargs: MockWeb3())

    sim_result = {
        "success": True,
        "tx_status": 1,
        "restoration_verified": True,
        "slot_changes": {
            PROXY_ADDR.lower(): {"before": "0x" + "00" * 32, "after": "0x" + "00" * 12 + EVIL_IMPL[2:]}
        },
    }

    onchain = ("0x" + "11" * 32, decoded.action_hash, "0x" + "33" * 32)
    verdict, rules = evaluate_rules(
        proposal_id="PROP-UPGRADE-EVIL",
        manifest=manifest,
        onchain_approved_tuple=onchain,
        decoded_tx=decoded,
        sim_result=sim_result,
    )

    assert verdict == VERDICT_MISMATCH
    r7 = next(r for r in rules if r.rule_id == "R7")
    assert r7.status == "FAIL"
    assert "Undeclared selector candidates detected" in r7.explanation
    assert SEL_SWEEP in r7.evidence["undeclared_selectors"]

