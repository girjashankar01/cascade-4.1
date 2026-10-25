// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MockToken} from "../src/MockToken.sol";
import {GovernanceRegistry} from "../src/GovernanceRegistry.sol";
import {Treasury} from "../src/Treasury.sol";
import {GuardedExecutor} from "../src/GuardedExecutor.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract RevertingReceiver {
    error CustomRevertError(string reason);

    fallback() external payable {
        revert CustomRevertError("receiver rejected payment");
    }
}

contract Stage1CoreTest is Test {
    MockToken public token;
    GovernanceRegistry public registry;
    Treasury public treasury;
    GuardedExecutor public executor;

    // Deterministic Anvil roles
    address public deployer = 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266;
    uint256 public deployerKey = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80;

    address public proposer = 0x70997970C51812dc3A010C7d01b50e0d17dc79C8;
    uint256 public proposerKey = 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d;

    address public governance = 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC;
    uint256 public governanceKey = 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a;

    address public verifier = 0x90F79bf6EB2c4f870365E785982E1f101E93b906;
    uint256 public verifierKey = 0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6;

    address public attacker = 0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65;
    uint256 public attackerKey = 0x47e179ec197488593b100f80a30ce7281644999c81a5992982d64243b7383e4b;

    address public recipient = 0x9965507D1a55BCC6475675304Ca994970De97744;

    bytes32 public pid = keccak256("PROP-001");
    bytes32 public versionHash = keccak256("v1-manifest-hash");
    bytes32 public evidenceRoot = keccak256("evidence-root-sha256");

    uint8 public constant VERIFIED = 1;
    uint256 public payoutAmount = 50_000 * 10**6; // 50,000 USDC
    bytes public payoutCalldata;
    bytes32 public actionHash;

    function setUp() public {
        vm.startPrank(deployer);

        // 1. Deploy contracts
        token = new MockToken("USD Coin", "USDC", 10_000_000 * 10**6);
        registry = new GovernanceRegistry(governance);
        treasury = new Treasury();
        executor = new GuardedExecutor(address(registry), payable(address(treasury)), verifier);

        // 2. Wire executor into treasury
        treasury.setExecutor(address(executor));

        // 3. Fund treasury
        token.transfer(address(treasury), 1_000_000 * 10**6);
        vm.deal(address(treasury), 10 ether);

        vm.stopPrank();

        // Standard ERC-20 transfer calldata: token.transfer(recipient, payoutAmount)
        payoutCalldata = abi.encodeWithSelector(token.transfer.selector, recipient, payoutAmount);
        actionHash = executor.computeActionHash(address(token), 0, payoutCalldata);
    }

    // Helper to generate verifier signature
    function _signAttestation(
        uint256 privKey,
        bytes32 pId,
        bytes32 vHash,
        bytes32 aHash,
        bytes32 eRoot,
        uint8 verdict,
        uint256 deadline
    ) internal view returns (bytes memory) {
        bytes32 digest = executor.hashAttestation(pId, vHash, aHash, eRoot, verdict, deadline);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privKey, digest);
        return abi.encodePacked(r, s, v);
    }

    // ==========================================
    // 1. Python/Solidity ActionHash Equality
    // ==========================================
    function test_ActionHash_Equality() public view {
        // Known test vector computed in Python:
        // target: 0x1111111111111111111111111111111111111111
        // value: 100
        // data: "hello world"
        address testTarget = 0x1111111111111111111111111111111111111111;
        uint256 testValue = 100;
        bytes memory testData = "hello world";

        bytes32 computed = executor.computeActionHash(testTarget, testValue, testData);
        bytes32 pythonExpected = 0x67ace4504a92394fd5e07872975fa56b94ce9583abb97c64adb24df2b4c36995;

        assertEq(computed, pythonExpected, "Action hash does not match Python test vector");
    }

    // ==========================================
    // 2. Execution of Valid Approved Payout
    // ==========================================
    function test_Execute_ValidApprovedPayout_Success() public {
        // Proposer commits version
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        // Governance approves version
        vm.prank(governance);
        registry.approve(pid, versionHash);

        // Verifier signs attestation
        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        uint256 recipientBalBefore = token.balanceOf(recipient);
        uint256 treasuryBalBefore = token.balanceOf(address(treasury));

        // Anyone can execute the attested transaction
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            sig
        );

        assertEq(token.balanceOf(recipient), recipientBalBefore + payoutAmount, "Recipient not credited");
        assertEq(token.balanceOf(address(treasury)), treasuryBalBefore - payoutAmount, "Treasury balance mismatch");
        assertTrue(executor.executed(pid), "Proposal not marked executed");
    }

    // ==========================================
    // 3. Action Mismatch Reverts
    // ==========================================
    function test_Revert_ActionMismatch_WrongRecipient() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        // Attacker substitutes recipient in calldata
        bytes memory evilCalldata = abi.encodeWithSelector(token.transfer.selector, attacker, payoutAmount);

        vm.expectRevert("action mismatch");
        executor.execute(
            pid,
            address(token),
            0,
            evilCalldata,
            VERIFIED,
            deadline,
            sig
        );
    }

    function test_Revert_ActionMismatch_WrongAmount() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        // Attacker inflates payout amount
        bytes memory inflatedCalldata = abi.encodeWithSelector(token.transfer.selector, recipient, payoutAmount * 2);

        vm.expectRevert("action mismatch");
        executor.execute(
            pid,
            address(token),
            0,
            inflatedCalldata,
            VERIFIED,
            deadline,
            sig
        );
    }

    function test_Revert_ActionMismatch_WrongValue() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        // Value sent is 1 ether instead of 0
        vm.expectRevert("action mismatch");
        executor.execute(
            pid,
            address(token),
            1 ether,
            payoutCalldata,
            VERIFIED,
            deadline,
            sig
        );
    }

    // ==========================================
    // 4. Version & Governance Reverts
    // ==========================================
    function test_Revert_UnapprovedProposal() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);
        // Governance has NOT approved

        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        vm.expectRevert("no approved version");
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            sig
        );
    }

    function test_Revert_WrongApprovedVersion() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        bytes32 v2Hash = keccak256("v2-manifest-hash");
        vm.prank(proposer);
        registry.commitVersion(pid, v2Hash, actionHash, evidenceRoot);

        // Governance approves version 2
        vm.prank(governance);
        registry.approve(pid, v2Hash);

        // Attestation was signed over old version 1
        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sigOld = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        vm.expectRevert("bad attestation");
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            sigOld
        );
    }

    function test_TextRevision_InvalidatesPriorApproval() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        (bytes32 vHash,,) = registry.approved(pid);
        assertEq(vHash, versionHash, "Initial approval missing");

        // Proposer commits revision v2 with identical action
        bytes32 v2Hash = keccak256("v2-revised-manifest-hash");
        vm.prank(proposer);
        registry.commitVersion(pid, v2Hash, actionHash, evidenceRoot);

        // Old approval must now be invalidated
        (bytes32 clearedHash,,) = registry.approved(pid);
        assertEq(clearedHash, bytes32(0), "Old approval must be invalidated upon new version commit");
    }

    function test_Revert_MockTokenMint_Unauthorized() public {
        vm.prank(attacker);
        vm.expectRevert("only deployer");
        token.mint(attacker, 1000 * 10**6);
    }

    // ==========================================
    // 5. Signature & Attestation Validation Reverts
    // ==========================================
    function test_Revert_InvalidSignature() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        // Attacker signs instead of verifier
        bytes memory fakeSig = _signAttestation(
            attackerKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        vm.expectRevert("bad attestation");
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            fakeSig
        );
    }

    function test_Revert_ExpiredDeadline() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 10 minutes;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        // Warp time past deadline
        vm.warp(deadline + 1 seconds);

        vm.expectRevert("attestation expired");
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            sig
        );
    }

    function test_Revert_NonVerifiedVerdict() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        uint8 mismatchVerdict = 2; // MISMATCH
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            mismatchVerdict,
            deadline
        );

        vm.expectRevert("not verified");
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            mismatchVerdict,
            deadline,
            sig
        );
    }

    // ==========================================
    // 6. Replay Execution Protection
    // ==========================================
    function test_Revert_ReplayExecution() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(pid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            pid,
            versionHash,
            actionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        // First execution succeeds
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            sig
        );

        // Second execution reverts
        vm.expectRevert("already executed");
        executor.execute(
            pid,
            address(token),
            0,
            payoutCalldata,
            VERIFIED,
            deadline,
            sig
        );
    }

    // ==========================================
    // 7. Registry Access Control Reverts
    // ==========================================
    function test_Revert_NonGovernanceApprove() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(attacker);
        vm.expectRevert("only governance");
        registry.approve(pid, versionHash);
    }

    function test_Revert_NonProposerCommit() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        bytes32 v2Hash = keccak256("v2-by-attacker");
        vm.prank(attacker);
        vm.expectRevert("only proposer");
        registry.commitVersion(pid, v2Hash, actionHash, evidenceRoot);
    }

    function test_Revert_ApproveNonLatestVersion() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        bytes32 v2Hash = keccak256("v2-hash");
        vm.prank(proposer);
        registry.commitVersion(pid, v2Hash, actionHash, evidenceRoot);

        // Governance tries to approve old version 1
        vm.prank(governance);
        vm.expectRevert("not latest version");
        registry.approve(pid, versionHash);
    }

    function test_Revert_DuplicateVersionHash() public {
        vm.prank(proposer);
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);

        vm.prank(proposer);
        vm.expectRevert("duplicate version hash");
        registry.commitVersion(pid, versionHash, actionHash, evidenceRoot);
    }

    function test_Revert_ZeroHashes() public {
        vm.prank(proposer);
        vm.expectRevert("invalid proposalId");
        registry.commitVersion(bytes32(0), versionHash, actionHash, evidenceRoot);

        vm.prank(proposer);
        vm.expectRevert("invalid versionHash");
        registry.commitVersion(pid, bytes32(0), actionHash, evidenceRoot);

        vm.prank(proposer);
        vm.expectRevert("invalid actionHash");
        registry.commitVersion(pid, versionHash, bytes32(0), evidenceRoot);

        vm.prank(proposer);
        vm.expectRevert("invalid evidenceRoot");
        registry.commitVersion(pid, versionHash, actionHash, bytes32(0));
    }

    // ==========================================
    // 8. Treasury Access Control Reverts
    // ==========================================
    function test_Revert_UnauthorizedTreasuryExec() public {
        vm.prank(attacker);
        vm.expectRevert("only executor");
        treasury.exec(recipient, 0, "");
    }

    function test_Revert_TreasurySetExecutorTwice() public {
        vm.prank(deployer);
        vm.expectRevert("executor already set");
        treasury.setExecutor(address(executor));

        vm.prank(attacker);
        vm.expectRevert("only deployer");
        treasury.setExecutor(attacker);
    }

    // ==========================================
    // 9. Downstream Revert Atomicity
    // ==========================================
    function test_Revert_FailedDownstreamExecution_RollsBackExecutedState() public {
        RevertingReceiver receiver = new RevertingReceiver();

        bytes memory badCalldata = abi.encodeWithSelector(bytes4(keccak256("fail()")));
        bytes32 badActionHash = executor.computeActionHash(address(receiver), 0, badCalldata);

        bytes32 failPid = keccak256("PROP-FAIL");
        vm.prank(proposer);
        registry.commitVersion(failPid, versionHash, badActionHash, evidenceRoot);

        vm.prank(governance);
        registry.approve(failPid, versionHash);

        uint256 deadline = block.timestamp + 1 hours;
        bytes memory sig = _signAttestation(
            verifierKey,
            failPid,
            versionHash,
            badActionHash,
            evidenceRoot,
            VERIFIED,
            deadline
        );

        vm.expectRevert(abi.encodeWithSelector(RevertingReceiver.CustomRevertError.selector, "receiver rejected payment"));
        executor.execute(
            failPid,
            address(receiver),
            0,
            badCalldata,
            VERIFIED,
            deadline,
            sig
        );

        // Crucial: executed[failPid] must be false because transaction reverted!
        assertFalse(executor.executed(failPid), "Executed state was not rolled back upon downstream revert");
    }
}
