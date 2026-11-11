# RAMP-001 — BOLA / IDOR (independent brief)

**Level:** Beginner · **Scope:** local RampLab only

## Scenario
Alice and Bob each have synthetic wallet accounts. An account lookup accepts a caller-supplied object identifier.

## Objective
Determine whether Alice can read an account owned by Bob. Compare the explicitly vulnerable and hardened API routes.

## Evidence to submit
- Requests and responses with synthetic identifiers only.
- The authorization boundary that failed or held.
- Impact stated in terms of the synthetic lab data.
- A regression test that prevents cross-owner reads.

## Scope
- Vulnerable: `GET /api/lab/accounts/{account_id}`
- Comparison: `GET /api/accounts/{account_id}`

Do not test any external service. Do not treat the demo identity header as real authentication.
