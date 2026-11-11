# RAMP-002 — Caller-controlled exchange rate

**Level:** Intermediate  
**Category:** Business logic / price integrity  
**Scope:** `POST /api/lab/quotes` compared with `POST /api/quotes`

## Scenario

A ramp engine accepts the exchange rate from the browser. The caller can request a conversion quote using a rate that the platform did not generate.

## Objective

Compare a normal NGN-to-USDC quote with a lab quote that supplies a deliberately unrealistic rate. Observe how the resulting destination amount changes.

## Guided exercise

```bash
curl -s http://127.0.0.1:8000/api/quotes \
  -H 'Content-Type: application/json' -H 'X-Demo-User: alice' \
  -d '{"source_currency":"NGN","target_currency":"USDC","amount":"1000.00"}'

curl -s http://127.0.0.1:8000/api/lab/quotes \
  -H 'Content-Type: application/json' -H 'X-Demo-User: alice' \
  -d '{"source_currency":"NGN","target_currency":"USDC","amount":"1000.00","rate_override":"1"}'
```

Expected: the lab route uses the caller-supplied rate. The hardened route schema has no `rate_override` field and computes a fixed server-side teaching rate.

## Questions

1. Can a customer-supplied amount ever be trusted without validation?
2. Where should quote provenance, expiry and price version be recorded?
3. How should an off-chain quote be bound to an on-chain execution?
4. How could stale or manipulated oracle data differ from a client-controlled rate?

## Remediation

Use a server-controlled pricing source, record the rate source and timestamp, bind quote details to the identity and accounts, expire quotes, and revalidate policy before execution. For on-chain flows, use a reviewed oracle design with freshness/deviation checks. The hard-coded rates in RampLab are fictional and are not an oracle.
