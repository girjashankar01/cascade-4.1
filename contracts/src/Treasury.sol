// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title Treasury
 * @notice Holds DAO funds (ETH and ERC-20 tokens).
 * @dev All executions must be routed through the GuardedExecutor.
 */
contract Treasury {
    address public immutable deployer;
    address public executor;

    event ExecutorSet(address indexed executor);
    event Executed(address indexed target, uint256 value, bytes data);
    event Received(address indexed sender, uint256 amount);

    modifier onlyExecutor() {
        require(msg.sender == executor, "only executor");
        _;
    }

    constructor() {
        deployer = msg.sender;
    }

    /**
     * @notice One-time initialization of the executor address by deployer.
     * @dev Permanently locked after setting.
     * @param _executor The GuardedExecutor address.
     */
    function setExecutor(address _executor) external {
        require(msg.sender == deployer, "only deployer");
        require(executor == address(0), "executor already set");
        require(_executor != address(0), "invalid executor");
        executor = _executor;
        emit ExecutorSet(_executor);
    }

    /**
     * @notice Execute an arbitrary call authorized by the executor.
     * @param target Contract or account to call.
     * @param value Native ETH value in wei.
     * @param data Calldata for the call.
     * @return returndata Result bytes from the external call.
     */
    function exec(
        address target,
        uint256 value,
        bytes calldata data
    ) external onlyExecutor returns (bytes memory) {
        require(target != address(0), "invalid target");
        emit Executed(target, value, data);
        (bool success, bytes memory returndata) = target.call{value: value}(data);
        if (!success) {
            if (returndata.length > 0) {
                assembly {
                    let returndata_size := mload(returndata)
                    revert(add(32, returndata), returndata_size)
                }
            } else {
                revert("treasury call failed");
            }
        }
        return returndata;
    }

    receive() external payable {
        emit Received(msg.sender, msg.value);
    }

    fallback() external payable {
        emit Received(msg.sender, msg.value);
    }
}
