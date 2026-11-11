// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Hardened upgradeable proxy (RAMP-013). Teaching counterpart.
/// @dev Only the admin may upgrade. A production proxy would also separate the
/// admin interface from user calls (transparent/UUPS) and guard initialisation.
contract SecureProxy {
    address public admin;
    address public implementation;

    error NotAdmin();

    constructor(address impl) {
        admin = msg.sender;
        implementation = impl;
    }

    function upgradeTo(address newImpl) external {
        if (msg.sender != admin) revert NotAdmin();
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
