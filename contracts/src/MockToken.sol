// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title MockToken
 * @notice OpenZeppelin ERC-20 with 6 decimals mimicking USDC for DAO payout scenarios.
 */
contract MockToken is ERC20 {
    uint8 private constant _DECIMALS = 6;
    address public immutable deployer;

    constructor(
        string memory name_,
        string memory symbol_,
        uint256 initialSupply_
    ) ERC20(name_, symbol_) {
        deployer = msg.sender;
        if (initialSupply_ > 0) {
            _mint(msg.sender, initialSupply_);
        }
    }

    function decimals() public pure override returns (uint8) {
        return _DECIMALS;
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == deployer, "only deployer");
        _mint(to, amount);
    }
}
