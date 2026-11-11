# RAMP-004 — Reentrancy (independent brief)

**Level:** Intermediate · **Scope:** local Foundry tests only

## Scenario
A simulated vault lets users deposit and withdraw test ETH. One implementation interacts with an external receiver during withdrawal.

## Objective
Determine whether a receiver can cause the withdrawal path to execute recursively before the vault's state is safely updated. Compare the second implementation and its invariant behaviour.

## Evidence to submit
- Foundry test output.
- Call sequence and relevant state transitions.
- Impact on the synthetic vault balance.
- A regression test demonstrating the secure invariant.

## Scope
- Vulnerable: `contracts/src/VulnerableVault.sol`
- Comparison: `contracts/src/SecureVault.sol`

Use only Foundry's local test environment. Never deploy the contracts to a public chain.
