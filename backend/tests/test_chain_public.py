"""Tests for isolated public EVM testnet tooling (backend/app/chain/public.py)."""

import os
from pathlib import Path
import socket
import subprocess
import time

from eth_account import Account
from eth_utils import to_checksum_address
import pytest
from web3 import Web3

from app.chain.client import deploy_contract, get_web3
from app.chain.public import (
    ProofConfig,
    explorer_addr_url,
    explorer_tx_url,
    get_next_nonce,
    load_proof_env,
    reset_nonce_counter,
    revert_reason,
    send_tx_1559,
)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def public_anvil_node():
    """Launch an isolated, ephemeral Anvil node on a random port."""
    port = find_free_port()
    proc = subprocess.Popen(
        ["anvil", "--port", str(port), "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc_url = f"http://127.0.0.1:{port}"
    w3 = get_web3(rpc_url)

    # Wait for node to respond
    for _ in range(40):
        if w3.is_connected():
            break
        time.sleep(0.1)

    yield {
        "w3": w3,
        "rpc_url": rpc_url,
        "port": port,
        "chain_id": w3.eth.chain_id,
    }

    proc.terminate()
    proc.wait()


def fund_account(w3: Web3, address: str, amount_wei: int = 10**19) -> None:
    """Fund an account with test ETH via Anvil RPC."""
    w3.provider.make_request(
        "anvil_setBalance",
        [to_checksum_address(address), hex(amount_wei)],
    )


def test_send_tx_1559_successful_transfer(public_anvil_node):
    """Test standard EIP-1559 transaction submission and mining with status 1."""
    w3 = public_anvil_node["w3"]
    sender = Account.create()
    recipient = Account.create()
    fund_account(w3, sender.address, Web3.to_wei(5, "ether"))

    reset_nonce_counter(sender.address)

    result = send_tx_1559(
        w3=w3,
        private_key=sender.key.hex(),
        tx_or_fn={"to": recipient.address},
        gas=25_000,
        value=Web3.to_wei(1, "ether"),
    )

    assert result["status"] == 1
    assert result["tx_hash"].startswith("0x")
    assert result["block_number"] > 0
    assert w3.eth.get_balance(recipient.address) == Web3.to_wei(1, "ether")


def test_send_tx_1559_expected_revert_and_revert_reason(public_anvil_node):
    """Test expected-revert transaction (status 0) and decode Solidity Error(string) via eth_call replay."""
    w3 = public_anvil_node["w3"]
    deployer = Account.create()
    attacker = Account.create()
    governance = Account.create()
    fund_account(w3, deployer.address, Web3.to_wei(5, "ether"))
    fund_account(w3, attacker.address, Web3.to_wei(5, "ether"))

    # Deploy GovernanceRegistry contract
    registry = deploy_contract(w3, deployer.key.hex(), "GovernanceRegistry", governance.address)

    # Attacker calls approve(...) directly (only governance is authorized)
    dummy_pid = b"\x01" * 32
    dummy_vhash = b"\x02" * 32

    fn_call = registry.functions.approve(dummy_pid, dummy_vhash)

    reset_nonce_counter(attacker.address)

    # Expect revert: status must be 0 and not raise RuntimeError
    result = send_tx_1559(
        w3=w3,
        private_key=attacker.key.hex(),
        tx_or_fn=fn_call,
        gas=200_000,
        expect_revert=True,
    )

    assert result["status"] == 0
    tx_hash = result["tx_hash"]
    assert tx_hash.startswith("0x")

    # Replay with revert_reason to extract exact require string
    reason = revert_reason(w3, tx_hash)
    assert reason == "only governance"


def test_nonce_sequencing_back_to_back(public_anvil_node):
    """Test that 3 back-to-back transactions sent rapidly from the same account receive sequential nonces."""
    w3 = public_anvil_node["w3"]
    sender = Account.create()
    recipient = Account.create()
    fund_account(w3, sender.address, Web3.to_wei(10, "ether"))

    reset_nonce_counter(sender.address)

    res1 = send_tx_1559(w3, sender.key.hex(), {"to": recipient.address, "value": 100}, gas=25_000)
    res2 = send_tx_1559(w3, sender.key.hex(), {"to": recipient.address, "value": 200}, gas=25_000)
    res3 = send_tx_1559(w3, sender.key.hex(), {"to": recipient.address, "value": 300}, gas=25_000)

    assert res1["status"] == 1
    assert res2["status"] == 1
    assert res3["status"] == 1

    tx1 = w3.eth.get_transaction(res1["tx_hash"])
    tx2 = w3.eth.get_transaction(res2["tx_hash"])
    tx3 = w3.eth.get_transaction(res3["tx_hash"])

    # Nonces must be strictly sequential (0, 1, 2)
    assert tx1["nonce"] == 0
    assert tx2["nonce"] == 1
    assert tx3["nonce"] == 2
    assert w3.eth.get_balance(recipient.address) == 600


def test_send_tx_1559_retry_on_underpriced(public_anvil_node, monkeypatch):
    """Test retry behavior when node throws replacement transaction underpriced."""
    w3 = public_anvil_node["w3"]
    sender = Account.create()
    recipient = Account.create()
    fund_account(w3, sender.address, Web3.to_wei(5, "ether"))

    reset_nonce_counter(sender.address)

    original_send = w3.eth.send_raw_transaction
    call_count = 0

    def mock_send(raw_tx):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("replacement transaction underpriced")
        return original_send(raw_tx)

    monkeypatch.setattr(w3.eth, "send_raw_transaction", mock_send)

    res = send_tx_1559(
        w3=w3,
        private_key=sender.key.hex(),
        tx_or_fn={"to": recipient.address, "value": 500},
        gas=25_000,
    )

    assert call_count == 2  # Proves retry was executed
    assert res["status"] == 1
    assert w3.eth.get_balance(recipient.address) == 500


def test_load_proof_env_chain_id_mismatch(public_anvil_node, tmp_path):
    """Test that load_proof_env raises ValueError when connected chain ID differs from CHAIN_ID."""
    env_file = tmp_path / ".env.test_mismatch"
    env_file.write_text(
        f"CHAIN_ID=80002\n"  # Amoy chain id, but Anvil node is 31337
        f"AMOY_RPC={public_anvil_node['rpc_url']}\n"
        f"EXPLORER_BASE=https://amoy.polygonscan.com\n"
        f"DEPLOYER_PK=0x1111111111111111111111111111111111111111111111111111111111111111\n"
    )

    with pytest.raises(ValueError) as exc_info:
        load_proof_env(path=env_file, w3=public_anvil_node["w3"])

    err = str(exc_info.value)
    assert "Chain ID mismatch" in err
    assert "80002" in err


def test_load_proof_env_success_and_redaction(public_anvil_node, tmp_path):
    """Test load_proof_env happy path, dictionary access, and private key redaction in repr."""
    secret_pk = "0x2222222222222222222222222222222222222222222222222222222222222222"
    env_file = tmp_path / ".env.test_valid"
    env_file.write_text(
        f"CHAIN_ID={public_anvil_node['chain_id']}\n"
        f"AMOY_RPC={public_anvil_node['rpc_url']}\n"
        f"EXPLORER_BASE=https://amoy.polygonscan.com\n"
        f"PRIORITY_FEE_GWEI=25.5\n"
        f"DEPLOYER_PK={secret_pk}\n"
        f"PROPOSER_PK={secret_pk}\n"
        f"GOVERNANCE_PK={secret_pk}\n"
        f"VERIFIER_PK={secret_pk}\n"
        f"DEPLOYER_ADDR=0x70997970C51812dc3A010C7d01b50e0d17dc79C8\n"
    )

    cfg = load_proof_env(path=env_file, w3=public_anvil_node["w3"])
    assert cfg.chain_id == public_anvil_node["chain_id"]
    assert cfg.rpc_url == public_anvil_node["rpc_url"]
    assert cfg.priority_fee_gwei == 25.5
    assert cfg.addresses["DEPLOYER_ADDR"] == "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

    # Verify that secret_pk is never revealed in __repr__
    cfg_repr = repr(cfg)
    assert secret_pk not in cfg_repr
    assert "[REDACTED]" in cfg_repr

    # Verify explorer URL builders
    tx_url = explorer_tx_url("0xabcdef123456", explorer_base=cfg.explorer_base)
    addr_url = explorer_addr_url("0x70997970C51812dc3A010C7d01b50e0d17dc79C8", explorer_base=cfg.explorer_base)

    assert tx_url == "https://amoy.polygonscan.com/tx/0xabcdef123456"
    assert addr_url == "https://amoy.polygonscan.com/address/0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
