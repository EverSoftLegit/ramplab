// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice INTENTIONALLY VULNERABLE price oracle (RAMP-012).
/// @dev Anyone can move the price: there is no access control on the writer and
/// no freshness guarantee. A consumer that trusts this can be driven to misprice
/// a conversion or over-value collateral.
contract VulnerablePriceOracle {
    uint256 public price;      // price of 1 base unit in quote terms, 8 decimals
    uint256 public updatedAt;

    event PriceUpdated(uint256 price, address by);

    // VULNERABLE: no access control. Any caller sets the price.
    function setPrice(uint256 newPrice) external {
        price = newPrice;
        updatedAt = block.timestamp;
        emit PriceUpdated(newPrice, msg.sender);
    }

    function latestPrice() external view returns (uint256) {
        return price;
    }
}
