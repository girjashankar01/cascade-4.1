"""Deterministic canonicalization for DAO Accountability Engine manifests."""

import json
import re
from typing import Any, Dict, List

ADDR_PATTERN = re.compile(r"^0x[0-9a-fA-F]{40}$")


def is_eth_address(val: str) -> bool:
    """Return True if val is a 42-character 0x-prefixed hex Ethereum address."""
    return bool(ADDR_PATTERN.match(val))


def normalize_for_canonical(val: Any) -> Any:
    """Recursively clean data structure: lowercase addresses, reject floats, sort dictionary keys."""
    if isinstance(val, float):
        raise ValueError(f"Floating point numbers are strictly forbidden in canonical manifests: {val}")

    if isinstance(val, dict):
        cleaned_dict: Dict[str, Any] = {}
        for k, v in val.items():
            if not isinstance(k, str):
                raise ValueError(f"Dictionary keys must be strings, got {type(k).__name__}")
            # If key is an Ethereum address, normalize to lowercase
            key = k.lower() if is_eth_address(k) else k
            cleaned_dict[key] = normalize_for_canonical(v)
        return cleaned_dict

    if isinstance(val, list):
        return [normalize_for_canonical(item) for item in val]

    if isinstance(val, str):
        # If string is an Ethereum address, normalize to lowercase
        if is_eth_address(val):
            return val.lower()
        return val

    # int, bool, None
    return val


def canonical_json(val: Any) -> str:
    """Serialize object to compact canonical JSON string with sorted keys, no whitespace, UTF-8."""
    cleaned = normalize_for_canonical(val)
    return json.dumps(cleaned, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def canonicalize_manifest(manifest: Dict[str, Any]) -> bytes:
    """Produce deterministic UTF-8 bytes for a canonical manifest."""
    return canonical_json(manifest).encode("utf-8")
