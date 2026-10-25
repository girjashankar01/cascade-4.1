// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/// Stage 0 smoke check that the OpenZeppelin remapping compiles and links.
contract DependencyTest is Test {
    function test_OpenZeppelinImport() public pure {
        assertEq(Math.max(1, 2), 2);
    }
}
