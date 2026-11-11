// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/VulnerablePriceOracle.sol";
import "../src/SecurePriceOracle.sol";
import "../src/PriceConsumer.sol";

/// Stands in for an unrelated attacker account.
contract OracleAttacker {
    function setPrice(address oracle, uint256 p) external returns (bool) {
        (bool ok, ) = oracle.call(abi.encodeWithSignature("setPrice(uint256)", p));
        return ok;
    }
}

contract PriceOracleTest {
    function testVulnerableOracleManipulationReprices() public {
        VulnerablePriceOracle oracle = new VulnerablePriceOracle();
        PriceConsumer consumer = new PriceConsumer(address(oracle));
        oracle.setPrice(1e8); // 1.00
        uint256 fair = consumer.quote(100);
        require(fair == 100, "fair quote");

        // An unrelated account manipulates the price upward with no authorisation.
        OracleAttacker attacker = new OracleAttacker();
        bool ok = attacker.setPrice(address(oracle), 100e8); // 100.00
        require(ok, "attacker could not set price");
        uint256 manipulated = consumer.quote(100);
        require(manipulated == 10000, "price not manipulated");
        require(manipulated == fair * 100, "expected 100x reprice");
    }

    function testSecureOracleRejectsUnauthorisedWriter() public {
        SecurePriceOracle oracle = new SecurePriceOracle(address(this), 1 hours);
        PriceConsumer consumer = new PriceConsumer(address(oracle));
        oracle.setPrice(1e8);
        require(consumer.quote(100) == 100, "authorised price works");

        OracleAttacker attacker = new OracleAttacker();
        bool ok = attacker.setPrice(address(oracle), 100e8);
        require(!ok, "unauthorised writer must be rejected");
        require(consumer.quote(100) == 100, "price unchanged after attack");
    }

    function testSecureOracleRevertsOnStalePrice() public {
        // Freshly constructed oracle has never been written: updatedAt == 0.
        SecurePriceOracle oracle = new SecurePriceOracle(address(this), 1 hours);
        PriceConsumer consumer = new PriceConsumer(address(oracle));
        (bool ok, ) = address(consumer).call(abi.encodeWithSignature("quote(uint256)", uint256(100)));
        require(!ok, "stale/unset price must revert the read");
    }
}
