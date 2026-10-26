// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {BoxUUPS} from "./BoxUUPS.sol";

contract BoxV2 is BoxUUPS {
    function version() external pure override returns (string memory) {
        return "2.0.0";
    }

    function increment() external onlyOwner {
        _value += 1;
        emit ValueChanged(_value);
    }
}
