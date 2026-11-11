# Local smart-contract lab

This Foundry project contains deliberately vulnerable and hardened teaching pairs: a reentrancy vault and a fiat-ramp deposit-confirmation flow. It is designed for a local Anvil chain only. Do not deploy either contract to a public chain or use real assets.

## Run

Install Foundry using its official installation instructions, then:

```bash
cd contracts
forge test -vv
```

The tests demonstrate that `VulnerableVault` can be re-entered to withdraw the seeded synthetic vault balance, while `SecureVault` updates state before the external call and blocks nested entry. They also demonstrate that `VulnerableRamp` lets an arbitrary caller fabricate a fiat deposit confirmation, while `SecureRamp` restricts confirmation to the configured payment operator.

## Safety

- `MockUSDC` is a synthetic six-decimal token, not USDC.
- No production token, bridge, exchange, oracle, or banking integration is included.
- Foundry's default development accounts and keys are publicly known.
- Never reuse development keys or seed phrases outside a local disposable environment.
- This is an educational example, not an audited contract template.
