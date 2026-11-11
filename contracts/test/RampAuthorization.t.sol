// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/MockUSDC.sol";
import "../src/VulnerableRamp.sol";
import "../src/SecureRamp.sol";

contract UntrustedRampCaller {
    function callConfirm(address ramp, address customer, uint256 amount, bytes32 providerRef) external {
        (bool ok, ) = ramp.call(abi.encodeWithSignature(
            "confirmFiatDeposit(address,uint256,bytes32)", customer, amount, providerRef
        ));
        require(ok, "confirmation rejected");
    }
}

contract RampAuthorizationTest {
    function testAnyoneCanFabricateFiatConfirmationOnVulnerableRamp() public {
        MockUSDC token = new MockUSDC();
        VulnerableRamp ramp = new VulnerableRamp(address(token));
        token.setMinter(address(ramp), true);
        UntrustedRampCaller attacker = new UntrustedRampCaller();
        address syntheticCustomer = address(0xBEEF);

        attacker.callConfirm(address(ramp), syntheticCustomer, 250 * 10 ** 6, keccak256("fake-provider-event"));
        require(token.balanceOf(syntheticCustomer) == 250 * 10 ** 6, "expected unverified mint");
    }

    function testSecureRampRejectsUntrustedFiatConfirmation() public {
        MockUSDC token = new MockUSDC();
        SecureRamp ramp = new SecureRamp(address(token), address(this));
        token.setMinter(address(ramp), true);
        UntrustedRampCaller attacker = new UntrustedRampCaller();
        address syntheticCustomer = address(0xCAFE);

        (bool ok, ) = address(attacker).call(abi.encodeWithSelector(
            UntrustedRampCaller.callConfirm.selector,
            address(ramp), syntheticCustomer, 250 * 10 ** 6, keccak256("forged-event")
        ));
        require(!ok, "untrusted caller should be rejected");
        require(token.balanceOf(syntheticCustomer) == 0, "secure ramp must not mint");

        ramp.confirmFiatDeposit(syntheticCustomer, 250 * 10 ** 6, keccak256("verified-demo-event"));
        require(token.balanceOf(syntheticCustomer) == 250 * 10 ** 6, "operator confirmation should mint");
    }
}
