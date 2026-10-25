"""Integration tests for Anvil EVM simulation, snapshot restoration, and dynamic discovery (simulate.py)."""

import socket
import subprocess
import time
from typing import Generator
import pytest
from eth_account import Account
from web3 import Web3

from app.chain.client import (
    PK_DEPLOYER,
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_VERIFIER,
    deploy_contract,
    send_tx,
)
from app.manifest.hashes import encode_erc20_transfer_calldata
from app.verification.simulate import (
    DYNAMIC_DISCOVERY_CAP,
    SimulationError,
    simulate_execution,
)

RECIPIENT_ADDR = "0x9965507D1a55BCC6475675304Ca994970De97744"
PAYOUT_AMOUNT = 50_000 * 10**6


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def anvil_node() -> Generator[str, None, None]:
    port = find_free_port()
    proc = subprocess.Popen(
        ["anvil", "--host", "127.0.0.1", "--port", str(port), "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    w3 = Web3(Web3.HTTPProvider(url))
    for _ in range(50):
        if w3.is_connected():
            break
        time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("Failed to connect to local Anvil instance")

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def deployed_env(anvil_node: str):
    w3 = Web3(Web3.HTTPProvider(anvil_node))
    governance_addr = Account.from_key(PK_GOVERNANCE).address
    verifier_addr = Account.from_key(PK_VERIFIER).address

    token = deploy_contract(w3, PK_DEPLOYER, "MockToken", "USD Coin", "USDC", 10_000_000 * 10**6)
    registry = deploy_contract(w3, PK_DEPLOYER, "GovernanceRegistry", governance_addr)
    treasury = deploy_contract(w3, PK_DEPLOYER, "Treasury")
    executor = deploy_contract(
        w3,
        PK_DEPLOYER,
        "GuardedExecutor",
        registry.address,
        treasury.address,
        verifier_addr,
    )

    send_tx(w3, PK_DEPLOYER, treasury.functions.setExecutor(executor.address))
    send_tx(w3, PK_DEPLOYER, token.functions.transfer(treasury.address, 1_000_000 * 10**6))

    manifest = {
        "proposalId": "PROP-002",
        "version": 1,
        "action": {
            "kind": "erc20_payout",
            "token": token.address.lower(),
            "decimals": 6,
            "recipient": RECIPIENT_ADDR,
            "amountRaw": str(PAYOUT_AMOUNT),
        },
        "envelope": {
            "maxTokenOutflow": {token.address.lower(): str(PAYOUT_AMOUNT)},
            "allowApprovals": False,
            "allowRoleChanges": False,
            "allowImplChange": False,
            "allowNewContracts": False,
        },
    }

    return {
        "w3": w3,
        "token": token,
        "registry": registry,
        "treasury": treasury,
        "executor": executor,
        "manifest": manifest,
    }


def test_simulation_success_and_state_restoration(deployed_env):
    w3 = deployed_env["w3"]
    token = deployed_env["token"]
    treasury = deployed_env["treasury"]
    executor = deployed_env["executor"]
    manifest = deployed_env["manifest"]

    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    # Baseline on-chain balances
    pre_treasury_bal = token.functions.balanceOf(treasury.address).call()
    pre_recipient_bal = token.functions.balanceOf(RECIPIENT_ADDR).call()
    pre_nonce = w3.eth.get_transaction_count(executor.address)
    pre_block = w3.eth.block_number

    # Execute simulation
    sim_res = simulate_execution(
        w3=w3,
        treasury_address=treasury.address,
        executor_address=executor.address,
        target=token.address,
        value=0,
        data=calldata,
        manifest=manifest,
    )

    assert sim_res["success"] is True
    assert sim_res["restoration_verified"] is True
    assert sim_res["treasury_outflow"] == PAYOUT_AMOUNT
    assert sim_res["recipient_inflow"] == PAYOUT_AMOUNT
    assert len(sim_res["unexpected_gains"]) == 0
    assert len(sim_res["allowance_changes"]) == 0
    assert len(sim_res["slot_changes"]) == 0

    # Confirm that on-chain world state was completely reverted
    post_treasury_bal = token.functions.balanceOf(treasury.address).call()
    post_recipient_bal = token.functions.balanceOf(RECIPIENT_ADDR).call()
    post_nonce = w3.eth.get_transaction_count(executor.address)
    post_block = w3.eth.block_number

    assert post_treasury_bal == pre_treasury_bal, "Treasury balance must be unchanged on real chain"
    assert post_recipient_bal == pre_recipient_bal, "Recipient balance must be unchanged on real chain"
    assert post_nonce == pre_nonce, "Executor nonce must be restored"
    assert post_block == pre_block, "Block number must be restored"


def test_simulation_reverts_on_excessive_amount_and_restores_state(deployed_env):
    w3 = deployed_env["w3"]
    token = deployed_env["token"]
    treasury = deployed_env["treasury"]
    executor = deployed_env["executor"]
    manifest = deployed_env["manifest"]

    # Request amount far exceeding treasury balance (10,000,000 USDC when treasury only has 1,000,000)
    excessive_amount = 10_000_000 * 10**6
    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, excessive_amount)

    pre_treasury_bal = token.functions.balanceOf(treasury.address).call()
    pre_block = w3.eth.block_number

    sim_res = simulate_execution(
        w3=w3,
        treasury_address=treasury.address,
        executor_address=executor.address,
        target=token.address,
        value=0,
        data=calldata,
        manifest=manifest,
    )

    assert sim_res["success"] is False
    assert sim_res["restoration_verified"] is True
    assert sim_res["treasury_outflow"] == 0

    # Ensure state still restored
    assert token.functions.balanceOf(treasury.address).call() == pre_treasury_bal
    assert w3.eth.block_number == pre_block


def test_raw_jsonrpc_snapshot_and_revert_behavior(deployed_env):
    w3 = deployed_env["w3"]

    # 1. evm_snapshot must return result without error
    snap_resp = w3.provider.make_request("evm_snapshot", [])
    assert snap_resp.get("error") is None
    assert "result" in snap_resp
    snapshot_id = snap_resp["result"]

    # 2. evm_revert with exact raw snapshot_id must return True
    revert_resp = w3.provider.make_request("evm_revert", [snapshot_id])
    assert revert_resp.get("error") is None
    assert revert_resp.get("result") is True

    # 3. Repeating revert with the same ID must return False (already reverted)
    second_revert = w3.provider.make_request("evm_revert", [snapshot_id])
    assert second_revert.get("result") is False or second_revert.get("error") is not None


def test_artificial_gas_funding_does_not_persist(deployed_env):
    """Confirm artificial gas funding is excluded from diffs and wiped clean after revert."""
    w3 = deployed_env["w3"]
    token = deployed_env["token"]
    treasury = deployed_env["treasury"]
    executor = deployed_env["executor"]
    manifest = deployed_env["manifest"]

    # Explicitly set executor ETH balance to 0 on Anvil
    w3.provider.make_request("anvil_setBalance", [executor.address, "0x0"])
    assert w3.eth.get_balance(executor.address) == 0

    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    sim_res = simulate_execution(
        w3=w3,
        treasury_address=treasury.address,
        executor_address=executor.address,
        target=token.address,
        value=0,
        data=calldata,
        manifest=manifest,
    )

    assert sim_res["success"] is True
    assert sim_res["restoration_verified"] is True
    # Confirm executor ETH balance was restored back to 0!
    assert w3.eth.get_balance(executor.address) == 0


def test_restoration_failure_raises_simulation_error(deployed_env, monkeypatch):
    """Confirm that if evm_revert fails or returns False, SimulationError is raised and fails closed."""
    w3 = deployed_env["w3"]
    token = deployed_env["token"]
    treasury = deployed_env["treasury"]
    executor = deployed_env["executor"]
    manifest = deployed_env["manifest"]

    calldata = encode_erc20_transfer_calldata(RECIPIENT_ADDR, PAYOUT_AMOUNT)

    orig_make_request = w3.provider.make_request

    def mock_make_request(method, params):
        if method == "evm_revert":
            # Simulate Anvil failing to revert snapshot
            return {"jsonrpc": "2.0", "id": 1, "result": False}
        return orig_make_request(method, params)

    monkeypatch.setattr(w3.provider, "make_request", mock_make_request)

    with pytest.raises(SimulationError, match="Snapshot restoration failed"):
        simulate_execution(
            w3=w3,
            treasury_address=treasury.address,
            executor_address=executor.address,
            target=token.address,
            value=0,
            data=calldata,
            manifest=manifest,
        )

