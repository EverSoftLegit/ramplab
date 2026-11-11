// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IPriceSource {
    function latestPrice() external view returns (uint256);
}

/// @notice Values an amount using a price source. The point of the challenge is
/// that its safety is entirely inherited from the oracle it trusts.
contract PriceConsumer {
    IPriceSource public immutable oracle;

    constructor(address oracle_) {
        oracle = IPriceSource(oracle_);
    }

    /// @return value of `amount` base units in quote terms (price is 8-decimal).
    function quote(uint256 amount) external view returns (uint256) {
        return amount * oracle.latestPrice() / 1e8;
    }
}
