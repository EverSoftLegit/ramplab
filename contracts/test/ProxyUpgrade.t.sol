// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/ProxyLogic.sol";
import "../src/VulnerableProxy.sol";
import "../src/SecureProxy.sol";

/// Stands in for an unrelated attacker account attempting an upgrade.
contract ProxyAttacker {
    function upgrade(address proxy, address newImpl) external returns (bool) {
        (bool ok, ) = proxy.call(abi.encodeWithSignature("upgradeTo(address)", newImpl));
        return ok;
    }
}

contract ProxyUpgradeTest {
    function testVulnerableProxyAnyoneCanUpgrade() public {
        LogicV1 v1 = new LogicV1();
        LogicV2 v2 = new LogicV2();
        VulnerableProxy proxy = new VulnerableProxy(address(v1));
        require(ILogic(address(proxy)).version() == 1, "starts on v1");

        // An unrelated account swaps the implementation with no authorisation.
        ProxyAttacker attacker = new ProxyAttacker();
        bool ok = attacker.upgrade(address(proxy), address(v2));
        require(ok, "attacker could not upgrade");
        require(ILogic(address(proxy)).version() == 2, "implementation was hijacked");
    }

    function testSecureProxyRejectsNonAdminUpgrade() public {
        LogicV1 v1 = new LogicV1();
        LogicV2 v2 = new LogicV2();
        SecureProxy proxy = new SecureProxy(address(v1)); // admin = this contract
        require(ILogic(address(proxy)).version() == 1, "starts on v1");

        ProxyAttacker attacker = new ProxyAttacker();
        bool ok = attacker.upgrade(address(proxy), address(v2));
        require(!ok, "non-admin upgrade must revert");
        require(ILogic(address(proxy)).version() == 1, "implementation unchanged");

        // The admin can still upgrade legitimately.
        proxy.upgradeTo(address(v2));
        require(ILogic(address(proxy)).version() == 2, "admin upgrade works");
    }
}
