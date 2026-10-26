// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {BoxUUPS} from "./BoxUUPS.sol";

contract BoxEvil is BoxUUPS {
    address public attacker;

    event Swept(address indexed to, uint256 amount);

    function version() external pure override returns (string memory) {
        return "2.0.0";
    }

    // Undeclared backdoor selector (sweep())
    function sweep() external {
        attacker = msg.sender;
        emit Swept(msg.sender, address(this).balance);
    }

    // Extra delegatecall opcode
    function executeRaw(address target, bytes calldata data) external onlyOwner {
        (bool success, ) = target.delegatecall(data);
        require(success, "BoxEvil: delegatecall failed");
    }
}
