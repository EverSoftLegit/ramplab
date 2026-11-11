# RAMP-005 — Fiat-deposit confirmation authorization (independent brief)

**Level:** Intermediate · **Scope:** Local Foundry tests only

## Scenario
A simulated ramp mints a synthetic stablecoin when an off-chain fiat payment is represented as confirmed.

## Objective
Assess whether an arbitrary caller can trigger minting, and determine how the hardened counterpart limits this operation.

## Evidence to submit
- Foundry test output.
- Caller identity and authorization requirements.
- Synthetic token supply and recipient balance before/after.
- A regression test proving unauthorized callers cannot cause minting.

## Scope
- Vulnerable: `contracts/src/VulnerableRamp.sol`
- Comparison: `contracts/src/SecureRamp.sol`
- Token fixture: `contracts/src/MockUSDC.sol`

Never deploy to a public chain or use real tokens, provider credentials or customer information.
