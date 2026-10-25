"""Tests for canonical manifest serialization (canon.py)."""

import json
import pytest

from app.manifest.canon import (
    canonical_json,
    canonicalize_manifest,
    is_eth_address,
    normalize_for_canonical,
)


def test_key_ordering_invariance():
    dict_a = {
        "version": 1,
        "proposalId": "PROP-001",
        "action": {
            "token": "0x6b175474e89094c44da98b954eedeac495271d0f",
            "kind": "erc20_payout",
            "recipient": "0x9965507d1a55bcc6475675304ca994970de97744",
            "amountRaw": "1000000000000",
            "decimals": 6,
        },
    }
    dict_b = {
        "action": {
            "decimals": 6,
            "amountRaw": "1000000000000",
            "kind": "erc20_payout",
            "recipient": "0x9965507d1a55bcc6475675304ca994970de97744",
            "token": "0x6b175474e89094c44da98b954eedeac495271d0f",
        },
        "proposalId": "PROP-001",
        "version": 1,
    }

    canon_a = canonical_json(dict_a)
    canon_b = canonical_json(dict_b)
    assert canon_a == canon_b, "Canonical JSON must be key-order invariant"
    assert canonicalize_manifest(dict_a) == canonicalize_manifest(dict_b)


def test_no_insignificant_whitespace():
    sample = {
        "b": "value",
        "a": [1, 2, 3],
        "c": {"inner": True},
    }
    canon = canonical_json(sample)
    assert " " not in canon
    assert "\n" not in canon
    assert "\t" not in canon
    assert canon == '{"a":[1,2,3],"b":"value","c":{"inner":true}}'


def test_eth_address_lowercasing():
    mixed_addr = "0x9965507D1a55BCC6475675304Ca994970De97744"
    lower_addr = "0x9965507d1a55bcc6475675304ca994970de97744"
    assert is_eth_address(mixed_addr)
    assert is_eth_address(lower_addr)

    manifest_mixed = {
        "recipient": mixed_addr,
        "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    }
    manifest_lower = {
        "recipient": lower_addr,
        "token": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    }
    assert canonical_json(manifest_mixed) == canonical_json(manifest_lower)
    assert canonicalize_manifest(manifest_mixed) == canonicalize_manifest(manifest_lower)


def test_strict_float_rejection():
    # Floating point numbers are strictly forbidden in canonical manifests
    with pytest.raises(ValueError, match="Floating point numbers are strictly forbidden"):
        canonical_json({"amount": 1000.50})

    with pytest.raises(ValueError, match="Floating point numbers are strictly forbidden"):
        canonical_json({"nested": {"ratio": 0.05}})

    with pytest.raises(ValueError, match="Floating point numbers are strictly forbidden"):
        canonical_json({"items": [1, 2, 3.14]})


def test_unicode_determinism():
    # Canonical JSON must produce identical UTF-8 bytes for unicode strings
    unicode_dict = {
        "title": "Überprüfung & Gültigkeit — 100% 🚀",
        "symbol": "€ / ¥ / £",
    }
    canon = canonical_json(unicode_dict)
    utf8_bytes = canonicalize_manifest(unicode_dict)
    assert utf8_bytes == canon.encode("utf-8")
    # Verify that ensure_ascii=False was used (raw unicode chars, not escaped \u...)
    assert "Überprüfung" in canon
    assert "🚀" in canon


def test_numbers_as_integer_strings():
    # Token amounts and 256-bit numbers must be integer strings to avoid precision loss
    large_num_str = "115792089237316195423570985008687907853269984665640564039457584007913129639935"
    manifest = {
        "amountRaw": large_num_str,
        "version": 1,
    }
    canon = canonical_json(manifest)
    parsed = json.loads(canon)
    assert parsed["amountRaw"] == large_num_str
    assert isinstance(parsed["amountRaw"], str)
