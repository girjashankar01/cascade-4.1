// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console} from "forge-std/console.sol";
import {MockToken} from "../src/MockToken.sol";
import {GovernanceRegistry} from "../src/GovernanceRegistry.sol";
import {Treasury} from "../src/Treasury.sol";
import {GuardedExecutor} from "../src/GuardedExecutor.sol";

/**
 * @title DeployProofScript
 * @notice Deploys the core DAO Accountability Engine architecture to a public testnet
 *         (Token, Registry, Treasury, GuardedExecutor) and configures executor & treasury funding.
 * @dev Does NOT deploy Box or UUPS contracts. Broadcaster is the deployer.
 */
contract DeployProofScript is Script {
    function run() external {
        address governanceAddr = vm.envAddress("GOVERNANCE_ADDR");
        address verifierAddr = vm.envAddress("VERIFIER_ADDR");

        console.log("=== DAO Accountability Engine - DeployProof ===");
        console.log("Broadcaster (Deployer):", msg.sender);
        console.log("Configured Governance:", governanceAddr);
        console.log("Configured Verifier:  ", verifierAddr);

        vm.startBroadcast();

        // 1. MockToken("USD Coin", "USDC", 10_000_000 * 10**6)
        MockToken token = new MockToken("USD Coin", "USDC", 10_000_000 * 10**6);
        console.log("1. MockToken deployed at:         ", address(token));

        // 2. GovernanceRegistry(GOVERNANCE_ADDR)
        GovernanceRegistry registry = new GovernanceRegistry(governanceAddr);
        console.log("2. GovernanceRegistry deployed at:", address(registry));

        // 3. Treasury()
        Treasury treasury = new Treasury();
        console.log("3. Treasury deployed at:          ", address(treasury));

        // 4. GuardedExecutor(registry, payable(treasury), VERIFIER_ADDR)
        GuardedExecutor executor = new GuardedExecutor(
            address(registry),
            payable(address(treasury)),
            verifierAddr
        );
        console.log("4. GuardedExecutor deployed at:   ", address(executor));

        // 5. treasury.setExecutor(executor)
        treasury.setExecutor(address(executor));
        console.log("5. Treasury executor set to:      ", address(executor));

        // 6. token.transfer(treasury, 1_000_000 * 10**6)
        token.transfer(address(treasury), 1_000_000 * 10**6);
        console.log("6. Funded Treasury with 1,000,000 USDC");

        vm.stopBroadcast();

        console.log("=== Deployment Complete ===");
    }
}
