"""End-to-end Python to Solidity EIP-712 interoperability integration test."""

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Generator

import pytest
from eth_account import Account
from web3 import Web3

from app.chain.attest import VERIFIED, compute_action_hash, sign_attestation

# Deterministic Anvil private keys
PK_DEPLOYER = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
PK_PROPOSER = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
PK_GOVERNANCE = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
PK_VERIFIER = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
PK_ATTACKER = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"

ADDR_RECIPIENT = "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"


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


def load_artifact(contract_name: str) -> dict[str, Any]:
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts" / "out"
    artifact_path = contracts_dir / f"{contract_name}.sol" / f"{contract_name}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found at {artifact_path}. Run 'forge build' first.")
    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)


def send_tx(w3: Web3, from_key: str, fn_call: Any) -> Any:
    account = Account.from_key(from_key)
    tx = fn_call.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 2_000_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, from_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
    assert receipt.status == 1
    return receipt


def deploy_contract(w3: Web3, from_key: str, artifact_name: str, *args: Any) -> Any:
    artifact = load_artifact(artifact_name)
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]["object"]
    factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    account = Account.from_key(from_key)

    tx = factory.constructor(*args).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 4_000_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, from_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
    assert receipt.status == 1
    return w3.eth.contract(address=receipt.contractAddress, abi=abi)


def test_python_solidity_interoperability(anvil_node: str) -> None:
    w3 = Web3(Web3.HTTPProvider(anvil_node))
    chain_id = w3.eth.chain_id

    deployer = Account.from_key(PK_DEPLOYER).address
    proposer = Account.from_key(PK_PROPOSER).address
    governance = Account.from_key(PK_GOVERNANCE).address
    verifier = Account.from_key(PK_VERIFIER).address

    # 1. Deploy all contracts
    token = deploy_contract(w3, PK_DEPLOYER, "MockToken", "USD Coin", "USDC", 10_000_000 * 10**6)
    registry = deploy_contract(w3, PK_DEPLOYER, "GovernanceRegistry", governance)
    treasury = deploy_contract(w3, PK_DEPLOYER, "Treasury")
    executor = deploy_contract(
        w3,
        PK_DEPLOYER,
        "GuardedExecutor",
        registry.address,
        treasury.address,
        verifier,
    )

    # 2. Wire executor into treasury and fund treasury
    send_tx(w3, PK_DEPLOYER, treasury.functions.setExecutor(executor.address))
    send_tx(w3, PK_DEPLOYER, token.functions.transfer(treasury.address, 1_000_000 * 10**6))
    assert token.functions.balanceOf(treasury.address).call() == 1_000_000 * 10**6

    # 3. Create payout action: token.transfer(ADDR_RECIPIENT, 50_000 * 10**6)
    payout_amount = 50_000 * 10**6
    calldata = token.encode_abi("transfer", [ADDR_RECIPIENT, payout_amount])

    # 4. Compute action hash using Python
    py_action_hash = compute_action_hash(token.address, 0, calldata)

    # Cross-check action hash equality on-chain
    sol_action_hash = executor.functions.computeActionHash(token.address, 0, calldata).call()
    assert py_action_hash == sol_action_hash, "Python and Solidity actionHash mismatch!"

    # 5. Proposer commits version
    pid = Web3.keccak(text="PROP-001")
    vhash = Web3.keccak(text="v1-manifest-hash")
    eroot = Web3.keccak(text="evidence-root-hash")

    send_tx(w3, PK_PROPOSER, registry.functions.commitVersion(pid, vhash, py_action_hash, eroot))

    # 6. Governance approves version
    send_tx(w3, PK_GOVERNANCE, registry.functions.approve(pid, vhash))

    # Verify approved state on registry
    app_vhash, app_ahash, app_eroot = registry.functions.approved(pid).call()
    assert app_vhash == vhash
    assert app_ahash == py_action_hash
    assert app_eroot == eroot

    # 7. Verifier signs EIP-712 attestation using Python attest module
    deadline = int(time.time()) + 3600
    py_sig = sign_attestation(
        private_key=PK_VERIFIER,
        proposal_id=pid,
        version_hash=vhash,
        action_hash=py_action_hash,
        evidence_root=eroot,
        verdict=VERIFIED,
        deadline=deadline,
        chain_id=chain_id,
        verifying_contract=executor.address,
    )

    recipient_bal_before = token.functions.balanceOf(ADDR_RECIPIENT).call()

    # 8. Execute payout on GuardedExecutor using the Python-signed attestation
    send_tx(
        w3,
        PK_PROPOSER,
        executor.functions.execute(
            pid,
            token.address,
            0,
            calldata,
            VERIFIED,
            deadline,
            py_sig,
        ),
    )

    # 9. Verify on-chain effects
    recipient_bal_after = token.functions.balanceOf(ADDR_RECIPIENT).call()
    assert recipient_bal_after - recipient_bal_before == payout_amount
    assert executor.functions.executed(pid).call() is True

    # 10. Verify replay attempt reverts
    replay_call = executor.functions.execute(
        pid,
        token.address,
        0,
        calldata,
        VERIFIED,
        deadline,
        py_sig,
    )
    with pytest.raises(Exception) as exc_info:
        replay_call.call({"from": proposer})
    assert "already executed" in str(exc_info.value)

    # 11. Verify action mismatch rejection on-chain
    pid2 = Web3.keccak(text="PROP-002")
    vhash2 = Web3.keccak(text="v2-manifest-hash")
    send_tx(w3, PK_PROPOSER, registry.functions.commitVersion(pid2, vhash2, py_action_hash, eroot))
    send_tx(w3, PK_GOVERNANCE, registry.functions.approve(pid2, vhash2))

    attacker_calldata = token.encode_abi("transfer", [Account.from_key(PK_ATTACKER).address, payout_amount])
    mismatch_call = executor.functions.execute(
        pid2,
        token.address,
        0,
        attacker_calldata,
        VERIFIED,
        deadline,
        py_sig,
    )
    with pytest.raises(Exception) as exc_info:
        mismatch_call.call({"from": proposer})
    assert "action mismatch" in str(exc_info.value)

    # 12. Verify invalid signature rejection on-chain
    attacker_sig = sign_attestation(
        private_key=PK_ATTACKER,
        proposal_id=pid2,
        version_hash=vhash2,
        action_hash=py_action_hash,
        evidence_root=eroot,
        verdict=VERIFIED,
        deadline=deadline,
        chain_id=chain_id,
        verifying_contract=executor.address,
    )
    bad_sig_call = executor.functions.execute(
        pid2,
        token.address,
        0,
        calldata,
        VERIFIED,
        deadline,
        attacker_sig,
    )
    with pytest.raises(Exception) as exc_info:
        bad_sig_call.call({"from": proposer})
    assert "bad attestation" in str(exc_info.value)
