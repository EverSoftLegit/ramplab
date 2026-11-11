// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IRampToken {
    function mint(address to, uint256 amount) external;
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @notice INTENTIONALLY VULNERABLE local on/off-ramp teaching contract.
/// @dev Anyone can claim a fiat deposit and cause synthetic tokens to be minted.
contract VulnerableRamp {
    IRampToken public immutable token;

    event FiatDepositCredited(address indexed customer, uint256 tokenAmount, bytes32 providerReference);
    event FiatPayoutRequested(address indexed customer, uint256 tokenAmount, bytes32 payoutReference);

    constructor(address tokenAddress) {
        require(tokenAddress != address(0), "zero token");
        token = IRampToken(tokenAddress);
    }

    function confirmFiatDeposit(address customer, uint256 tokenAmount, bytes32 providerReference) external {
        // RAMP-005: no operator authorization or verifiable payment proof.
        require(customer != address(0) && tokenAmount > 0, "invalid deposit");
        token.mint(customer, tokenAmount);
        emit FiatDepositCredited(customer, tokenAmount, providerReference);
    }

    function requestFiatWithdrawal(uint256 tokenAmount, bytes32 payoutReference) external {
        require(tokenAmount > 0, "zero amount");
        require(token.transferFrom(msg.sender, address(this), tokenAmount), "token transfer failed");
        emit FiatPayoutRequested(msg.sender, tokenAmount, payoutReference);
    }
}
