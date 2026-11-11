# RAMP-002 — Quote integrity (independent brief)

**Level:** Intermediate · **Scope:** local RampLab only

## Scenario
A simulated crypto/fiat ramp produces a conversion quote. Different API paths may have different assumptions about who controls the price.

## Objective
Establish whether a caller can influence the rate used to calculate a quote, and determine whether the same input is accepted by the normal quote path.

## Evidence to submit
- Two synthetic quote requests and responses.
- The trust boundary violated.
- The effect on the destination amount and fee calculation.
- A regression test showing the quote service owns the authoritative rate.

## Scope
- Vulnerable: `POST /api/lab/quotes`
- Comparison: `POST /api/quotes`

All rates are fictional. Do not use live FX or market data.
