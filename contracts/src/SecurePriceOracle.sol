// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Hardened price oracle (RAMP-012). Teaching counterpart; not audited.
/// @dev Only an authorised updater may write, prices must be non-zero, and reads
/// revert once the last update is older than `maxAge` (staleness protection).
contract SecurePriceOracle {
    address public immutable updater;
    uint256 public immutable maxAge;
    uint256 private _price;
    uint256 public updatedAt;

    error NotUpdater();
    error BadPrice();
    error StalePrice();

    event PriceUpdated(uint256 price);

    constructor(address updater_, uint256 maxAge_) {
        require(updater_ != address(0) && maxAge_ > 0, "bad config");
        updater = updater_;
        maxAge = maxAge_;
    }

    function setPrice(uint256 newPrice) external {
        if (msg.sender != updater) revert NotUpdater();
        if (newPrice == 0) revert BadPrice();
        _price = newPrice;
        updatedAt = block.timestamp;
        emit PriceUpdated(newPrice);
    }

    function latestPrice() external view returns (uint256) {
        if (updatedAt == 0 || block.timestamp - updatedAt > maxAge) revert StalePrice();
        return _price;
    }
}
