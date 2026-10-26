// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts/proxy/utils/UUPSUpgradeable.sol";
import {BoxUUPS} from "../src/BoxUUPS.sol";
import {BoxV2} from "../src/BoxV2.sol";
import {BoxEvil} from "../src/BoxEvil.sol";
import {Treasury} from "../src/Treasury.sol";

contract UpgradeTest is Test {
    bytes32 internal constant IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    Treasury internal treasury;
    BoxUUPS internal boxImpl;
    BoxV2 internal boxV2Impl;
    BoxEvil internal boxEvilImpl;
    ERC1967Proxy internal proxy;
    BoxUUPS internal boxProxy;

    address internal deployer = address(0xD1);
    address internal executor = address(0xE1);
    address internal attacker = address(0xBAD);

    function setUp() public {
        vm.startPrank(deployer);

        treasury = new Treasury();
        treasury.setExecutor(executor);

        boxImpl = new BoxUUPS();
        boxV2Impl = new BoxV2();
        boxEvilImpl = new BoxEvil();

        bytes memory initData = abi.encodeWithSelector(BoxUUPS.initialize.selector, address(treasury));
        proxy = new ERC1967Proxy(address(boxImpl), initData);
        boxProxy = BoxUUPS(address(proxy));

        vm.stopPrank();
    }

    function test_InitialDeploymentAndImplementationSlot() public view {
        assertEq(boxProxy.owner(), address(treasury));
        assertEq(boxProxy.version(), "1.0.0");
        assertEq(boxProxy.getValue(), 0);

        bytes32 slotVal = vm.load(address(proxy), IMPLEMENTATION_SLOT);
        assertEq(address(uint160(uint256(slotVal))), address(boxImpl));
    }

    function test_Revert_DirectUnauthorizedUpgrade() public {
        vm.prank(attacker);
        vm.expectRevert("BoxUUPS: caller is not the owner");
        boxProxy.upgradeToAndCall(address(boxV2Impl), "");
    }

    function test_TreasuryExecutesBenignUpgrade() public {
        // Set initial state via Treasury
        vm.prank(executor);
        treasury.exec(address(proxy), 0, abi.encodeWithSelector(BoxUUPS.setValue.selector, 42));
        assertEq(boxProxy.getValue(), 42);

        // Perform upgrade via Treasury
        bytes memory upgradeCalldata = abi.encodeWithSelector(
            UUPSUpgradeable.upgradeToAndCall.selector,
            address(boxV2Impl),
            ""
        );

        vm.prank(executor);
        treasury.exec(address(proxy), 0, upgradeCalldata);

        // Verify implementation slot updated
        bytes32 slotVal = vm.load(address(proxy), IMPLEMENTATION_SLOT);
        assertEq(address(uint160(uint256(slotVal))), address(boxV2Impl));

        // Verify version and preserved storage
        BoxV2 upgradedBox = BoxV2(address(proxy));
        assertEq(upgradedBox.version(), "2.0.0");
        assertEq(upgradedBox.getValue(), 42);

        // Test V2 increment functionality
        vm.prank(executor);
        treasury.exec(address(proxy), 0, abi.encodeWithSelector(BoxV2.increment.selector));
        assertEq(upgradedBox.getValue(), 43);
    }

    function test_TreasuryExecutesEvilUpgrade_UndeclaredSelectorPresent() public {
        bytes memory upgradeCalldata = abi.encodeWithSelector(
            UUPSUpgradeable.upgradeToAndCall.selector,
            address(boxEvilImpl),
            ""
        );

        vm.prank(executor);
        treasury.exec(address(proxy), 0, upgradeCalldata);

        bytes32 slotVal = vm.load(address(proxy), IMPLEMENTATION_SLOT);
        assertEq(address(uint160(uint256(slotVal))), address(boxEvilImpl));

        BoxEvil evilBox = BoxEvil(address(proxy));
        assertEq(evilBox.version(), "2.0.0");

        // Attacker can call undeclared sweep()
        vm.prank(attacker);
        evilBox.sweep();
        assertEq(evilBox.attacker(), attacker);
    }
}
