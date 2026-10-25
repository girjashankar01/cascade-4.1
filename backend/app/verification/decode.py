"""Strict calldata decoding and manifest-to-transaction field comparison."""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Union

from eth_utils import keccak

from app.chain.attest import compute_action_hash

ADDR_PATTERN = re.compile(r"^0x[0-9a-fA-F]{40}$")

SELECTOR_ERC20_TRANSFER = "0xa9059cbb"
SELECTOR_ERC20_APPROVE = "0x095ea7b3"
SELECTOR_UPGRADE_TO_AND_CALL = "0x4f1ef286"

SUPPORTED_SELECTORS = {
    SELECTOR_ERC20_TRANSFER: "transfer(address,uint256)",
    SELECTOR_ERC20_APPROVE: "approve(address,uint256)",
}


class DecodingError(Exception):
    """Raised when calldata is malformed, truncated, or has non-canonical padding."""


@dataclass
class DecodedTransaction:
    target: str
    value: int
    raw_data: bytes
    selector: str
    method_name: str
    is_supported: bool
    token: Optional[str] = None
    recipient: Optional[str] = None
    spender: Optional[str] = None
    amount_raw: Optional[str] = None
    calldata_hash: str = ""
    action_hash: str = ""
    decoding_error: Optional[str] = None
    diff: Dict[str, Any] = field(default_factory=dict)
    matches_manifest: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "value": self.value,
            "calldata": f"0x{self.raw_data.hex()}" if self.raw_data else "",
            "selector": self.selector,
            "method_name": self.method_name,
            "is_supported": self.is_supported,
            "token": self.token,
            "recipient": self.recipient,
            "spender": self.spender,
            "amount_raw": self.amount_raw,
            "calldata_hash": self.calldata_hash,
            "action_hash": self.action_hash,
            "decoding_error": self.decoding_error,
            "diff": self.diff,
            "matches_manifest": self.matches_manifest,
        }


