// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Role and permission registry for the RampLab contracts.
/// @dev Minimal, standalone RBAC: an admin grants and revokes named roles, and
/// callers can gate functionality on `hasRole` / `requireRole`. Teaching code;
/// a production system would use a battle-tested library and multi-sig admin.
contract AccessControlManager {
    address public admin;
    mapping(bytes32 => mapping(address => bool)) private _roles;

    event RoleGranted(bytes32 indexed role, address indexed account, address indexed by);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed by);
    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);

    error NotAdmin();
    error MissingRole(bytes32 role, address account);
    error ZeroAddress();

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    constructor() {
        admin = msg.sender;
        emit AdminTransferred(address(0), msg.sender);
    }

    function grantRole(bytes32 role, address account) external onlyAdmin {
        if (account == address(0)) revert ZeroAddress();
        _roles[role][account] = true;
        emit RoleGranted(role, account, msg.sender);
    }

    function revokeRole(bytes32 role, address account) external onlyAdmin {
        _roles[role][account] = false;
        emit RoleRevoked(role, account, msg.sender);
    }

    function hasRole(bytes32 role, address account) public view returns (bool) {
        return _roles[role][account];
    }

    /// @notice Reverts unless `account` holds `role`. For callers to gate on.
    function requireRole(bytes32 role, address account) external view {
        if (!_roles[role][account]) revert MissingRole(role, account);
    }

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroAddress();
        emit AdminTransferred(admin, newAdmin);
        admin = newAdmin;
    }
}
