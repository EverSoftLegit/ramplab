# RAMP-004 — Reentrancy in a simulated vault

**Level:** Intermediate  
**Category:** Smart-contract reentrancy  
**Scope:** `contracts/src/VulnerableVault.sol` and `contracts/src/SecureVault.sol`

## Scenario

A vault sends ETH to an external caller before updating the caller's balance. The receiver can call the withdrawal function again while the original call has not completed.

## Objective

Run the Foundry tests and compare the vulnerable and hardened outcomes.

## Guided exercise

```bash
cd contracts
forge test -vv
```

The vulnerable test should show the reentrant receiver draining the synthetic vault balance. The secure test should show that the same receiver only recovers its own deposit.

## Questions

1. Which external interaction occurs before the state update?
2. Why does a reentrancy guard complement, rather than replace, checks-effects-interactions?
3. Which invariants should a property-based test assert?
4. How might token hooks, callbacks or cross-function reentrancy change the attack surface?

## Remediation

Validate preconditions, update internal state before external interaction, use a reviewed reentrancy guard where appropriate, check call outcomes, and test invariants under adversarial callbacks. These contracts are small teaching examples, not production templates.
