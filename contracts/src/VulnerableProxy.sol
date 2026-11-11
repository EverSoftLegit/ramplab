// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice INTENTIONALLY VULNERABLE upgradeable proxy (RAMP-013).
/// @dev `upgradeTo` has no access control, so any caller can replace the
/// implementation the proxy delegates to — a full takeover of the logic.
contract VulnerableProxy {
    address public implementation;

    constructor(address impl) {
        implementation = impl;
    }

    // VULNERABLE: anyone can change the implementation.
    function upgradeTo(address newImpl) external {
        implementation = newImpl;
    }

    fallback() external payable {
        address impl = implementation;
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }

    receive() external payable {}
}
