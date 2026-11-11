# RampLab implementation backlog

Status key: **Done** = included in MVP scaffold; **Next** = first follow-up; **Later** = planned, not implemented.

## Epic 0 — Project foundation

- [x] Establish product goals, non-goals and supported audiences.
- [x] Create repository scaffold, contribution policy and safety boundary.
- [x] Add local run and Docker Compose configuration.
- [x] Add API and unit-test baseline.

## Epic 1 — Synthetic financial core

- [x] Seed Alice, Bob, treasury and clearing accounts.
- [x] Support NGN, GHS, KES, ZAR, USD, EUR, GBP and synthetic USDC.
- [x] Use integer minor units and Decimal calculations.
- [x] Generate expiring, identity-bound conversion quotes.
- [x] Execute conversion atomically and write transaction/ledger records.
- [x] Add double-entry ledger invariant checker.
- [x] Add concurrent conversion test and race-condition challenge.
- [x] Add quote cancellation and explicit lifecycle state machine.

## Epic 2 — API security labs

- [x] RAMP-001 BOLA vulnerable route and ownership-checked counterpart.
- [x] RAMP-002 client-controlled rate route and server-rate counterpart.
- [x] RAMP-003 unsigned/replayable webhook and HMAC/idempotent counterpart.
- [ ] Add JWT/session lab with intentionally weak and hardened session handling.
- [x] Add admin role and function-level authorization challenge.
- [ ] Add mass-assignment challenge with safe DTO comparison.

## Epic 3 — Smart-contract labs

- [x] Add vulnerable and secure vault contracts.
- [x] Add vulnerable and secure ramp deposit-confirmation contracts.
- [x] Add Foundry reentrancy and ramp authorization tests (verified green locally with Foundry 1.5.1 / solc 0.8.24).
- [ ] Add access-control/misconfigured minter challenge.
- [ ] Add mock oracle and price-integrity challenge.
- [ ] Add token decimal and rounding challenge.
- [ ] Add contract invariant/property tests and Slither CI job.
- [x] Connect the API simulator to Anvil for end-to-end local mint/redeem workflows (no public RPC).

## Epic 4 — Learning experience

- [x] Add dashboard with wallet balances and conversion form.
- [x] Add challenge catalogue and API docs.
- [x] Add initial guided/independent challenge documents.
- [x] Add learner mode toggle and hint reveal.
- [ ] Add challenge reset per scenario.
- [ ] Add facilitator pack and printable score sheet.
- [ ] Add accessible keyboard and screen-reader review.

## Epic 5 — Reliability and community release

- [x] Add synthetic-only policy and security disclosure instructions.
- [ ] Add dependency scanning and CodeQL/Semgrep CI.
- [ ] Add PostgreSQL profile for concurrent multi-user labs.
- [ ] Add schema migrations and deterministic seed versioning.
- [ ] Conduct external code review and threat-model review.
- [ ] Publish v0.1.0 release only after a clean installation test on Linux, macOS and Windows.

## Suggested sequence

1. Stabilise conversion invariants and add API tests.
2. Validate the Foundry reentrancy tests on a clean Foundry install.
3. Complete RAMP-001 to RAMP-005 facilitator guides and hints.
4. Add concurrency and double-entry ledger verification.
5. Run an external review before announcing a public release.