def decode_transaction(
    target: str,
    value: int,
    data: Union[str, bytes],
    manifest: Optional[Dict[str, Any]] = None,
) -> DecodedTransaction:
    """Strictly decode calldata and compare against approved governance manifest.

    Validates:
    - Target address format.
    - Non-negative ETH value.
    - Exact 68-byte calldata for static ERC-20 calls.
    - Canonical 12-byte zero padding for address parameters.
    - Known/supported selectors.
    - Exact field-level diff against manifest.
    """
    # 1. Validate target format
    target_clean = target.strip()
    if not ADDR_PATTERN.match(target_clean):
        return DecodedTransaction(
            target=target_clean,
            value=value,
            raw_data=b"",
            selector="",
            method_name="invalid_target",
            is_supported=False,
            decoding_error=f"Invalid target Ethereum address: '{target}'",
        )

    # 2. Validate ETH value
    if not isinstance(value, int) or value < 0:
        return DecodedTransaction(
            target=target_clean.lower(),
            value=value,
            raw_data=b"",
            selector="",
            method_name="invalid_value",
            is_supported=False,
            decoding_error=f"Invalid ETH value: {value} (must be non-negative integer)",
        )

    # 3. Normalize raw data bytes without mutating bytes
    if isinstance(data, str):
        hex_str = data.strip()
        if hex_str.startswith("0x") or hex_str.startswith("0X"):
            hex_str = hex_str[2:]
        try:
            raw_bytes = bytes.fromhex(hex_str)
        except ValueError as e:
            return DecodedTransaction(
                target=target_clean.lower(),
                value=value,
                raw_data=b"",
                selector="",
                method_name="invalid_hex",
                is_supported=False,
                decoding_error=f"Invalid hex string calldata: {e}",
            )
    else:
        raw_bytes = bytes(data)

    calldata_hash = "0x" + keccak(raw_bytes).hex().lower()
    computed_action_hash = "0x" + compute_action_hash(target_clean, value, raw_bytes).hex().lower()

    # 4. Check minimum selector length
    if len(raw_bytes) < 4:
        return DecodedTransaction(
            target=target_clean.lower(),
            value=value,
            raw_data=raw_bytes,
            selector=raw_bytes.hex(),
            method_name="truncated_calldata",
            is_supported=False,
            calldata_hash=calldata_hash,
            action_hash=computed_action_hash,
            decoding_error=f"Calldata too short for selector: got {len(raw_bytes)} bytes (minimum 4)",
        )

    selector = "0x" + raw_bytes[:4].hex().lower()

    # 5. Check supported selectors
    if selector == SELECTOR_UPGRADE_TO_AND_CALL:
        kind = manifest.get("action", {}).get("kind") if manifest else None
        if kind != "proxy_upgrade":
            return DecodedTransaction(
                target=target_clean.lower(),
                value=value,
                raw_data=raw_bytes,
                selector=selector,
                method_name="upgradeToAndCall(address,bytes)",
                is_supported=False,
                calldata_hash=calldata_hash,
                action_hash=computed_action_hash,
                decoding_error="upgradeToAndCall is unsupported for payout proposals",
            )

        if len(raw_bytes) < 36:
            return DecodedTransaction(
                target=target_clean.lower(),
                value=value,
                raw_data=raw_bytes,
                selector=selector,
                method_name="upgradeToAndCall(address,bytes)",
                is_supported=False,
                calldata_hash=calldata_hash,
                action_hash=computed_action_hash,
                decoding_error=f"Calldata too short for upgradeToAndCall: got {len(raw_bytes)} bytes",
            )

        word1 = raw_bytes[4:36]
        if word1[:12] != b"\x00" * 12:
            return DecodedTransaction(
                target=target_clean.lower(),
                value=value,
                raw_data=raw_bytes,
                selector=selector,
                method_name="upgradeToAndCall(address,bytes)",
                is_supported=False,
                calldata_hash=calldata_hash,
                action_hash=computed_action_hash,
                decoding_error="Non-canonical address encoding for new implementation (upper 12 bytes must be 0x00)",
            )

        new_impl_address = "0x" + word1[12:32].hex().lower()
        diff: Dict[str, Any] = {}
        action = manifest.get("action", {})
        expected_proxy = (action.get("proxy") or "").lower()
        expected_impl = (action.get("newImpl") or "").lower()

        diff["target"] = {
            "match": target_clean.lower() == expected_proxy,
            "approved": expected_proxy,
            "submitted": target_clean.lower(),
        }
        diff["recipient"] = {
            "match": new_impl_address.lower() == expected_impl,
            "approved": expected_impl,
            "submitted": new_impl_address.lower(),
        }
        diff["newImpl"] = diff["recipient"]
        diff["value"] = {
            "match": value == 0,
            "approved": 0,
            "submitted": value,
        }

        matches_manifest = all(item["match"] for item in diff.values())

        return DecodedTransaction(
            target=target_clean.lower(),
            value=value,
            raw_data=raw_bytes,
            selector=selector,
            method_name="upgradeToAndCall(address,bytes)",
            is_supported=True,
            recipient=new_impl_address,
            calldata_hash=calldata_hash,
            action_hash=computed_action_hash,
            decoding_error=None,
            diff=diff,
            matches_manifest=matches_manifest,
        )

    if selector not in SUPPORTED_SELECTORS:
        return DecodedTransaction(
            target=target_clean.lower(),
            value=value,
            raw_data=raw_bytes,
            selector=selector,
            method_name="unknown",
            is_supported=False,
            calldata_hash=calldata_hash,
            action_hash=computed_action_hash,
            decoding_error=f"Unknown or unsupported selector: {selector}",
        )

    method_name = SUPPORTED_SELECTORS[selector]

    # 6. Strict validation for static ERC-20 calls (must be exactly 68 bytes)
    if len(raw_bytes) != 68:
        return DecodedTransaction(
            target=target_clean.lower(),
            value=value,
            raw_data=raw_bytes,
            selector=selector,
            method_name=method_name,
            is_supported=False,
            calldata_hash=calldata_hash,
            action_hash=computed_action_hash,
            decoding_error=f"Calldata length mismatch: expected exactly 68 bytes for {method_name}, got {len(raw_bytes)}",
        )

    word1 = raw_bytes[4:36]
    word2 = raw_bytes[36:68]

    # Check canonical address encoding: upper 12 bytes must be 0x00
    if word1[:12] != b"\x00" * 12:
        return DecodedTransaction(
            target=target_clean.lower(),
            value=value,
            raw_data=raw_bytes,
            selector=selector,
            method_name=method_name,
            is_supported=False,
            calldata_hash=calldata_hash,
            action_hash=computed_action_hash,
            decoding_error="Non-canonical address encoding: upper 12 bytes of address word must be zero",
        )

    extracted_address = "0x" + word1[12:].hex().lower()
    amount_int = int.from_bytes(word2, byteorder="big")
    amount_raw_str = str(amount_int)

    recipient = extracted_address if selector == SELECTOR_ERC20_TRANSFER else None
    spender = extracted_address if selector == SELECTOR_ERC20_APPROVE else None
    token = target_clean.lower()

    # 7. Compare with manifest if provided
    diff: Dict[str, Any] = {}
    matches_manifest = False

    if manifest:
        action = manifest.get("action", {})
        expected_kind = action.get("kind")
        expected_token = (action.get("token") or "").lower()
        expected_recipient = (action.get("recipient") or "").lower()
        expected_amount_raw = str(action.get("amountRaw", ""))

        diff = {
            "target": {
                "approved": expected_token,
                "submitted": token,
                "match": token == expected_token,
            },
            "value": {
                "approved": 0,
                "submitted": value,
                "match": value == 0,
            },
            "function": {
                "approved": "transfer",
                "submitted": "transfer" if selector == SELECTOR_ERC20_TRANSFER else "approve",
                "match": selector == SELECTOR_ERC20_TRANSFER and expected_kind == "erc20_payout",
            },
            "recipient": {
                "approved": expected_recipient,
                "submitted": recipient or spender,
                "match": recipient == expected_recipient,
            },
            "amountRaw": {
                "approved": expected_amount_raw,
                "submitted": amount_raw_str,
                "match": amount_raw_str == expected_amount_raw,
            },
            "token": {
                "approved": expected_token,
                "submitted": token,
                "match": token == expected_token,
            },
        }

        # Check expected action hash if provided in manifest
        expected_action_hash = manifest.get("expected_action_hash") or manifest.get("action_hash")
        if expected_action_hash:
            diff["actionHash"] = {
                "approved": expected_action_hash.lower(),
                "submitted": computed_action_hash.lower(),
                "match": computed_action_hash.lower() == expected_action_hash.lower(),
            }

        matches_manifest = all(item["match"] for item in diff.values())

    return DecodedTransaction(
        target=token,
        value=value,
        raw_data=raw_bytes,
        selector=selector,
        method_name=method_name,
        is_supported=True,
        token=token,
        recipient=recipient,
        spender=spender,
        amount_raw=amount_raw_str,
        calldata_hash=calldata_hash,
        action_hash=computed_action_hash,
        decoding_error=None,
        diff=diff,
        matches_manifest=matches_manifest,
    )


# Backward-compatibility alias
decode_calldata = decode_transaction

