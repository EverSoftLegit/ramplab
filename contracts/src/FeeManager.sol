// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Simulated transaction fee logic for RampLab.
/// @dev Computes a basis-point fee with a minimum-fee floor, so dust-sized
/// transactions cannot round their fee to zero (the on-chain counterpart of the
/// RAMP-016 hardened policy). Owner-gated configuration. Teaching code.
contract FeeManager {
    address public owner;
    uint16 public feeBps;        // basis points (1/100 of a percent); max 10000
    uint256 public minFee;       // minimum fee in token minor units
    address public feeRecipient;

    event FeeConfigUpdated(uint16 feeBps, uint256 minFee, address indexed recipient);
    event OwnerTransferred(address indexed previousOwner, address indexed newOwner);

    error NotOwner();
    error BadConfig();
    error ZeroAddress();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(uint16 feeBps_, uint256 minFee_, address recipient_) {
        if (feeBps_ > 10000 || recipient_ == address(0)) revert BadConfig();
        owner = msg.sender;
        feeBps = feeBps_;
        minFee = minFee_;
        feeRecipient = recipient_;
        emit FeeConfigUpdated(feeBps_, minFee_, recipient_);
    }

    function setFeeConfig(uint16 feeBps_, uint256 minFee_, address recipient_) external onlyOwner {
        if (feeBps_ > 10000 || recipient_ == address(0)) revert BadConfig();
        feeBps = feeBps_;
        minFee = minFee_;
        feeRecipient = recipient_;
        emit FeeConfigUpdated(feeBps_, minFee_, recipient_);
    }

    /// @notice Fee for `amount`, enforcing the minimum-fee floor for positive amounts.
    function feeFor(uint256 amount) public view returns (uint256 fee) {
        fee = amount * feeBps / 10000;
        if (amount > 0 && fee < minFee) fee = minFee;
    }

    /// @return net amount after fee, and the fee charged.
    function netOf(uint256 amount) external view returns (uint256 net, uint256 fee) {
        fee = feeFor(amount);
        net = amount > fee ? amount - fee : 0;
    }

    function transferOwner(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        emit OwnerTransferred(owner, newOwner);
        owner = newOwner;
    }
}
