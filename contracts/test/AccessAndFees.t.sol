// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/AccessControlManager.sol";
import "../src/FeeManager.sol";

contract RoleCaller {
    function tryGrant(address acm, bytes32 role, address who) external returns (bool) {
        (bool ok, ) = acm.call(abi.encodeWithSignature("grantRole(bytes32,address)", role, who));
        return ok;
    }
}

contract OwnerCaller {
    function trySetConfig(address fm, uint16 bps, uint256 min, address rec) external returns (bool) {
        (bool ok, ) = fm.call(abi.encodeWithSignature("setFeeConfig(uint16,uint256,address)", bps, min, rec));
        return ok;
    }
}

contract AccessControlManagerTest {
    bytes32 constant OPERATOR = keccak256("OPERATOR");

    function testAdminGrantsAndRevokesRoles() public {
        AccessControlManager acm = new AccessControlManager();
        address op = address(0xA11CE);
        require(!acm.hasRole(OPERATOR, op), "starts without role");
        acm.grantRole(OPERATOR, op);
        require(acm.hasRole(OPERATOR, op), "role granted");
        acm.requireRole(OPERATOR, op); // must not revert
        acm.revokeRole(OPERATOR, op);
        require(!acm.hasRole(OPERATOR, op), "role revoked");
    }

    function testNonAdminCannotGrantAndRequireRoleReverts() public {
        AccessControlManager acm = new AccessControlManager();
        address op = address(0xB0B);
        RoleCaller attacker = new RoleCaller();
        bool ok = attacker.tryGrant(address(acm), OPERATOR, op);
        require(!ok, "non-admin must not grant");
        require(!acm.hasRole(OPERATOR, op), "role not granted");
        (bool rr, ) = address(acm).call(abi.encodeWithSignature("requireRole(bytes32,address)", OPERATOR, op));
        require(!rr, "requireRole must revert for missing role");
    }
}

contract FeeManagerTest {
    function testBpsFeeAndMinimumFloor() public {
        FeeManager fm = new FeeManager(50, 1, address(0xFEE)); // 0.50%, min 1
        require(fm.feeFor(1_000_000) == 5000, "bps fee");          // 0.5% of 1,000,000
        require(fm.feeFor(1) == 1, "dust pays the minimum, not zero");
        require(fm.feeFor(0) == 0, "zero amount pays nothing");
        (uint256 net, uint256 fee) = fm.netOf(1_000_000);
        require(fee == 5000 && net == 995000, "netOf");
    }

    function testOnlyOwnerConfiguresAndBadConfigReverts() public {
        FeeManager fm = new FeeManager(50, 1, address(0xFEE));
        OwnerCaller attacker = new OwnerCaller();
        bool ok = attacker.trySetConfig(address(fm), 100, 2, address(0xFEE));
        require(!ok, "non-owner must not configure");
        require(fm.feeBps() == 50, "config unchanged");
        // Owner can configure, but an out-of-range bps reverts.
        (bool bad, ) = address(fm).call(abi.encodeWithSignature("setFeeConfig(uint16,uint256,address)", uint16(10001), uint256(1), address(0xFEE)));
        require(!bad, "bps > 10000 must revert");
        fm.setFeeConfig(100, 2, address(0xFEE));
        require(fm.feeBps() == 100 && fm.minFee() == 2, "owner config applied");
    }
}
