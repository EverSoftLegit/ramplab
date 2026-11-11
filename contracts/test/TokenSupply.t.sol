// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/MockUSDC.sol";

contract UnauthorisedCaller {
    function tryBurn(address token, address from, uint256 amount) external {
        MockUSDC(token).burn(from, amount);
    }
}

contract TokenSupplyTest {
    function testMinterCanMintAndBurnAdjustsSupply() public {
        MockUSDC token = new MockUSDC();
        address customer = address(0xBEEF);
        token.mint(customer, 500 * 10 ** 6);
        require(token.totalSupply() == 500 * 10 ** 6, "mint supply");
        require(token.balanceOf(customer) == 500 * 10 ** 6, "mint balance");

        token.burn(customer, 200 * 10 ** 6);
        require(token.totalSupply() == 300 * 10 ** 6, "burn supply");
        require(token.balanceOf(customer) == 300 * 10 ** 6, "burn balance");
    }

    function testBurnRejectsUnauthorisedCallerAndOverflow() public {
        MockUSDC token = new MockUSDC();
        address customer = address(0xCAFE);
        token.mint(customer, 100 * 10 ** 6);

        UnauthorisedCaller attacker = new UnauthorisedCaller();
        (bool ok, ) = address(attacker).call(
            abi.encodeWithSelector(UnauthorisedCaller.tryBurn.selector, address(token), customer, 10 * 10 ** 6)
        );
        require(!ok, "non-minter must not burn");

        (bool ok2, ) = address(token).call(
            abi.encodeWithSelector(MockUSDC.burn.selector, customer, 1_000 * 10 ** 6)
        );
        require(!ok2, "cannot burn more than balance");
        require(token.balanceOf(customer) == 100 * 10 ** 6, "balance unchanged");
    }
}
