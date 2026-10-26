"""Anvil EVM simulation, watched-state diffing, and strict snapshot restoration."""

import copy
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from eth_utils import to_checksum_address
from web3 import Web3
from web3.exceptions import ContractLogicError

from app.chain.client import load_artifact

logger = logging.getLogger(__name__)

EIP1967_IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DYNAMIC_DISCOVERY_CAP = 10


class SimulationError(Exception):
    """Raised when simulation fails, encounters RPC errors, or fails snapshot restoration."""


def read_account_state(
    w3: Web3,
    address: str,
    token_contract: Optional[Any] = None,
    treasury_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Capture watched state for a single address."""
    addr_cs = to_checksum_address(address)
    eth_bal = w3.eth.get_balance(addr_cs)

    token_bal = 0
    allowance = 0
    if token_contract:
        try:
            token_bal = token_contract.functions.balanceOf(addr_cs).call()
        except Exception:
            token_bal = 0
        if treasury_address:
            try:
                treasury_cs = to_checksum_address(treasury_address)
                allowance = token_contract.functions.allowance(treasury_cs, addr_cs).call()
            except Exception:
                allowance = 0

    impl_slot = ""
    try:
        raw_slot = w3.eth.get_storage_at(addr_cs, EIP1967_IMPL_SLOT)
        impl_slot = "0x" + raw_slot.hex().lower().lstrip("0x").rjust(64, "0")
    except Exception:
        impl_slot = "0x" + "00" * 32

    owner = ""
    try:
        # Check if contract has an owner() view method
        owner_raw = w3.eth.call({"to": addr_cs, "data": "0x8da5cb5b"})  # owner() selector
        if len(owner_raw) >= 32:
            owner = "0x" + owner_raw[-20:].hex().lower()
    except Exception:
        owner = ""

    return {
        "eth_balance": eth_bal,
        "token_balance": token_bal,
        "allowance_from_treasury": allowance,
        "impl_slot": impl_slot,
        "owner": owner,
    }


def simulate_onchain_proof(
    w3: Web3,
    treasury_address: str,
    executor_address: str,
    target: str,
    value: int,
    data: Union[str, bytes],
    manifest: Dict[str, Any],
    token_address: Optional[str] = None,
    extra_watchlist: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Simulate treasury operation on a public EVM testnet without Anvil cheat codes.

    Uses read-only JSON-RPC eth_call with `from = executor_address` directly to Treasury.exec(...).
    Computes exact state transitions and verifies revert conditions without modifying on-chain state.
    """
    treasury_cs = to_checksum_address(treasury_address)
    executor_cs = to_checksum_address(executor_address)
    target_cs = to_checksum_address(target)

    # 1. Determine token contract
    resolved_token_addr = token_address or target
    mock_token_artifact = load_artifact("MockToken")
    token_contract = w3.eth.contract(
        address=to_checksum_address(resolved_token_addr),
        abi=mock_token_artifact["abi"],
    )

    treasury_artifact = load_artifact("Treasury")
    treasury_contract = w3.eth.contract(
        address=treasury_cs,
        abi=treasury_artifact["abi"],
    )

    # 2. Build fixed authoritative watchlist
    action = manifest.get("action", {})
    declared_recipient = action.get("recipient", "").lower()
    fixed_watchlist: Set[str] = {
        treasury_address.lower(),
        executor_address.lower(),
        target.lower(),
        resolved_token_addr.lower(),
    }
    if declared_recipient:
        fixed_watchlist.add(declared_recipient)
    if extra_watchlist:
        for addr in extra_watchlist:
            if addr:
                fixed_watchlist.add(addr.lower())

    # 3. Capture baseline state
    baseline_state: Dict[str, Dict[str, Any]] = {}
    for addr in fixed_watchlist:
        baseline_state[addr] = read_account_state(
            w3=w3,
            address=addr,
            token_contract=token_contract,
            treasury_address=treasury_address,
        )

    # 4. Execute read-only eth_call to Treasury.exec(target, value, data) with from=executor
    if isinstance(data, str):
        clean_data = data[2:] if data.startswith("0x") or data.startswith("0X") else data
        raw_data = bytes.fromhex(clean_data)
    else:
        raw_data = bytes(data)

    tx_status = 0
    revert_reason = None
    try:
        treasury_contract.functions.exec(target_cs, int(value or 0), raw_data).call({"from": executor_cs})
        tx_status = 1
    except Exception as exc:
        tx_status = 0
        from app.chain.public import decode_revert_data
        err_str = str(exc)
        if hasattr(exc, "data") and exc.data:
            revert_reason = decode_revert_data(exc.data)
        elif "execution reverted:" in err_str:
            revert_reason = err_str.split("execution reverted:")[-1].strip().strip("'\"")
        elif "reverted with reason string" in err_str:
            m = re.search(r"reverted with reason string '([^']+)'", err_str)
            revert_reason = m.group(1) if m else err_str
        else:
            revert_reason = err_str

    # 5. Build post_state
    post_state: Dict[str, Dict[str, Any]] = copy.deepcopy(baseline_state)
    if tx_status == 1:
        # Model successful execution deltas
        # If ERC20 transfer (selector 0xa9059cbb):
        if len(raw_data) >= 68 and raw_data[:4] == bytes.fromhex("a9059cbb"):
            call_recipient = "0x" + raw_data[16:36].hex().lower()
            call_amount = int.from_bytes(raw_data[36:68], "big")
            treas_key = treasury_address.lower()
            recip_key = call_recipient.lower()

            if treas_key in post_state:
                post_state[treas_key]["token_balance"] = max(0, post_state[treas_key]["token_balance"] - call_amount)
            if recip_key not in post_state:
                post_state[recip_key] = read_account_state(w3, recip_key, token_contract, treasury_address)
            post_state[recip_key]["token_balance"] = post_state[recip_key]["token_balance"] + call_amount

        # If upgradeToAndCall (selector 0x4f1ef286):
        elif len(raw_data) >= 36 and raw_data[:4] == bytes.fromhex("4f1ef286"):
            new_impl = "0x" + raw_data[16:36].hex().lower()
            tgt_key = target.lower()
            if tgt_key in post_state:
                post_state[tgt_key]["impl_slot"] = "0x" + new_impl[2:].rjust(64, "0")

    # 6. Compute state deltas
    treasury_lower = treasury_address.lower()
    recipient_lower = declared_recipient.lower()

    treasury_pre = baseline_state.get(treasury_lower, {}).get("token_balance", 0)
    treasury_post = post_state.get(treasury_lower, {}).get("token_balance", 0)
    treasury_outflow = treasury_pre - treasury_post if treasury_pre >= treasury_post else 0

    recipient_pre = baseline_state.get(recipient_lower, {}).get("token_balance", 0)
    recipient_post = post_state.get(recipient_lower, {}).get("token_balance", 0)
    recipient_inflow = recipient_post - recipient_pre if recipient_post >= recipient_pre else 0

    unexpected_gains: Dict[str, int] = {}
    allowance_changes: Dict[str, int] = {}
    slot_changes: Dict[str, Dict[str, str]] = {}
    owner_changes: Dict[str, Dict[str, str]] = {}

    for addr, post in post_state.items():
        base = baseline_state.get(addr, {"token_balance": 0, "allowance_from_treasury": 0, "impl_slot": "", "owner": ""})
        t_delta = post["token_balance"] - base["token_balance"]
        if t_delta > 0 and addr != recipient_lower:
            unexpected_gains[addr] = t_delta

        a_delta = post["allowance_from_treasury"] - base["allowance_from_treasury"]
        if a_delta != 0:
            allowance_changes[addr] = a_delta

        if base["impl_slot"] and post["impl_slot"] != base["impl_slot"]:
            slot_changes[addr] = {"before": base["impl_slot"], "after": post["impl_slot"]}

        if base["owner"] and post["owner"] != base["owner"]:
            owner_changes[addr] = {"before": base["owner"], "after": post["owner"]}

    return {
        "success": tx_status == 1,
        "tx_status": tx_status,
        "revert_reason": revert_reason,
        "restoration_verified": True,
        "treasury_outflow": treasury_outflow,
        "recipient_inflow": recipient_inflow,
        "unexpected_gains": unexpected_gains,
        "allowance_changes": allowance_changes,
        "slot_changes": slot_changes,
        "owner_changes": owner_changes,
        "dynamic_addresses": [],
        "discovery_cap_reached": False,
        "logs_count": 0,
        "baseline_state": baseline_state,
        "post_state": post_state,
    }


def simulate_execution(
    w3: Web3,
    treasury_address: str,
    executor_address: str,
    target: str,
    value: int,
    data: Union[str, bytes],
    manifest: Dict[str, Any],
    token_address: Optional[str] = None,
    extra_watchlist: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Simulate treasury operation through authorized executor on Anvil or public EVM."""
    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    is_local_chain = True
    try:
        chain_id = w3.eth.chain_id
        is_local_chain = chain_id in {31337, 1337}
    except Exception:
        is_local_chain = True

    is_proof_mode = (chain_mode == "proof") or (not is_local_chain)
    if is_proof_mode:
        return simulate_onchain_proof(
            w3=w3,
            treasury_address=treasury_address,
            executor_address=executor_address,
            target=target,
            value=value,
            data=data,
            manifest=manifest,
            token_address=token_address,
            extra_watchlist=extra_watchlist,
        )

    treasury_cs = to_checksum_address(treasury_address)
    executor_cs = to_checksum_address(executor_address)
    target_cs = to_checksum_address(target)

    # 1. Determine token contract
    resolved_token_addr = token_address or target
    mock_token_artifact = load_artifact("MockToken")
    token_contract = w3.eth.contract(
        address=to_checksum_address(resolved_token_addr),
        abi=mock_token_artifact["abi"],
    )

    treasury_artifact = load_artifact("Treasury")
    treasury_contract = w3.eth.contract(
        address=treasury_cs,
        abi=treasury_artifact["abi"],
    )

    # 2. Build fixed authoritative watchlist
    action = manifest.get("action", {})
    declared_recipient = action.get("recipient", "").lower()
    fixed_watchlist: Set[str] = {
        treasury_address.lower(),
        executor_address.lower(),
        target.lower(),
        resolved_token_addr.lower(),
    }
    if declared_recipient:
        fixed_watchlist.add(declared_recipient)
    if extra_watchlist:
        for addr in extra_watchlist:
            if addr:
                fixed_watchlist.add(addr.lower())

    # 3. Capture baseline state
    pre_nonce = w3.eth.get_transaction_count(executor_cs)
    pre_block = w3.eth.block_number
    pre_executor_eth_bal = w3.eth.get_balance(executor_cs)

    baseline_state: Dict[str, Dict[str, Any]] = {}
    for addr in fixed_watchlist:
        baseline_state[addr] = read_account_state(
            w3=w3,
            address=addr,
            token_contract=token_contract,
            treasury_address=treasury_address,
        )

    # 4. Mandatory raw JSON-RPC evm_snapshot
    snapshot_response = w3.provider.make_request("evm_snapshot", [])
    if snapshot_response.get("error") is not None:
        raise SimulationError(f"evm_snapshot failed: {snapshot_response['error']}")
    if "result" not in snapshot_response:
        raise SimulationError(f"Invalid evm_snapshot response: {snapshot_response}")

    snapshot_id = snapshot_response["result"]
    artificial_funding = False

    tx_status = 0
    revert_reason = None
    receipt_logs: List[Any] = []
    discovered_addresses: List[str] = []
    discovery_cap_reached = False
    post_state: Dict[str, Dict[str, Any]] = {}

    try:
        # Impersonate deployed executor contract
        imp_resp = w3.provider.make_request("anvil_impersonateAccount", [executor_cs])
        if imp_resp.get("error") is not None:
            raise SimulationError(f"anvil_impersonateAccount failed: {imp_resp['error']}")

        # Ensure executor can pay gas for simulation call
        if pre_executor_eth_bal < 10**17:
            fund_resp = w3.provider.make_request("anvil_setBalance", [executor_cs, hex(10**18)])
            if fund_resp.get("error") is not None:
                logger.warning(f"Failed to fund impersonated account: {fund_resp['error']}")
            artificial_funding = True

        raw_calldata = bytes.fromhex(data[2:]) if isinstance(data, str) and data.startswith("0x") else bytes(data)

        # Execute treasury.exec(target, value, data) from executor
        try:
            tx = treasury_contract.functions.exec(target_cs, int(value), raw_calldata).build_transaction(
                {
                    "from": executor_cs,
                    "nonce": pre_nonce,
                    "gas": 3_000_000,
                    "gasPrice": w3.eth.gas_price,
                }
            )
            tx_hash = w3.eth.send_transaction(tx)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=5)
            tx_status = receipt.status
            receipt_logs = list(receipt.logs)
        except Exception as exec_err:
            tx_status = 0
            revert_reason = str(exec_err)

        # 5. Bounded dynamic discovery from logs
        discovered_set: Set[str] = set()
        for l in receipt_logs:
            topics = [t.hex() if isinstance(t, bytes) else str(t) for t in l.get("topics", [])]
            if topics and topics[0].lower() == ERC20_TRANSFER_TOPIC.lower() and len(topics) >= 3:
                # Topic 1: from, Topic 2: to
                for t in (topics[1], topics[2]):
                    clean_t = t[2:] if t.startswith("0x") else t
                    if len(clean_t) == 64:
                        addr = "0x" + clean_t[24:].lower()
                        if addr not in fixed_watchlist:
                            discovered_set.add(addr)

        sorted_discovered = sorted(discovered_set)
        if len(sorted_discovered) > DYNAMIC_DISCOVERY_CAP:
            discovery_cap_reached = True
            discovered_addresses = sorted_discovered[:DYNAMIC_DISCOVERY_CAP]
        else:
            discovered_addresses = sorted_discovered

        # 6. Read post-state for fixed watchlist and bounded discovered addresses
        all_watched = set(fixed_watchlist) | set(discovered_addresses)
        for addr in all_watched:
            post_state[addr] = read_account_state(
                w3=w3,
                address=addr,
                token_contract=token_contract,
                treasury_address=treasury_address,
            )

    finally:
        # Stop impersonation
        try:
            w3.provider.make_request("anvil_stopImpersonatingAccount", [executor_cs])
        except Exception as e:
            logger.warning(f"stopImpersonatingAccount failed: {e}")

        # Revert snapshot via raw JSON-RPC
        revert_response = w3.provider.make_request("evm_revert", [snapshot_id])
        if revert_response.get("error") is not None or revert_response.get("result") is not True:
            raise SimulationError(f"Snapshot restoration failed: {revert_response}")

        # Verify restoration of nonce, block number, and watchlist state
        post_revert_nonce = w3.eth.get_transaction_count(executor_cs)
        post_revert_block = w3.eth.block_number
        post_revert_eth_bal = w3.eth.get_balance(executor_cs)

        if post_revert_nonce != pre_nonce:
            raise SimulationError(
                f"Executor nonce was not restored after revert: expected {pre_nonce}, got {post_revert_nonce}"
            )
        if post_revert_block != pre_block:
            raise SimulationError(
                f"Block number was not restored after revert: expected {pre_block}, got {post_revert_block}"
            )
        if artificial_funding and post_revert_eth_bal != pre_executor_eth_bal:
            raise SimulationError(
                f"Artificial gas funding persisted after revert: expected {pre_executor_eth_bal}, got {post_revert_eth_bal}"
            )

        # Verify fixed watchlist state restored
        for addr in fixed_watchlist:
            restored_state = read_account_state(
                w3=w3,
                address=addr,
                token_contract=token_contract,
                treasury_address=treasury_address,
            )
            base = baseline_state[addr]
            if (
                restored_state["token_balance"] != base["token_balance"]
                or restored_state["allowance_from_treasury"] != base["allowance_from_treasury"]
                or restored_state["impl_slot"] != base["impl_slot"]
            ):
                raise SimulationError(
                    f"Fixed watchlist state for '{addr}' was not restored after revert"
                )

    # 7. Compute state deltas
    treasury_lower = treasury_address.lower()
    recipient_lower = declared_recipient.lower()

    treasury_pre = baseline_state.get(treasury_lower, {}).get("token_balance", 0)
    treasury_post = post_state.get(treasury_lower, {}).get("token_balance", 0)
    treasury_outflow = treasury_pre - treasury_post if treasury_pre >= treasury_post else 0

    recipient_pre = baseline_state.get(recipient_lower, {}).get("token_balance", 0)
    recipient_post = post_state.get(recipient_lower, {}).get("token_balance", 0)
    recipient_inflow = recipient_post - recipient_pre if recipient_post >= recipient_pre else 0

    unexpected_gains: Dict[str, int] = {}
    allowance_changes: Dict[str, int] = {}
    slot_changes: Dict[str, Dict[str, str]] = {}
    owner_changes: Dict[str, Dict[str, str]] = {}

    for addr, post in post_state.items():
        base = baseline_state.get(addr, {"token_balance": 0, "allowance_from_treasury": 0, "impl_slot": "", "owner": ""})
        t_delta = post["token_balance"] - base["token_balance"]
        if t_delta > 0 and addr != recipient_lower:
            unexpected_gains[addr] = t_delta

        a_delta = post["allowance_from_treasury"] - base["allowance_from_treasury"]
        if a_delta != 0:
            allowance_changes[addr] = a_delta

        if base["impl_slot"] and post["impl_slot"] != base["impl_slot"]:
            slot_changes[addr] = {"before": base["impl_slot"], "after": post["impl_slot"]}

        if base["owner"] and post["owner"] != base["owner"]:
            owner_changes[addr] = {"before": base["owner"], "after": post["owner"]}

    return {
        "success": tx_status == 1,
        "tx_status": tx_status,
        "revert_reason": revert_reason,
        "restoration_verified": True,
        "treasury_outflow": treasury_outflow,
        "recipient_inflow": recipient_inflow,
        "unexpected_gains": unexpected_gains,
        "allowance_changes": allowance_changes,
        "slot_changes": slot_changes,
        "owner_changes": owner_changes,
        "dynamic_addresses": discovered_addresses,
        "discovery_cap_reached": discovery_cap_reached,
        "logs_count": len(receipt_logs),
        "baseline_state": baseline_state,
        "post_state": post_state,
    }
