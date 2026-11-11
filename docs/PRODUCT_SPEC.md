# RampLab product and technical specification

**Version:** 0.1.0 MVP  
**Status:** Working specification; subject to community review  
**Audience:** Web3 learners, application-security engineers, smart-contract auditors, fintech developers, educators and researchers

## 1. Product statement

RampLab is a deliberately vulnerable, local-only Web3 fintech training environment. It models a synthetic fiat/crypto on-ramp and off-ramp so learners can investigate weaknesses that arise across web applications, APIs, transaction processing, internal ledgers, payment callbacks and smart contracts.

It is not an exchange, wallet provider, payment processor, custody service, KYC service or financial product. All balances, identities, market rates and payment-provider events are synthetic.

## 2. Goals

1. Provide a realistic end-to-end fintech workflow rather than isolated code puzzles.
2. Teach beginners through guided labs, clear objectives, hints and remediation.
3. Give experienced practitioners an independent-exploitation mode with minimal hints.
4. Pair deliberately vulnerable components with hardened teaching counterparts.
5. Make each lab reproducible and resettable.
6. Support African and global currency contexts without live FX feeds.
7. Be easy to run locally with Docker Compose; core API also runs directly with Python.
8. Provide repeatable tests proving both the weakness and the remediation.

## 3. Non-goals

- No real funds, bank transfers, card acquiring, payment-provider integration or cash-out.
- No public-chain deployments, public RPC calls or mainnet forks in the default project.
- No real identity documents, real KYC records, PII collection or production authentication.
- No custodial wallet, key management, bridge, stablecoin issuer or exchange functionality.
- No internet-hosted vulnerable instance.
- No claim that the secure examples are production-ready or independently audited.

## 4. Personas and learning modes

### Beginner
Needs a clear business scenario, learning objective, setup instructions, safe test account, hints, expected observation and remediation explanation.

### Experienced security professional
Needs a resettable lab, API/contract source, clear scope, no mandatory hints, logs and tests to validate impact and remediation.

### Educator / team lead
Needs deterministic state, challenge objectives, facilitator notes, repeatable tests and an option to reset between learners.

### Learning modes

- **Guided:** objective → context → setup → hints → validation → remediation → regression test.
- **Independent:** scope → synthetic target → challenge ID → learner documents findings; hints and walkthrough are separate files.

## 5. Supported synthetic currencies

| Code | Meaning | Decimal places | Treatment |
|---|---|---:|---|
| NGN | Nigerian naira | 2 | Fiat simulation |
| GHS | Ghanaian cedi | 2 | Fiat simulation |
| KES | Kenyan shilling | 2 | Fiat simulation |
| ZAR | South African rand | 2 | Fiat simulation |
| USD | US dollar | 2 | Fiat simulation |
| EUR | Euro | 2 | Fiat simulation |
| GBP | Pound sterling | 2 | Fiat simulation |
| USDC | Synthetic USD Coin-like unit | 6 | Internal mock token; not real USDC |

All exchange rates are fixed fictional fixtures stored in configuration. They are neither current exchange rates nor representations of a market. No external rate oracle is called in the MVP.

## 6. Core workflows

### 6.1 Fiat-to-crypto (simulated on-ramp)

1. Select a seeded demo identity.
2. Select a fiat source currency and synthetic USDC destination.
3. Request a quote. The quote binds owner, source/destination accounts, amount, rate, fee and expiry.
4. Confirm the quote. The API atomically debits the source account, updates treasury balances, credits the destination account, creates a transaction and writes ledger entries.
5. Inspect the transaction and ledger entries.

### 6.2 Crypto-to-fiat (simulated off-ramp)

Same workflow in reverse: synthetic USDC is debited and the chosen fiat wallet is credited. No token is sent to a public blockchain in this MVP.

### 6.3 Simulated payment callback

A vulnerable endpoint accepts an unsigned callback and processes repeated event IDs more than once. The hardened teaching endpoint validates an HMAC over the exact request body and uses a unique event ID in a database transaction to enforce idempotency.

### 6.4 Smart-contract exercise

A separate Foundry project has vulnerable/hardened vault and ramp deposit-confirmation contracts, including a synthetic six-decimal token and withdrawal request event. Tests run against local EVM execution only. The API is not yet wired to the local chain.

## 7. Domain invariants

The following are the expected secure behaviours. Labs may deliberately violate one or more invariants.

- A demo identity may only read accounts that it owns.
- A quote is bound to one identity, one source account and one destination account.
- A quote can be executed at most once and only before expiry.
- An executed conversion cannot debit more than the available source balance.
- Monetary calculations use integer minor units and decimal arithmetic, not binary floating point.
- Each conversion writes paired ledger movements for the customer and treasury in each currency.
- A payment event can be credited at most once.
- Payment callbacks must be authenticated and bound to a known account and event.
- A transaction's state transitions must be explicit and auditable.
- A local reset restores deterministic synthetic data.

## 8. Functional requirements

| ID | Requirement | MVP state |
|---|---|---|
| FR-01 | Seed Alice and Bob with synthetic accounts | Implemented |
| FR-02 | Support NGN, GHS, KES, ZAR, USD, EUR, GBP and USDC | Implemented |
| FR-03 | Show demo balances | Implemented |
| FR-04 | Create a fixed-rate conversion quote | Implemented |
| FR-05 | Execute a quote atomically with ledger entries | Implemented |
| FR-06 | List a user's own transactions | Implemented |
| FR-07 | Demonstrate BOLA and hardened ownership check | Implemented |
| FR-08 | Demonstrate client-controlled rate and fixed-rate counterpart | Implemented |
| FR-09 | Demonstrate webhook forgery/replay and HMAC/idempotency counterpart | Implemented |
| FR-10 | Provide local smart-contract reentrancy exercise | Scaffolded; Foundry execution pending |
| FR-11 | Provide local fiat-deposit mint authorization exercise | Scaffolded; Foundry execution pending |
| FR-12 | Provide guided and independent lab guides | Initial guides included |
| FR-13 | Reset all synthetic state | Implemented |

## 9. Non-functional requirements

- **Safety:** bind to loopback on the host; no live integrations; local-only chain.
- **Reproducibility:** deterministic seeded identities, fixtures and reset procedure.
- **Portability:** Linux/macOS/Windows with Python 3.11+; Docker is recommended.
- **Observability:** transaction references, ledger entries, API errors and lab identifiers.
- **Correctness:** integer minor units, decimal rates, explicit quote expiry and database transactions.
- **Accessibility:** keyboard-operable web UI, plain-language lab instructions and clear warnings.
- **Maintainability:** small modular backend, schema versioning as the project grows, tests for each domain invariant.

## 10. Acceptance criteria for MVP 0.1.0

- The app starts locally and displays the synthetic wallet dashboard.
- Alice and Bob can view their own seeded accounts.
- Alice can convert NGN to USDC and USDC to NGN using a quote.
- Conversion writes corresponding ledger entries and cannot be replayed with the same quote.
- The vulnerable BOLA route exposes a deliberately seeded other-user account; the hardened counterpart denies it.
- The vulnerable rate route accepts a caller-controlled rate; the hardened route ignores such input by schema design.
- The vulnerable webhook can be replayed; the hardened webhook rejects invalid signatures and ignores duplicate event IDs.
- Automated tests pass.
- The Foundry test proves the vulnerable vault can be re-entered and the secure counterpart resists the same test.
- Docker host port is bound to 127.0.0.1 and the Compose network is internal.
