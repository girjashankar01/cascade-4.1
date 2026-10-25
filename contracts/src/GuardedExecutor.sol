// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {GovernanceRegistry} from "./GovernanceRegistry.sol";
import {Treasury} from "./Treasury.sol";

/**
 * @title GuardedExecutor
 * @notice Trust anchor of the DAO Accountability Engine.
 * @dev Enforces that executed calldata matches the approved manifest and a valid EIP-712 verifier attestation.
 */
contract GuardedExecutor is EIP712 {
    bytes32 public constant ATTEST_TYPEHASH = keccak256(
        "Attestation(bytes32 proposalId,bytes32 versionHash,bytes32 actionHash,bytes32 evidenceRoot,uint8 verdict,uint256 deadline)"
    );

    uint8 public constant VERIFIED = 1;

    GovernanceRegistry public immutable registry;
    Treasury public immutable treasury;
    address public immutable verifier;

    mapping(bytes32 => bool) public executed;

    event ExecutionSucceeded(
        bytes32 indexed proposalId,
        address indexed target,
        uint256 value,
        bytes32 actionHash
    );

    constructor(
        address registry_,
        address payable treasury_,
        address verifier_
    ) EIP712("GuardedExecutor", "1") {
        require(registry_ != address(0), "invalid registry");
        require(treasury_ != address(0), "invalid treasury");
        require(verifier_ != address(0), "invalid verifier");

        registry = GovernanceRegistry(registry_);
        treasury = Treasury(treasury_);
        verifier = verifier_;
    }

    /**
     * @notice Computes actionHash deterministically: keccak256(abi.encode(target, value, keccak256(data))).
     */
    function computeActionHash(
        address target,
        uint256 value,
        bytes memory data
    ) public pure returns (bytes32) {
        return keccak256(abi.encode(target, value, keccak256(data)));
    }

    /**
     * @notice Helper to compute the EIP-712 typed data digest for an attestation.
     */
    function hashAttestation(
        bytes32 pid,
        bytes32 versionHash,
        bytes32 actionHash,
        bytes32 evidenceRoot,
        uint8 verdict,
        uint256 deadline
    ) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                ATTEST_TYPEHASH,
                pid,
                versionHash,
                actionHash,
                evidenceRoot,
                verdict,
                deadline
            )
        );
        return _hashTypedDataV4(structHash);
    }

    /**
     * @notice Enforces policy and executes an authorized transaction via Treasury.
     * @param pid Proposal identifier.
     * @param target Target contract or recipient address.
     * @param value Native value in wei.
     * @param data Calldata for the call.
     * @param verdict Must equal VERIFIED (1).
     * @param deadline Unix timestamp after which attestation expires.
     * @param sig EIP-712 signature over attestation signed by verifier.
     */
    function execute(
        bytes32 pid,
        address target,
        uint256 value,
        bytes calldata data,
        uint8 verdict,
        uint256 deadline,
        bytes calldata sig
    ) external returns (bytes memory) {
        require(!executed[pid], "already executed");
        require(block.timestamp <= deadline, "attestation expired");
        require(verdict == VERIFIED, "not verified");

        bytes32 ah = computeActionHash(target, value, data);
        {
            (bytes32 versionHash, bytes32 approvedAction, bytes32 evidenceRoot) = registry.approved(pid);
            require(versionHash != bytes32(0), "no approved version");
            require(ah == approvedAction, "action mismatch");

            bytes32 digest = hashAttestation(
                pid,
                versionHash,
                ah,
                evidenceRoot,
                verdict,
                deadline
            );
            require(ECDSA.recover(digest, sig) == verifier, "bad attestation");
        }

        // Checks-Effects-Interactions: record execution and emit event before external call
        executed[pid] = true;
        emit ExecutionSucceeded(pid, target, value, ah);

        // Execute call via Treasury
        bytes memory returndata = treasury.exec(target, value, data);
        return returndata;
    }
}
