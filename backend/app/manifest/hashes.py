"""Cryptographic hash computations for the DAO Accountability Engine version chain."""

import re
from typing import Any, Dict, List, Union
from eth_utils import keccak, to_bytes, to_checksum_address
from app.chain.attest import compute_action_hash

INITIAL_PREV_VERSION_HASH = "0x" + "00" * 32
ERC20_TRANSFER_SELECTOR = bytes.fromhex("a9059cbb")


def normalize_hex_32(h: Union[str, bytes]) -> str:
    """Ensure a 32-byte hash is returned as a 66-character lowercase hex string with 0x prefix."""
    if isinstance(h, bytes):
        raw = h
    else:
        s = h.strip()
        if s.startswith("0x") or s.startswith("0X"):
            s = s[2:]
        raw = bytes.fromhex(s)
    if len(raw) != 32:
        raise ValueError(f"Expected 32 bytes for hash, got {len(raw)} bytes")
    return "0x" + raw.hex().lower()


def compute_proposal_text_hash(text: Union[str, bytes]) -> str:
    """Compute keccak256 of the exact proposal text seen by voters.

    Input: text (str or bytes).
    Formula: keccak256(UTF-8 bytes of exact proposal text).
    """
    raw_bytes = text.encode("utf-8") if isinstance(text, str) else text
    digest = keccak(raw_bytes)
    return "0x" + digest.hex().lower()


def compute_evidence_root(sha256_hashes: List[str]) -> str:
    """Compute evidenceRoot = keccak256(concatenated sorted binary sha256 digests).

    Formula:
        Sorted list of evidence file SHA-256 hashes, concatenated as 32-byte binary values,
        then hashed with Keccak-256.
    """
    if not sha256_hashes:
        return "0x" + keccak(b"").hex().lower()

    # Clean and sort hexadecimal strings
    clean_hashes = []
    for h in sha256_hashes:
        s = h.strip()
        if s.startswith("0x") or s.startswith("0X"):
            s = s[2:]
        if len(s) != 64:
            raise ValueError(f"Invalid SHA-256 hash length: {len(s)} hex chars (expected 64)")
        clean_hashes.append(s.lower())

    clean_hashes.sort()
    binary_concat = b"".join(bytes.fromhex(h) for h in clean_hashes)
    digest = keccak(binary_concat)
    return "0x" + digest.hex().lower()


def compute_version_hash(canonical_manifest_bytes: bytes, prev_version_hash: str) -> str:
    """Compute versionHash = keccak256(canonical(manifest) || prevVersionHash).

    Input:
        canonical_manifest_bytes: UTF-8 encoded compact canonical JSON.
        prev_version_hash: 32-byte hex string (with or without 0x).
    Formula:
        keccak256(canonical_manifest_bytes + 32-byte binary prevVersionHash).
    """
    clean_prev = prev_version_hash.strip()
    if clean_prev.startswith("0x") or clean_prev.startswith("0X"):
        clean_prev = clean_prev[2:]
    prev_bytes = bytes.fromhex(clean_prev)
    if len(prev_bytes) != 32:
        raise ValueError(f"prevVersionHash must be 32 bytes, got {len(prev_bytes)}")

    payload = canonical_manifest_bytes + prev_bytes
    digest = keccak(payload)
    return "0x" + digest.hex().lower()


def encode_erc20_transfer_calldata(recipient: str, amount_raw: Union[int, str]) -> bytes:
    """Encode standard ERC-20 transfer(address,uint256) calldata."""
    clean_addr = recipient.strip()
    if clean_addr.startswith("0x") or clean_addr.startswith("0X"):
        clean_addr = clean_addr[2:]
    if len(clean_addr) != 40:
        raise ValueError(f"Invalid Ethereum address length: {len(clean_addr)}")

    recipient_bytes = bytes.fromhex(clean_addr.rjust(64, "0"))
    amount_int = int(amount_raw)
    amount_bytes = amount_int.to_bytes(32, byteorder="big")
    return ERC20_TRANSFER_SELECTOR + recipient_bytes + amount_bytes


def encode_upgrade_to_and_call_calldata(new_impl: str, data: bytes = b"") -> bytes:
    """Encode standard UUPS upgradeToAndCall(address,bytes) calldata."""
    clean_addr = new_impl.strip()
    if clean_addr.startswith("0x") or clean_addr.startswith("0X"):
        clean_addr = clean_addr[2:]
    if len(clean_addr) != 40:
        raise ValueError(f"Invalid Ethereum address length: {len(clean_addr)}")

    selector = bytes.fromhex("4f1ef286")
    addr_bytes = bytes.fromhex(clean_addr.rjust(64, "0"))
    offset_bytes = (64).to_bytes(32, byteorder="big")
    len_bytes = len(data).to_bytes(32, byteorder="big")
    padding_len = (32 - (len(data) % 32)) % 32
    padded_data = data + (b"\x00" * padding_len)
    return selector + addr_bytes + offset_bytes + len_bytes + padded_data


def compute_manifest_action_hash(action: Dict[str, Any]) -> str:
    """Compute actionHash from manifest action dictionary.

    Formula:
        actionHash = keccak256(abi.encode(target, value, keccak256(calldata)))
    """
    kind = action.get("kind")
    if kind == "erc20_payout":
        token = action.get("token")
        recipient = action.get("recipient")
        amount_raw = action.get("amountRaw")

        if not token or not recipient or amount_raw is None:
            raise ValueError("Missing required fields for erc20_payout action")

        calldata = encode_erc20_transfer_calldata(recipient=recipient, amount_raw=amount_raw)
        ah = compute_action_hash(target=token, value=0, data=calldata)
        return "0x" + ah.hex().lower()
    elif kind == "proxy_upgrade":
        proxy = action.get("proxy")
        new_impl = action.get("newImpl")
        if not proxy or not new_impl:
            raise ValueError("Missing required fields (proxy, newImpl) for proxy_upgrade action")
        calldata = encode_upgrade_to_and_call_calldata(new_impl=new_impl, data=b"")
        ah = compute_action_hash(target=proxy, value=0, data=calldata)
        return "0x" + ah.hex().lower()
    else:
        raise ValueError(f"Unsupported action kind: '{kind}'")
