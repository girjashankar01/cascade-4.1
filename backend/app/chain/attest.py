"""EIP-712 attestation signing and action-hash computation for GuardedExecutor."""

from typing import Any, Union
from eth_abi import encode
from eth_account import Account
from eth_account.messages import SignableMessage, encode_typed_data
from eth_utils import keccak, to_bytes, to_checksum_address
from web3 import Web3

EIP712_DOMAIN_NAME = "GuardedExecutor"
EIP712_DOMAIN_VERSION = "1"
PRIMARY_TYPE = "Attestation"
VERIFIED = 1

EIP712_TYPES: dict[str, list[dict[str, str]]] = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "Attestation": [
        {"name": "proposalId", "type": "bytes32"},
        {"name": "versionHash", "type": "bytes32"},
        {"name": "actionHash", "type": "bytes32"},
        {"name": "evidenceRoot", "type": "bytes32"},
        {"name": "verdict", "type": "uint8"},
        {"name": "deadline", "type": "uint256"},
    ],
}


def to_bytes32(val: Union[bytes, str]) -> bytes:
    """Normalize input into exactly 32 bytes."""
    if isinstance(val, str):
        if val.startswith("0x") or val.startswith("0X"):
            b = to_bytes(hexstr=val)
        else:
            b = val.encode("utf-8")
    else:
        b = val
    if len(b) > 32:
        raise ValueError(f"Value exceeds 32 bytes: {len(b)} bytes")
    if len(b) < 32:
        b = b.rjust(32, b"\x00")
    return b


def compute_action_hash(target: str, value: int, data: Union[bytes, str]) -> bytes:
    """Compute actionHash = keccak256(abi.encode(target, value, keccak256(data))).

    Matches Solidity:
        keccak256(abi.encode(target, value, keccak256(data)))
    """
    checksum_target = to_checksum_address(target)
    if isinstance(data, str):
        if data.startswith("0x") or data.startswith("0X"):
            data_bytes = to_bytes(hexstr=data)
        else:
            data_bytes = data.encode("utf-8")
    else:
        data_bytes = data

    data_hash = keccak(data_bytes)
    encoded = encode(
        ["address", "uint256", "bytes32"],
        [checksum_target, int(value), data_hash],
    )
    return keccak(encoded)


def build_attestation_typed_data(
    proposal_id: Union[bytes, str],
    version_hash: Union[bytes, str],
    action_hash: Union[bytes, str],
    evidence_root: Union[bytes, str],
    verdict: int,
    deadline: int,
    chain_id: int,
    verifying_contract: str,
) -> dict[str, Any]:
    """Build the canonical EIP-712 payload for a GuardedExecutor attestation."""
    pid_bytes = to_bytes32(proposal_id)
    vhash_bytes = to_bytes32(version_hash)
    ahash_bytes = to_bytes32(action_hash)
    eroot_bytes = to_bytes32(evidence_root)

    domain = {
        "name": EIP712_DOMAIN_NAME,
        "version": EIP712_DOMAIN_VERSION,
        "chainId": int(chain_id),
        "verifyingContract": to_checksum_address(verifying_contract),
    }

    message = {
        "proposalId": pid_bytes,
        "versionHash": vhash_bytes,
        "actionHash": ahash_bytes,
        "evidenceRoot": eroot_bytes,
        "verdict": int(verdict),
        "deadline": int(deadline),
    }

    return {
        "types": EIP712_TYPES,
        "primaryType": PRIMARY_TYPE,
        "domain": domain,
        "message": message,
    }


def get_signable_attestation(
    proposal_id: Union[bytes, str],
    version_hash: Union[bytes, str],
    action_hash: Union[bytes, str],
    evidence_root: Union[bytes, str],
    verdict: int,
    deadline: int,
    chain_id: int,
    verifying_contract: str,
) -> SignableMessage:
    """Generate an eth_account SignableMessage for an attestation."""
    typed_data = build_attestation_typed_data(
        proposal_id=proposal_id,
        version_hash=version_hash,
        action_hash=action_hash,
        evidence_root=evidence_root,
        verdict=verdict,
        deadline=deadline,
        chain_id=chain_id,
        verifying_contract=verifying_contract,
    )
    return encode_typed_data(full_message=typed_data)


def sign_attestation(
    private_key: Union[str, bytes],
    proposal_id: Union[bytes, str],
    version_hash: Union[bytes, str],
    action_hash: Union[bytes, str],
    evidence_root: Union[bytes, str],
    verdict: int,
    deadline: int,
    chain_id: int,
    verifying_contract: str,
) -> bytes:
    """Sign an EIP-712 attestation with the given private key, returning the 65-byte signature."""
    signable = get_signable_attestation(
        proposal_id=proposal_id,
        version_hash=version_hash,
        action_hash=action_hash,
        evidence_root=evidence_root,
        verdict=verdict,
        deadline=deadline,
        chain_id=chain_id,
        verifying_contract=verifying_contract,
    )
    signed = Account.sign_message(signable, private_key=private_key)
    return bytes(signed.signature)


def recover_attestation_signer(
    proposal_id: Union[bytes, str],
    version_hash: Union[bytes, str],
    action_hash: Union[bytes, str],
    evidence_root: Union[bytes, str],
    verdict: int,
    deadline: int,
    chain_id: int,
    verifying_contract: str,
    signature: Union[bytes, str],
) -> str:
    """Recover the signer address from an attestation and signature."""
    signable = get_signable_attestation(
        proposal_id=proposal_id,
        version_hash=version_hash,
        action_hash=action_hash,
        evidence_root=evidence_root,
        verdict=verdict,
        deadline=deadline,
        chain_id=chain_id,
        verifying_contract=verifying_contract,
    )
    sig_bytes = to_bytes(hexstr=signature) if isinstance(signature, str) else signature
    return Account.recover_message(signable, signature=sig_bytes)
