# RampLab threat model

**Method:** lightweight STRIDE + abuse-case analysis  
**System:** RampLab 0.1.0 local training environment  
**Data classification:** synthetic only

## 1. Security objectives

- Prevent unintended access to another demo user's account in hardened examples.
- Preserve financial arithmetic and ledger consistency in the hardened conversion flow.
- Authenticate and deduplicate hardened webhook events.
- Make vulnerabilities discoverable only within an explicitly local training environment.
- Prevent contributors from confusing demonstration code with production templates.
- Keep reset and test data deterministic.

## 2. Assets

| Asset | Security property |
|---|---|
| Synthetic account balances | Integrity |
| Conversion quotes | Integrity, ownership, expiry, one-time use |
| Ledger entries | Integrity, consistency, traceability |
| Webhook secret | Confidentiality within local lab |
| Demo identity context | Correct ownership association; not real authentication |
| Solidity contract state | Integrity and bounded local execution |
| Host machine | Isolation from intentionally vulnerable services |

## 3. Actors

- **Learner:** authorised user of their own local copy; may intentionally exploit lab weaknesses.
- **Instructor:** seeds scenarios and resets the lab.
- **Malicious local learner:** attempts to exceed their assigned synthetic account scope.
- **External attacker:** must not be able to reach the lab; public exposure is outside the supported deployment model.
- **Contributor:** submits code, challenge content or documentation; changes require review and tests.

## 4. Trust boundaries and assumptions

- The application is run by one learner on a machine they control.
- The Docker Compose host port binds to loopback only.
- The Compose network is internal; no production providers or external APIs are configured.
- The `X-Demo-User` header is an intentionally simplified identity selector. It is trivially forgeable and MUST NOT be described as authentication.
- The default webhook secret is a demonstration secret and MUST be replaced for local experiments; it is not suitable for any real service.
- SQLite contains synthetic data only.

## 5. Abuse cases and controls

| ID | Abuse case | Deliberate lab weakness | Hardened teaching control |
|---|---|---|---|
| TM-01 | Read another user's wallet | BOLA route omits ownership check | Derive identity from authenticated server-side context; check owner on every object access |
| TM-02 | Obtain an unfair conversion | Lab quote accepts client-supplied rate | Rate sourced from trusted server-side quote service; signed/versioned quote; short expiry |
| TM-03 | Credit a deposit without provider confirmation | Lab webhook has no signature validation | HMAC over exact raw body; key rotation/secrets management; TLS in real deployment |
| TM-04 | Replay a payment callback | Lab webhook has no idempotency record | Unique provider event ID, database uniqueness and atomic credit operation |
| TM-05 | Double-spend via concurrent conversion | Quote execution and balance updates are database-transactional in hardened path | Lock/serialise balance mutation; one-time quote status; concurrency regression tests |
| TM-06 | Exploit decimal/rounding differences | Challenge extension | Currency-specific precision, integer minor units, checked rounding and invariant tests |
| TM-07 | Drain a vault by re-entering withdraw | VulnerableVault external call before state update | Checks-effects-interactions and reentrancy guard; invariant/property testing |
| TM-08 | Reach local vulnerable service remotely | Misconfigured port or network | Host loopback bind, internal Docker network, no public deployment instructions |
| TM-09 | Abuse reset endpoint | Reset route intentionally unauthenticated for local lab | Never host the lab; keep reset local; future hosted instances need per-learner isolation and access control |
| TM-10 | Treat seeded exchange rates as real | Static demo prices | Prominent UI/API labels; no real market feed; avoid currency conversion claims |
| TM-11 | Mint tokens after a fabricated fiat deposit confirmation | Vulnerable ramp accepts public confirmation calls | Restricted operator role plus provider attestation, event uniqueness and reconciliation in a real design |

## 6. STRIDE summary

- **Spoofing:** demo identity header is spoofable by design. No real user identity exists in 0.1.0. A future hosted lab must use isolated learner sessions and server-side identity claims.
- **Tampering:** client-controlled rate and unsigned webhook are intentional examples. Hardened quote and callback paths validate server-side state and HMAC.
- **Repudiation:** transactions and ledger entries have references and timestamps, but they are educational records, not tamper-evident audit records.
- **Information disclosure:** vulnerable account lookup is a BOLA lab. The secure endpoint checks owner.
- **Denial of service:** local learners can exhaust their own lab resources. Do not host shared public instances without quotas and isolation.
- **Elevation of privilege:** role-based administration and KYC bypass are future backlog items, not implemented authentication controls.

## 7. Containment requirements

- Run on a personal workstation or disposable VM.
- Bind published ports to `127.0.0.1` only.
- Do not use `--host 0.0.0.0` for direct host execution.
- Do not configure public RPC endpoints, real provider credentials or production wallets.
- Use only synthetic accounts and local development keys.
- Do not upload real customer data, credentials, seed phrases, transaction exports or identity documents into issues or pull requests.
- Reset the database after completing a lab.

## 8. Residual risk

The application remains intentionally vulnerable by design. Loopback binding and internal container networking reduce accidental exposure but do not make the code safe for internet deployment. A user can bypass container safeguards by changing configuration. The project must keep safety warnings prominent and reject requests to turn the vulnerable edition into a production financial service.
