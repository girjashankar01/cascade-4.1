"""Tests for backend/app/chain/attest.py."""

from eth_account import Account
from web3 import Web3

from app.chain.attest import (
    EIP712_DOMAIN_NAME,
    EIP712_DOMAIN_VERSION,
    PRIMARY_TYPE,
    VERIFIED,
    build_attestation_typed_data,
    compute_action_hash,
    recover_attestation_signer,
    sign_attestation,
    to_bytes32,
)

ANVIL_VERIFIER_KEY = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
ANVIL_VERIFIER_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


def test_compute_action_hash_deterministic() -> None:
    target = "0x1111111111111111111111111111111111111111"
    value = 100
    data = b"hello world"
    ah = compute_action_hash(target, value, data)
    assert ah.hex() == "67ace4504a92394fd5e07872975fa56b94ce9583abb97c64adb24df2b4c36995"


def test_compute_action_hash_transfer_selector() -> None:
    # Test vector mimicking ERC20.transfer(recipient, 5_000_000 * 10**6)
    recipient = "0x9965507D1a55bcC6475675304Ca994970de97744"
    amount = 5_000_000_000_000  # 5M tokens with 6 decimals
    # 0xa9059cbb + address padded to 32 bytes + uint256 padded to 32 bytes
    selector = bytes.fromhex("a9059cbb")
    recipient_padded = bytes.fromhex(recipient[2:].lower().rjust(64, "0"))
    amount_padded = amount.to_bytes(32, byteorder="big")
    calldata = selector + recipient_padded + amount_padded

    token = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    ah = compute_action_hash(token, 0, calldata)
    assert len(ah) == 32
    assert ah.hex() != ""


def test_build_attestation_typed_data_structure() -> None:
    pid = "PROP-001"
    vhash = "0x" + "a1" * 32
    ahash = "0x" + "b2" * 32
    eroot = "0x" + "c3" * 32
    contract = "0x0000000000000000000000000000000000000123"

    typed = build_attestation_typed_data(
        proposal_id=pid,
        version_hash=vhash,
        action_hash=ahash,
        evidence_root=eroot,
        verdict=VERIFIED,
        deadline=1893456000,
        chain_id=31337,
        verifying_contract=contract,
    )

    assert typed["primaryType"] == PRIMARY_TYPE
    assert typed["domain"]["name"] == EIP712_DOMAIN_NAME
    assert typed["domain"]["version"] == EIP712_DOMAIN_VERSION
    assert typed["domain"]["chainId"] == 31337
    assert typed["domain"]["verifyingContract"] == Web3.to_checksum_address(contract)
    assert typed["message"]["verdict"] == 1
    assert typed["message"]["deadline"] == 1893456000
    assert len(typed["message"]["proposalId"]) == 32


def test_sign_and_recover_attestation() -> None:
    pid = "0x" + "11" * 32
    vhash = "0x" + "22" * 32
    ahash = "0x" + "33" * 32
    eroot = "0x" + "44" * 32
    contract = "0x0000000000000000000000000000000000000456"

    sig = sign_attestation(
        private_key=ANVIL_VERIFIER_KEY,
        proposal_id=pid,
        version_hash=vhash,
        action_hash=ahash,
        evidence_root=eroot,
        verdict=VERIFIED,
        deadline=2000000000,
        chain_id=31337,
        verifying_contract=contract,
    )

    assert len(sig) == 65
    recovered = recover_attestation_signer(
        proposal_id=pid,
        version_hash=vhash,
        action_hash=ahash,
        evidence_root=eroot,
        verdict=VERIFIED,
        deadline=2000000000,
        chain_id=31337,
        verifying_contract=contract,
        signature=sig,
    )
    assert recovered.lower() == ANVIL_VERIFIER_ADDR.lower()
