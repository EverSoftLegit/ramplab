# RAMP-005 — Unauthorised fiat-deposit confirmation

**Level:** Intermediate · **Category:** Smart-contract access control / ramp business logic  
**Scope:** Local Foundry tests only

## Scenario

A fiat on-ramp listens for an off-chain payment provider and mints synthetic USDC after a fiat deposit is confirmed. The vulnerable contract exposes that confirmation function without restricting who may call it or requiring verifiable provider evidence.

## Objective

Show that an arbitrary caller can trigger token minting through the vulnerable ramp. Compare the operator-restricted implementation.

## Run

```bash
cd contracts
forge test --match-path test/RampAuthorization.t.sol -vv
```

## Questions

1. Which trust boundary is crossed between the off-chain bank/provider and the on-chain contract?
2. Why is an event reference or transaction hash not proof by itself?
3. What should bind a payment confirmation to an amount, customer, currency, provider and unique event?
4. Why is a single operator key an incomplete production control?

## Remediation

Use a narrowly scoped payment-operator role, authenticated provider attestations, unique event IDs, amount/currency/account binding, expiry, monitoring, key rotation and a controlled pause path. For real systems, the complete design must be reviewed against the provider's verification mechanism and the on-chain trust model.

The synthetic token is not real USDC. Never deploy this exercise to a public network.
