"""Public chain Web3 utilities for EIP-1559 transactions and testnet verification.

Isolated from local Anvil flows. Targets public EVM testnets (e.g. Polygon Amoy, Base Sepolia).
"""

from dataclasses import dataclass, field
from decimal import Decimal
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Union

import eth_abi
from eth_account import Account
from eth_utils import to_checksum_address
from web3 import Web3
from web3.exceptions import ContractLogicError

logger = logging.getLogger("chain_public")


def parse_priority_fee_wei(val: Union[str, float, int, Decimal, None]) -> int:
    """Parse priority fee from Gwei string, float or Decimal to exact Wei integer.

    Accepts decimal values (e.g. 0.0001, 25.5).
    """
    if val is None or str(val).strip() == "":
        return 0
    try:
        d = Decimal(str(val).strip())
        return int(d * Decimal(10**9))
    except Exception as e:
        logger.warning(f"Invalid priority fee '{val}': {e}; using 0 wei")
        return 0


def call_with_rpc_retry(fn, max_retries: int = 3, base_delay: float = 1.0) -> Any:
    """Execute Web3 RPC read call with exponential backoff on HTTP 429 or transient timeouts."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            err_str = str(exc).lower()
            is_transient = "429" in err_str or "rate limit" in err_str or "timeout" in err_str or "connection" in err_str
            if is_transient and attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise

# In-memory per-address nonce tracker to prevent collisions on rapid back-to-back submissions
_NONCE_LOCK = threading.Lock()
_ADDRESS_NONCES: Dict[str, int] = {}


def get_next_nonce(w3: Web3, address: str) -> int:
    """Retrieve the next collision-safe transaction nonce for an address.

    Queries pending transaction count from the node and reconciles with an in-memory counter.
    """
    cs_addr = to_checksum_address(address)
    with _NONCE_LOCK:
        pending_nonce = w3.eth.get_transaction_count(cs_addr, "pending")
        prev_nonce = _ADDRESS_NONCES.get(cs_addr)
        if prev_nonce is None:
            nonce = pending_nonce
        else:
            nonce = max(pending_nonce, prev_nonce + 1)
        _ADDRESS_NONCES[cs_addr] = nonce
        return nonce


def reset_nonce_counter(address: Optional[str] = None) -> None:
    """Reset the in-memory nonce tracker (useful for test isolation)."""
    with _NONCE_LOCK:
        if address:
            _ADDRESS_NONCES.pop(to_checksum_address(address), None)
        else:
            _ADDRESS_NONCES.clear()


@dataclass
class ProofConfig:
    """Holds configuration loaded from proof environment file without exposing private keys in logs."""

    chain_id: int
    rpc_url: str
    explorer_base: str
    priority_fee_gwei: Optional[float]
    deployer_pk: str = field(repr=False)
    proposer_pk: str = field(repr=False)
    governance_pk: str = field(repr=False)
    verifier_pk: str = field(repr=False)
    addresses: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, str] = field(default_factory=dict, repr=False)
    w3: Optional[Web3] = field(default=None, repr=False)

    def __getitem__(self, key: str) -> Any:
        if key in self.raw:
            return self.raw[key]
        attr = key.lower()
        if hasattr(self, attr):
            return getattr(self, attr)
        raise KeyError(key)

    def __repr__(self) -> str:
        safe_keys = {k: ("[REDACTED]" if "PK" in k or "PRIVATE_KEY" in k else v) for k, v in self.raw.items()}
        return f"ProofConfig(chain_id={self.chain_id}, rpc_url='{self.rpc_url}', explorer_base='{self.explorer_base}', keys={safe_keys})"


def load_proof_env(path: Union[str, Path] = ".env.amoy", w3: Optional[Web3] = None) -> ProofConfig:
    """Load public chain configuration from environment file.

    Loads CHAIN_ID, AMOY_RPC (or RPC_URL_PROOF), EXPLORER_BASE, PRIORITY_FEE_GWEI (optional),
    DEPLOYER_PK, PROPOSER_PK, GOVERNANCE_PK, VERIFIER_PK, and any *_ADDR values.

    Never logs any *_PK values.
    Raises ValueError if connected chain ID differs from configured CHAIN_ID.
    """
    env_path = Path(path)
    if not env_path.is_absolute() and not env_path.exists():
        # Fall back to repo root resolution
        repo_root = Path(__file__).resolve().parents[3]
        candidate = repo_root / path
        if candidate.exists():
            env_path = candidate

    if not env_path.exists():
        raise FileNotFoundError(f"Proof environment file not found at {path} (resolved {env_path})")

    raw_env: Dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                raw_env[k] = v

    # 1. Parse chain ID
    chain_id_val = raw_env.get("CHAIN_ID") or os.environ.get("CHAIN_ID")
    if not chain_id_val:
        raise ValueError(f"Missing required CHAIN_ID in {env_path}")
    try:
        expected_chain_id = int(chain_id_val)
    except ValueError as e:
        raise ValueError(f"Invalid integer for CHAIN_ID '{chain_id_val}': {e}") from e

    # 2. Parse RPC URL
    rpc_url = (
        raw_env.get("AMOY_RPC")
        or raw_env.get("RPC_URL_PROOF")
        or os.environ.get("AMOY_RPC")
        or os.environ.get("RPC_URL_PROOF")
    )
    if not rpc_url:
        raise ValueError(f"Missing AMOY_RPC or RPC_URL_PROOF in {env_path}")

    # 3. Explorer base
    explorer_base = (raw_env.get("EXPLORER_BASE") or os.environ.get("EXPLORER_BASE") or "").rstrip("/")

    # 4. Priority fee
    p_fee = raw_env.get("PRIORITY_FEE_GWEI") or os.environ.get("PRIORITY_FEE_GWEI")
    priority_fee_gwei = float(p_fee) if p_fee else None

    # 5. Extract private keys without logging
    deployer_pk = raw_env.get("DEPLOYER_PK") or os.environ.get("DEPLOYER_PK", "")
    proposer_pk = raw_env.get("PROPOSER_PK") or os.environ.get("PROPOSER_PK", "")
    governance_pk = raw_env.get("GOVERNANCE_PK") or os.environ.get("GOVERNANCE_PK", "")
    verifier_pk = raw_env.get("VERIFIER_PK") or os.environ.get("VERIFIER_PK", "")

    # 6. Extract *_ADDR values
    addresses: Dict[str, str] = {}
    for k, v in raw_env.items():
        if k.endswith("_ADDR"):
            addresses[k] = v
    for k, v in os.environ.items():
        if k.endswith("_ADDR") and k not in addresses:
            addresses[k] = v

    # Log safe summary
    logger.info(
        f"Loaded proof env from {env_path.name}: CHAIN_ID={expected_chain_id}, "
        f"RPC={rpc_url}, addresses={list(addresses.keys())} (all *_PK values redacted)"
    )

    # 7. Validate connection and chain ID match
    active_w3 = w3
    if active_w3 is None:
        active_w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not active_w3.is_connected():
        raise ConnectionError(f"Unable to connect to Web3 provider at {rpc_url}")

    try:
        actual_chain_id = active_w3.eth.chain_id
    except Exception as e:
        raise ConnectionError(f"Failed to query eth_chainId from {rpc_url}: {e}") from e

    if actual_chain_id != expected_chain_id:
        raise ValueError(
            f"Chain ID mismatch: connected chain ID {actual_chain_id} "
            f"differs from configured CHAIN_ID {expected_chain_id}"
        )

    return ProofConfig(
        chain_id=expected_chain_id,
        rpc_url=rpc_url,
        explorer_base=explorer_base,
        priority_fee_gwei=priority_fee_gwei,
        deployer_pk=deployer_pk,
        proposer_pk=proposer_pk,
        governance_pk=governance_pk,
        verifier_pk=verifier_pk,
        addresses=addresses,
        raw=raw_env,
        w3=active_w3,
    )


def send_tx_1559(
    w3: Web3,
    private_key: str,
    tx_or_fn: Any,
    *,
    gas: int,
    value: int = 0,
    wait_timeout: int = 120,
    expect_revert: bool = False,
) -> Dict[str, Any]:
    """Build, sign, and broadcast an EIP-1559 (Type 2) transaction with fee bumping and collision-safe nonce.

    - Builds Type 2 tx: maxPriorityFeePerGas = max(PRIORITY_FEE_GWEI, w3.eth.max_priority_fee),
      maxFeePerGas = 2 * latest baseFee + tip.
    - Resolves nonce from get_transaction_count(addr, "pending") with an in-memory tracker.
    - Retries once on "replacement transaction underpriced" or "nonce too low" with fees bumped 25%.
    - Waits up to wait_timeout.
    - Returns dict {tx_hash, status, block_number, receipt}. Raises if status == 0 unless expect_revert=True.
    """
    account = Account.from_key(private_key)
    caller_addr = account.address

    # Calculate base fees and tip
    env_p_gwei = os.environ.get("PRIORITY_FEE_GWEI")
    configured_tip_wei = parse_priority_fee_wei(env_p_gwei)

    try:
        node_tip_wei = w3.eth.max_priority_fee
    except Exception:
        node_tip_wei = Web3.to_wei(2, "gwei")

    max_priority_fee = max(configured_tip_wei, node_tip_wei)

    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas", Web3.to_wei(1, "gwei"))
    max_fee_per_gas = (2 * base_fee) + max_priority_fee
    chain_id = w3.eth.chain_id

    nonce = get_next_nonce(w3, caller_addr)

    tx_val = int(tx_or_fn.get("value", value)) if isinstance(tx_or_fn, dict) else int(value)
    tx_gas = int(tx_or_fn.get("gas", gas)) if isinstance(tx_or_fn, dict) else int(gas)

    tx_params = {
        "from": caller_addr,
        "nonce": nonce,
        "gas": tx_gas,
        "value": tx_val,
        "maxPriorityFeePerGas": int(max_priority_fee),
        "maxFeePerGas": int(max_fee_per_gas),
        "chainId": int(chain_id),
        "type": 2,
    }

    if hasattr(tx_or_fn, "build_transaction"):
        tx = tx_or_fn.build_transaction(tx_params)
    elif isinstance(tx_or_fn, dict):
        tx = {**tx_params, **tx_or_fn, "nonce": nonce, "gas": tx_gas, "value": tx_val}
    else:
        raise TypeError(f"tx_or_fn must be a ContractFunction or dict, got {type(tx_or_fn)}")

    signed = w3.eth.account.sign_transaction(tx, private_key)

    try:
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    except Exception as exc:
        err_msg = str(exc).lower()
        if "replacement transaction underpriced" in err_msg or "nonce too low" in err_msg:
            logger.warning(f"send_raw_transaction encountered '{exc}'; retrying once with 25% bumped fees...")
            # Bump priority fee and max fee by 25%
            bumped_tip = int(max_priority_fee * 1.25) + 1
            bumped_max_fee = int(max_fee_per_gas * 1.25) + 1

            if "nonce too low" in err_msg:
                # Refresh nonce from node
                with _NONCE_LOCK:
                    pending = w3.eth.get_transaction_count(caller_addr, "pending")
                    nonce = max(pending, _ADDRESS_NONCES.get(caller_addr, 0) + 1)
                    _ADDRESS_NONCES[caller_addr] = nonce

            tx_params["nonce"] = nonce
            tx_params["maxPriorityFeePerGas"] = bumped_tip
            tx_params["maxFeePerGas"] = bumped_max_fee

            if hasattr(tx_or_fn, "build_transaction"):
                tx = tx_or_fn.build_transaction(tx_params)
            else:
                tx = {**tx_params, **tx_or_fn, "nonce": nonce, "gas": tx_gas, "value": tx_val}

            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        elif expect_revert:
            logger.warning(f"Transaction rejected by node before mempool/mining: {exc}")
            reason = str(exc)
            if "execution reverted:" in err_msg:
                reason = err_msg.split("execution reverted:")[-1].strip().strip("'\"")
            return {
                "tx_hash": None,
                "status": 0,
                "block_number": None,
                "receipt": None,
                "revert_reason": reason,
                "node_rejected_before_mining": True,
            }
        else:
            raise

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=wait_timeout)
    hex_hash = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    if not hex_hash.startswith("0x"):
        hex_hash = "0x" + hex_hash

    res = {
        "tx_hash": hex_hash,
        "status": int(receipt.status),
        "block_number": int(receipt.blockNumber),
        "receipt": receipt,
        "revert_reason": None,
    }

    if receipt.status == 0:
        reason = revert_reason(w3, hex_hash)
        res["revert_reason"] = reason
        if not expect_revert:
            raise RuntimeError(
                f"Transaction {hex_hash} mined with failure status 0 at block {receipt.blockNumber}. "
                f"Revert reason: {reason}"
            )

    return res


def decode_revert_data(raw_data: Union[str, bytes]) -> str:
    """Decode raw ABI-encoded revert bytes into a human-readable string."""
    if isinstance(raw_data, str):
        clean = raw_data.strip()
        if clean.startswith("0x") or clean.startswith("0X"):
            clean = clean[2:]
        try:
            raw_bytes = bytes.fromhex(clean)
        except Exception:
            return "unknown"
    else:
        raw_bytes = raw_data

    # Error(string) selector: 0x08c379a0
    if len(raw_bytes) >= 4 and raw_bytes[:4] == bytes.fromhex("08c379a0"):
        try:
            decoded = eth_abi.decode(["string"], raw_bytes[4:])[0]
            return str(decoded)
        except Exception:
            pass

    # Panic(uint256) selector: 0x4e487b71
    if len(raw_bytes) >= 4 and raw_bytes[:4] == bytes.fromhex("4e487b71"):
        try:
            code = eth_abi.decode(["uint256"], raw_bytes[4:])[0]
            return f"Panic({code})"
        except Exception:
            pass

    return "unknown"


def revert_reason(w3: Web3, tx_hash: Union[str, bytes]) -> str:
    """Replay a mined transaction via eth_call at (block_number - 1) to extract its revert reason."""
    hex_hash = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    if not hex_hash.startswith("0x"):
        hex_hash = "0x" + hex_hash

    try:
        tx = w3.eth.get_transaction(hex_hash)
        receipt = w3.eth.get_transaction_receipt(hex_hash)
    except Exception as exc:
        logger.debug(f"revert_reason: Could not query tx or receipt for {hex_hash}: {exc}")
        return "unknown"

    block_num = receipt.get("blockNumber")
    if block_num is None:
        return "unknown"

    call_block = max(0, block_num - 1)
    call_payload = {
        "from": tx.get("from"),
        "to": tx.get("to"),
        "value": tx.get("value", 0),
        "data": tx.get("input", b""),
        "gas": tx.get("gas", 2_000_000),
    }

    # Replay call at (block_number - 1), then block_number as fallback
    for blk in (call_block, block_num):
        try:
            w3.eth.call(call_payload, block_identifier=blk)
        except Exception as call_err:
            # 1. Check data attribute
            raw_data = getattr(call_err, "data", None)
            if raw_data:
                reason = decode_revert_data(raw_data)
                if reason != "unknown":
                    return reason

            # 2. Check exception args
            for arg in getattr(call_err, "args", []):
                if isinstance(arg, (str, bytes)):
                    reason = decode_revert_data(arg)
                    if reason != "unknown":
                        return reason
                elif isinstance(arg, dict):
                    data_val = arg.get("data")
                    if data_val:
                        reason = decode_revert_data(data_val)
                        if reason != "unknown":
                            return reason

            # 3. Check regex match for 'execution reverted: <msg>'
            err_str = str(call_err)
            match = re.search(r"execution reverted:\s*([^\'\",]+)", err_str)
            if match:
                parsed = match.group(1).strip()
                if parsed and not parsed.startswith("0x"):
                    return parsed

            # 4. Check for embedded hex error in string
            hex_match = re.search(r"0x08c379a0[0-9a-fA-F]+", err_str)
            if hex_match:
                reason = decode_revert_data(hex_match.group(0))
                if reason != "unknown":
                    return reason

    return "unknown"


def get_explorer_base(chain_id: Optional[int] = None) -> str:
    """Return the canonical block explorer URL for a given chain ID or environment setting."""
    env_base = os.environ.get("EXPLORER_BASE")
    if env_base:
        return env_base.rstrip("/")
    cid = chain_id or 11155111
    if cid == 11155111:
        return "https://sepolia.etherscan.io"
    elif cid == 84532:
        return "https://sepolia.basescan.org"
    elif cid == 80002:
        return "https://amoy.polygonscan.com"
    elif cid in (31337, 1337):
        return "http://127.0.0.1:8545"
    return "https://etherscan.io"


def explorer_tx_url(tx_hash: str, explorer_base: Optional[str] = None) -> str:
    """Build explorer URL for a transaction hash."""
    base = (explorer_base or os.environ.get("EXPLORER_BASE") or get_explorer_base()).rstrip("/")
    tx = tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash
    if not base:
        return tx
    return f"{base}/tx/{tx}"


def explorer_addr_url(address: str, explorer_base: Optional[str] = None) -> str:
    """Build explorer URL for an address."""
    base = (explorer_base or os.environ.get("EXPLORER_BASE") or get_explorer_base()).rstrip("/")
    addr = to_checksum_address(address)
    if not base:
        return addr
    return f"{base}/address/{addr}"
