// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISecureRampToken {
    function mint(address to, uint256 amount) external;
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @notice Hardened teaching counterpart; not audited or production-ready.
contract SecureRamp {
    ISecureRampToken public immutable token;
    address public paymentOperator;

    event PaymentOperatorUpdated(address indexed previousOperator, address indexed newOperator);
    event FiatDepositCredited(address indexed customer, uint256 tokenAmount, bytes32 providerReference);
    event FiatPayoutRequested(address indexed customer, uint256 tokenAmount, bytes32 payoutReference);

    modifier onlyPaymentOperator() {
        require(msg.sender == paymentOperator, "not payment operator");
        _;
    }

    constructor(address tokenAddress, address operator) {
        require(tokenAddress != address(0) && operator != address(0), "zero address");
        token = ISecureRampToken(tokenAddress);
        paymentOperator = operator;
    }

    function updatePaymentOperator(address nextOperator) external onlyPaymentOperator {
        require(nextOperator != address(0), "zero operator");
        emit PaymentOperatorUpdated(paymentOperator, nextOperator);
        paymentOperator = nextOperator;
    }

    function confirmFiatDeposit(address customer, uint256 tokenAmount, bytes32 providerReference) external onlyPaymentOperator {
        require(customer != address(0) && tokenAmount > 0, "invalid deposit");
        // This lab uses an operator allowlist as the simple secure comparison.
        // Real systems also need provider signature verification, replay controls,
        // event reconciliation, key rotation and operational monitoring.
        token.mint(customer, tokenAmount);
        emit FiatDepositCredited(customer, tokenAmount, providerReference);
    }

    function requestFiatWithdrawal(uint256 tokenAmount, bytes32 payoutReference) external {
        require(tokenAmount > 0, "zero amount");
        require(token.transferFrom(msg.sender, address(this), tokenAmount), "token transfer failed");
        emit FiatPayoutRequested(msg.sender, tokenAmount, payoutReference);
    }
}
