// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ILogic {
    function version() external pure returns (uint256);
}

/// The legitimate implementation behind the proxy.
contract LogicV1 {
    function version() external pure returns (uint256) {
        return 1;
    }
}

/// A different implementation an attacker could swap in if upgrades are unguarded.
contract LogicV2 {
    function version() external pure returns (uint256) {
        return 2;
    }
}
