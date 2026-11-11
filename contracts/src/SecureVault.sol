// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Hardened teaching counterpart. Still not production audited software.
contract SecureVault {
    mapping(address => uint256) public balances;
    bool private locked;

    function deposit() external payable {
        require(msg.value > 0, "zero deposit");
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(!locked, "reentrant call");
        require(amount > 0 && balances[msg.sender] >= amount, "bad amount");
        locked = true;
        balances[msg.sender] -= amount; // checks-effects-interactions
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        locked = false;
    }
}
