"""Unit tests for strict calldata decoding and manifest comparison (decode.py)."""

import pytest

from app.chain.attest import compute_action_hash
from app.manifest.hashes import encode_erc20_transfer_calldata
from app.verification.decode import (
    SELECTOR_ERC20_APPROVE,
    SELECTOR_ERC20_TRANSFER,
    SELECTOR_UPGRADE_TO_AND_CALL,
    decode_transaction,
)

TOKEN_ADDR = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
RECIPIENT_ADDR = "0x9965507d1a55bcc6475675304ca994970de97744"
ATTACKER_ADDR = "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65"
AMOUNT_RAW = "1000000000000"


@pytest.fixture
def clean_manifest():
    return {
        "proposalId": "PROP-002",
        "version": 1,
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
        "expected_action_hash": "0x"
        + compute_action_hash(
            TOKEN_ADDR, 0, encode_erc20_transfer_calldata(RECIPIENT_ADDR, AMOUNT_RAW)
        ).hex(),
    }


def test_valid_erc20_transfer_decoding(clean_manifest):
    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, AMOUNT_RAW)
    assert len(calldata) == 68

    decoded = decode_transaction(
        target=TOKEN_ADDR,
        value=0,
        data=calldata,
        manifest=clean_manifest,
    )

    assert decoded.is_supported is True
    assert decoded.decoding_error is None
    assert decoded.selector == SELECTOR_ERC20_TRANSFER
    assert decoded.recipient == RECIPIENT_ADDR
    assert decoded.amount_raw == AMOUNT_RAW
    assert decoded.matches_manifest is True
    assert decoded.diff["all_matched"] is True if "all_matched" in decoded.diff else True


def test_reject_calldata_length_mismatch(clean_manifest):
    valid_calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, AMOUNT_RAW)

    # Truncated (67 bytes)
    truncated = valid_calldata[:-1]
    d_trunc = decode_transaction(target=TOKEN_ADDR, value=0, data=truncated, manifest=clean_manifest)
    assert d_trunc.is_supported is False
    assert "Calldata length mismatch" in d_trunc.decoding_error

    # Trailing bytes (69 bytes)
    trailing = valid_calldata + b"\x00"
    d_trail = decode_transaction(target=TOKEN_ADDR, value=0, data=trailing, manifest=clean_manifest)
    assert d_trail.is_supported is False
    assert "Calldata length mismatch" in d_trail.decoding_error

    # Less than 4 bytes
    d_short = decode_transaction(target=TOKEN_ADDR, value=0, data=b"\xa9\x05", manifest=clean_manifest)
    assert d_short.is_supported is False
    assert "Calldata too short" in d_short.decoding_error


def test_reject_noncanonical_address_padding(clean_manifest):
    # Standard: 4 bytes selector + 12 bytes 0x00 + 20 bytes address + 32 bytes amount
    selector = bytes.fromhex("a9059cbb")
    # Non-zero byte in the upper 12 bytes of address word
    dirty_padding = bytes.fromhex("000000000000000000000001")
    addr_bytes = bytes.fromhex(RECIPIENT_ADDR[2:])
    amount_bytes = int(AMOUNT_RAW).to_bytes(32, byteorder="big")

    malformed_calldata = selector + dirty_padding + addr_bytes + amount_bytes
    assert len(malformed_calldata) == 68

    decoded = decode_transaction(
        target=TOKEN_ADDR,
        value=0,
        data=malformed_calldata,
        manifest=clean_manifest,
    )

    assert decoded.is_supported is False
    assert "Non-canonical address encoding" in decoded.decoding_error


def test_reject_invalid_target_and_negative_value(clean_manifest):
    valid_calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, AMOUNT_RAW)

    # Invalid target address
    d_bad_target = decode_transaction(target="0xnotanaddress", value=0, data=valid_calldata)
    assert d_bad_target.is_supported is False
    assert "Invalid target Ethereum address" in d_bad_target.decoding_error

    # Negative ETH value
    d_neg_value = decode_transaction(target=TOKEN_ADDR, value=-1, data=valid_calldata)
    assert d_neg_value.is_supported is False
    assert "Invalid ETH value" in d_neg_value.decoding_error


def test_unsupported_selectors(clean_manifest):
    # Random unknown selector
    unknown_calldata = bytes.fromhex("12345678") + b"\x00" * 64
    d_unknown = decode_transaction(target=TOKEN_ADDR, value=0, data=unknown_calldata)
    assert d_unknown.is_supported is False
    assert "Unknown or unsupported selector" in d_unknown.decoding_error

    # upgradeToAndCall
    upgrade_calldata = bytes.fromhex("4f1ef286") + b"\x00" * 64
    d_upgrade = decode_transaction(target=TOKEN_ADDR, value=0, data=upgrade_calldata)
    assert d_upgrade.is_supported is False
    assert "upgradeToAndCall is unsupported" in d_upgrade.decoding_error


def test_manifest_comparison_detects_altered_recipient_and_amount(clean_manifest):
    # Altered recipient
    bad_recip_calldata = encode_erc20_transfer_calldata(ATTACKER_ADDR, AMOUNT_RAW)
    d_bad_recip = decode_transaction(
        target=TOKEN_ADDR,
        value=0,
        data=bad_recip_calldata,
        manifest=clean_manifest,
    )
    assert d_bad_recip.is_supported is True
    assert d_bad_recip.matches_manifest is False
    assert d_bad_recip.diff["recipient"]["match"] is False
    assert d_bad_recip.diff["recipient"]["approved"] == RECIPIENT_ADDR
    assert d_bad_recip.diff["recipient"]["submitted"] == ATTACKER_ADDR

    # Inflated amount
    inflated_amount = str(int(AMOUNT_RAW) * 2)
    bad_amount_calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, inflated_amount)
    d_bad_amount = decode_transaction(
        target=TOKEN_ADDR,
        value=0,
        data=bad_amount_calldata,
        manifest=clean_manifest,
    )
    assert d_bad_amount.is_supported is True
    assert d_bad_amount.matches_manifest is False
    assert d_bad_amount.diff["amountRaw"]["match"] is False
    assert d_bad_amount.diff["amountRaw"]["approved"] == AMOUNT_RAW
    assert d_bad_amount.diff["amountRaw"]["submitted"] == inflated_amount
