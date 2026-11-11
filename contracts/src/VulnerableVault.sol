// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice INTENTIONALLY VULNERABLE teaching contract. Local Anvil only.
/// @dev State is cleared after the external call, allowing reentrant withdrawals.
contract VulnerableVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        require(msg.value > 0, "zero deposit");
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(amount > 0 && balances[msg.sender] == amount, "withdraw full balance");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        // RAMP-004: deliberately unsafe order and state reset for this lab.
        balances[msg.sender] = 0;
    }
}
