# RAMP-003 — Unsigned and replayable payment callback

**Level:** Intermediate  
**Category:** Payment integration / webhook authenticity / idempotency  
**Scope:** `/api/lab/webhooks/deposit` and `/api/webhooks/deposit`

## Scenario

A simulated payment provider tells the ramp that a fiat deposit has completed. The vulnerable endpoint trusts the JSON body and credits the account every time it is called.

## Objective

Show that the same event can be submitted more than once to the vulnerable route. Then test the hardened endpoint's HMAC verification and idempotency control.

## Guided exercise

1. In the dashboard, note Alice's NGN balance and account ID.
2. Submit the same lab event twice:

```bash
curl -s http://127.0.0.1:8000/api/lab/webhooks/deposit \
  -H 'Content-Type: application/json' \
  -d '{"owner":"alice","account_id":"ALICE_NGN_ACCOUNT_ID","amount":"100.00","event_id":"evt-replay-1"}'
```

Repeat the exact command. The vulnerable endpoint credits twice.

3. For the hardened endpoint, generate an HMAC using the local secret from `.env.example`:

```bash
python scripts/sign_webhook.py --account-id ALICE_NGN_ACCOUNT_ID --amount 100.00 --event-id evt-secure-1
```

The script prints the exact compact JSON body and `sha256=` signature. Send the exact body as `--data-binary` with the signature in `X-Ramp-Signature`. Send it a second time; the second response should be `duplicate_ignored`.

## Remediation

Verify a provider signature over the exact raw request body, use constant-time signature comparison, enforce timestamp/replay windows where supported, store a provider event ID under a uniqueness constraint, and update the ledger and idempotency record in one database transaction. In real systems, use secret rotation, managed secret storage, TLS, provider-specific verification guidance and monitored failure handling.
