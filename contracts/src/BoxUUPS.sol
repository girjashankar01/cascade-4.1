// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {UUPSUpgradeable} from "@openzeppelin/contracts/proxy/utils/UUPSUpgradeable.sol";

contract BoxUUPS is UUPSUpgradeable {
    address public owner;
    uint256 internal _value;
    bool private _initialized;

    event ValueChanged(uint256 newValue);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "BoxUUPS: caller is not the owner");
        _;
    }

    function initialize(address initialOwner) external {
        require(!_initialized, "BoxUUPS: already initialized");
        require(initialOwner != address(0), "BoxUUPS: zero owner");
        _initialized = true;
        owner = initialOwner;
        emit OwnershipTransferred(address(0), initialOwner);
    }

    function setValue(uint256 val) external onlyOwner {
        _value = val;
        emit ValueChanged(val);
    }

    function getValue() external view returns (uint256) {
        return _value;
    }

    function version() external pure virtual returns (string memory) {
        return "1.0.0";
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}
}
