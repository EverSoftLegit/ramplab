# RAMP-003 — Payment callback integrity (independent brief)

**Level:** Intermediate · **Scope:** local RampLab only

## Scenario
A mock payment provider sends a deposit notification to the ramp. The application converts that notification into a synthetic wallet credit.

## Objective
Evaluate the callback's authenticity and replay behaviour. Determine whether the same provider event can affect the synthetic balance more than once.

## Evidence to submit
- Synthetic request/response pairs.
- Whether the callback authenticity is verified.
- Whether event processing is idempotent.
- A test that demonstrates the expected secure behaviour.

## Scope
- Vulnerable: `POST /api/lab/webhooks/deposit`
- Comparison: `POST /api/webhooks/deposit`

Do not contact real payment providers or submit real transaction references.
