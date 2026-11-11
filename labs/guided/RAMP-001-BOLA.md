# RAMP-001 — Broken object-level authorization

**Level:** Beginner  
**Category:** API authorization / BOLA (IDOR)  
**Scope:** `GET /api/lab/accounts/{account_id}` and `GET /api/accounts/{account_id}`

## Scenario

Alice and Bob have separate synthetic wallet accounts. A developer implemented an account lookup using an opaque account ID but forgot to verify that the requested account belongs to the current demo identity.

## Objective

Demonstrate that the vulnerable route returns Bob's synthetic account when the caller selects Alice, then show that the hardened route rejects the same access.

## Setup

Run RampLab locally and open `/`. Switch the demo identity to Bob, refresh balances, and note Bob's NGN account ID. Switch back to Alice.

## Guided exercise

```bash
# Replace BOB_NGN_ACCOUNT_ID with the synthetic account ID shown for Bob.
curl -s http://127.0.0.1:8000/api/lab/accounts/BOB_NGN_ACCOUNT_ID \
  -H 'X-Demo-User: alice'

curl -i http://127.0.0.1:8000/api/accounts/BOB_NGN_ACCOUNT_ID \
  -H 'X-Demo-User: alice'
```

Expected: the lab route returns the Bob account; the hardened route returns HTTP 403.

## Questions

1. Which object identifier is controlled by the caller?
2. Where should the server derive the authenticated subject in a real system?
3. Why is an unguessable UUID not an authorization control?
4. Which tests should cover account, transaction, beneficiary and KYC objects?

## Remediation

Use a server-verified identity (for example, a validated session/JWT subject) and scope the object query to both object ID and owner. Do not use `X-Demo-User` as real identity; it is intentionally spoofable in this lab.
